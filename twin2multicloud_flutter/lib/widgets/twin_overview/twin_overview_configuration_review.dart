import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../models/twin_configuration_view.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import '../results/cheapest_path_visualization.dart';
import 'twin_overview_code_artifact.dart';

class TwinOverviewConfigurationReview extends StatelessWidget {
  final TwinOverviewLoaded state;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const TwinOverviewConfigurationReview({
    super.key,
    required this.state,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final view = TwinConfigurationView.fromState(state);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'CONFIGURATION REVIEW',
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
            letterSpacing: 1.2,
          ),
        ),
        const Divider(),
        const SizedBox(height: AppSpacing.md),
        _ProviderArchitectureSection(pathSegments: view.pathSegments),
        const SizedBox(height: AppSpacing.md),
        _OptimizationSummarySection(optimization: view.optimization),
        const SizedBox(height: AppSpacing.md),
        _PricingDataSection(
          snapshots: view.pricingSnapshots,
          onViewArtifact: onViewArtifact,
          onDownloadArtifact: onDownloadArtifact,
        ),
        const SizedBox(height: AppSpacing.md),
        _ConfigurationFilesSection(
          artifacts: view.configurationArtifacts,
          onViewArtifact: onViewArtifact,
          onDownloadArtifact: onDownloadArtifact,
        ),
        const SizedBox(height: AppSpacing.md),
        _UserFunctionsSection(
          functionGroups: view.functionGroups,
          onViewArtifact: onViewArtifact,
          onDownloadArtifact: onDownloadArtifact,
        ),
      ],
    );
  }
}

class _ProviderArchitectureSection extends StatelessWidget {
  final List<String> pathSegments;

  const _ProviderArchitectureSection({required this.pathSegments});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.architecture),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  'Provider Architecture',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
            Center(child: CheapestPathVisualization(path: pathSegments)),
          ],
        ),
      ),
    );
  }
}

class _OptimizationSummarySection extends StatelessWidget {
  final OptimizationSummaryView optimization;

