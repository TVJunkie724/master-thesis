import 'dart:convert';

import 'package:flutter/services.dart';

import '../config/app_runtime.dart';

typedef DemoClock = DateTime Function();

class DemoApiException implements Exception {
  final String code;
  final String message;

  const DemoApiException(this.code, this.message);

  @override
  String toString() => message;
}

class DemoFixtureStore {
  static const supportedSchemaVersion = 1;
  static const _requiredMapKeys = {
    'twin_configs',
    'optimizer_configs',
    'deployer_configs',
    'cloud_access',
    'pricing_health',
    'pricing_reports',
    'pricing_traces',
    'deployment_outputs',
    'deployment_logs',
    'verification',
  };
  static const _providers = {'aws', 'azure', 'gcp'};
  static const _purposes = {'pricing', 'deployment'};
  static const _twinStates = {
    'draft',
    'configured',
    'deploying',
    'deployed',
    'destroying',
    'destroyed',
    'error',
    'inactive',
  };

  final Map<String, dynamic> _root;
  final DemoClock clock;
  int _sequence;

  DemoFixtureStore._(this._root, this.clock, this._sequence);

  factory DemoFixtureStore.fromJson(
    Map<String, dynamic> fixture, {
    DemoClock? clock,
  }) {
    final copy = _copyMap(fixture);
    _validate(copy);
    return DemoFixtureStore._(
      copy,
      clock ?? () => DateTime.now().toUtc(),
      _initialSequence(copy),
    );
  }

  static Future<DemoFixtureStore> load(
    DemoScenario scenario, {
    AssetBundle? bundle,
    DemoClock? clock,
  }) async {
    final source = bundle ?? rootBundle;
    final path = 'assets/demo/v1/${scenario.name}.json';
    final raw = await source.loadString(path);
    final decoded = jsonDecode(raw);
    if (decoded is! Map) {
      throw const DemoApiException(
        'DEMO_FIXTURE_ROOT_INVALID',
        'Demo fixture root must be a JSON object.',
      );
    }
    final fixture = Map<String, dynamic>.from(decoded);
    if (fixture['scenario'] != scenario.name) {
      throw DemoApiException(
        'DEMO_FIXTURE_SCENARIO_MISMATCH',
        'Demo fixture "$path" declares scenario '
            '"${fixture['scenario']}" instead of "${scenario.name}".',
      );
    }
    return DemoFixtureStore.fromJson(fixture, clock: clock);
  }

  String get scenario => _root['scenario'] as String;

  Map<String, dynamic> get user => _copyMap(_map('user'));

  List<Map<String, dynamic>> get twins => _copyMapList(_list('twins'));

  List<Map<String, dynamic>> get cloudConnections =>
      _copyMapList(_list('cloud_connections'));

  Map<String, dynamic> get cloudAccess => _copyMap(_map('cloud_access'));

  Map<String, dynamic> get pricingHealth => _copyMap(_map('pricing_health'));

  Map<String, dynamic> twin(String twinId) {
    return _copyMap(_findById(_list('twins'), twinId, 'DEMO_TWIN_NOT_FOUND'));
  }

  Map<String, dynamic>? twinConfig(String twinId) {
    return _copyNullableMap(_map('twin_configs')[twinId]);
  }

  Map<String, dynamic>? optimizerConfig(String twinId) {
    return _copyNullableMap(_map('optimizer_configs')[twinId]);
  }

  Map<String, dynamic>? deployerConfig(String twinId) {
    return _copyNullableMap(_map('deployer_configs')[twinId]);
  }

  Map<String, dynamic>? deploymentOutput(String twinId) {
    return _copyNullableMap(_map('deployment_outputs')[twinId]);
  }

  List<Map<String, dynamic>> deploymentLogs(String twinId) {
    final value = _map('deployment_logs')[twinId];
    return value is List ? _copyMapList(value) : const [];
  }

  Map<String, dynamic>? verification(String twinId) {
    return _copyNullableMap(_map('verification')[twinId]);
  }

  void setVerification(String twinId, Map<String, dynamic> value) {
    twin(twinId);
    _map('verification')[twinId] = _copyMap(value);
  }

