import 'dart:convert';

import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
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
        _ProviderArchitectureSection(state: state),
        const SizedBox(height: AppSpacing.md),
        _OptimizationSummarySection(state: state),
        const SizedBox(height: AppSpacing.md),
        _PricingDataSection(
          state: state,
          onViewArtifact: onViewArtifact,
          onDownloadArtifact: onDownloadArtifact,
        ),
        const SizedBox(height: AppSpacing.md),
        _ConfigurationFilesSection(
          state: state,
          onViewArtifact: onViewArtifact,
          onDownloadArtifact: onDownloadArtifact,
        ),
        const SizedBox(height: AppSpacing.md),
        _UserFunctionsSection(
          state: state,
          onViewArtifact: onViewArtifact,
          onDownloadArtifact: onDownloadArtifact,
        ),
      ],
    );
  }
}

class _ProviderArchitectureSection extends StatelessWidget {
  final TwinOverviewLoaded state;

  const _ProviderArchitectureSection({required this.state});

  @override
  Widget build(BuildContext context) {
    final result = state.optimizerResult;
    final cheapestPath = result?['cheapestPath'] == null
        ? <String>[]
        : List<String>.from(result!['cheapestPath'] as List);

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
            Center(child: CheapestPathVisualization(path: cheapestPath)),
          ],
        ),
      ),
    );
  }
}

class _OptimizationSummarySection extends StatelessWidget {
  final TwinOverviewLoaded state;

