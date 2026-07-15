import 'dart:convert';

import '../bloc/twin_overview/twin_overview_state.dart';
import 'calc_params.dart';
import 'calc_result.dart';
import 'cloud_connection.dart';
import 'deployer_config.dart';
import 'optimizer_config.dart';

class TwinConfigurationView {
  final List<String> pathSegments;
  final OptimizationSummaryView optimization;
  final List<ProviderPricingSnapshotView> pricingSnapshots;
  final List<ConfigurationArtifactView> configurationArtifacts;
  final List<FunctionArtifactGroupView> functionGroups;

  const TwinConfigurationView({
    required this.pathSegments,
    required this.optimization,
    required this.pricingSnapshots,
    required this.configurationArtifacts,
    required this.functionGroups,
  });

  factory TwinConfigurationView.fromState(TwinOverviewLoaded state) {
    final deployerConfig = state.deployerConfig ?? const DeployerConfigData();
    final optimizerConfig = state.optimizerConfig;
    final pathSegments =
        optimizerConfig?.optimization?.result.cheapestPath ?? const [];
    final l2Provider = _providerForLayer(
      layer: 'l2',
      cheapestPath: optimizerConfig?.cheapestPath,
      pathSegments: pathSegments,
      fallback: 'aws',
    );
    final l4Provider = _providerForLayer(
      layer: 'l4',
      cheapestPath: optimizerConfig?.cheapestPath,
      pathSegments: pathSegments,
      fallback: 'aws',
    );

    return TwinConfigurationView(
      pathSegments: pathSegments,
      optimization: OptimizationSummaryView.fromData(
        result: optimizerConfig?.optimization?.result,
        params: optimizerConfig?.params,
        calculatedAt: optimizerConfig?.calculatedAt,
      ),
      pricingSnapshots: [
        for (final provider in CloudProvider.values)
          ProviderPricingSnapshotView.fromSnapshot(
            optimizerConfig?.snapshot(provider) ??
                ProviderPricingSnapshot(provider: provider),
          ),
      ],
      configurationArtifacts: _configurationArtifacts(
        deployerConfig: deployerConfig,
        l2Provider: l2Provider,
        l4Provider: l4Provider,
      ),
      functionGroups: _functionGroups(
        deployerConfig: deployerConfig,
        l2Provider: l2Provider,
      ),
    );
  }
}

class OptimizationSummaryView {
  final bool hasResult;
  final double totalCost;
  final String? numberOfDevices;
  final String? messagesPerHour;
  final String? retention;
  final String? calculatedAt;

  const OptimizationSummaryView({
    required this.hasResult,
    required this.totalCost,
    this.numberOfDevices,
    this.messagesPerHour,
    this.retention,
    this.calculatedAt,
  });

  factory OptimizationSummaryView.fromData({
    required CalcResult? result,
    required CalcParams? params,
    required DateTime? calculatedAt,
  }) {
    return OptimizationSummaryView(
      hasResult: result != null,
      totalCost: result?.totalCost ?? 0,
      numberOfDevices: params?.numberOfDevices.toString(),
      messagesPerHour: _messagesPerHour(params),
      retention: _retention(params),
      calculatedAt: calculatedAt?.toIso8601String(),
    );
  }
}

class ProviderPricingSnapshotView {
  final String provider;
  final String? updatedAt;
  final String? artifactContent;

  const ProviderPricingSnapshotView({
    required this.provider,
    this.updatedAt,
    this.artifactContent,
  });

  factory ProviderPricingSnapshotView.fromSnapshot(
    ProviderPricingSnapshot snapshot,
  ) {
    return ProviderPricingSnapshotView(
      provider: snapshot.provider.label,
      updatedAt: snapshot.updatedAt?.toIso8601String(),
      artifactContent: snapshot.payload == null
          ? null
          : _prettyPrintJson(snapshot.payload!),
    );
  }

  bool get hasData => artifactContent != null;
  String get filename => '${provider.toLowerCase()}_pricing.json';
  String get title => '$provider Pricing';
}

class ConfigurationArtifactView {
  final String title;
  final String filename;
  final String content;

  const ConfigurationArtifactView({
    required this.title,
    required this.filename,
    required this.content,
  });
}

class FunctionArtifactGroupView {
  final String title;
  final List<ConfigurationArtifactView> artifacts;

  const FunctionArtifactGroupView({
    required this.title,
    required this.artifacts,
  });

  bool get isNotEmpty => artifacts.isNotEmpty;
}