  List<Map<String, dynamic>> pricingReports(String provider) {
    final value = _map('pricing_reports')[provider.toLowerCase()];
    return value is List ? _copyMapList(value) : const [];
  }

  Map<String, dynamic>? pricingTrace(String reportId) {
    return _copyNullableMap(_map('pricing_traces')[reportId]);
  }

  String nextId(String prefix) {
    _sequence += 1;
    return '$prefix-${_sequence.toString().padLeft(4, '0')}';
  }

  void updateUser(Map<String, dynamic> values) {
    _map('user').addAll(_copyMap(values));
  }

  void addTwin(Map<String, dynamic> twin) {
    final id = twin['id']?.toString();
    if (id == null || id.isEmpty) {
      throw const DemoApiException(
        'DEMO_TWIN_ID_REQUIRED',
        'Twin ID is required.',
      );
    }
    if (_list('twins').any((item) => item is Map && item['id'] == id)) {
      throw DemoApiException(
        'DEMO_TWIN_ID_CONFLICT',
        'A twin with ID "$id" already exists.',
      );
    }
    _list('twins').add(_copyMap(twin));
  }

  void updateTwin(String twinId, Map<String, dynamic> values) {
    _findById(_list('twins'), twinId, 'DEMO_TWIN_NOT_FOUND')
      ..addAll(_copyMap(values))
      ..['updated_at'] = clock().toIso8601String();
  }

  void removeTwin(String twinId) {
    final twins = _list('twins');
    final index = twins.indexWhere(
      (item) => item is Map && item['id']?.toString() == twinId,
    );
    if (index < 0) {
      throw DemoApiException(
        'DEMO_TWIN_NOT_FOUND',
        'Twin "$twinId" does not exist.',
      );
    }
    twins.removeAt(index);
    for (final key in [
      'twin_configs',
      'optimizer_configs',
      'deployer_configs',
      'deployment_outputs',
      'deployment_logs',
      'verification',
    ]) {
      _map(key).remove(twinId);
    }
  }

  void setTwinConfig(String twinId, Map<String, dynamic> value) {
    twin(twinId);
    _map('twin_configs')[twinId] = _copyMap(value);
  }

  void setOptimizerConfig(String twinId, Map<String, dynamic> value) {
    twin(twinId);
    _map('optimizer_configs')[twinId] = _copyMap(value);
  }

  void setDeployerConfig(String twinId, Map<String, dynamic> value) {
    twin(twinId);
    _map('deployer_configs')[twinId] = _copyMap(value);
  }

  void setDeploymentOutput(String twinId, Map<String, dynamic>? value) {
    twin(twinId);
    if (value == null) {
      _map('deployment_outputs').remove(twinId);
    } else {
      _map('deployment_outputs')[twinId] = _copyMap(value);
    }
  }

  void addDeploymentLog(String twinId, Map<String, dynamic> value) {
    twin(twinId);
    final logs = _map('deployment_logs').putIfAbsent(twinId, () => <dynamic>[]);
    if (logs is! List) {
      throw DemoApiException(
        'DEMO_FIXTURE_COLLECTION_INVALID',
        'Deployment logs for "$twinId" must be a list.',
      );
    }
    logs.add(_copyMap(value));
  }

  void addCloudConnection(Map<String, dynamic> connection) {
    final id = connection['id']?.toString() ?? '';
    if (_list(
      'cloud_connections',
    ).any((item) => item is Map && item['id']?.toString() == id)) {
      throw DemoApiException(
        'DEMO_CONNECTION_ID_CONFLICT',
        'A cloud connection with ID "$id" already exists.',
      );
    }
    _list('cloud_connections').add(_copyMap(connection));
  }

  void updateCloudConnection(String id, Map<String, dynamic> values) {
    _findById(_list('cloud_connections'), id, 'DEMO_CONNECTION_NOT_FOUND')
      ..addAll(_copyMap(values))
      ..['updated_at'] = clock().toIso8601String();
  }

