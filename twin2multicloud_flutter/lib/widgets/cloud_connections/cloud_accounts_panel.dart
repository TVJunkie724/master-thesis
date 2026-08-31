import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/cloud_connection.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'cloud_connection_create_dialog.dart';
import 'cloud_connection_import_dialog.dart';
import 'cloud_connection_strings.dart';

class CloudAccountsPanel extends StatelessWidget {
  final List<CloudConnection> connections;
  final bool isLoading;
  final String? loadError;
  final Set<String> busyConnectionIds;
  final bool isCreating;
  final bool isImporting;
  final VoidCallback onRetry;
  final ValueChanged<CloudConnectionCreateRequest> onCreate;
  final ValueChanged<CloudConnectionImportRequest> onImport;
  final ValueChanged<CloudConnection> onValidate;
  final ValueChanged<CloudConnection> onDelete;
  final Future<void> Function(CloudProvider) onOpenSetupGuide;

  const CloudAccountsPanel({
    super.key,
    required this.connections,
    required this.isLoading,
    required this.loadError,
    required this.busyConnectionIds,
    required this.isCreating,
    required this.isImporting,
    required this.onRetry,
    required this.onCreate,
    required this.onImport,
    required this.onValidate,
    required this.onDelete,
    required this.onOpenSetupGuide,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    CloudConnectionStrings.providerConnectionsTitle,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    CloudConnectionStrings.providerConnectionsHelp,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            if (isLoading && connections.isNotEmpty)
              const Padding(
                padding: EdgeInsets.only(right: AppSpacing.sm),
                child: SizedBox.square(
                  dimension: AppSpacing.iconMd,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
              ),
            IconButton(
              onPressed: isLoading ? null : onRetry,
              icon: const Icon(Icons.refresh),
              tooltip: CloudConnectionStrings.refreshProviders,
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        if (loadError != null) ...[
          _LoadError(message: loadError!, onRetry: onRetry),
          const SizedBox(height: AppSpacing.md),
        ],
        if (isLoading && connections.isEmpty)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(AppSpacing.xl),
              child: CircularProgressIndicator(),
            ),
          )
        else
          LayoutBuilder(
            builder: (context, constraints) {
              final width =
                  constraints.maxWidth >=
                      AppSpacing.configurationWorkloadCompactBreakpoint
                  ? (constraints.maxWidth - (AppSpacing.md * 2)) / 3
                  : constraints.maxWidth >= AppSpacing.maxContentWidthMedium
                  ? (constraints.maxWidth - AppSpacing.md) / 2
                  : constraints.maxWidth;
              return Wrap(
                spacing: AppSpacing.md,
                runSpacing: AppSpacing.md,
                children: CloudProvider.values
                    .map(
                      (provider) => SizedBox(
                        width: width,
                        child: _ProviderDeploymentCard(
                          provider: provider,
                          connections: connections
                              .where(
                                (connection) => connection.provider == provider,
                              )
                              .toList(growable: false),
                          busyConnectionIds: busyConnectionIds,
                          isCreating: isCreating,
                          isImporting: isImporting,
                          onCreate: () => _openCreateDialog(context, provider),
                          onImport: () => _openImportDialog(context, provider),
                          onOpenSetupGuide: () => onOpenSetupGuide(provider),
                          onValidate: onValidate,
                          onDelete: (connection) =>
                              _confirmDelete(context, connection),
                        ),
                      ),
                    )
                    .toList(growable: false),
              );
            },
          ),
      ],
    );
  }

  Future<void> _openCreateDialog(
    BuildContext context,
    CloudProvider provider,
  ) async {
    final request = await showDialog<CloudConnectionCreateRequest>(
      context: context,
      builder: (context) => CloudConnectionCreateDialog(provider: provider),
    );
    if (request != null) onCreate(request);
  }

  Future<void> _openImportDialog(
    BuildContext context,
    CloudProvider provider,
  ) async {
    final request = await showDialog<CloudConnectionImportRequest>(
      context: context,
      builder: (context) => CloudConnectionImportDialog(provider: provider),
    );
    if (request != null) onImport(request);
  }

  Future<void> _confirmDelete(
    BuildContext context,
    CloudConnection connection,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete deployment administrator?'),
        content: Text(
          'Delete ${connection.displayName}? Connections bound to a Twin are rejected by the server and remain visible.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
              foregroundColor: Theme.of(context).colorScheme.onError,
            ),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true) onDelete(connection);
  }
}