List<ConfigurationArtifactView> _configurationArtifacts({
  required DeployerConfigData deployerConfig,
  required String l2Provider,
  required String l4Provider,
}) {
  final hierarchyFilename = l4Provider == 'azure'
      ? 'azure_hierarchy.json'
      : 'aws_hierarchy.json';
  final sceneFilename = l4Provider == 'azure'
      ? '3DScenesConfiguration.json'
      : 'scene.json';

  return [
    if (deployerConfig.configEventsJson != null)
      ConfigurationArtifactView(
        title: 'config_events.json',
        filename: 'config_events.json',
        content: deployerConfig.configEventsJson!,
      ),
    if (deployerConfig.configIotDevicesJson != null)
      ConfigurationArtifactView(
        title: 'config_iot_devices.json',
        filename: 'config_iot_devices.json',
        content: deployerConfig.configIotDevicesJson!,
      ),
    if (deployerConfig.payloadsJson != null)
      ConfigurationArtifactView(
        title: 'payloads.json',
        filename: 'payloads.json',
        content: deployerConfig.payloadsJson!,
      ),
    if (deployerConfig.stateMachineContent != null)
      ConfigurationArtifactView(
        title: _stateMachineFilename(l2Provider),
        filename: _stateMachineFilename(l2Provider),
        content: deployerConfig.stateMachineContent!,
      ),
    if (deployerConfig.hierarchyContent != null)
      ConfigurationArtifactView(
        title: hierarchyFilename,
        filename: hierarchyFilename,
        content: deployerConfig.hierarchyContent!,
      ),
    if (deployerConfig.sceneConfigContent != null)
      ConfigurationArtifactView(
        title: sceneFilename,
        filename: sceneFilename,
        content: deployerConfig.sceneConfigContent!,
      ),
    if (deployerConfig.userConfigContent != null)
      ConfigurationArtifactView(
        title: 'config_user.json',
        filename: 'config_user.json',
        content: deployerConfig.userConfigContent!,
      ),
  ];
}

List<FunctionArtifactGroupView> _functionGroups({
  required DeployerConfigData deployerConfig,
  required String l2Provider,
}) {
  final groups = <FunctionArtifactGroupView>[
    FunctionArtifactGroupView(
      title: 'Processors',
      artifacts: _functionArtifacts(
        values: deployerConfig.processorContents,
        l2Provider: l2Provider,
      ),
    ),
    FunctionArtifactGroupView(
      title: 'Event Feedback',
      artifacts: deployerConfig.eventFeedbackContent == null
          ? const []
          : [
              ConfigurationArtifactView(
                title: 'event-feedback/${_functionFilename(l2Provider)}',
                filename: 'event-feedback/${_functionFilename(l2Provider)}',
                content: deployerConfig.eventFeedbackContent!,
              ),
            ],
    ),
    FunctionArtifactGroupView(
      title: 'Event Actions',
      artifacts: _functionArtifacts(
        values: deployerConfig.eventActionContents,
        l2Provider: l2Provider,
      ),
    ),
  ];

  return groups.where((group) => group.isNotEmpty).toList();
}

List<ConfigurationArtifactView> _functionArtifacts({
  required Map<String, String> values,
  required String l2Provider,
}) {
  return values.entries.map((entry) {
    final filename = '${entry.key}/${_functionFilename(l2Provider)}';
    return ConfigurationArtifactView(
      title: filename,
      filename: filename,
      content: entry.value,
    );
  }).toList();
}

String _providerForLayer({
  required String layer,
  required CheapestPath? cheapestPath,
  required List<String> pathSegments,
  required String fallback,
}) {
  final direct = cheapestPath?.providerForLayer(layer);
  if (direct != null) return direct.apiValue;

  final segment = pathSegments.cast<String?>().firstWhere(
    (item) =>
        item?.toLowerCase().startsWith('${layer.toLowerCase()}_') ?? false,
    orElse: () => null,
  );
  final split = segment?.split('_');
  if (split != null && split.length >= 2 && split.last.isNotEmpty) {
    return split.last.toLowerCase();
  }
  return fallback;
}

String? _messagesPerHour(CalcParams? params) {
  final interval = params?.deviceSendingIntervalInMinutes;
  if (interval == null || interval <= 0) return null;
  return (60.0 / interval).toStringAsFixed(1);
}

String? _retention(CalcParams? params) {
  final hot = params?.hotStorageDurationInMonths ?? 0;
  final cool = params?.coolStorageDurationInMonths ?? 0;
  final archive = params?.archiveStorageDurationInMonths ?? 0;
  final totalMonths = hot + cool + archive;
  if (totalMonths <= 0) return null;
  return '$totalMonths months';
}

String _functionFilename(String provider) {
  return switch (provider.toLowerCase()) {
    'gcp' => 'main.py',
    'azure' => 'function_app.py',
    _ => 'lambda_function.py',
  };
}

String _stateMachineFilename(String provider) {
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
