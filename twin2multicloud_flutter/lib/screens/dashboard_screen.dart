import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../models/twin.dart';
import '../models/twin_transfer.dart';
import '../providers/theme_provider.dart';
import '../providers/twins_provider.dart';
import '../theme/spacing.dart';
import '../utils/api_error_handler.dart';
import '../utils/file_download_utils.dart';
import '../widgets/branded_app_bar.dart';
import '../widgets/dashboard/dashboard_strings.dart';
import '../widgets/dashboard/twin_inventory_panel.dart';
import '../widgets/selectable_scaffold.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  bool _needsRefresh = true;

  void _refreshDashboard(WidgetRef ref) {
    ref.invalidate(twinsProvider);
  }

  @override
  Widget build(BuildContext context) {
    if (_needsRefresh) {
      _needsRefresh = false;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _refreshDashboard(ref);
      });
    }

    final twinsAsync = ref.watch(twinsProvider);
    final isBusy = ref.watch(twinCommandProvider).isLoading;

    return SelectableScaffold(
      appBar: BrandedAppBar(
        title: DashboardStrings.appTitle,
        actions: [
          IconButton(
            icon: Icon(
              ref.watch(themeProvider) == ThemeMode.dark
                  ? Icons.light_mode
                  : Icons.dark_mode,
            ),
            onPressed: () => ref.read(themeProvider.notifier).toggle(),
            tooltip: DashboardStrings.toggleThemeTooltip,
          ),
          const SizedBox(width: AppSpacing.sm),
          IconButton(
            onPressed: () => context.go('/settings'),
            icon: const Icon(Icons.cloud_outlined),
            tooltip: DashboardStrings.openCloudAccessTooltip,
          ),
          const SizedBox(width: AppSpacing.sm),
        ],
      ),
      body: SingleChildScrollView(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppSpacing.maxContentWidthLarge,
            ),
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: twinsAsync.when(
                data: (twins) => TwinInventoryPanel(
                  twins: twins,
                  isBusy: isBusy,
                  onCreate: () => context.go('/wizard'),
                  onImport: () => _handleImport(context, ref),
                  onRefresh: () => _refreshDashboard(ref),
                  onOpen: (twin) => _openTwin(context, twin),
                  onDuplicate: (twin) => _handleDuplicate(context, ref, twin),
                  onExport: (twin) => _handleExport(context, ref, twin),
                  onDelete: (twin) => _handleDelete(context, ref, twin),
                ),
                loading: () => const _InventoryLoading(),
                error: (error, _) => _InventoryError(
                  message: ApiErrorHandler.extractMessage(error),
                  onRetry: () => _refreshDashboard(ref),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _openTwin(BuildContext context, Twin twin) {
    context.go(
      twin.isDraft ? '/wizard/${twin.id}' : '/twins/${twin.id}/overview',
    );
  }

  Future<void> _handleDelete(
    BuildContext context,
    WidgetRef ref,
    Twin twin,
  ) async {
    if (twin.isDeployed) {
      await showDialog<void>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          icon: Icon(
            Icons.warning_amber_rounded,
            color: Theme.of(dialogContext).colorScheme.error,
            size: AppSpacing.xxl,
          ),
          title: const Text(DashboardStrings.cannotDeleteTitle),
          content: const Text(DashboardStrings.cannotDeleteBody),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text(DashboardStrings.okay),
            ),
          ],
        ),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        icon: Icon(
          Icons.delete_forever,
          color: Theme.of(dialogContext).colorScheme.error,
          size: AppSpacing.xxl,
        ),
        title: const Text(DashboardStrings.deleteTitle),
        content: Text(
          '${DashboardStrings.deleteQuestionPrefix}${twin.name}'
          '${DashboardStrings.deleteQuestionSuffix}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text(DashboardStrings.cancel),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(dialogContext).colorScheme.error,
              foregroundColor: Theme.of(dialogContext).colorScheme.onError,
            ),
            onPressed: () => Navigator.pop(dialogContext, true),
            child: const Text(DashboardStrings.delete),
          ),
        ],
      ),
    );

    if (confirmed != true) return;
    try {
      await ref.read(twinCommandProvider.notifier).deleteTwin(twin.id);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${DashboardStrings.deletedPrefix}${twin.name}"'),
          ),
        );
      }
    } catch (error) {
      if (context.mounted) {
        _showError(
          context,
          DashboardStrings.failedToDeletePrefix,
          error,
          separator: '',
        );
      }
    }
  }

  Future<void> _handleDuplicate(
    BuildContext context,
    WidgetRef ref,
    Twin twin,
  ) async {
    final name = await _requestTwinName(
      context,
      title: DashboardStrings.duplicateTitle,
      actionLabel: DashboardStrings.duplicateAction,
      initialName: '${twin.name}${DashboardStrings.copySuffix}',
    );
    if (name == null || !context.mounted) return;

    try {
      final duplicate = await ref
          .read(twinCommandProvider.notifier)
          .duplicateTwin(twin.id, TwinDuplicateRequest(name: name));
      if (duplicate != null && context.mounted) {
        context.go('/wizard/${duplicate.id}');
      }
    } catch (error) {
      if (context.mounted) {
        _showError(context, DashboardStrings.duplicateFailed, error);
      }
    }
  }

  Future<void> _handleImport(BuildContext context, WidgetRef ref) async {
    final name = await _requestTwinName(
      context,
      title: DashboardStrings.importTitle,
      actionLabel: DashboardStrings.selectArchive,
    );
    if (name == null || !context.mounted) return;

    try {
      final result = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: const ['zip'],
        withData: true,
      );
      if (result == null || result.files.isEmpty || !context.mounted) return;
      final file = result.files.single;
      final bytes = file.bytes;
      if (bytes == null) {
        throw const FormatException(DashboardStrings.unreadableArchive);
      }
      final imported = await ref
          .read(twinCommandProvider.notifier)
          .importTwin(
            TwinImportRequest(newName: name, filename: file.name, bytes: bytes),
          );
      if (imported != null && context.mounted) {
        context.go('/wizard/${imported.id}');
      }
    } catch (error) {
      if (context.mounted) {
        _showError(context, DashboardStrings.importFailed, error);
      }
    }
  }

  Future<void> _handleExport(
    BuildContext context,
    WidgetRef ref,
    Twin twin,
  ) async {
    try {
      final download = await ref
          .read(twinCommandProvider.notifier)
          .exportTwin(twin.id);
      if (download == null) return;
      final result = await saveBinaryFile(
        bytes: download.bytes,
        suggestedName: download.filename,
        mimeType: download.mediaType,
      );
      if (!context.mounted || result.cancelled) return;
      if (result.success) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(result.message!)));
      } else if (result.error != null) {
        _showError(context, DashboardStrings.exportFailed, result.error!);
      }
    } catch (error) {
      if (context.mounted) {
        _showError(context, DashboardStrings.exportFailed, error);
      }
    }
  }

  Future<String?> _requestTwinName(
    BuildContext context, {
    required String title,
    required String actionLabel,
    String initialName = '',
  }) => showDialog<String>(
    context: context,
    builder: (dialogContext) => _TwinNameDialog(
      title: title,
      actionLabel: actionLabel,
      initialName: initialName,
    ),
  );

  void _showError(
    BuildContext context,
    String prefix,
    Object error, {
    String separator = ': ',
  }) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          '$prefix$separator${ApiErrorHandler.extractMessage(error)}',
        ),
        backgroundColor: Theme.of(context).colorScheme.error,
      ),
    );
  }
}

