import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/cloud_access_inventory.dart';
import '../../models/cloud_connection.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'cloud_connection_create_dialog.dart';

class CloudAccountsPanel extends StatelessWidget {
  final CloudAccessInventory? inventory;
  final bool isLoading;
  final String? loadError;
  final Set<String> busyConnectionIds;
  final bool isCreating;
  final VoidCallback onRetry;
  final ValueChanged<CloudConnectionCreateRequest> onCreate;
  final ValueChanged<CloudAccessEntry> onValidate;
  final ValueChanged<CloudAccessEntry> onSetDefault;
  final ValueChanged<CloudAccessEntry> onDelete;

  const CloudAccountsPanel({
    super.key,
    required this.inventory,
    required this.isLoading,
    required this.loadError,
    required this.busyConnectionIds,
    required this.isCreating,
    required this.onRetry,
    required this.onCreate,
    required this.onValidate,
    required this.onSetDefault,
    required this.onDelete,
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
                    'Cloud accounts & access',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Pricing and deployment identities available to your account.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            if (isLoading && inventory != null)
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
              tooltip: 'Refresh cloud access',
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        if (inventory != null && loadError != null) ...[
          _LoadError(message: loadError, onRetry: onRetry),
          const SizedBox(height: AppSpacing.md),
        ],
        if (inventory == null && isLoading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(AppSpacing.xl),
              child: CircularProgressIndicator(),
            ),
          )
        else if (inventory == null)
          _LoadError(message: loadError, onRetry: onRetry)
        else
          LayoutBuilder(
            builder: (context, constraints) {
              final stack =
                  constraints.maxWidth < AppSpacing.pricingReviewCardBreakpoint;
              final width = stack
                  ? constraints.maxWidth
                  : (constraints.maxWidth - (AppSpacing.md * 2)) / 3;
              return Wrap(
                spacing: AppSpacing.md,
                runSpacing: AppSpacing.md,
                children: CloudProvider.values
                    .map((provider) {
                      final providerInventory =
                          inventory!.providers[provider.apiValue] ??
                          _missingProvider(provider);
                      return SizedBox(
                        width: width,
                        child: _ProviderAccessCard(
                          provider: provider,
                          inventory: providerInventory,
                          busyConnectionIds: busyConnectionIds,
                          isCreating: isCreating,
                          onCreate: (purpose) =>
                              _openCreateDialog(context, provider, purpose),
                          onValidate: onValidate,
                          onSetDefault: onSetDefault,
                          onDelete: (entry) => _confirmDelete(context, entry),
                        ),
                      );
                    })
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
    CloudConnectionPurpose purpose,
  ) async {
    final request = await showDialog<CloudConnectionCreateRequest>(
      context: context,
      builder: (context) =>
          CloudConnectionCreateDialog(provider: provider, purpose: purpose),
    );
    if (request != null) onCreate(request);
  }

  Future<void> _confirmDelete(
    BuildContext context,
    CloudAccessEntry entry,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete cloud access?'),
        content: Text(
          entry.purpose == 'pricing' && entry.isDefaultForPricing == true
              ? 'Delete ${entry.identityLabel}? Pricing refresh stays disabled until another default is selected.'
              : 'Delete ${entry.identityLabel}? This cannot be undone.',
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
    if (confirmed == true) onDelete(entry);
  }
}

class _ProviderAccessCard extends StatelessWidget {
  final CloudProvider provider;
  final CloudAccessProviderInventory inventory;
  final Set<String> busyConnectionIds;
  final bool isCreating;
  final ValueChanged<CloudConnectionPurpose> onCreate;
  final ValueChanged<CloudAccessEntry> onValidate;
  final ValueChanged<CloudAccessEntry> onSetDefault;
  final ValueChanged<CloudAccessEntry> onDelete;

  const _ProviderAccessCard({
    required this.provider,
    required this.inventory,
    required this.busyConnectionIds,
    required this.isCreating,
    required this.onCreate,
    required this.onValidate,
    required this.onSetDefault,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppColors.getProviderColor(provider.apiValue);
    final entries = <CloudAccessEntry>[
      if (inventory.pricingOptions.isEmpty) inventory.pricing,
      ...inventory.pricingOptions,
      ...inventory.deployment,
    ];

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.md,
          AppSpacing.md,
          AppSpacing.sm,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.cloud_outlined, color: color),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    provider.label,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
                PopupMenuButton<CloudConnectionPurpose>(
                  enabled: !isCreating,
                  tooltip: 'Add ${provider.label} access',
                  icon: const Icon(Icons.add),
                  onSelected: onCreate,
                  itemBuilder: (context) => [
                    if (provider != CloudProvider.azure)
                      const PopupMenuItem(
                        value: CloudConnectionPurpose.pricing,
                        child: ListTile(
                          leading: Icon(Icons.price_check_outlined),
                          title: Text('Pricing access'),
                        ),
                      ),
                    const PopupMenuItem(
                      value: CloudConnectionPurpose.deployment,
                      child: ListTile(
                        leading: Icon(Icons.rocket_launch_outlined),
                        title: Text('Deployment access'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            _MetricLine(
              label: 'Pricing',
              value: _statusLabel(inventory.pricing.status),
              color: _statusColor(inventory.pricing.status),
            ),
            const SizedBox(height: AppSpacing.xs),
            _MetricLine(
              label: 'Deployment',
              value: '${inventory.deployment.length}',
              color: Theme.of(context).colorScheme.onSurface,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              _identitySummary(inventory.pricing),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const Divider(height: AppSpacing.lg),
            ExpansionTile(
              tilePadding: EdgeInsets.zero,
              childrenPadding: EdgeInsets.zero,
              title: Text(
                'Access details (${entries.length})',
                style: Theme.of(context).textTheme.labelLarge,
              ),
              children: [
                for (var index = 0; index < entries.length; index++) ...[
                  _AccessRow(
                    entry: entries[index],
                    isBusy:
                        entries[index].connectionId != null &&
                        busyConnectionIds.contains(entries[index].connectionId),
                    onValidate: onValidate,
                    onSetDefault: onSetDefault,
                    onDelete: onDelete,
                  ),
                  if (index != entries.length - 1) const Divider(height: 1),
                ],
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MetricLine extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _MetricLine({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(label)),
        Text(
          value,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(color: color),
        ),
      ],
    );
  }
}

class _AccessRow extends StatelessWidget {
  final CloudAccessEntry entry;
  final bool isBusy;
  final ValueChanged<CloudAccessEntry> onValidate;
  final ValueChanged<CloudAccessEntry> onSetDefault;
  final ValueChanged<CloudAccessEntry> onDelete;

  const _AccessRow({
    required this.entry,
    required this.isBusy,
    required this.onValidate,
    required this.onSetDefault,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final canValidate =
        entry.connectionId != null && entry.actions.contains('validate');
    final canSetDefault =
        entry.connectionId != null &&
        entry.actions.contains('set_pricing_default');
    final canDelete =
        entry.connectionId != null && entry.actions.contains('delete');
    final deleteBlocked = entry.actions.contains('delete_blocked');

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            entry.purpose == 'pricing'
                ? Icons.price_check_outlined
                : Icons.rocket_launch_outlined,
            size: AppSpacing.iconMd,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        entry.identityLabel,
                        style: Theme.of(context).textTheme.labelLarge,
                      ),
                    ),
                    if (entry.isDefaultForPricing == true)
                      const Padding(
                        padding: EdgeInsets.only(left: AppSpacing.xs),
                        child: Text('Default'),
                      ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  _entrySummary(entry),
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                if (entry.lastValidatedAt != null) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    'Validated ${DateFormat.yMMMd().format(entry.lastValidatedAt!.toLocal())}',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
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
          else if (canValidate || canSetDefault || canDelete || deleteBlocked)
            PopupMenuButton<String>(
              tooltip: 'Actions for ${entry.identityLabel}',
              onSelected: (action) {
                switch (action) {
                  case 'validate':
                    onValidate(entry);
                  case 'default':
                    onSetDefault(entry);
                  case 'delete':
                    onDelete(entry);
                }
              },
              itemBuilder: (context) => [
                if (canValidate)
                  const PopupMenuItem(
                    value: 'validate',
                    child: ListTile(
                      leading: Icon(Icons.verified_outlined),
                      title: Text('Validate'),
                    ),
                  ),
                if (canSetDefault)
                  const PopupMenuItem(
                    value: 'default',
                    child: ListTile(
                      leading: Icon(Icons.check_circle_outline),
                      title: Text('Use for pricing'),
                    ),
                  ),
                if (canDelete)
                  const PopupMenuItem(
                    value: 'delete',
                    child: ListTile(
                      leading: Icon(Icons.delete_outline),
                      title: Text('Delete'),
                    ),
                  ),
                if (deleteBlocked)
                  const PopupMenuItem(
                    enabled: false,
                    child: ListTile(
                      leading: Icon(Icons.lock_outline),
                      title: Text('Used by a twin'),
                    ),
                  ),
              ],
            ),
        ],
      ),
    );
  }
}

class _LoadError extends StatelessWidget {
  final String? message;
  final VoidCallback onRetry;

  const _LoadError({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.error_outline, color: Theme.of(context).colorScheme.error),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: Text(message ?? 'Cloud access could not be loaded.')),
        TextButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Retry'),
        ),
      ],
    );
  }
}

CloudAccessProviderInventory _missingProvider(CloudProvider provider) {
  return CloudAccessProviderInventory(
    provider: provider.apiValue,
    pricing: CloudAccessEntry(
      provider: provider.apiValue,
      purpose: 'pricing',
      scope: 'user',
      identityLabel: '${provider.label} pricing access unavailable',
      status: 'missing',
    ),
  );
}

String _identitySummary(CloudAccessEntry entry) {
  return entry.providerAccountId ??
      entry.providerProjectId ??
      entry.providerSubscriptionId ??
      entry.identityLabel;
}

String _entrySummary(CloudAccessEntry entry) {
  final binding = entry.boundTwinCount > 0
      ? 'Used by ${entry.boundTwinLabels.join(', ')}'
      : null;
  return [
    entry.purpose == 'pricing' ? 'Pricing' : 'Deployment',
    _statusLabel(entry.status),
    binding,
  ].whereType<String>().join(' - ');
}

String _statusLabel(String status) => switch (status) {
  'active' => 'Active',
  'invalid' => 'Invalid',
  'needs_validation' => 'Needs validation',
  'stale' => 'Stale',
  'disabled' => 'Disabled',
  _ => 'Missing',
};

Color _statusColor(String status) => switch (status) {
  'active' => AppColors.success,
  'invalid' || 'disabled' => AppColors.error,
  'needs_validation' || 'stale' => AppColors.warning,
  _ => AppColors.warning,
};