  void removeCloudConnection(String id) {
    for (final entry in _map('twin_configs').entries) {
      final config = entry.value;
      if (config is Map && config.values.contains(id)) {
        throw DemoApiException(
          'DEMO_CONNECTION_IN_USE',
          'Cloud connection "$id" is still bound to a twin.',
        );
      }
    }
    final connections = _list('cloud_connections');
    final index = connections.indexWhere(
      (item) => item is Map && item['id']?.toString() == id,
    );
    if (index < 0) {
      throw DemoApiException(
        'DEMO_CONNECTION_NOT_FOUND',
        'Cloud connection "$id" does not exist.',
      );
    }
    connections.removeAt(index);
  }

  Map<String, dynamic> cloudConnection(String id) {
    return _copyMap(
      _findById(_list('cloud_connections'), id, 'DEMO_CONNECTION_NOT_FOUND'),
    );
  }

  List<Map<String, dynamic>> twinsBoundToConnection(String connectionId) {
    final boundIds = <String>{};
    for (final entry in _map('twin_configs').entries) {
      final config = entry.value;
      if (config is Map && config.values.contains(connectionId)) {
        boundIds.add(entry.key);
      }
    }
    return twins
        .where((twin) => boundIds.contains(twin['id']))
        .toList(growable: false);
  }

  void updatePricingHealth(String provider, Map<String, dynamic> values) {
    final providers = _map('pricing_health')['providers'];
    if (providers is! Map || providers[provider] is! Map) {
      throw DemoApiException(
        'DEMO_PRICING_PROVIDER_NOT_FOUND',
        'Pricing provider "$provider" does not exist.',
      );
    }
    (providers[provider] as Map).addAll(_copyMap(values));
  }

  static void _validate(Map<String, dynamic> root) {
    if (root['schema_version'] != supportedSchemaVersion) {
      throw DemoApiException(
        'DEMO_FIXTURE_VERSION_UNSUPPORTED',
        'Unsupported demo fixture schema version '
            '"${root['schema_version']}". Expected $supportedSchemaVersion.',
      );
    }
    if (root['scenario'] is! String ||
        !DemoScenario.values.any((item) => item.name == root['scenario'])) {
      throw const DemoApiException(
        'DEMO_FIXTURE_SCENARIO_INVALID',
        'Demo fixture scenario is missing or unsupported.',
      );
    }
    if (root['user'] is! Map) {
      throw const DemoApiException(
        'DEMO_FIXTURE_USER_INVALID',
        'Demo fixture user must be an object.',
      );
    }
    for (final key in _requiredMapKeys) {
      if (root[key] is! Map) {
        throw DemoApiException(
          'DEMO_FIXTURE_COLLECTION_INVALID',
          'Demo fixture collection "$key" must be an object.',
        );
      }
    }
    for (final key in ['twins', 'cloud_connections']) {
      if (root[key] is! List) {
        throw DemoApiException(
          'DEMO_FIXTURE_COLLECTION_INVALID',
          'Demo fixture collection "$key" must be a list.',
        );
      }
    }

    final twinIds = _validateEntities(
      root['twins'] as List,
      'twin',
      stateValidator: (item) => _twinStates.contains(item['state']),
    );
    final connectionIds = _validateEntities(
      root['cloud_connections'] as List,
      'cloud connection',
      stateValidator: (item) =>
          _providers.contains(item['provider']) &&
          _purposes.contains(item['purpose']),
    );

    for (final key in [
      'twin_configs',
      'optimizer_configs',
      'deployer_configs',
      'deployment_outputs',
      'deployment_logs',
      'verification',
    ]) {
      final collection = root[key] as Map;
      for (final id in collection.keys) {
        if (!twinIds.contains(id.toString())) {
          throw DemoApiException(
            'DEMO_FIXTURE_DANGLING_TWIN_REFERENCE',
            'Collection "$key" references unknown twin "$id".',
          );
        }
      }
    }

    final twinConfigs = root['twin_configs'] as Map;
    for (final config in twinConfigs.values.whereType<Map>()) {
      for (final key in [
        'aws_cloud_connection_id',
        'azure_cloud_connection_id',
        'gcp_cloud_connection_id',
      ]) {
        final id = config[key]?.toString();
        if (id != null && !connectionIds.contains(id)) {
          throw DemoApiException(
            'DEMO_FIXTURE_DANGLING_CONNECTION_REFERENCE',
            'Twin configuration references unknown connection "$id".',
          );
        }
      }
    }

    final reportIds = <String>{};
    final reportCollections = root['pricing_reports'] as Map;
    for (final entry in reportCollections.entries) {
      if (!_providers.contains(entry.key)) {
        throw DemoApiException(
          'DEMO_FIXTURE_PROVIDER_INVALID',
          'Pricing reports contain unknown provider "${entry.key}".',
        );
      }
      if (entry.value is! List) {
        throw const DemoApiException(
          'DEMO_FIXTURE_COLLECTION_INVALID',
          'Pricing reports must be provider-keyed lists.',
        );
      }
      for (final report in (entry.value as List).whereType<Map>()) {
        final id = report['report_id']?.toString() ?? '';
        if (id.isEmpty || !reportIds.add(id)) {
          throw DemoApiException(
            'DEMO_FIXTURE_REPORT_ID_INVALID',
            'Pricing report ID "$id" is empty or duplicated.',
          );
        }
        final candidateIds = <String>{};
        for (final candidate in (report['candidates'] as List? ?? const [])) {
          if (candidate is! Map) continue;
          final candidateId = candidate['candidate_id']?.toString() ?? '';
          if (candidateId.isEmpty || !candidateIds.add(candidateId)) {
            throw DemoApiException(
              'DEMO_FIXTURE_CANDIDATE_ID_INVALID',
              'Pricing candidate ID "$candidateId" is empty or duplicated.',
            );
          }
        }
      }
    }
    for (final id in (root['pricing_traces'] as Map).keys) {
      if (!reportIds.contains(id.toString())) {
        throw DemoApiException(
          'DEMO_FIXTURE_DANGLING_REPORT_REFERENCE',
          'Pricing trace references unknown report "$id".',
        );
      }
    }
  }

