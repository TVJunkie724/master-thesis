import 'package:flutter/material.dart';

import '../../theme/spacing.dart';

class DeployTwinConfirmationDialog extends StatelessWidget {
  final String resourceName;

  const DeployTwinConfirmationDialog({super.key, required this.resourceName});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    return AlertDialog(
      title: Row(
        children: [
          Icon(Icons.rocket_launch, color: colors.primary),
          const SizedBox(width: AppSpacing.sm),
          const Expanded(child: Text('Deploy to Cloud?')),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('This will provision cloud resources for:'),
          const SizedBox(height: AppSpacing.sm),
          Text(
            resourceName,
            style: theme.textTheme.bodyLarge?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            'Estimated time: 5-15 minutes',
            style: theme.textTheme.bodySmall?.copyWith(
              color: colors.onSurfaceVariant,
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('confirm-deploy'),
          autofocus: true,
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Deploy Now'),
        ),
      ],
    );
  }
}

class DestroyTwinConfirmationDialog extends StatefulWidget {
  const DestroyTwinConfirmationDialog({super.key});

  @override
  State<DestroyTwinConfirmationDialog> createState() =>
      _DestroyTwinConfirmationDialogState();
}

class _DestroyTwinConfirmationDialogState
    extends State<DestroyTwinConfirmationDialog> {
  bool _acknowledged = false;
  final FocusNode _confirmFocusNode = FocusNode();

  @override
  void dispose() {
    _confirmFocusNode.dispose();
    super.dispose();
  }

  void _setAcknowledged(bool value) {
    setState(() => _acknowledged = value);
    if (value) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _confirmFocusNode.requestFocus();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return AlertDialog(
      title: Row(
        children: [
          Icon(Icons.warning_amber, color: colors.error),
          const SizedBox(width: AppSpacing.sm),
          const Expanded(child: Text('Destroy Cloud Resources?')),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('This will permanently delete:'),
          const SizedBox(height: AppSpacing.sm),
          const Text('All deployed infrastructure'),
          const Text('IoT device connections'),
          const Text('Stored data in hot, cold, and archive storage'),
          const SizedBox(height: AppSpacing.md),
          CheckboxListTile(
            key: const Key('acknowledge-destroy'),
            value: _acknowledged,
            onChanged: (value) => _setAcknowledged(value ?? false),
            title: const Text('I understand this action is irreversible'),
            controlAffinity: ListTileControlAffinity.leading,
            contentPadding: EdgeInsets.zero,
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('confirm-destroy'),
          focusNode: _confirmFocusNode,
          onPressed: _acknowledged
              ? () => Navigator.of(context).pop(true)
              : null,
          style: FilledButton.styleFrom(
            backgroundColor: colors.error,
            foregroundColor: colors.onError,
          ),
          child: const Text('Destroy'),
        ),
      ],
    );
  }
}

class DeleteTwinConfirmationDialog extends StatelessWidget {
  final String projectName;

  const DeleteTwinConfirmationDialog({super.key, required this.projectName});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return AlertDialog(
      title: Row(
        children: [
          Icon(Icons.delete_forever, color: colors.error),
          const SizedBox(width: AppSpacing.sm),
          const Expanded(child: Text('Delete Twin?')),
        ],
      ),
      content: Text(
        'Are you sure you want to delete "$projectName"? This action cannot be undone.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('confirm-delete'),
          onPressed: () => Navigator.of(context).pop(true),
          style: FilledButton.styleFrom(
            backgroundColor: colors.error,
            foregroundColor: colors.onError,
          ),
          child: const Text('Delete'),
        ),
      ],
    );
  }
}

class SimulatorDownloadConfirmationDialog extends StatefulWidget {
  final String provider;

  const SimulatorDownloadConfirmationDialog({
    super.key,
    required this.provider,
  });

  @override
  State<SimulatorDownloadConfirmationDialog> createState() =>
      _SimulatorDownloadConfirmationDialogState();
}

class _SimulatorDownloadConfirmationDialogState
    extends State<SimulatorDownloadConfirmationDialog> {
  bool _acknowledged = false;
  final FocusNode _confirmFocusNode = FocusNode();

  @override
  void dispose() {
    _confirmFocusNode.dispose();
    super.dispose();
  }

  void _setAcknowledged(bool value) {
    setState(() => _acknowledged = value);
    if (value) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _confirmFocusNode.requestFocus();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Download simulator package?'),
      content: SizedBox(
        width: AppSpacing.dialogContentMaxWidth,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'The ${widget.provider} package contains narrowly scoped '
              'device/runtime authentication material that can send telemetry '
              'to this twin.',
            ),
            const SizedBox(height: AppSpacing.md),
            CheckboxListTile(
              key: const Key('acknowledge-simulator-credentials'),
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              value: _acknowledged,
              onChanged: (value) => _setAcknowledged(value ?? false),
              title: const Text(
                'I will store the archive securely and remove it when no longer needed.',
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          key: const Key('confirm-simulator-download'),
          focusNode: _confirmFocusNode,
          onPressed: _acknowledged
              ? () => Navigator.of(context).pop(true)
              : null,
          icon: const Icon(Icons.download_outlined),
          label: const Text('Download'),
        ),
      ],
    );
  }
}