  const _OptimizationSummarySection({required this.state});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final result = state.optimizerResult;
    final params = state.optimizerParams;

    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.analytics),
        title: const Text('Optimization Summary'),
        initiallyExpanded: true,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: result == null
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
                            '\$${(result['totalCost'] ?? 0).toStringAsFixed(2)}/month',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: AppColors.success,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.md),
                      if (params != null) ...[
                        _ParamRow(
                          label: 'Devices',
                          value: '${params['numberOfDevices'] ?? 'N/A'}',
                        ),
                        _ParamRow(
                          label: 'Messages/hour',
                          value: _formatMessagesPerHour(params),
                        ),
                        _ParamRow(
                          label: 'Retention',
                          value: _formatRetention(params),
                        ),
                        const SizedBox(height: AppSpacing.sm),
                      ],
                      if (state.calculatedAt != null)
                        _CalculatedAtBadge(
                          timestamp: _formatTimestamp(state.calculatedAt!),
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
  final TwinOverviewLoaded state;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _PricingDataSection({
    required this.state,
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
                _PricingRow(
                  provider: 'AWS',
                  color: AppColors.aws,
                  pricing: state.pricingAws,
                  updatedAt: state.pricingAwsUpdatedAt,
                  onViewArtifact: onViewArtifact,
                  onDownloadArtifact: onDownloadArtifact,
                ),
                const SizedBox(height: AppSpacing.sm),
                _PricingRow(
                  provider: 'Azure',
                  color: AppColors.azure,
                  pricing: state.pricingAzure,
                  updatedAt: state.pricingAzureUpdatedAt,
                  onViewArtifact: onViewArtifact,
                  onDownloadArtifact: onDownloadArtifact,
                ),
                const SizedBox(height: AppSpacing.sm),
                _PricingRow(
                  provider: 'GCP',
                  color: AppColors.gcp,
                  pricing: state.pricingGcp,
                  updatedAt: state.pricingGcpUpdatedAt,
                  onViewArtifact: onViewArtifact,
                  onDownloadArtifact: onDownloadArtifact,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ConfigurationFilesSection extends StatelessWidget {
  final TwinOverviewLoaded state;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _ConfigurationFilesSection({
    required this.state,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    final config = state.deployerConfig;
    final l2Provider =
        state.cheapestPath?['l2']?.toString().toLowerCase() ?? 'aws';
    final l4Provider =
        state.cheapestPath?['l4']?.toString().toLowerCase() ?? 'aws';
    final hierarchyFilename = l4Provider == 'azure'
        ? 'azure_hierarchy.json'
        : 'aws_hierarchy.json';
    final sceneFilename = l4Provider == 'azure'
        ? '3DScenesConfiguration.json'
        : 'scene.json';

    final artifacts = <TwinOverviewCodeArtifact>[
      if (config?['config_events_json'] != null)
        TwinOverviewCodeArtifact(
          title: 'config_events.json',
          filename: 'config_events.json',
          content: config!['config_events_json'] as String,
        ),
      if (config?['config_iot_devices_json'] != null)
        TwinOverviewCodeArtifact(
          title: 'config_iot_devices.json',
          filename: 'config_iot_devices.json',
          content: config!['config_iot_devices_json'] as String,
        ),
      if (config?['payloads_json'] != null)
        TwinOverviewCodeArtifact(
          title: 'payloads.json',
          filename: 'payloads.json',
          content: config!['payloads_json'] as String,
        ),
      if (config?['state_machine_content'] != null)
        TwinOverviewCodeArtifact(
          title: _getStateMachineFilename(l2Provider),
          filename: _getStateMachineFilename(l2Provider),
          content: config!['state_machine_content'] as String,
        ),
      if (config?['hierarchy_content'] != null)
        TwinOverviewCodeArtifact(
          title: hierarchyFilename,
          filename: hierarchyFilename,
          content: config!['hierarchy_content'] as String,
        ),
      if (config?['scene_config_content'] != null)
        TwinOverviewCodeArtifact(
          title: sceneFilename,
          filename: sceneFilename,
          content: config!['scene_config_content'] as String,
        ),
      if (config?['user_config_content'] != null)
        TwinOverviewCodeArtifact(
          title: 'config_user.json',
          filename: 'config_user.json',
          content: config!['user_config_content'] as String,
        ),
    ];

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
                            artifact: artifact,
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
  final TwinOverviewLoaded state;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _UserFunctionsSection({
    required this.state,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    final config = state.deployerConfig;
    final l2Provider =
        state.cheapestPath?['l2']?.toString().toLowerCase() ?? 'aws';

    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.functions),
        title: const Text('User Functions'),
        initiallyExpanded: false,
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: config == null
                ? const Text('No user functions available')
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (config['processor_contents'] != null &&
                          (config['processor_contents'] as Map).isNotEmpty)
                        _FunctionGroup(
                          title: 'Processors',
                          functions:
                              config['processor_contents']
                                  as Map<String, dynamic>,
                          l2Provider: l2Provider,
                          onViewArtifact: onViewArtifact,
                          onDownloadArtifact: onDownloadArtifact,
                        ),
                      if (config['event_feedback_content'] != null)
                        _FunctionGroup(
                          title: 'Event Feedback',
                          functions: {
                            'event-feedback':
                                config['event_feedback_content'] as String,
                          },
                          l2Provider: l2Provider,
                          onViewArtifact: onViewArtifact,
                          onDownloadArtifact: onDownloadArtifact,
                        ),
                      if (config['event_action_contents'] != null &&
                          (config['event_action_contents'] as Map).isNotEmpty)
                        _FunctionGroup(
                          title: 'Event Actions',
                          functions:
                              config['event_action_contents']
                                  as Map<String, dynamic>,
                          l2Provider: l2Provider,
                          onViewArtifact: onViewArtifact,
                          onDownloadArtifact: onDownloadArtifact,
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

class _PricingRow extends StatelessWidget {
  final String provider;
  final Color color;
  final Map<String, dynamic>? pricing;
  final String? updatedAt;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _PricingRow({
    required this.provider,
    required this.color,
    required this.pricing,
    required this.updatedAt,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    final artifact = pricing == null
        ? null
        : TwinOverviewCodeArtifact(
            title: '$provider Pricing',
            filename: '${provider.toLowerCase()}_pricing.json',
            content: _prettyPrintJson(pricing!),
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
                  '$provider Pricing',
                  style: Theme.of(
                    context,
                  ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500),
                ),
                Text(
                  updatedAt != null
                      ? 'Fetched: ${_formatTimestamp(updatedAt!)}'
                      : 'No pricing data',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
          if (updatedAt != null) ...[
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
  final String title;
  final Map<String, dynamic> functions;
  final String l2Provider;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const _FunctionGroup({
    required this.title,
    required this.functions,
    required this.l2Provider,
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
            title,
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: AppSpacing.sm),
          ...functions.entries.map((entry) {
            final filename = '${entry.key}/${_getFunctionFilename(l2Provider)}';
            final artifact = TwinOverviewCodeArtifact(
              title: filename,
              filename: filename,
              content: entry.value as String,
            );

            return _CodeArtifactRow(
              artifact: artifact,
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

String _formatMessagesPerHour(Map<String, dynamic> params) {
  final interval = params['deviceSendingIntervalInMinutes'];
  if (interval == null) return 'N/A';
  final messagesPerHour = 60.0 / (interval as num);
  return messagesPerHour.toStringAsFixed(1);
}

String _formatRetention(Map<String, dynamic> params) {
  final hot = params['hotStorageDurationInMonths'] as num? ?? 0;
  final cool = params['coolStorageDurationInMonths'] as num? ?? 0;
  final archive = params['archiveStorageDurationInMonths'] as num? ?? 0;
  final totalMonths = hot + cool + archive;
  if (totalMonths == 0) return 'N/A';
  return '${totalMonths.toStringAsFixed(0)} months';
}

String _getFunctionFilename(String provider) {
  return switch (provider.toLowerCase()) {
    'gcp' => 'main.py',
    'azure' => 'function_app.py',
    _ => 'lambda_function.py',
  };
}

String _getStateMachineFilename(String provider) {
  return switch (provider.toLowerCase()) {
    'gcp' => 'google_cloud_workflow.yaml',
    'azure' => 'azure_logic_app.json',
    _ => 'aws_step_function.json',
  };
}

String _prettyPrintJson(Map<String, dynamic> json) {
  try {
    const encoder = JsonEncoder.withIndent('  ');
    return encoder.convert(json);
  } catch (_) {
    return json.toString();
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