  static Set<String> _validateEntities(
    List<dynamic> values,
    String label, {
    required bool Function(Map<dynamic, dynamic>) stateValidator,
  }) {
    final ids = <String>{};
    for (final value in values) {
      if (value is! Map) {
        throw DemoApiException(
          'DEMO_FIXTURE_ENTITY_INVALID',
          'Every $label must be an object.',
        );
      }
      final id = value['id']?.toString() ?? '';
      if (id.isEmpty || !ids.add(id)) {
        throw DemoApiException(
          'DEMO_FIXTURE_ENTITY_ID_INVALID',
          '$label ID "$id" is empty or duplicated.',
        );
      }
      if (!stateValidator(value)) {
        throw DemoApiException(
          'DEMO_FIXTURE_ENTITY_VALUE_INVALID',
          '$label "$id" contains an unsupported state, provider, or purpose.',
        );
      }
    }
    return ids;
  }

  Map<String, dynamic> _map(String key) {
    final value = _root[key];
    if (value is Map<String, dynamic>) return value;
    if (value is Map) {
      final converted = Map<String, dynamic>.from(value);
      _root[key] = converted;
      return converted;
    }
    throw DemoApiException(
      'DEMO_FIXTURE_COLLECTION_INVALID',
      'Demo fixture collection "$key" is not an object.',
    );
  }

  List<dynamic> _list(String key) {
    final value = _root[key];
    if (value is List) return value;
    throw DemoApiException(
      'DEMO_FIXTURE_COLLECTION_INVALID',
      'Demo fixture collection "$key" is not a list.',
    );
  }

  static Map<String, dynamic> _findById(
    List<dynamic> values,
    String id,
    String errorCode,
  ) {
    for (final value in values) {
      if (value is Map && value['id']?.toString() == id) {
        return value is Map<String, dynamic>
            ? value
            : Map<String, dynamic>.from(value);
      }
    }
    throw DemoApiException(errorCode, 'Resource "$id" does not exist.');
  }

  static int _initialSequence(Map<String, dynamic> root) {
    return (root['twins'] as List).length +
        (root['cloud_connections'] as List).length;
  }

  static Map<String, dynamic> _copyMap(Map<dynamic, dynamic> value) {
    return Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
  }

  static Map<String, dynamic>? _copyNullableMap(dynamic value) {
    return value is Map ? _copyMap(value) : null;
  }

  static List<Map<String, dynamic>> _copyMapList(List<dynamic> value) {
    return value
        .whereType<Map>()
        .map((item) => _copyMap(item))
        .toList(growable: false);
  }
}
