import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../models/cloud_connection.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'cloud_connection_create_dialog.dart';

typedef CloudConnectionCreateCallback =
    Future<void> Function(CloudConnectionCreateRequest request);
typedef CloudConnectionActionCallback =
    Future<void> Function(CloudConnection connection);

class CloudAccountsPanel extends StatelessWidget {
  final AsyncValue<List<CloudConnection>> connections;
  final CloudConnectionCreateCallback onCreate;
  final CloudConnectionActionCallback onValidate;
  final CloudConnectionActionCallback onDelete;
  final VoidCallback onRetry;

  const CloudAccountsPanel({
    super.key,
    required this.connections,
    required this.onCreate,
    required this.onValidate,
    required this.onDelete,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.cloud_done_outlined,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    'Cloud Accounts',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh'),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Stored Cloud Connections are reusable credential records for '
              'pricing refreshes and deployments. Secret values are write-only.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            connections.when(
              data: (items) => _CloudAccountsContent(
                connections: items,
                onCreate: onCreate,
                onValidate: onValidate,
                onDelete: onDelete,
              ),
              loading: () => const _CloudAccountsLoading(),
              error: (error, _) =>
                  _CloudAccountsError(message: '$error', onRetry: onRetry),
            ),
          ],
        ),
      ),
    );
  }
}

class _CloudAccountsContent extends StatelessWidget {
  final List<CloudConnection> connections;
  final CloudConnectionCreateCallback onCreate;
  final CloudConnectionActionCallback onValidate;
  final CloudConnectionActionCallback onDelete;

  const _CloudAccountsContent({
    required this.connections,
    required this.onCreate,
    required this.onValidate,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: CloudProvider.values
          .map(
            (provider) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.md),
              child: _ProviderCloudAccountSection(
                provider: provider,
                connections: connections
                    .where((connection) => connection.provider == provider)
                    .toList(),
                onCreate: onCreate,
                onValidate: onValidate,
                onDelete: onDelete,
              ),
            ),
          )
          .toList(),
    );
  }
}

class _ProviderCloudAccountSection extends StatelessWidget {
  final CloudProvider provider;
  final List<CloudConnection> connections;
  final CloudConnectionCreateCallback onCreate;
  final CloudConnectionActionCallback onValidate;
  final CloudConnectionActionCallback onDelete;

  const _ProviderCloudAccountSection({
    required this.provider,
    required this.connections,
    required this.onCreate,
    required this.onValidate,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final providerColor = AppColors.getProviderColor(provider.apiValue);

    return DecoratedBox(
      decoration: BoxDecoration(
        border: Border.all(color: providerColor.withAlpha(80)),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.cloud, color: providerColor),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    provider.label,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                OutlinedButton.icon(
                  onPressed: () => _openCreateDialog(context),
                  icon: const Icon(Icons.add),
                  label: Text('New ${provider.label} connection'),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            if (connections.isEmpty)
              _EmptyProviderState(provider: provider)
            else
              ...connections.map(
                (connection) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: _CloudAccountTile(
                    connection: connection,
                    onValidate: onValidate,
                    onDelete: onDelete,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _openCreateDialog(BuildContext context) async {
    final request = await showDialog<CloudConnectionCreateRequest>(
      context: context,
      builder: (context) => CloudConnectionCreateDialog(provider: provider),
    );
    if (request != null) {
      await onCreate(request);
    }
  }
}

class _CloudAccountTile extends StatelessWidget {
  final CloudConnection connection;
  final CloudConnectionActionCallback onValidate;
  final CloudConnectionActionCallback onDelete;

  const _CloudAccountTile({
    required this.connection,
    required this.onValidate,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final isNarrow =
                constraints.maxWidth < AppSpacing.pricingReviewCardBreakpoint;
            final details = _CloudAccountDetails(connection: connection);
            final actions = _CloudAccountActions(
              connection: connection,
              onValidate: onValidate,
              onDelete: onDelete,
            );

            if (isNarrow) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  details,
                  const SizedBox(height: AppSpacing.md),
                  actions,
                ],
              );
            }

            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: details),
                const SizedBox(width: AppSpacing.md),
                actions,
              ],
            );
          },
        ),
      ),
    );
  }
}