  const _OptimizationSummarySection({required this.optimization});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.analytics),
        title: const Text('Optimization Summary'),
        initiallyExpanded: true,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: !optimization.hasResult
                ? Text(
                    'No optimization result available',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(
                            Icons.attach_money,
                            color: AppColors.success,
                          ),
                          const SizedBox(width: AppSpacing.sm),
                          Text(
                            'Estimated Cost: ',
                            style: theme.textTheme.titleMedium,
                          ),
                          Text(
                            '\$${optimization.totalCost.toStringAsFixed(2)}/month',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: AppColors.success,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.md),
                      if (optimization.numberOfDevices != null) ...[
                        _ParamRow(
                          label: 'Devices',
                          value: optimization.numberOfDevices!,
                        ),
                      ],
                      if (optimization.messagesPerHour != null) ...[
                        _ParamRow(
                          label: 'Messages/hour',
                          value: optimization.messagesPerHour!,
                        ),
                      ],
                      if (optimization.retention != null) ...[
                        _ParamRow(
                          label: 'Retention',
                          value: optimization.retention!,
                        ),
                      ],
                      if (optimization.numberOfDevices != null ||
                          optimization.messagesPerHour != null ||
                          optimization.retention != null)
                        const SizedBox(height: AppSpacing.sm),
                      if (optimization.calculatedAt != null)
                        _CalculatedAtBadge(
                          timestamp: _formatTimestamp(
                            optimization.calculatedAt!,
                          ),
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _PricingDataSection extends StatelessWidget {
  final List<ProviderPricingSnapshotView> snapshots;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _PricingDataSection({
    required this.snapshots,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.attach_money),
        title: const Text('Pricing Data'),
        initiallyExpanded: false,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              children: [
                for (var index = 0; index < snapshots.length; index++) ...[
                  _PricingRow(
                    snapshot: snapshots[index],
                    color: _providerColor(snapshots[index].provider),
                    onViewArtifact: onViewArtifact,
                    onDownloadArtifact: onDownloadArtifact,
                  ),
                  if (index < snapshots.length - 1)
                    const SizedBox(height: AppSpacing.sm),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ConfigurationFilesSection extends StatelessWidget {
  final List<ConfigurationArtifactView> artifacts;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _ConfigurationFilesSection({
    required this.artifacts,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.code),
        title: const Text('Configuration Files'),
        initiallyExpanded: false,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: artifacts.isEmpty
                ? const Text('No configuration files available')
                : Column(
                    children: artifacts
                        .map(
                          (artifact) => _CodeArtifactRow(
                            artifact: _toCodeArtifact(artifact),
                            icon: Icons.insert_drive_file_outlined,
                            onViewArtifact: onViewArtifact,
                            onDownloadArtifact: onDownloadArtifact,
                          ),
                        )
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _UserFunctionsSection extends StatelessWidget {
  final List<FunctionArtifactGroupView> functionGroups;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _UserFunctionsSection({
    required this.functionGroups,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.functions),
        title: const Text('User Functions'),
        initiallyExpanded: false,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: functionGroups.isEmpty
                ? const Text('No user functions available')
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: functionGroups
                        .map(
                          (group) => _FunctionGroup(
                            group: group,
                            onViewArtifact: onViewArtifact,
                            onDownloadArtifact: onDownloadArtifact,
                          ),
                        )
                        .toList(),
                  ),
          ),
        ],
      ),
    );
  }
}

class _PricingRow extends StatelessWidget {
  final ProviderPricingSnapshotView snapshot;
  final Color color;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _PricingRow({
    required this.snapshot,
    required this.color,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    final artifact = !snapshot.hasData
        ? null
        : TwinOverviewCodeArtifact(
            title: snapshot.title,
            filename: snapshot.filename,
            content: snapshot.artifactContent!,
          );

    return Container(
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 40,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(AppSpacing.xxs),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  snapshot.title,
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500),
                ),
                Text(
                  snapshot.updatedAt != null
                      ? 'Fetched: ${_formatTimestamp(snapshot.updatedAt!)}'
                      : 'No pricing data',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          if (snapshot.updatedAt != null) ...[
            IconButton(
              onPressed: artifact == null
                  ? null
                  : () => onViewArtifact(artifact),
              icon: const Icon(Icons.visibility_outlined),
              tooltip: 'View',
            ),
            IconButton(
              onPressed: artifact == null
                  ? null
                  : () => onDownloadArtifact(artifact),
              icon: const Icon(Icons.download_outlined),
              tooltip: 'Download',
            ),
          ],
        ],
      ),
    );
  }
}

class _CodeArtifactRow extends StatelessWidget {
  final TwinOverviewCodeArtifact artifact;
  final IconData icon;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _CodeArtifactRow({
    required this.artifact,
    required this.icon,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Row(
        children: [
          Icon(icon, size: 20),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: Text(artifact.filename)),
          IconButton(
            onPressed: () => onViewArtifact(artifact),
            icon: const Icon(Icons.visibility_outlined),
            tooltip: 'View',
          ),
          IconButton(
            onPressed: () => onDownloadArtifact(artifact),
            icon: const Icon(Icons.download_outlined),
            tooltip: 'Download',
          ),
        ],
      ),
    );
  }
}

class _FunctionGroup extends StatelessWidget {
  final FunctionArtifactGroupView group;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _FunctionGroup({
    required this.group,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            group.title,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: AppSpacing.sm),
          ...group.artifacts.map((artifact) {
            return _CodeArtifactRow(
              artifact: _toCodeArtifact(artifact),
              icon: Icons.code,
              onViewArtifact: onViewArtifact,
              onDownloadArtifact: onDownloadArtifact,
            );
          }),
        ],
      ),
    );
  }
}

class _ParamRow extends StatelessWidget {
  final String label;
  final String value;

  const _ParamRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxs),
      child: Row(
        children: [
          Text(
            '$label: ',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          Text(
            value,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500),
          ),
        ],
      ),
    );
  }
}

class _CalculatedAtBadge extends StatelessWidget {
  final String timestamp;

  const _CalculatedAtBadge({required this.timestamp});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(AppSpacing.xs),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.schedule, size: 16, color: theme.colorScheme.primary),
          const SizedBox(width: AppSpacing.sm),
          Text(
            'Calculated: $timestamp',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onPrimaryContainer,
            ),
          ),
        ],
      ),
    );
  }
}

String _formatTimestamp(String timestamp) {
  try {
    final dt = DateTime.parse(timestamp);
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
        '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')} UTC';
  } catch (_) {
    return timestamp;
  }
}

Color _providerColor(String provider) {
  return AppColors.getProviderColor(provider);
}

TwinOverviewCodeArtifact _toCodeArtifact(ConfigurationArtifactView artifact) {
  return TwinOverviewCodeArtifact(
    title: artifact.title,
    filename: artifact.filename,
    content: artifact.content,
  );
}
