import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../models/twin.dart';
import '../models/twin_transfer.dart';
import '../providers/auth_provider.dart';
import '../providers/theme_provider.dart';
import '../providers/twins_provider.dart';
import '../theme/spacing.dart';
import '../utils/api_error_handler.dart';
import '../utils/file_download_utils.dart';
import '../utils/twin_state_utils.dart';
import '../widgets/branded_app_bar.dart';
import '../widgets/selectable_scaffold.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  int _sortColumnIndex = 0;
  bool _sortAscending = true;
  String? _selectedStateFilter; // null means "All"
  bool _needsRefresh = true; // Refresh on first build

  List<Twin> _sortTwins(List<Twin> twins) {
    final sorted = List<Twin>.from(twins);
    sorted.sort((a, b) {
      int cmp;
      switch (_sortColumnIndex) {
        case 0: // Name
          cmp = a.name.toLowerCase().compareTo(b.name.toLowerCase());
          break;
        case 2: // Last Updated
          cmp = a.updatedAt.compareTo(b.updatedAt);
          break;
        default:
          cmp = 0;
      }
      return _sortAscending ? cmp : -cmp;
    });
    return sorted;
  }

  List<Twin> _filterTwins(List<Twin> twins) {
    if (_selectedStateFilter == null) return twins;
    return twins.where((t) => t.state == _selectedStateFilter).toList();
  }

  /// Invalidate the research inventory to force a fresh fetch.
  void _refreshDashboard(WidgetRef ref) {
    ref.invalidate(twinsProvider);
  }

  @override
  Widget build(BuildContext context) {
    // Invalidate stale cache on first build to ensure fresh data when navigating
    // This ensures state changes (e.g., from deployments) are reflected
    if (_needsRefresh) {
      _needsRefresh = false;
      // Schedule for after this build frame to avoid rebuild loop
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _refreshDashboard(ref);
      });
    }

    final twinsAsync = ref.watch(twinsProvider);

    return SelectableScaffold(
      appBar: BrandedAppBar(
        title: 'Twin2MultiCloud',
        actions: [
          IconButton(
            icon: Icon(
              ref.watch(themeProvider) == ThemeMode.dark
                  ? Icons.light_mode
                  : Icons.dark_mode,
            ),
            onPressed: () => ref.read(themeProvider.notifier).toggle(),
            tooltip: 'Toggle theme',
          ),
          const SizedBox(width: 8),
          PopupMenuButton<String>(
            offset: const Offset(0, 56),
            tooltip: 'Profile menu',
            onSelected: (value) async {
              switch (value) {
                case 'settings':
                  context.go('/settings');
                  break;
                case 'logout':
                  await ref.read(authProvider.notifier).logout();
                  break;
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'settings',
                child: Row(
                  children: [
                    Icon(Icons.settings, size: 20),
                    SizedBox(width: 12),
                    Text('Settings'),
                  ],
                ),
              ),
              const PopupMenuDivider(),
              PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    Icon(Icons.logout, size: 20, color: Colors.red),
                    const SizedBox(width: 12),
                    Text('Logout', style: TextStyle(color: Colors.red)),
                  ],
                ),
              ),
            ],
            child: const Padding(
              padding: EdgeInsets.symmetric(horizontal: 8),
              child: CircleAvatar(child: Icon(Icons.person)),
            ),
          ),
          const SizedBox(width: 8),
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
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(
                        AppSpacing.borderRadiusLg,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(
                            alpha:
                                Theme.of(context).brightness == Brightness.dark
                                ? 0.2
                                : 0.06,
                          ),
                          blurRadius: AppSpacing.borderRadiusLg,
                          spreadRadius: 1,
                          offset: const Offset(0, 0),
                        ),
                      ],
                    ),
                    child: Card(
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(
                          AppSpacing.borderRadiusLg,
                        ),
                        side: BorderSide(
                          color: Theme.of(context).brightness == Brightness.dark
                              ? Colors.white.withValues(alpha: 0.1)
                              : Colors.black.withValues(alpha: 0.05),
                          width: 1,
                        ),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.lg),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            // Twins list header
                            _ResearchInventoryHeader(
                              isBusy: ref.watch(twinCommandProvider).isLoading,
                              onCreate: () => context.go('/wizard'),
                              onImport: () => _handleImport(context, ref),
                            ),
                            const SizedBox(height: AppSpacing.md),

                            // State filter chips
                            _buildStateFilterChips(),
                            const SizedBox(height: AppSpacing.md),

                            // Twins table
                            twinsAsync.when(
                              data: (twins) =>
                                  _buildTwinsTable(context, ref, twins),
                              loading: () => const Padding(
                                padding: EdgeInsets.all(48),
                                child: Center(
                                  child: CircularProgressIndicator(),
                                ),
                              ),
                              error: (err, stack) => Padding(
                                padding: const EdgeInsets.all(48),
                                child: Center(
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(
                                        Icons.cloud_off,
                                        size: 64,
                                        color: Colors.grey.shade600,
                                      ),
                                      const SizedBox(height: 16),
                                      Text(
                                        'Failed to load twins',
                                        style: Theme.of(
                                          context,
                                        ).textTheme.titleMedium,
                                      ),
                                      const SizedBox(height: 8),
                                      Text(
                                        ApiErrorHandler.extractMessage(err),
                                        style: TextStyle(
                                          color: Colors.grey.shade600,
                                        ),
                                      ),
                                      const SizedBox(height: 16),
                                      OutlinedButton.icon(
                                        onPressed: () => _refreshDashboard(ref),
                                        icon: const Icon(Icons.refresh),
                                        label: const Text('Retry'),
                                      ),
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  // Use TwinStateUtils for consistent state colors across screens
  Color _getStateColor(String? state) => TwinStateUtils.getColor(state);

  Widget _buildStateFilterChips() {
    final filters = [
      (null, 'All'),
      ('draft', 'Draft'),
      ('configured', 'Configured'),
      ('deployed', 'Deployed'),
      ('destroyed', 'Destroyed'),
      ('error', 'Error'),
    ];

    return Wrap(
      spacing: 8,
      children: filters.map((filter) {
        final (value, label) = filter;
        final isSelected = _selectedStateFilter == value;
        final color = _getStateColor(value);

        return FilterChip(
          label: Text(
            label,
            style: TextStyle(
              color: isSelected ? Colors.white : color,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
            ),
          ),
          selected: isSelected,
          onSelected: (_) {
            setState(() => _selectedStateFilter = value);
          },
          backgroundColor: color.withAlpha(25),
          selectedColor: color,
          showCheckmark: false,
          side: BorderSide(color: color.withAlpha(100)),
        );
      }).toList(),
    );
  }

  Future<void> _handleDelete(
    BuildContext context,
    WidgetRef ref,
    Twin twin,
  ) async {
    if (twin.isDeployed) {
      // Show warning - can't delete deployed twins
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: Icon(
            Icons.warning_amber_rounded,
            color: Colors.orange.shade400,
            size: 48,
          ),
          title: const Text('Cannot Delete'),
          content: const Text(
            'This digital twin is currently deployed. You must destroy all cloud resources before deleting.\n\n'
            'Go to the Deployer step and run "Destroy" first.',
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('OK'),
            ),
          ],
        ),
      );
    } else {
      // Show confirmation dialog
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: Icon(
            Icons.delete_forever,
            color: Colors.red.shade400,
            size: 48,
          ),
          title: const Text('Delete Twin?'),
          content: Text(
            'Are you sure you want to delete "${twin.name}"?\n\n'
            'This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: Colors.red),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete'),
            ),
          ],
        ),
      );

      if (confirmed == true) {
        try {
          await ref.read(twinCommandProvider.notifier).deleteTwin(twin.id);
          if (context.mounted) {
            ScaffoldMessenger.of(
              context,
            ).showSnackBar(SnackBar(content: Text('Deleted "${twin.name}"')));
          }
        } catch (e) {
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  'Failed to delete: ${ApiErrorHandler.extractMessage(e)}',
                ),
                backgroundColor: Colors.red,
              ),
            );
          }
        }
      }
    }
  }

  Widget _buildTwinsTable(
    BuildContext context,
    WidgetRef ref,
    List<Twin> twins,
  ) {
    if (twins.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_queue, size: 64, color: Colors.grey.shade600),
            const SizedBox(height: 16),
            Text(
              'No digital twins yet',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Create your first twin to get started',
              style: TextStyle(color: Colors.grey.shade600),
            ),
          ],
        ),
      );
    }

    final isDark = Theme.of(context).brightness == Brightness.dark;

    return LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: ConstrainedBox(
          constraints: BoxConstraints(minWidth: constraints.maxWidth),
          child: DataTable(
            sortColumnIndex: _sortColumnIndex,
            sortAscending: _sortAscending,
            headingRowColor: WidgetStateProperty.all(
              isDark
                  ? Colors.white.withValues(alpha: 0.05)
                  : Theme.of(context).colorScheme.surfaceContainerHighest,
            ),
            columnSpacing: 24,
            columns: [
              DataColumn(
                label: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('Name'),
                    const SizedBox(width: 4),
                    Icon(
                      Icons.swap_vert,
                      size: 16,
                      color: Colors.grey.shade500,
                    ),
                  ],
                ),
                onSort: (columnIndex, ascending) {
                  setState(() {
                    _sortColumnIndex = columnIndex;
                    _sortAscending = ascending;
                  });
                },
              ),
              const DataColumn(label: Text('State')),
              DataColumn(
                label: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('Last Updated'),
                    const SizedBox(width: 4),
                    Icon(
                      Icons.swap_vert,
                      size: 16,
                      color: Colors.grey.shade500,
                    ),
                  ],
                ),
                onSort: (columnIndex, ascending) {
                  setState(() {
                    _sortColumnIndex = columnIndex;
                    _sortAscending = ascending;
                  });
                },
              ),
              const DataColumn(label: Text('Last Deploy')),
              const DataColumn(label: Text('Actions')),
            ],
            rows: _sortTwins(
              _filterTwins(twins),
            ).map((twin) => _buildTwinRow(context, ref, twin)).toList(),
          ),
        ),
      ),
    );
  }

  DataRow _buildTwinRow(BuildContext context, WidgetRef ref, Twin twin) {
    return DataRow(
      cells: [
        // Name
        DataCell(
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildStateIcon(twin.state),
              const SizedBox(width: 8),
              Text(
                twin.name,
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
            ],
          ),
        ),
        // State
        DataCell(_buildStateBadge(twin.state)),
        // Last Updated
        DataCell(Text(_formatDate(twin.updatedAt))),
        // Last Deploy
        DataCell(Text(_formatDate(twin.lastDeployedAt))),
        // Actions
        DataCell(
          _TwinActions(
            twin: twin,
            isBusy: ref.watch(twinCommandProvider).isLoading,
            onOpen: () => _openTwin(context, twin),
            onDuplicate: () => _handleDuplicate(context, ref, twin),
            onExport: () => _handleExport(context, ref, twin),
            onDelete: () => _handleDelete(context, ref, twin),
          ),
        ),
      ],
    );
  }

  void _openTwin(BuildContext context, Twin twin) {
    context.go(
      twin.state == 'draft'
          ? '/wizard/${twin.id}'
          : '/twins/${twin.id}/overview',
    );
  }

  Future<void> _handleDuplicate(
    BuildContext context,
    WidgetRef ref,
    Twin twin,
  ) async {
    final name = await _requestTwinName(
      context,
      title: 'Duplicate Twin',
      actionLabel: 'Duplicate',
      initialName: '${twin.name} copy',
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
      if (context.mounted) _showError(context, 'Duplicate failed', error);
    }
  }

  Future<void> _handleImport(BuildContext context, WidgetRef ref) async {
    final name = await _requestTwinName(
      context,
      title: 'Import portable Twin',
      actionLabel: 'Select archive',
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
        throw const FormatException('The selected archive could not be read.');
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
      if (context.mounted) _showError(context, 'Import failed', error);
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
        _showError(context, 'Export failed', result.error!);
      }
    } catch (error) {
      if (context.mounted) _showError(context, 'Export failed', error);
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

  void _showError(BuildContext context, String prefix, Object error) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$prefix: ${ApiErrorHandler.extractMessage(error)}'),
        backgroundColor: Theme.of(context).colorScheme.error,
      ),
    );
  }

  Widget _buildStateIcon(String state) {
    final config = TwinStateUtils.getConfig(state);
    return Icon(config.icon, color: config.color, size: 20);
  }

  Widget _buildStateBadge(String state) {
    final config = TwinStateUtils.getConfig(state);
    final bgColor = config.color.withAlpha(38);
    final textColor = config.color;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        config.label.substring(0, 1) + config.label.substring(1).toLowerCase(),
        style: TextStyle(
          color: textColor,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  String _formatDate(DateTime? date) {
    if (date == null) return '—';
    return DateFormat('MMM d, yyyy').format(date);
  }
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
        decoration: const InputDecoration(labelText: 'Twin name'),
        validator: (value) =>
            value == null || value.trim().isEmpty ? 'Enter a Twin name.' : null,
        onFieldSubmitted: (_) => _submit(),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
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

class _TwinActions extends StatelessWidget {
  final Twin twin;
  final bool isBusy;
  final VoidCallback onOpen;
  final VoidCallback onDuplicate;
  final VoidCallback onExport;
  final VoidCallback onDelete;

  const _TwinActions({
    required this.twin,
    required this.isBusy,
    required this.onOpen,
    required this.onDuplicate,
    required this.onExport,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final openLabel = twin.state == 'draft' ? 'Edit' : 'Open';
    return Semantics(
      label: 'Actions for ${twin.name}',
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconButton(
            icon: const Icon(Icons.open_in_new, size: AppSpacing.iconMd),
            onPressed: isBusy ? null : onOpen,
            tooltip: '$openLabel ${twin.name}',
          ),
          IconButton(
            icon: const Icon(Icons.copy_outlined, size: AppSpacing.iconMd),
            onPressed: isBusy ? null : onDuplicate,
            tooltip: 'Duplicate ${twin.name}',
          ),
          IconButton(
            icon: const Icon(Icons.download_outlined, size: AppSpacing.iconMd),
            onPressed: isBusy ? null : onExport,
            tooltip: 'Export ${twin.name}',
          ),
          IconButton(
            icon: const Icon(Icons.delete_outline, size: AppSpacing.iconMd),
            onPressed: isBusy ? null : onDelete,
            tooltip: twin.isDeployed
                ? 'Destroy resources before deleting ${twin.name}'
                : 'Delete ${twin.name}',
            color: twin.isDeployed ? colors.outline : colors.error,
          ),
        ],
      ),
    );
  }
}

class _ResearchInventoryHeader extends StatelessWidget {
  final bool isBusy;
  final VoidCallback onCreate;
  final VoidCallback onImport;

  const _ResearchInventoryHeader({
    required this.isBusy,
    required this.onCreate,
    required this.onImport,
  });

  @override
  Widget build(BuildContext context) {
    final title = Text(
      'Digital Twin research inventory',
      style: Theme.of(context).textTheme.headlineSmall,
    );
    final actions = Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm,
      children: [
        OutlinedButton.icon(
          onPressed: isBusy ? null : onImport,
          icon: const Icon(Icons.upload_file_outlined),
          label: const Text('Import Twin'),
        ),
        FilledButton.icon(
          onPressed: isBusy ? null : onCreate,
          icon: const Icon(Icons.add),
          label: const Text('New Twin'),
        ),
      ],
    );
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth <
            AppSpacing.resolvedDeploymentWideBreakpoint) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              title,
              const SizedBox(height: AppSpacing.sm),
              actions,
            ],
          );
        }
        return Row(
          children: [
            Expanded(child: title),
            const SizedBox(width: AppSpacing.md),
            actions,
          ],
        );
      },
    );
  }
}