class _InventoryLoading extends StatelessWidget {
  const _InventoryLoading();

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.all(AppSpacing.xxl),
    child: Center(child: CircularProgressIndicator()),
  );
}

class _InventoryError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _InventoryError({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(AppSpacing.xxl),
    child: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.cloud_off,
            size: AppSpacing.xxl,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            DashboardStrings.failedToLoad,
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            message,
            style: Theme.of(context).textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.md),
          OutlinedButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text(DashboardStrings.retry),
          ),
        ],
      ),
    ),
  );
}

class _TwinNameDialog extends StatefulWidget {
  final String title;
  final String actionLabel;
  final String initialName;

  const _TwinNameDialog({
    required this.title,
    required this.actionLabel,
    required this.initialName,
  });

  @override
  State<_TwinNameDialog> createState() => _TwinNameDialogState();
}

class _TwinNameDialogState extends State<_TwinNameDialog> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialName);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text(widget.title),
    content: Form(
      key: _formKey,
      child: TextFormField(
        controller: _controller,
        autofocus: true,
        maxLength: 120,
        decoration: const InputDecoration(labelText: DashboardStrings.twinName),
        validator: (value) => value == null || value.trim().isEmpty
            ? DashboardStrings.enterTwinName
            : null,
        onFieldSubmitted: (_) => _submit(),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text(DashboardStrings.cancel),
      ),
      FilledButton(onPressed: _submit, child: Text(widget.actionLabel)),
    ],
  );

  void _submit() {
    if (_formKey.currentState?.validate() == true) {
      Navigator.pop(context, _controller.text.trim());
    }
  }
}
