import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'cloud_connection_selector.dart';
import 'cloud_connection_strings.dart';
import 'cloud_connection_validation_status.dart';

class CloudConnectionSection extends StatelessWidget {
  final CloudProvider provider;
  final IconData icon;
  final List<CloudConnection> connections;
  final String? selectedConnectionId;
  final bool isLoading;
  final String? errorMessage;
  final CloudConnectionValidationResult? validation;
  final VoidCallback onCreate;
  final VoidCallback? onValidate;
  final VoidCallback? onUnbind;
  final ValueChanged<String?> onSelected;
  final ValueChanged<String> onDelete;

  const CloudConnectionSection({
    super.key,
    required this.provider,
    required this.icon,
    required this.connections,
    required this.selectedConnectionId,
    required this.isLoading,
    required this.errorMessage,
    required this.validation,
    required this.onCreate,
    required this.onValidate,
    required this.onUnbind,
    required this.onSelected,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final providerColor = AppColors.getProviderColor(provider.label);
    final selectedConnection = _selectedConnection;
    final unknownSelection =
        selectedConnectionId != null && selectedConnection == null;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: providerColor),
                const SizedBox(width: AppSpacing.sm),
                Text(provider.label, style: theme.textTheme.titleMedium),
                const Spacer(),
                if (isLoading)
                  const SizedBox(
                    width: AppSpacing.lg,
                    height: AppSpacing.lg,
                    child: CircularProgressIndicator(),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            if (errorMessage != null)
              _MessageBox(
                icon: Icons.error_outline,
                message: errorMessage!,
                color: theme.colorScheme.error,
              ),
            if (unknownSelection)
              _MessageBox(
                icon: Icons.warning_amber_rounded,
                message:
                    'Selected connection $selectedConnectionId was not found.',
                color: theme.colorScheme.error,
              ),
            if (connections.isEmpty && !isLoading)
              Text(
                'No ${provider.label} Cloud Connections yet.',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              )
            else
              CloudConnectionSelector(
                provider: provider,
                connections: connections,
                selectedConnectionId: selectedConnectionId,
                enabled: !isLoading,
                onChanged: onSelected,
              ),
            const SizedBox(height: AppSpacing.md),
            if (selectedConnection != null) ...[
              _ConnectionSummary(connection: selectedConnection),
              const SizedBox(height: AppSpacing.md),
              CloudConnectionValidationStatus(
                connection: selectedConnection,
                validation: validation,
                isLoading: isLoading,
              ),
              const SizedBox(height: AppSpacing.md),
            ],
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                FilledButton.icon(
                  icon: const Icon(Icons.add),
                  label: const Text(CloudConnectionStrings.newConnection),
                  onPressed: isLoading ? null : onCreate,
                ),
                OutlinedButton.icon(
                  icon: const Icon(Icons.check_circle_outline),
                  label: const Text(CloudConnectionStrings.validate),
                  onPressed: selectedConnection == null || isLoading
                      ? null
                      : onValidate,
                ),
                OutlinedButton.icon(
                  icon: const Icon(Icons.link_off),
                  label: const Text(CloudConnectionStrings.unbind),
                  onPressed: selectedConnection == null || isLoading
                      ? null
                      : onUnbind,
                ),
                OutlinedButton.icon(
                  icon: const Icon(Icons.delete_outline),
                  label: const Text(CloudConnectionStrings.delete),
                  onPressed: selectedConnection == null || isLoading
                      ? null
                      : () => _confirmDelete(context, selectedConnection.id),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  CloudConnection? get _selectedConnection {
    for (final connection in connections) {
      if (connection.id == selectedConnectionId) {
        return connection;
      }
    }
    return null;
  }

  Future<void> _confirmDelete(BuildContext context, String connectionId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Cloud Connection?'),
        content: const Text(
          'This removes the reusable connection if no twin is using it.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text(CloudConnectionStrings.cancel),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text(CloudConnectionStrings.delete),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      onDelete(connectionId);
    }
  }
}

class _ConnectionSummary extends StatelessWidget {
  final CloudConnection connection;

  const _ConnectionSummary({required this.connection});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final summary = connection.payloadSummary.entries
        .where(
          (entry) => entry.value != null && entry.value.toString().isNotEmpty,
        )
        .map((entry) => '${entry.key}: ${entry.value}')
        .join(' | ');

    return Text(
      summary.isEmpty ? 'No public summary available' : summary,
      style: theme.textTheme.bodySmall?.copyWith(
        color: theme.colorScheme.onSurfaceVariant,
      ),
    );
  }
}

class _MessageBox extends StatelessWidget {
  final IconData icon;
  final String message;
  final Color color;

  const _MessageBox({
    required this.icon,
    required this.message,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Row(
        children: [
          Icon(icon, color: color),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: theme.textTheme.bodySmall?.copyWith(color: color),
            ),
          ),
        ],
      ),
    );
  }
}