class _ProviderDeploymentCard extends StatelessWidget {
  final CloudProvider provider;
  final List<CloudConnection> connections;
  final Set<String> busyConnectionIds;
  final bool isCreating;
  final bool isImporting;
  final VoidCallback onCreate;
  final VoidCallback onImport;
  final VoidCallback onOpenSetupGuide;
  final ValueChanged<CloudConnection> onValidate;
  final ValueChanged<CloudConnection> onDelete;

  const _ProviderDeploymentCard({
    required this.provider,
    required this.connections,
    required this.busyConnectionIds,
    required this.isCreating,
    required this.isImporting,
    required this.onCreate,
    required this.onImport,
    required this.onOpenSetupGuide,
    required this.onValidate,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppColors.getProviderColor(provider.apiValue);
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.admin_panel_settings_outlined, color: color),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    provider.label,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                Chip(
                  label: Text('${connections.length}'),
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              _providerResponsibility(provider),
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                FilledButton.icon(
                  onPressed: isImporting ? null : onImport,
                  icon: const Icon(Icons.upload_file_outlined),
                  label: Text(
                    provider == CloudProvider.aws
                        ? CloudConnectionStrings.importCsv
                        : CloudConnectionStrings.importJson,
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: isCreating ? null : onCreate,
                  icon: const Icon(Icons.key_outlined),
                  label: const Text(CloudConnectionStrings.enterManually),
                ),
                TextButton.icon(
                  onPressed: onOpenSetupGuide,
                  icon: const Icon(Icons.open_in_new),
                  label: const Text(CloudConnectionStrings.setupGuide),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            if (connections.isEmpty)
              Text(
                'No ${provider.label} deployment administrator stored.',
                style: Theme.of(context).textTheme.bodySmall,
              )
            else
              for (var index = 0; index < connections.length; index++) ...[
                if (index > 0) const Divider(),
                _ConnectionRow(
                  connection: connections[index],
                  isBusy: busyConnectionIds.contains(connections[index].id),
                  onValidate: onValidate,
                  onDelete: onDelete,
                ),
              ],
          ],
        ),
      ),
    );
  }
}

class _ConnectionRow extends StatelessWidget {
  final CloudConnection connection;
  final bool isBusy;
  final ValueChanged<CloudConnection> onValidate;
  final ValueChanged<CloudConnection> onDelete;

  const _ConnectionRow({
    required this.connection,
    required this.isBusy,
    required this.onValidate,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final statusColor = switch (connection.validationStatus) {
      'valid' => AppColors.success,
      'invalid' => AppColors.error,
      _ => AppColors.warning,
    };
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(Icons.circle, color: statusColor, size: AppSpacing.iconXs),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                connection.displayName,
                style: Theme.of(context).textTheme.labelLarge,
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                _connectionSummary(connection),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              if (connection.lastValidatedAt != null) ...[
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Validated ${DateFormat.yMMMd().format(connection.lastValidatedAt!.toLocal())}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
        if (isBusy)
          const Padding(
            padding: EdgeInsets.all(AppSpacing.sm),
            child: SizedBox.square(
              dimension: AppSpacing.iconMd,
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          )
        else
          PopupMenuButton<String>(
            tooltip: 'Actions for ${connection.displayName}',
            onSelected: (action) {
              if (action == 'validate') onValidate(connection);
              if (action == 'delete') onDelete(connection);
            },
            itemBuilder: (context) => const [
              PopupMenuItem(
                value: 'validate',
                child: ListTile(
                  leading: Icon(Icons.verified_outlined),
                  title: Text('Validate'),
                ),
              ),
              PopupMenuItem(
                value: 'delete',
                child: ListTile(
                  leading: Icon(Icons.delete_outline),
                  title: Text('Delete'),
                ),
              ),
            ],
          ),
      ],
    );
  }
}

class _LoadError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _LoadError({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.error_outline, color: Theme.of(context).colorScheme.error),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: Text(message)),
        TextButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Retry'),
        ),
      ],
    );
  }
}

String _connectionSummary(CloudConnection connection) {
  return [
    connection.validationStatus.replaceAll('_', ' '),
    connection.authType,
    if (connection.provider == CloudProvider.azure &&
        connection.payloadSummary['preparation_client_configured'] == true)
      CloudConnectionStrings.azureBundleSummary,
  ].where((value) => value.isNotEmpty).join(' · ');
}

String _providerResponsibility(CloudProvider provider) => switch (provider) {
  CloudProvider.aws => 'One identity for PoC deployment and cleanup.',
  CloudProvider.azure => CloudConnectionStrings.azureBundleSummary,
  CloudProvider.gcp => 'One service account for PoC deployment and cleanup.',
};