class _CloudAccountDetails extends StatelessWidget {
  final CloudConnection connection;

  const _CloudAccountDetails({required this.connection});

  @override
  Widget build(BuildContext context) {
    final metadata = _metadataLines(connection);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Flexible(
              child: Text(
                connection.displayName,
                style: Theme.of(context).textTheme.titleSmall,
              ),
            ),
            const SizedBox(width: AppSpacing.sm),
            _ValidationBadge(status: connection.validationStatus),
          ],
        ),
        const SizedBox(height: AppSpacing.xs),
        if (connection.payloadFingerprint.isNotEmpty)
          Text(
            'Fingerprint: ${connection.payloadFingerprint}',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        if (connection.lastValidatedAt != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Last validated: ${DateFormat.yMMMd().add_Hm().format(connection.lastValidatedAt!.toLocal())}',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
        if (connection.validationMessage != null) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            connection.validationMessage!,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
        if (metadata.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            children: metadata
                .map((line) => Chip(label: Text(line)))
                .toList(growable: false),
          ),
        ],
      ],
    );
  }

  List<String> _metadataLines(CloudConnection connection) {
    final lines = <String>[];
    for (final entry in connection.cloudScope.entries) {
      final value = entry.value?.toString().trim();
      if (value != null && value.isNotEmpty) {
        lines.add('${entry.key}: $value');
      }
    }
    for (final entry in connection.payloadSummary.entries) {
      final value = entry.value?.toString().trim();
      if (value != null && value.isNotEmpty) {
        lines.add('${entry.key}: $value');
      }
    }
    return lines;
  }
}

class _CloudAccountActions extends StatelessWidget {
  final CloudConnection connection;
  final CloudConnectionActionCallback onValidate;
  final CloudConnectionActionCallback onDelete;

  const _CloudAccountActions({
    required this.connection,
    required this.onValidate,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm,
      alignment: WrapAlignment.end,
      children: [
        OutlinedButton.icon(
          onPressed: () => onValidate(connection),
          icon: const Icon(Icons.verified_outlined),
          label: const Text('Validate'),
        ),
        OutlinedButton.icon(
          onPressed: () => _confirmDelete(context),
          icon: const Icon(Icons.delete_outline),
          label: const Text('Delete'),
          style: OutlinedButton.styleFrom(
            foregroundColor: Theme.of(context).colorScheme.error,
          ),
        ),
      ],
    );
  }

  Future<void> _confirmDelete(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Cloud Connection?'),
        content: Text(
          'Delete ${connection.displayName}? This is blocked when a twin still '
          'references the connection.',
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

    if (confirmed == true) {
      await onDelete(connection);
    }
  }
}

class _ValidationBadge extends StatelessWidget {
  final String status;

  const _ValidationBadge({required this.status});

  @override
  Widget build(BuildContext context) {
    final color = switch (status) {
      'valid' => AppColors.success,
      'invalid' => AppColors.error,
      'failed' => AppColors.error,
      _ => AppColors.warning,
    };
    final label = switch (status) {
      'valid' => 'Valid',
      'invalid' => 'Invalid',
      'failed' => 'Failed',
      'untested' => 'Untested',
      _ => 'Review',
    };

    return DecoratedBox(
      decoration: BoxDecoration(
        color: color.withAlpha(32),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.sm,
          vertical: AppSpacing.xs,
        ),
        child: Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: color,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}

class _EmptyProviderState extends StatelessWidget {
  final CloudProvider provider;

  const _EmptyProviderState({required this.provider});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(
          Icons.info_outline,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
          size: AppSpacing.iconMd,
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            'No ${provider.label} Cloud Connection stored.',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      ],
    );
  }
}

class _CloudAccountsLoading extends StatelessWidget {
  const _CloudAccountsLoading();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.all(AppSpacing.lg),
      child: Center(child: CircularProgressIndicator()),
    );
  }
}

class _CloudAccountsError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _CloudAccountsError({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.error_outline, color: Theme.of(context).colorScheme.error),
        const SizedBox(width: AppSpacing.md),
        Expanded(child: Text('Cloud Accounts could not be loaded: $message')),
        OutlinedButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Retry'),
        ),
      ],
    );
  }
}
