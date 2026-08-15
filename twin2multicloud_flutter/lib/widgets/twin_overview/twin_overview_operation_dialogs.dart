import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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

class RotateGcpGrafanaViewerConfirmationDialog extends StatelessWidget {
  const RotateGcpGrafanaViewerConfirmationDialog({super.key});

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Row(
        children: [
          Icon(Icons.key_outlined),
          SizedBox(width: AppSpacing.sm),
          Expanded(child: Text('Create a new Viewer password?')),
        ],
      ),
      content: const SizedBox(
        width: AppSpacing.dialogContentMaxWidth,
        child: Text(
          'The current GCP Grafana Viewer password becomes invalid. The new '
          'password is shown once after rotation.',
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          key: const Key('confirm-gcp-viewer-rotation'),
          autofocus: true,
          onPressed: () => Navigator.of(context).pop(true),
          icon: const Icon(Icons.key_outlined),
          label: const Text('Create password'),
        ),
      ],
    );
  }
}

class GcpGrafanaCredentialRevealDialog extends StatefulWidget {
  final String username;
  final String password;

  const GcpGrafanaCredentialRevealDialog({
    super.key,
    required this.username,
    required this.password,
  });

  @override
  State<GcpGrafanaCredentialRevealDialog> createState() =>
      _GcpGrafanaCredentialRevealDialogState();
}

class _GcpGrafanaCredentialRevealDialogState
    extends State<GcpGrafanaCredentialRevealDialog> {
  late final TextEditingController _passwordController;
  bool _showPassword = false;

  @override
  void initState() {
    super.initState();
    _passwordController = TextEditingController(text: widget.password);
  }

  @override
  void dispose() {
    _passwordController.clear();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _copy(String value, String label) async {
    await Clipboard.setData(ClipboardData(text: value));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$label copied by explicit user action.')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Row(
        children: [
          Icon(Icons.key_outlined),
          SizedBox(width: AppSpacing.sm),
          Expanded(child: Text('GCP Grafana Viewer credential')),
        ],
      ),
      content: SizedBox(
        width: AppSpacing.dialogContentMaxWidth,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'This password is shown once. Store it securely. Creating '
              'another password invalidates this one.',
            ),
            const SizedBox(height: AppSpacing.md),
            Text('Username', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: AppSpacing.xs),
            Row(
              children: [
                Expanded(child: SelectableText(widget.username)),
                const SizedBox(width: AppSpacing.sm),
                TextButton.icon(
                  key: const Key('copy-gcp-viewer-username'),
                  autofocus: true,
                  onPressed: () => _copy(widget.username, 'Username'),
                  icon: const Icon(Icons.copy_outlined),
                  label: const Text('Copy username'),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            Text('Password', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: AppSpacing.xs),
            TextField(
              key: const Key('gcp-viewer-password'),
              controller: _passwordController,
              readOnly: true,
              obscureText: !_showPassword,
              enableSuggestions: false,
              autocorrect: false,
              decoration: const InputDecoration(border: OutlineInputBorder()),
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                Semantics(
                  label: _showPassword ? 'Hide password' : 'Show password',
                  button: true,
                  child: TextButton.icon(
                    key: const Key('toggle-gcp-viewer-password'),
                    onPressed: () =>
                        setState(() => _showPassword = !_showPassword),
                    icon: Icon(
                      _showPassword
                          ? Icons.visibility_off_outlined
                          : Icons.visibility_outlined,
                    ),
                    label: Text(_showPassword ? 'Hide' : 'Show'),
                  ),
                ),
                TextButton.icon(
                  key: const Key('copy-gcp-viewer-password'),
                  onPressed: () => _copy(widget.password, 'Password'),
                  icon: const Icon(Icons.copy_outlined),
                  label: const Text('Copy password'),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              'Copying is deliberate and may retain the value in the '
              'operating system clipboard or clipboard history. The app '
              'never copies credentials automatically.',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
      actions: [
        FilledButton(
          key: const Key('close-gcp-viewer-credential'),
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }
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
