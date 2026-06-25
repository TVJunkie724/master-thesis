import 'dart:convert';

import '../bloc/twin_overview/twin_overview_state.dart';

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
    final deployerConfig = _mapValue(state.deployerConfig);
    final pathSegments = _pathSegments(state.optimizerResult);
    final cheapestPath = _mapValue(state.cheapestPath);
    final l2Provider = _providerForLayer(
      layer: 'l2',
      cheapestPath: cheapestPath,
      pathSegments: pathSegments,
      fallback: 'aws',
    );
    final l4Provider = _providerForLayer(
      layer: 'l4',
      cheapestPath: cheapestPath,
      pathSegments: pathSegments,
      fallback: 'aws',
    );

    return TwinConfigurationView(
      pathSegments: pathSegments,
      optimization: OptimizationSummaryView.fromMaps(
        result: state.optimizerResult,
        params: state.optimizerParams,
        calculatedAt: state.calculatedAt,
      ),
      pricingSnapshots: [
        ProviderPricingSnapshotView.fromMap(
          provider: 'AWS',
          pricing: state.pricingAws,
          updatedAt: state.pricingAwsUpdatedAt,
        ),
        ProviderPricingSnapshotView.fromMap(
          provider: 'Azure',
          pricing: state.pricingAzure,
          updatedAt: state.pricingAzureUpdatedAt,
        ),
        ProviderPricingSnapshotView.fromMap(
          provider: 'GCP',
          pricing: state.pricingGcp,
          updatedAt: state.pricingGcpUpdatedAt,
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

  factory OptimizationSummaryView.fromMaps({
    required Map<String, dynamic>? result,
    required Map<String, dynamic>? params,
    required String? calculatedAt,
  }) {
    return OptimizationSummaryView(
      hasResult: result != null,
      totalCost: _doubleValue(result?['totalCost']) ?? 0,
      numberOfDevices: params?['numberOfDevices']?.toString(),
      messagesPerHour: _messagesPerHour(params),
      retention: _retention(params),
      calculatedAt: calculatedAt,
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

  factory ProviderPricingSnapshotView.fromMap({
    required String provider,
    required Map<String, dynamic>? pricing,
    required String? updatedAt,
  }) {
    return ProviderPricingSnapshotView(
      provider: provider,
      updatedAt: updatedAt,
      artifactContent: pricing == null ? null : _prettyPrintJson(pricing),
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
  required Map<String, dynamic> deployerConfig,
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
    if (_stringValue(deployerConfig['config_events_json']) != null)
      ConfigurationArtifactView(
        title: 'config_events.json',
        filename: 'config_events.json',
        content: _stringValue(deployerConfig['config_events_json'])!,
      ),
    if (_stringValue(deployerConfig['config_iot_devices_json']) != null)
      ConfigurationArtifactView(
        title: 'config_iot_devices.json',
        filename: 'config_iot_devices.json',
        content: _stringValue(deployerConfig['config_iot_devices_json'])!,
      ),
    if (_stringValue(deployerConfig['payloads_json']) != null)
      ConfigurationArtifactView(
        title: 'payloads.json',
        filename: 'payloads.json',
        content: _stringValue(deployerConfig['payloads_json'])!,
      ),
    if (_stringValue(deployerConfig['state_machine_content']) != null)
      ConfigurationArtifactView(
        title: _stateMachineFilename(l2Provider),
        filename: _stateMachineFilename(l2Provider),
        content: _stringValue(deployerConfig['state_machine_content'])!,
      ),
    if (_stringValue(deployerConfig['hierarchy_content']) != null)
      ConfigurationArtifactView(
        title: hierarchyFilename,
        filename: hierarchyFilename,
        content: _stringValue(deployerConfig['hierarchy_content'])!,
      ),
    if (_stringValue(deployerConfig['scene_config_content']) != null)
      ConfigurationArtifactView(
        title: sceneFilename,
        filename: sceneFilename,
        content: _stringValue(deployerConfig['scene_config_content'])!,
      ),
    if (_stringValue(deployerConfig['user_config_content']) != null)
      ConfigurationArtifactView(
        title: 'config_user.json',
        filename: 'config_user.json',
        content: _stringValue(deployerConfig['user_config_content'])!,
      ),
  ];
}

List<FunctionArtifactGroupView> _functionGroups({
  required Map<String, dynamic> deployerConfig,
  required String l2Provider,
}) {
  final groups = <FunctionArtifactGroupView>[
    FunctionArtifactGroupView(
      title: 'Processors',
      artifacts: _functionArtifacts(
        values: _stringMap(deployerConfig['processor_contents']),
        l2Provider: l2Provider,
      ),
    ),
    FunctionArtifactGroupView(
      title: 'Event Feedback',
      artifacts: _stringValue(deployerConfig['event_feedback_content']) == null
          ? const []
          : [
              ConfigurationArtifactView(
                title: 'event-feedback/${_functionFilename(l2Provider)}',
                filename: 'event-feedback/${_functionFilename(l2Provider)}',
                content: _stringValue(
                  deployerConfig['event_feedback_content'],
                )!,
              ),
            ],
    ),
    FunctionArtifactGroupView(
      title: 'Event Actions',
      artifacts: _functionArtifacts(
        values: _stringMap(deployerConfig['event_action_contents']),
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

List<String> _pathSegments(Map<String, dynamic>? optimizerResult) {
  final rawPath = optimizerResult?['cheapestPath'];
  if (rawPath is! List) return const [];
  return rawPath.map((item) => item.toString()).toList();
}

String _providerForLayer({
  required String layer,
  required Map<String, dynamic> cheapestPath,
  required List<String> pathSegments,
  required String fallback,
}) {
  final direct = cheapestPath[layer]?.toString().toLowerCase();
  if (direct != null && direct.isNotEmpty) return direct;

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

String? _messagesPerHour(Map<String, dynamic>? params) {
  final interval = _doubleValue(params?['deviceSendingIntervalInMinutes']);
  if (interval == null || interval <= 0) return null;
  return (60.0 / interval).toStringAsFixed(1);
}

String? _retention(Map<String, dynamic>? params) {
  final hot = _doubleValue(params?['hotStorageDurationInMonths']) ?? 0;
  final cool = _doubleValue(params?['coolStorageDurationInMonths']) ?? 0;
  final archive = _doubleValue(params?['archiveStorageDurationInMonths']) ?? 0;
  final totalMonths = hot + cool + archive;
  if (totalMonths <= 0) return null;
  return '${totalMonths.toStringAsFixed(0)} months';
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

Map<String, dynamic> _mapValue(dynamic value) {
  if (value is! Map) return const {};
  return Map<String, dynamic>.from(value);
}

Map<String, String> _stringMap(dynamic value) {
  if (value is! Map) return const {};
  return Map<String, dynamic>.from(
    value,
  ).map((key, item) => MapEntry(key, item?.toString() ?? ''));
}

String? _stringValue(dynamic value) {
  if (value is! String || value.isEmpty) return null;
  return value;
}

double? _doubleValue(dynamic value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}
