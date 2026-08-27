import 'dart:convert';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:crypto/crypto.dart';

import '../core/result.dart';
import '../models/architecture_profile.dart';
import '../models/calc_params.dart';
import '../models/cloud_connection.dart';
import '../models/deployment_access.dart';
import '../models/deployment_operations.dart';
import '../models/deployment_readiness.dart';
import '../models/deployment_verification.dart';
import '../models/deployer_config.dart';
import '../models/optimizer_config.dart';
import '../models/pricing_catalog.dart';
import '../models/provider_capability.dart';
import '../models/resolved_deployment_specification.dart';
import '../models/resolved_twin_architecture.dart';
import '../models/twin.dart';
import '../models/twin_config.dart';
import '../models/twin_transfer.dart';
import '../models/user_function_extension.dart';
import '../models/user.dart';
import '../models/wizard_config_requests.dart';
import '../services/management_api.dart';
import 'demo_fixture_store.dart';

class DemoManagementApi implements ManagementApi {
  static const double _sixLayerEurPerUsd = 0.865948;
  final DemoFixtureStore store;
  final Duration latency;
  static const _token = 'demo-token';
  final Map<String, Map<String, dynamic>> _deploymentReadinessCache = {};
  final List<UserFunctionArtifact> _extensionArtifacts = [];
  final Map<String, TwinExtensionBinding> _extensionBindings = {};
  final Map<String, ResolvedTwinArchitectureRead> _resolvedArchitectures = {};
  final Map<String, List<TelemetryVerificationRecord>> _telemetryVerifications =
      {};

  DemoManagementApi({
    required this.store,
    this.latency = const Duration(milliseconds: 120),
  });

  @override
  void setUnauthorizedHandler(void Function()? handler) {}

  @override
  Future<String?> getAuthToken() async => _token;

  @override
  @override
  Future<User> getCurrentUser() async => User.fromJson(store.user);

  @override
  Future<Map<String, dynamic>> updateUserPreferences({
    String? themePreference,
  }) async {
    await _pause();
    if (themePreference != null &&
        !{'light', 'dark'}.contains(themePreference)) {
      throw const DemoApiException(
        'DEMO_THEME_INVALID',
        'Theme preference must be light or dark.',
      );
    }
    store.updateUser({
      if (themePreference != null) 'theme_preference': themePreference,
    });
    return store.user;
  }

  @override
  Future<ArchitectureProfileDetail> getCanonicalArchitectureContract() async {
    await _pause();
    store.architectureProfile('six-layer-eventing', '1');
    return ArchitectureProfileDetail.fromJson(
      _architectureProfileDetailJson('six-layer-eventing', '1'),
    );
  }

  @override
  Future<TwinArchitectureSelection> getTwinArchitectureContract(
    String twinId,
  ) async {
    await _pause();
    final twin = store.twin(twinId);
    final selectedAt = DateTime.parse(twin['created_at'].toString()).toUtc();
    final updatedAt = DateTime.parse(twin['updated_at'].toString()).toUtc();
    final profile = store.sixLayerProfile();
    return TwinArchitectureSelection(
      twinId: twinId,
      profileRef: PinnedArchitectureReference(
        id: profile['profile_id'].toString(),
        version: profile['profile_version'].toString(),
        digest: profile['content_digest'].toString(),
      ),
      revision: 1,
      selectedAt: selectedAt,
      updatedAt: updatedAt,
      selectedByUserId: store.user['id'].toString(),
    );
  }

  @override
  Future<ResolvedTwinArchitectureRead> getSelectedResolvedArchitecture(
    String twinId,
  ) async {
    await _pause();
    store.twin(twinId);
    throw const DemoApiException(
      'ARCH_RESOLUTION_NOT_SELECTED',
      'No resolved architecture is selected for this Twin.',
    );
  }

  @override
  Future<ResolvedTwinArchitectureRead> getRunResolvedArchitecture(
    String runId,
  ) async {
    await _pause();
    final architecture = _resolvedArchitectures[runId];
    if (architecture != null) return architecture;
    throw const DemoApiException(
      'ARCH_LEGACY_NOT_RESOLVABLE',
      'The historical demo run has no native resolved architecture.',
    );
  }

  @override
  Future<List<ExtensionSlot>> listExtensionSlots() async {
    await _pause();
    return const [
      ExtensionSlot(
        slotId: 'processor.telemetry',
        slotVersion: '1',
        displayName: 'Telemetry processor',
        runtimeId: 'python311',
        configurationFields: [
          ExtensionConfigurationField(
            name: 'scale_factor',
            type: 'number',
            title: 'Scale factor',
            required: true,
            minimum: 0,
            maximum: 1000,
          ),
        ],
        resourceLimits: {
          'timeout_seconds': 30,
          'memory_mb': 256,
          'artifact_bytes': 10485760,
          'source_bytes': 2097152,
          'response_bytes': 1048576,
          'file_count': 64,
          'dependency_count': 64,
        },
        permissionCapabilities: ['capability.telemetry.process'],
      ),
    ];
  }

  @override
  Future<UserFunctionValidationResult> validateUserFunctionArtifact(
    UserFunctionArtifactUpload upload,
  ) async {
    await _pause();
    _validateExtensionUpload(upload);
    return _extensionValidation(upload);
  }

  @override
  Future<UserFunctionArtifact> createUserFunctionArtifact(
    UserFunctionArtifactUpload upload,
  ) async {
    await _pause();
    _validateExtensionUpload(upload);
    final validation = _extensionValidation(upload);
    final existing = _extensionArtifacts
        .where((item) => item.artifactDigest == validation.artifactDigest)
        .firstOrNull;
    if (existing != null) return existing;
    final sequence = _extensionArtifacts.length + 1;
    final artifact = UserFunctionArtifact(
      schemaVersion: 'user-function-artifact.v1',
      artifactId:
          '00000000-0000-4000-8000-${sequence.toString().padLeft(12, '0')}',
      artifactState: 'valid',
      artifactDigest: validation.artifactDigest,
      slotId: upload.slot.slotId,
      slotVersion: upload.slot.slotVersion,
      runtimeId: upload.slot.runtimeId,
      configuration: upload.draft.configuration,
      declaredCapabilities: upload.slot.permissionCapabilities,
      validatorVersion: 'user-function-validator.v1',
      sourceFiles: validation.sourceFiles,
      dependencyCount: validation.dependencies.length,
      createdAt: store.clock().toUtc(),
    );
    _extensionArtifacts.add(artifact);
    return artifact;
  }

  @override
  Future<List<UserFunctionArtifact>> listUserFunctionArtifacts() async {
    await _pause();
    return List.unmodifiable(_extensionArtifacts);
  }

  @override
  Future<List<TwinExtensionBinding>> listTwinExtensionBindings(
    String twinId,
  ) async {
    await _pause();
    store.twin(twinId);
    return List.unmodifiable(
      _extensionBindings.values.where(
        (binding) => binding.twinId == twinId && binding.active,
      ),
    );
  }

  @override
  Future<TwinExtensionBinding> bindTwinExtensionArtifact(
    String twinId,
    ExtensionSlot slot,
    String artifactId, {
    int? expectedRevision,
  }) async {
    await _pause();
    store.twin(twinId);
    final artifact = _extensionArtifacts
        .where(
          (item) =>
              item.artifactId == artifactId &&
              item.slotId == slot.slotId &&
              item.slotVersion == slot.slotVersion &&
              item.isValid,
        )
        .firstOrNull;
    if (artifact == null) {
      throw const DemoApiException(
        'EXTENSION_BINDING_UNRESOLVED',
        'The validated artifact is unavailable for this slot.',
      );
    }
    final key = '$twinId:${slot.slotId}:${slot.slotVersion}';
    final current = _extensionBindings[key];
    if (expectedRevision != null && current?.revision != expectedRevision) {
      throw const DemoApiException(
        'EXTENSION_BINDING_UNRESOLVED',
        'The extension binding revision is stale.',
      );
    }
    final revision = (current?.revision ?? 0) + 1;
    final binding = TwinExtensionBinding(
      bindingId:
          '10000000-0000-4000-8000-${revision.toString().padLeft(12, '0')}',
      twinId: twinId,
      slotId: slot.slotId,
      slotVersion: slot.slotVersion,
      artifactId: artifact.artifactId,
      artifactDigest: artifact.artifactDigest,
      bindingDigest:
          'sha256:${sha256.convert(utf8.encode('$key:${artifact.artifactDigest}'))}',
      active: true,
      revision: revision,
      createdAt: store.clock().toUtc(),
      unboundAt: null,
    );
    _extensionBindings[key] = binding;
    return binding;
  }

  @override
  Future<void> unbindTwinExtensionArtifact(
    String twinId,
    ExtensionSlot slot, {
    int? expectedRevision,
  }) async {
    await _pause();
    final key = '$twinId:${slot.slotId}:${slot.slotVersion}';
    final current = _extensionBindings[key];
    if (current == null ||
        (expectedRevision != null && current.revision != expectedRevision)) {
      throw const DemoApiException(
        'EXTENSION_BINDING_UNRESOLVED',
        'The extension binding revision is stale.',
      );
    }
    _extensionBindings.remove(key);
  }

  UserFunctionValidationResult _extensionValidation(
    UserFunctionArtifactUpload upload,
  ) {
    final digest = sha256.convert([
      ...upload.metadataBytes,
      ...upload.draft.bytes,
    ]);
    return UserFunctionValidationResult(
      artifactDigest: 'sha256:$digest',
      slotId: upload.slot.slotId,
      slotVersion: upload.slot.slotVersion,
      runtimeId: upload.slot.runtimeId,
      sourceFiles: const ['process.py', 'requirements.lock'],
      dependencies: const [],
      checks: const [
        'archive_safe',
        'schema_valid',
        'entrypoint_valid',
        'dependencies_valid',
        'secret_scan_passed',
        'configuration_valid',
        'runtime_compatible',
        'capabilities_authorized',
        'package_deterministic',
        'binding_compatible',
      ],
    );
  }

  void _validateExtensionUpload(UserFunctionArtifactUpload upload) {
    if (!upload.draft.filename.toLowerCase().endsWith('.zip') ||
        upload.draft.bytes.isEmpty ||
        upload.draft.bytes.length > 10 * 1024 * 1024) {
      throw const DemoApiException(
        'EXTENSION_ARCHIVE_UNSAFE',
        'Choose a non-empty source ZIP within the v1 size limit.',
      );
    }
    final fields = upload.slot.configurationFields;
    final allowed = fields.map((field) => field.name).toSet();
    final configuration = upload.draft.configuration;
    if (configuration.keys.toSet().difference(allowed).isNotEmpty ||
        fields.any(
          (field) => field.required && !configuration.containsKey(field.name),
        )) {
      throw const DemoApiException(
        'EXTENSION_CONFIG_INVALID',
        'Complete only the approved non-secret configuration fields.',
      );
    }
    final serialized = jsonEncode(configuration).toLowerCase();
    if (RegExp(
      r'(secret|password|token|credential|private_key|api_key)',
    ).hasMatch(serialized)) {
      throw const DemoApiException(
        'EXTENSION_SECRET_MATERIAL_DETECTED',
        'Secret material is forbidden in user-function v1.',
      );
    }
  }

  @override
  Future<List<CloudConnection>> listCloudConnections({
    CloudProvider? provider,
  }) async {
    await _pause();
    return store.cloudConnections
        .where(
          (item) => provider == null || item['provider'] == provider.apiValue,
        )
        .map(CloudConnection.fromJson)
        .toList(growable: false);
  }

  @override
  @override
  Future<CloudConnection> createCloudConnection(
    CloudConnectionCreateRequest request,
  ) async {
    await _pause();
    if (request.displayName.trim().isEmpty) {
      throw const DemoApiException(
        'DEMO_CONNECTION_NAME_REQUIRED',
        'Cloud connection display name is required.',
      );
    }
    if (request.credentials.isEmpty ||
        (request.provider == CloudProvider.gcp &&
            (request.credentials['service_account_json']
                    ?.toString()
                    .trim()
                    .isEmpty ??
                true))) {
      throw const DemoApiException(
        'DEMO_CONNECTION_CREDENTIALS_REQUIRED',
        'Provider credentials are required.',
      );
    }
    final now = store.clock().toIso8601String();
    final id = store.nextId('demo-${request.provider.apiValue}-connection');
    final payloadSummary = _payloadSummary(request);
    final value = <String, dynamic>{
      'id': id,
      'provider': request.provider.apiValue,
      'purpose': 'deployment',
      'scope': 'user',
      'display_name': request.displayName.trim(),
      'auth_type': request.authType ?? _defaultAuthType(request.provider),
      'cloud_scope': request.cloudScope,
      'payload_fingerprint': '$id-fingerprint',
      'payload_summary': payloadSummary,
      'validation_status': 'untested',
      'validation_message': null,
      'last_validated_at': null,
      'last_used_at': null,
      'created_at': now,
      'updated_at': now,
    };
    store.addCloudConnection(value);
    return CloudConnection.fromJson(value);
  }

  @override
  Future<CloudConnection> importCloudConnection(
    CloudConnectionImportRequest request,
  ) async {
    await _pause();
    final now = store.clock().toIso8601String();
    final id = store.nextId('demo-${request.provider.apiValue}-connection');
    final cloudScope = switch (request.provider) {
      CloudProvider.aws => {
        if (request.accountId != null) 'account_id': request.accountId,
      },
      CloudProvider.azure => {'subscription_id': request.targetScopeId},
      CloudProvider.gcp => {'project_id': request.targetScopeId},
    };
    final payloadSummary = switch (request.provider) {
      CloudProvider.aws => {
        'region': request.region,
        'credential_source': 'aws_csv',
      },
      CloudProvider.azure => {
        'region': request.region,
        'credential_source': 'azure_service_principal_json',
      },
      CloudProvider.gcp => {
        'region': request.region,
        'credential_source': 'gcp_service_account_json',
      },
    };
    final value = <String, dynamic>{
      'id': id,
      'provider': request.provider.apiValue,
      'purpose': 'deployment',
      'scope': 'user',
      'display_name': request.displayName,
      'auth_type': _defaultAuthType(request.provider),
      'cloud_scope': cloudScope,
      'payload_fingerprint': '$id-import-fingerprint',
      'payload_summary': payloadSummary,
      'validation_status': 'untested',
      'validation_message': null,
      'last_validated_at': null,
      'last_used_at': null,
      'created_at': now,
      'updated_at': now,
    };
    store.addCloudConnection(value);
    return CloudConnection.fromJson(value);
  }

  @override
  Future<void> deleteCloudConnection(String id) async {
    await _pause();
    store.removeCloudConnection(id);
  }

  @override
  Future<CloudConnectionValidationResult> validateCloudConnection(
    String id,
  ) async {
    await _pause();
    final connection = store.cloudConnection(id);
    final now = store.clock().toIso8601String();
    store.updateCloudConnection(id, {
      'validation_status': 'valid',
      'validation_message': 'Demo permission checks completed successfully.',
      'last_validated_at': now,
    });
    return CloudConnectionValidationResult.fromJson({
      'id': id,
      'provider': connection['provider'],
      'valid': true,
      'validation_status': 'valid',
      'message': 'Demo permission checks completed successfully.',
      'optimizer': {
        'valid': true,
        'message': 'Frozen pricing evidence is available to the optimizer.',
      },
      'deployer': {'valid': true, 'message': 'Deployment access is ready.'},
    });
  }

  @override
  Future<List<Twin>> getTwins() async {
    await _pause();
    return store.twins.map(Twin.fromJson).toList(growable: false);
  }

  @override
  Future<PlatformProviderCapabilities> getProviderCapabilities() async {
    await _pause();
    return PlatformProviderCapabilities.fromJson(_demoProviderCapabilities());
  }

  @override
  Future<Twin> getTwin(String twinId) async {
    await _pause();
    return Twin.fromJson(store.twin(twinId));
  }

  @override
  Future<Twin> createTwin(String name) async {
    await _pause();
    final trimmed = name.trim();
    if (trimmed.isEmpty) {
      throw const DemoApiException(
        'DEMO_TWIN_NAME_REQUIRED',
        'Twin name is required.',
      );
    }
    if (store.twins.any(
      (item) => item['name']?.toString().toLowerCase() == trimmed.toLowerCase(),
    )) {
      throw DemoApiException(
        'DEMO_TWIN_NAME_CONFLICT',
        'A twin named "$trimmed" already exists.',
      );
    }
    final id = store.nextId('demo-twin');
    final now = store.clock().toIso8601String();
    final twin = <String, dynamic>{
      'id': id,
      'name': trimmed,
      'state': 'draft',
      'providers': <String>[],
      'created_at': now,
      'updated_at': now,
      'last_deployed_at': null,
    };
    store.addTwin(twin);
    store.setTwinConfig(id, {
      'highest_step_reached': 0,
      'debug_mode': true,
      'aws_cloud_connection_id': null,
      'azure_cloud_connection_id': null,
      'gcp_cloud_connection_id': null,
    });
    return Twin.fromJson(twin);
  }

  @override
  Future<Twin> duplicateTwin(
    String twinId,
    TwinDuplicateRequest request,
  ) async {
    await _pause();
    store.twin(twinId);
    final created = await createTwin(request.name);
    final sourceConfig = store.twinConfig(twinId);
    if (sourceConfig != null) {
      store.setTwinConfig(created.id, {
        ...sourceConfig,
        'highest_step_reached': 0,
        'aws_validated': false,
        'azure_validated': false,
        'gcp_validated': false,
      });
    }
    final sourceOptimizer = store.optimizerConfig(twinId);
    if (sourceOptimizer?['params'] is Map) {
      store.setOptimizerConfig(created.id, {
        'params': _copyMap(sourceOptimizer!['params'] as Map),
      });
    }
    final sourceDeployer = store.deployerConfig(twinId);
    if (sourceDeployer != null) {
      store.setDeployerConfig(created.id, sourceDeployer);
    }
    return Twin.fromJson(store.twin(created.id));
  }

  @override
  Future<Twin> importTwin(TwinImportRequest request) async {
    await _pause();
    final definition = _decodePortableTwinDefinition(request.bytes);
    final created = await createTwin(request.newName);
    final providerSettings = definition['provider_settings'];
    store.setTwinConfig(created.id, {
      'highest_step_reached': 0,
      'debug_mode': definition['debug_mode'] == true,
      if (providerSettings is Map) ...{
        'aws_region': providerSettings['aws_region'],
        'aws_sso_region': providerSettings['aws_sso_region'],
        'azure_region': providerSettings['azure_region'],
        'azure_region_iothub': providerSettings['azure_region_iothub'],
        'azure_region_digital_twin':
            providerSettings['azure_region_digital_twin'],
        'gcp_project_id': providerSettings['gcp_project_id'],
        'gcp_region': providerSettings['gcp_region'],
      },
      'aws_cloud_connection_id': null,
      'azure_cloud_connection_id': null,
      'gcp_cloud_connection_id': null,
      'aws_validated': false,
      'azure_validated': false,
      'gcp_validated': false,
    });
    if (definition['optimizer_params'] case final Map params) {
      store.setOptimizerConfig(created.id, {'params': _copyMap(params)});
    }
    if (definition['deployer'] case final Map deployer) {
      store.setDeployerConfig(created.id, _copyMap(deployer));
    }
    return Twin.fromJson(store.twin(created.id));
  }

  @override
  Future<PortableTwinDownload> exportTwin(String twinId) async {
    await _pause();
    final twin = store.twin(twinId);
    final config = store.twinConfig(twinId) ?? const <String, dynamic>{};
    final optimizer = store.optimizerConfig(twinId);
    final definition = <String, dynamic>{
      'schema_version': 'twin-definition.v1',
      'source_name': twin['name'],
      'debug_mode': config['debug_mode'] == true,
      'provider_settings': {
        'aws_region': config['aws_region'] ?? 'eu-central-1',
        'aws_sso_region': config['aws_sso_region'],
        'azure_region': config['azure_region'] ?? 'westeurope',
        'azure_region_iothub': config['azure_region_iothub'],
        'azure_region_digital_twin': config['azure_region_digital_twin'],
        'gcp_project_id': config['gcp_project_id'],
        'gcp_region': config['gcp_region'] ?? 'europe-west1',
      },
      'optimizer_params': optimizer?['params'],
      'deployer': store.deployerConfig(twinId),
    };
    final safeName = twin['name'].toString().trim().replaceAll(
      RegExp(r'[^A-Za-z0-9._-]+'),
      '-',
    );
    return PortableTwinDownload(
      filename: '${safeName.isEmpty ? 'twin' : safeName}.twin.zip',
      mediaType: PortableTwinDownload.mediaTypeZip,
      bytes: _encodePortableTwinDefinition(definition),
    );
  }

  @override
  Future<Twin> updateTwin(String twinId, {String? name, String? state}) async {
    await _pause();
    if (name != null && name.trim().isEmpty) {
      throw const DemoApiException(
        'DEMO_TWIN_NAME_REQUIRED',
        'Twin name is required.',
      );
    }
    if (state != null &&
        !{
          'draft',
          'configured',
          'deploying',
          'deployed',
          'destroying',
          'destroyed',
          'error',
          'inactive',
        }.contains(state)) {
      throw DemoApiException(
        'DEMO_TWIN_STATE_INVALID',
        'Twin state "$state" is unsupported.',
      );
    }
    store.updateTwin(twinId, {
      if (name != null) 'name': name.trim(),
      if (state != null) 'state': state,
    });
    return Twin.fromJson(store.twin(twinId));
  }

  @override
  Future<void> deleteTwin(String twinId) async {
    await _pause();
    final twin = store.twin(twinId);
    if ({'deploying', 'deployed', 'destroying'}.contains(twin['state'])) {
      throw const DemoApiException(
        'DEMO_TWIN_DELETE_CONFLICT',
        'Active or deployed twins must be destroyed before deletion.',
      );
    }
    store.removeTwin(twinId);
    _deploymentReadinessCache.remove(twinId);
  }

  @override
  Future<TwinConfigData> getTwinConfig(String twinId) async {
    await _pause();
    return TwinConfigData.fromJson(_twinConfigResponse(twinId));
  }

  @override
  Future<TwinConfigData> updateTwinConfig(
    String twinId,
    Map<String, dynamic> config,
  ) async {
    await _pause();
    final current = store.twinConfig(twinId) ?? <String, dynamic>{};
    final update = _copyMap(config);
    final connections = update.remove('cloud_connections');
    if (connections is Map) {
      for (final provider in CloudProvider.values) {
        if (connections.containsKey(provider.apiValue)) {
          final id = connections[provider.apiValue]?.toString();
          if (id != null) {
            final connection = store.cloudConnection(id);
            if (connection['provider'] != provider.apiValue ||
                connection['purpose'] != 'deployment') {
              throw DemoApiException(
                'DEMO_CONNECTION_BINDING_INVALID',
                'Connection "$id" is not ${provider.label} deployment access.',
              );
            }
          }
          current['${provider.apiValue}_cloud_connection_id'] = id;
        }
      }
    }
    current.addAll(update);
    store.setTwinConfig(twinId, current);
    _deploymentReadinessCache.remove(twinId);
    return TwinConfigData.fromJson(_twinConfigResponse(twinId));
  }

  @override
  Future<TwinConfigData> updateTwinConfigRequest(
    String twinId,
    TwinConfigUpdateRequest request,
  ) {
    return updateTwinConfig(twinId, request.toJson());
  }

  @override
  Future<OptimizerRunData> createOptimizerRun(
    String twinId,
    CalcParams params,
  ) async {
    await _pause();
    store.twin(twinId);
    if (!params.isSixLayer) {
      throw const DemoApiException(
        'ARCH_WORKLOAD_INCOMPATIBLE',
        'New demo calculations require a frozen Six-layer workload scenario.',
      );
    }
    final paramsJson = params.toJson();
    final now = store.clock().toUtc();
    final runId = _nextDemoRunId();
    final scenario = params.scenario!.name;
    final specification = store.sixLayerDeploymentSpecification(scenario)
      ..['calculation_run_id'] = runId
      ..['currency'] = params.currency;
    _replaceCurrency(specification, params.currency);
    specification['digest'] =
        ResolvedDeploymentSpecificationData.calculateDigest(specification);
    final parsedSpecification = ResolvedDeploymentSpecificationData.fromJson(
      specification,
    );
    if (parsedSpecification is! ResolvedDeploymentSpecificationV2) {
      throw const DemoApiException(
        'DEMO_DEPLOYMENT_SPECIFICATION_INVALID',
        'The canonical Six-layer demo specification is unsupported.',
      );
    }

    final architecture = store.sixLayerResolvedArchitecture(scenario)
      ..['calculation_run_id'] = runId;
    _convertSixLayerArchitectureCurrency(architecture, params.currency);
    final deploymentRef =
        _copyMap(architecture['deployment_specification_ref'] as Map)
          ..['calculation_run_id'] = runId
          ..['digest'] = parsedSpecification.digest;
    architecture['deployment_specification_ref'] = deploymentRef;
    final configured = store.optimizerConfig('demo-configured');
    final result = configured?['result'] is Map
        ? _copyMap(configured!['result'] as Map)
        : _defaultCalculationResult(paramsJson);
    final cheapestPath = _sixLayerCheapestPath(architecture);
    final totalCostExact =
        ((architecture['cost_summary'] as Map)['monthly_total']).toString();
    architecture['content_digest'] = ResolvedTwinArchitecture.calculateDigest(
      architecture,
    );
    final resolvedRead = ResolvedTwinArchitectureRead.fromJson({
      'twin_id': twinId,
      'calculation_run_id': runId,
      'selected_for_deployment_at': null,
      'architecture_compatibility_status': 'ready',
      'origin': 'native_v2',
      'architecture': architecture,
    });
    _resolvedArchitectures[runId] = resolvedRead;

    result
      ..remove('transferPricingContext')
      ..remove('optimizationDiagnostics')
      ..remove('transferCosts')
      ..remove('awsCosts')
      ..remove('azureCosts')
      ..remove('gcpCosts')
      ..remove('inputParamsUsed')
      ..['cheapestPath'] = cheapestPath
      ..['calculationResult'] = _sixLayerCalculationResult(cheapestPath)
      ..['totalCost'] = double.parse(totalCostExact)
      ..['totalCostExact'] = totalCostExact
      ..['currency'] = params.currency
      ..['optimization_profile_id'] = 'cost-minimization-v2'
      ..['result_schema_version'] = 'cost-result.v2'
      ..['optimizationProfile'] = {
        'enabled': true,
        'profile_version': '2',
        'scoring_strategy_id': 'profile-local-min-total-cost-v2',
        'calculation_model_ids': ['profile-resolution-v2@2'],
        'pricing_registry_version': 'phase-08-complete-service-pricing@1',
      }
      ..['evidenceReferences'] = {
        'pricing_registry': 'phase-08-complete-service-pricing@1',
      }
      ..['resolvedTwinArchitecture'] = _copyMap(architecture)
      ..['resolvedDeploymentSpecification'] = _copyMap(specification)
      ..['pricingCatalogs'] = _demoPricingCatalogContext(store.clock());
    final optimization = OptimizationResultData.fromApiJson({'result': result});
    final parsedCheapestPath = CheapestPath.fromSegments(cheapestPath);
    final pricingCatalogContext = optimization.result.pricingCatalogContext!;
    store.setOptimizerConfig(twinId, {
      'params': _copyMap(paramsJson),
      'result': _copyMap(optimization.payload),
      'cheapest_path': parsedCheapestPath.toJson(),
      'pricing_catalog_context': pricingCatalogContext.toJson(),
      'calculated_at': now.toIso8601String(),
    });
    final twinConfig = store.twinConfig(twinId) ?? <String, dynamic>{};
    twinConfig
      ..['optimizer_params'] = _copyMap(paramsJson)
      ..['optimizer_result'] = _copyMap(optimization.payload);
    store.setTwinConfig(twinId, twinConfig);

    final runJson = {
      'id': runId,
      'twin_id': twinId,
      'status': 'succeeded',
      'result_summary': optimization.payload,
      'total_monthly_cost': optimization.result.totalCost,
      'currency': params.currency,
      'deployment_compatibility_status': 'ready',
      'deployment_specification_digest': parsedSpecification.digest,
      'deployment_specification_version': specification['schema_version'],
      'resolved_deployment_specification': specification,
      'selected_for_deployment_at': null,
      'created_at': now.toIso8601String(),
      'completed_at': now.toIso8601String(),
    };
    store.addOptimizerRun(twinId, runJson);
    return OptimizerRunData.fromJson(runJson);
  }

  @override
  Future<OptimizerDeploymentRunData?> getLatestOptimizerRun(
    String twinId,
  ) async {
    await _pause();
    store.twin(twinId);
    final runs = store.optimizerRuns(twinId);
    if (runs.isEmpty) return null;
    runs.sort((left, right) {
      final leftCreated = DateTime.parse(left['created_at'].toString());
      final rightCreated = DateTime.parse(right['created_at'].toString());
      final timestamp = rightCreated.compareTo(leftCreated);
      return timestamp != 0
          ? timestamp
          : right['id'].toString().compareTo(left['id'].toString());
    });
    return OptimizerDeploymentRunData.fromDetailJson(runs.first);
  }

  @override
  Future<OptimizerRunSelectionData> selectOptimizerRunForDeployment(
    String twinId,
    String runId,
  ) async {
    await _pause();
    final runs = store.optimizerRuns(twinId);
    final run = runs.cast<Map<String, dynamic>?>().firstWhere(
      (item) => item?['id']?.toString() == runId,
      orElse: () => null,
    );
    if (run == null ||
        run['status'] != 'succeeded' ||
        run['deployment_compatibility_status'] != 'ready' ||
        run['resolved_deployment_specification'] is! Map) {
      throw DemoApiException(
        'DEMO_OPTIMIZER_RUN_NOT_SELECTABLE',
        'Optimizer run "$runId" is not selectable.',
      );
    }
    final parsedSelectionSpecification =
        ResolvedDeploymentSpecificationData.fromJson(
          _copyMap(run['resolved_deployment_specification'] as Map),
        );
    if (parsedSelectionSpecification is ResolvedDeploymentSpecificationV2 &&
        parsedSelectionSpecification.readiness.evaluationOnly) {
      throw const DemoApiException(
        'DEPLOYMENT_CAPACITY_EVIDENCE_PENDING',
        'The Six-layer result is evaluation-only until its live-capacity gates are evidenced.',
      );
    }
    final selectedAt = store.clock().toUtc().toIso8601String();
    store.selectOptimizerRun(twinId, runId, selectedAt);
    final selectedRun = store
        .optimizerRuns(twinId)
        .firstWhere((item) => item['id']?.toString() == runId);
    final specification = _copyMap(
      selectedRun['resolved_deployment_specification'] as Map,
    );
    final summary = _copyMap(selectedRun)
      ..remove('resolved_deployment_specification')
      ..remove('result_summary')
      ..remove('params')
      ..remove('result_items');
    return OptimizerRunSelectionData.fromJson({
      'run': summary,
      'selected_for_deployment_at': selectedAt,
      'resolved_deployment_specification': specification,
    });
  }

  @override
  Future<OptimizerConfigData?> getOptimizerConfig(String twinId) async {
    await _pause();
    store.twin(twinId);
    if (store.optimizerConfig(twinId) == null) return null;
    return OptimizerConfigData.fromJson(_optimizerConfigResponse(twinId));
  }

  @override
  Future<DeployerConfigData?> getDeployerConfig(String twinId) async {
    await _pause();
    store.twin(twinId);
    final config = store.deployerConfig(twinId);
    return config == null ? null : DeployerConfigData.fromJson(config);
  }

  @override
  Future<DeployerConfigData> updateDeployerConfig(
    String twinId,
    Map<String, dynamic> config,
  ) async {
    await _pause();
    final current = store.deployerConfig(twinId) ?? <String, dynamic>{};
    current.addAll(_copyMap(config));
    store.setDeployerConfig(twinId, current);
    return DeployerConfigData.fromJson(current);
  }

  @override
  Future<DeployerConfigData> updateDeployerConfigRequest(
    String twinId,
    DeployerConfigUpdateRequest request,
  ) {
    return updateDeployerConfig(twinId, request.toJson());
  }

  @override
  Future<Map<String, dynamic>> validateDeployerConfig(
    String twinId,
    String configType,
    String content,
  ) async {
    await _pause();
    store.twin(twinId);
    if (!{'config', 'events', 'iot', 'payloads'}.contains(configType)) {
      throw DemoApiException(
        'DEMO_DEPLOYER_CONFIG_TYPE_INVALID',
        'Deployer configuration type "$configType" is unsupported.',
      );
    }
    return _jsonValidation(content);
  }

  @override
  Future<Map<String, dynamic>> validateL2Content(
    String twinId,
    String type,
    String content,
    String provider,
  ) async {
    await _pause();
    store.twin(twinId);
    _provider(provider);
    if (!{'function-code', 'state-machine'}.contains(type)) {
      throw DemoApiException(
        'DEMO_L2_CONTENT_TYPE_INVALID',
        'L2 content type "$type" is unsupported.',
      );
    }
    if (content.trim().isEmpty) {
      return {'valid': false, 'message': 'Content must not be empty.'};
    }
    return type == 'state-machine'
        ? _jsonValidation(content)
        : {'valid': true, 'message': 'Demo function syntax accepted.'};
  }

  @override
  Future<Map<String, dynamic>> validateL4Content(
    String twinId,
    String type,
    String content,
    String provider,
  ) async {
    await _pause();
    store.twin(twinId);
    _provider(provider);
    if (!{'hierarchy', 'scene-config', 'user-config'}.contains(type)) {
      throw DemoApiException(
        'DEMO_L4_CONTENT_TYPE_INVALID',
        'L4/L5 content type "$type" is unsupported.',
      );
    }
    return _jsonValidation(content);
  }

  @override
  Future<Map<String, dynamic>> uploadSceneGlb(
    String twinId,
    Uint8List fileBytes,
    String filename,
  ) async {
    await _pause();
    final bytes = _bytes(fileBytes);
    if (!filename.toLowerCase().endsWith('.glb') || bytes.isEmpty) {
      throw const DemoApiException(
        'DEMO_GLB_INVALID',
        'A non-empty GLB file is required.',
      );
    }
    final config = store.deployerConfig(twinId) ?? <String, dynamic>{};
    config['scene_glb_uploaded'] = true;
    store.setDeployerConfig(twinId, config);
    return {
      'message': 'Demo scene asset stored in memory.',
      'size_mb': bytes.length / (1024 * 1024),
    };
  }

  @override
  Future<void> deleteSceneGlb(String twinId) async {
    await _pause();
    final config = store.deployerConfig(twinId) ?? <String, dynamic>{};
    config['scene_glb_uploaded'] = false;
    store.setDeployerConfig(twinId, config);
  }

  @override
  Future<Map<String, dynamic>> uploadProjectZip(
    String twinId,
    Uint8List fileBytes,
    String filename,
  ) async {
    await _pause();
    store.twin(twinId);
    if (!filename.toLowerCase().endsWith('.zip') || _bytes(fileBytes).isEmpty) {
      throw const DemoApiException(
        'DEMO_ZIP_INVALID',
        'A non-empty ZIP file is required.',
      );
    }
    return {
      'success': true,
      'validation_errors': <String>[],
      'warnings': <String>[],
      'files': {
        'config.json': {
          'exists': true,
          'content': '{"digital_twin_name":"demo-import"}',
          'validation_error': null,
        },
        'config_events.json': {
          'exists': true,
          'content': '{}',
          'validation_error': null,
        },
        'config_iot_devices.json': {
          'exists': true,
          'content': '{"devices":[]}',
          'validation_error': null,
        },
        'iot_device_simulator/payloads.json': {
          'exists': true,
          'content': '{}',
          'validation_error': null,
        },
      },
      'functions': <String, dynamic>{},
      'assets': {
        'scene_glb': {'exists': false, 'saved': false},
      },
    };
  }

  @override
  Future<Result<TwinConfigData>> getTwinConfigResult(String twinId) async {
    try {
      return Success(await getTwinConfig(twinId));
    } on DemoApiException catch (error) {
      return Failure(AppException(error.message, code: error.code));
    }
  }

  @override
  Future<OperationSession> deployTwin(String twinId) async {
    await _pause();
    final twin = store.twin(twinId);
    if (!{'configured', 'destroyed', 'error'}.contains(twin['state'])) {
      throw DemoApiException(
        'DEMO_DEPLOY_STATE_CONFLICT',
        'Twin "$twinId" is not ready for deployment.',
      );
    }
    final readiness = _deploymentReadinessCache[twinId];
    if (readiness == null || readiness['ready'] != true) {
      throw const DemoApiException(
        'DEMO_DEPLOYMENT_PREFLIGHT_REQUIRED',
        'Deployment preflight is required before infrastructure deployment.',
      );
    }
    final sessionId = store.nextId('demo-deploy-session');
    final now = store.clock().toIso8601String();
    store.updateTwin(twinId, {
      'state': 'deployed',
      'deployed_at': now,
      'last_deployed_at': now,
      'last_error': null,
    });
    final outputs = {
      'iot_endpoint': 'https://$twinId.iot.demo.local',
      'dashboard_url': 'https://$twinId.dashboard.demo.local',
      'storage_bucket': '$twinId-storage',
    };
    store.setDeploymentOutput(twinId, {'outputs': outputs, 'deployed_at': now});
    store.setVerification(
      twinId,
      store.verification('demo-deployed') ?? _defaultVerification(),
    );
    store.addDeploymentLog(twinId, {
      'id': 1,
      'session_id': sessionId,
      'level': 'info',
      'message': 'Demo deployment completed successfully.',
      'timestamp': now,
    });
    return OperationSession(
      sessionId: sessionId,
      sseUrl: '/demo/deployment/$twinId/$sessionId',
    );
  }

  @override
  Future<DeploymentReadinessSnapshot> getDeploymentReadiness(
    String twinId,
  ) async {
    await _pause();
    store.twin(twinId);
    final cached = _deploymentReadinessCache[twinId];
    final document = cached == null
        ? _buildDeploymentReadiness(twinId, executeChecks: false)
        : _copyMap(cached);
    document['schema_version'] =
        DeploymentReadinessSnapshot.cachedSchemaVersion;
    return DeploymentReadinessSnapshot.fromCachedJson(document);
  }

  @override
  Future<DeploymentReadinessSnapshot> runDeploymentPreflight(
    String twinId,
  ) async {
    await _pause();
    store.twin(twinId);
    final document = _buildDeploymentReadiness(twinId, executeChecks: true);
    _deploymentReadinessCache[twinId] = {
      ..._copyMap(document),
      'schema_version': DeploymentReadinessSnapshot.cachedSchemaVersion,
    };
    document['schema_version'] =
        DeploymentReadinessSnapshot.preflightSchemaVersion;
    return DeploymentReadinessSnapshot.fromPreflightJson(document);
  }

  @override
  Future<OperationSession> destroyTwin(String twinId) async {
    await _pause();
    final twin = store.twin(twinId);
    if (!{'deployed', 'error'}.contains(twin['state'])) {
      throw DemoApiException(
        'DEMO_DESTROY_STATE_CONFLICT',
        'Twin "$twinId" has no active infrastructure to destroy.',
      );
    }
    final sessionId = store.nextId('demo-destroy-session');
    store.updateTwin(twinId, {
      'state': 'destroyed',
      'destroyed_at': store.clock().toIso8601String(),
    });
    store.setDeploymentOutput(twinId, null);
    return OperationSession(
      sessionId: sessionId,
      sseUrl: '/demo/destroy/$twinId/$sessionId',
    );
  }

  @override
  Future<DeploymentStatusSnapshot> getDeploymentStatus(String twinId) async {
    await _pause();
    return DeploymentStatusSnapshot.fromJson({
      'schema_version': DeploymentStatusSnapshot.supportedSchemaVersion,
      'state': store.twin(twinId)['state'],
      'last_error': store.twin(twinId)['last_error'],
      'deployed_at': store.twin(twinId)['last_deployed_at'],
      'destroyed_at': store.twin(twinId)['destroyed_at'],
      'active_session': null,
      'latest_deployment': null,
    });
  }

  @override
  Future<DeploymentOutputsSnapshot> getDeploymentOutputs(String twinId) async {
    await _pause();
    store.twin(twinId);
    final fixture = store.deploymentOutput(twinId);
    return DeploymentOutputsSnapshot.fromJson({
      'schema_version': DeploymentOutputsSnapshot.supportedSchemaVersion,
      'outputs': fixture?['outputs'],
      'deployed_at': fixture?['deployed_at'],
      'source_deployment': null,
      'redacted': true,
    });
  }

  @override
  Future<DeploymentAccessSnapshot> getDeploymentAccess(String twinId) async {
    await _pause();
    final twin = store.twin(twinId);
    if (twin['state'] != 'deployed') {
      throw DemoApiException(
        'DEMO_DEPLOYMENT_ACCESS_STATE_CONFLICT',
        'Twin "$twinId" must be deployed before layer access is available.',
      );
    }
    final path = store.optimizerConfig(twinId)?['cheapest_path'];
    final providers = path is Map ? path : const <String, dynamic>{};
    final l4 = _demoProvider(providers['l4'], fallback: CloudProvider.azure);
    final l5 = _demoProvider(providers['l5'], fallback: CloudProvider.aws);
    final generatedAt =
        store.deploymentOutput(twinId)?['deployed_at']?.toString() ??
        store.clock().toUtc().toIso8601String();
    return DeploymentAccessSnapshot.fromJson({
      'schema_version': DeploymentAccessSnapshot.supportedSchemaVersion,
      'twin_id': twinId,
      'deployment_id': 'demo-deployment-$twinId',
      'generated_at': generatedAt,
      'availability': 'available',
      'reason_code': null,
      'surfaces': [
        _demoAccessSurface(DeploymentLayer.l4, l4, twinId),
        _demoAccessSurface(DeploymentLayer.l5, l5, twinId),
      ],
    }, expectedTwinId: twinId);
  }

  @override
  Future<DeploymentAccessCredential> rotateGcpGrafanaViewerCredential(
    String twinId,
  ) async {
    final access = await getDeploymentAccess(twinId);
    final l5 = access.surfaceFor(DeploymentLayer.l5);
    if (l5?.provider != CloudProvider.gcp ||
        l5?.auth.credentialAction != DeploymentAccessCredentialAction.rotate) {
      throw const DemoApiException(
        'DEMO_GCP_GRAFANA_ROTATION_UNAVAILABLE',
        'Viewer credential rotation is only available for GCP Grafana.',
      );
    }
    final requestId = store.nextId('demo-grafana-viewer-rotation');
    return DeploymentAccessCredential.fromJson({
      'schema_version': DeploymentAccessCredential.supportedSchemaVersion,
      'layer': 'l5',
      'provider': 'gcp',
      'username': l5!.auth.principalLabel,
      'password': 'demo-viewer-$requestId',
      'issued_at': store.clock().toUtc().toIso8601String(),
    });
  }

  @override
  Future<DeploymentHistory> getDeploymentHistory(
    String twinId, {
    int limit = 10,
  }) async {
    await _pause();
    if (limit < 1 || limit > 50) {
      throw const DemoApiException(
        'DEMO_DEPLOYMENT_HISTORY_LIMIT_INVALID',
        'Deployment history limit must be between 1 and 50.',
      );
    }
    final twin = store.twin(twinId);
    final logs = store.deploymentLogs(twinId);
    final deployments = logs.isEmpty
        ? <Map<String, dynamic>>[]
        : [
            {
              'id': 'demo-deployment-$twinId',
              'session_id': logs.last['session_id'],
              'operation_id': null,
              'operation_type': 'deploy',
              'status': twin['state'] == 'error' ? 'failed' : 'success',
              'error_code': twin['state'] == 'error'
                  ? 'DEMO_DEPLOYMENT_FAILED'
                  : null,
              'error_message': twin['last_error'],
              'started_at': logs.first['timestamp'],
              'completed_at': logs.last['timestamp'],
            },
          ];
    return DeploymentHistory.fromJson({
      'schema_version': DeploymentHistory.supportedSchemaVersion,
      'deployments': deployments.take(limit).toList(growable: false),
    });
  }

  @override
  String getSseUrl(String sseUrl, {int? lastEventId}) {
    if (lastEventId != null && lastEventId > 0) {
      return '$sseUrl?last_event_id=$lastEventId';
    }
    return sseUrl;
  }

  @override
  Future<DeploymentLogPage> getDeploymentLogs(
    String twinId, {
    String? sessionId,
    int? afterEventId,
    int limit = 100,
  }) async {
    await _pause();
    if (limit < 1 || limit > 500) {
      throw const DemoApiException(
        'DEMO_DEPLOYMENT_LOG_LIMIT_INVALID',
        'Deployment log limit must be between 1 and 500.',
      );
    }
    if (afterEventId != null && afterEventId < 0) {
      throw const DemoApiException(
        'DEMO_DEPLOYMENT_LOG_CURSOR_INVALID',
        'Deployment log cursor cannot be negative.',
      );
    }
    if (sessionId != null && sessionId.trim().isEmpty) {
      throw const DemoApiException(
        'DEMO_DEPLOYMENT_LOG_SESSION_INVALID',
        'Deployment log session ID cannot be empty.',
      );
    }
    var logs = store.deploymentLogs(twinId);
    logs.sort(
      (left, right) =>
          _deploymentLogEventId(left).compareTo(_deploymentLogEventId(right)),
    );
    if (sessionId != null) {
      logs = logs
          .where((item) => item['session_id'] == sessionId)
          .toList(growable: false);
    }
    final scopedLogs = logs;
    if (afterEventId != null) {
      logs = logs
          .where((item) => _deploymentLogEventId(item) > afterEventId)
          .toList(growable: false);
    }
    final pageLogs = logs.take(limit).toList(growable: false);
    final normalizedLogs = pageLogs
        .map(
          (item) => {
            'event_id': _deploymentLogEventId(item),
            'session_id': item['session_id'],
            'timestamp': item['timestamp'],
            'level': item['level'],
            'message': item['message'],
            'operation_type': item['operation_type'] ?? 'deploy',
          },
        )
        .toList(growable: false);
    final nextAfterEventId = normalizedLogs.isEmpty
        ? afterEventId ?? 0
        : normalizedLogs.last['event_id'] as int;
    final latestEventId = scopedLogs.isEmpty
        ? null
        : scopedLogs
              .map(_deploymentLogEventId)
              .fold<int>(
                0,
                (current, value) => value > current ? value : current,
              );
    return DeploymentLogPage.fromJson({
      'schema_version': DeploymentLogPage.supportedSchemaVersion,
      'twin_id': twinId,
      'session_id': sessionId,
      'after_event_id': afterEventId ?? 0,
      'limit': limit,
      'logs': normalizedLogs,
      'has_more': logs.length > pageLogs.length,
      'next_after_event_id': nextAfterEventId,
      'latest_event_id': latestEventId,
    });
  }

  @override
  Future<LogTraceStartResult> startLogTrace(String twinId) async {
    await _pause();
    final twin = store.twin(twinId);
    if (twin['state'] != 'deployed') {
      throw const DemoApiException(
        'DEMO_TRACE_STATE_CONFLICT',
        'The twin must be deployed before tracing data flow.',
      );
    }
    final traceId = store.nextId('demo-trace');
    return LogTraceStartResult.fromJson({
      'trace_id': traceId,
      'sent_at': store.clock().toIso8601String(),
      'l1_provider': 'aws',
      'providers': ['aws', 'azure', 'gcp'],
      'message': 'Demo trace message accepted.',
      'session_id': traceId,
      'sse_url': '/demo/trace/$twinId/$traceId',
    });
  }

  @override
  Future<Map<String, dynamic>> verifyInfrastructure(String twinId) async {
    await _pause();
    final verification = store.verification(twinId);
    final value = verification?['infrastructure'];
    if (value is Map) return _copyMap(value);
    throw DemoApiException(
      'DEMO_VERIFICATION_UNAVAILABLE',
      'Infrastructure verification is unavailable for twin "$twinId".',
    );
  }

  @override
  Future<TelemetryVerificationStart> verifyDataFlow(
    String twinId,
    Map<String, dynamic> payload,
  ) async {
    await _pause();
    store.twin(twinId);
    if (payload['iotDeviceId']?.toString().trim().isEmpty ?? true) {
      throw const DemoApiException(
        'DEMO_DATAFLOW_PAYLOAD_INVALID',
        'Data-flow payload requires iotDeviceId.',
      );
    }
    final sessionId = store.nextId('demo-verification-session');
    final verificationId = store.nextId('demo-verification');
    final now = store.clock().toUtc();
    final record = TelemetryVerificationRecord(
      id: verificationId,
      twinId: twinId,
      sessionId: sessionId,
      deviceId: payload['iotDeviceId'].toString(),
      status: TelemetryVerificationStatus.notRun,
      errorCode: 'DEMO_NOT_RUN',
      errorMessage: 'Live telemetry verification is unavailable in demo mode.',
      requestedAt: now,
      completedAt: now,
    );
    _telemetryVerifications.putIfAbsent(twinId, () => []).insert(0, record);
    return TelemetryVerificationStart(
      schemaVersion: TelemetryVerificationStart.supportedSchemaVersion,
      verificationId: verificationId,
      sessionId: sessionId,
      sseUrl: '/demo/verification/$twinId/$sessionId',
      statusUrl: '/twins/$twinId/verify/dataflow/$verificationId',
      status: TelemetryVerificationStatus.notRun,
    );
  }

  @override
  Future<TelemetryVerificationHistory> listDataFlowVerifications(
    String twinId, {
    int limit = 25,
  }) async {
    store.twin(twinId);
    if (limit < 1 || limit > 25) {
      throw const DemoApiException(
        'DEMO_VERIFICATION_LIMIT_INVALID',
        'Telemetry verification history limit must be between 1 and 25.',
      );
    }
    final records = _telemetryVerifications[twinId] ?? const [];
    return TelemetryVerificationHistory(
      schemaVersion: TelemetryVerificationHistory.supportedSchemaVersion,
      verifications: List.unmodifiable(records.take(limit)),
    );
  }

  @override
  Future<TelemetryVerificationRecord> getDataFlowVerification(
    String twinId,
    String verificationId,
  ) async {
    store.twin(twinId);
    for (final record in _telemetryVerifications[twinId] ?? const []) {
      if (record.id == verificationId) return record;
    }
    throw const DemoApiException(
      'DEMO_VERIFICATION_NOT_FOUND',
      'Telemetry verification evidence does not exist.',
    );
  }

  @override
  Future<BinaryDownload> downloadSimulator(String twinId) async {
    await _pause();
    final twin = store.twin(twinId);
    if (twin['state'] != 'deployed') {
      throw const DemoApiException(
        'DEMO_SIMULATOR_STATE_CONFLICT',
        'Simulator packages are available only for deployed twins.',
      );
    }
    return BinaryDownload(
      bytes: Uint8List.fromList(utf8.encode('Twin2MultiCloud demo simulator')),
      filename: 'simulator_${twinId}_demo.zip',
      mediaType: 'application/zip',
    );
  }

  Future<void> _pause() {
    return latency == Duration.zero
        ? Future<void>.value()
        : Future<void>.delayed(latency);
  }

  Map<String, dynamic> _buildDeploymentReadiness(
    String twinId, {
    required bool executeChecks,
  }) {
    final optimizer = store.optimizerConfig(twinId);
    final rawPath = optimizer?['cheapest_path'];
    final requiredProviders = <String>[];
    if (rawPath is Map) {
      requiredProviders.addAll(
        rawPath.values
            .where((value) => value != null && value.toString().isNotEmpty)
            .map((value) => _provider(value.toString()))
            .toSet(),
      );
      requiredProviders.sort();
    }
    final issues = <Map<String, dynamic>>[];
    if (requiredProviders.isEmpty) {
      issues.add(
        _readinessCheck(
          component: 'architecture',
          code: 'DEPLOYMENT_ARCHITECTURE_MISSING',
          message:
              'No optimized provider architecture is stored for this twin.',
          action:
              'Complete cost optimization and save the selected provider path.',
        ),
      );
    }

    final config = store.twinConfig(twinId) ?? const <String, dynamic>{};
    final checkedAt = store.clock().toIso8601String();
    final providers = requiredProviders
        .map(
          (provider) => _buildProviderReadiness(
            provider,
            config['${provider}_cloud_connection_id']?.toString(),
            executeChecks: executeChecks,
            checkedAt: checkedAt,
          ),
        )
        .toList(growable: false);
    final ready =
        requiredProviders.isNotEmpty &&
        issues.isEmpty &&
        providers.every((provider) => provider['ready'] == true);
    final checkedProviders = providers.where(
      (provider) => provider['checked_at'] != null,
    );
    return {
      'schema_version': executeChecks
          ? DeploymentReadinessSnapshot.preflightSchemaVersion
          : DeploymentReadinessSnapshot.cachedSchemaVersion,
      'twin_id': twinId,
      'ready': ready,
      'summary': issues.isNotEmpty
          ? 'Deployment architecture must be completed before preflight.'
          : ready
          ? 'All required providers are ready for deployment.'
          : '${providers.where((provider) => provider['ready'] != true).length} '
                'of ${providers.length} required providers need review.',
      'required_providers': requiredProviders,
      'providers': providers,
      'checked_at': checkedProviders.isEmpty ? null : checkedAt,
      'issues': issues,
    };
  }

  Map<String, dynamic> _buildProviderReadiness(
    String provider,
    String? connectionId, {
    required bool executeChecks,
    required String checkedAt,
  }) {
    Map<String, dynamic>? connection;
    if (connectionId != null) {
      try {
        connection = store.cloudConnection(connectionId);
      } on DemoApiException {
        connection = null;
      }
    }
    String failureCode;
    String failureMessage;
    String failureAction;
    if (connectionId == null) {
      failureCode = 'CLOUD_CONNECTION_MISSING';
      failureMessage =
          'No deployment Cloud Connection is bound for this provider.';
      failureAction =
          'Open Cloud Accounts and bind deployment access to the twin.';
    } else if (connection == null) {
      failureCode = 'CLOUD_CONNECTION_UNAVAILABLE';
      failureMessage = 'The bound deployment Cloud Connection is unavailable.';
      failureAction = 'Select an available deployment Cloud Connection.';
    } else if (connection['provider'] != provider) {
      failureCode = 'CLOUD_CONNECTION_PROVIDER_MISMATCH';
      failureMessage =
          'The bound Cloud Connection belongs to a different provider.';
      failureAction = 'Bind a matching deployment Cloud Connection.';
    } else if (connection['purpose'] != 'deployment') {
      failureCode = 'CLOUD_CONNECTION_PURPOSE_INVALID';
      failureMessage =
          'Pricing access cannot be used for infrastructure deployment.';
      failureAction = 'Bind a deployment-purpose Cloud Connection.';
    } else if (!executeChecks) {
      failureCode = 'PREFLIGHT_NOT_RUN';
      failureMessage =
          'Deployment preflight has not been run for this provider binding.';
      failureAction = 'Run deployment preflight before deploying this twin.';
    } else {
      return {
        'provider': provider,
        'connection_id': connectionId,
        'connection_display_name': connection['display_name'],
        'ready': true,
        'status': 'ready',
        'summary': 'Cloud connection preflight passed',
        'checked_at': checkedAt,
        'checks': [
          _readinessCheck(
            component: 'optimizer',
            status: 'passed',
            code: 'OK',
            message: 'Optimizer access passed.',
            action: 'No action required.',
          ),
          _readinessCheck(
            component: 'deployer',
            status: 'passed',
            code: 'OK',
            message: 'Deployer access passed.',
            action: 'No action required.',
          ),
        ],
      };
    }

    return {
      'provider': provider,
      'connection_id': connection?['id'],
      'connection_display_name': connection?['display_name'],
      'ready': false,
      'status': executeChecks ? 'review_required' : 'not_checked',
      'summary': failureMessage,
      'checked_at': null,
      'checks': [
        _readinessCheck(
          component: 'configuration',
          code: failureCode,
          message: failureMessage,
          action: failureAction,
        ),
      ],
    };
  }

  Map<String, dynamic> _readinessCheck({
    required String component,
    String status = 'failed',
    required String code,
    required String message,
    required String action,
  }) {
    return {
      'component': component,
      'status': status,
      'code': code,
      'message': message,
      'action': action,
      'permissions': <String>[],
    };
  }

  String _provider(String value) {
    final normalized = value.toLowerCase() == 'google'
        ? 'gcp'
        : value.toLowerCase();
    if (!{'aws', 'azure', 'gcp'}.contains(normalized)) {
      throw DemoApiException(
        'DEMO_PROVIDER_INVALID',
        'Cloud provider "$value" is unsupported.',
      );
    }
    return normalized;
  }

  Map<String, dynamic> _twinConfigResponse(String twinId) {
    final twin = store.twin(twinId);
    final raw = store.twinConfig(twinId) ?? <String, dynamic>{};
    final configuredProviders = <String>[];
    final credentialSources = <String, String?>{};
    final boundConnections = <String, Map<String, dynamic>?>{};
    final response = <String, dynamic>{
      'id': 'config-$twinId',
      'twin_id': twinId,
      'twin_state': twin['state'],
      'debug_mode': raw['debug_mode'] as bool? ?? false,
      'highest_step_reached': raw['highest_step_reached'] as int? ?? 0,
      'optimizer_params': raw['optimizer_params'],
      'optimizer_result': raw['optimizer_result'],
      'updated_at': twin['updated_at'],
    };

    for (final provider in CloudProvider.values) {
      final prefix = provider.apiValue;
      final connectionId = raw['${prefix}_cloud_connection_id'] as String?;
      final connection = connectionId == null
          ? null
          : store.cloudConnection(connectionId);
      final configured = connection != null;
      if (configured) configuredProviders.add(prefix);
      credentialSources[prefix] = configured ? 'cloud_connection' : null;
      boundConnections[prefix] = connection == null
          ? null
          : {
              'id': connection['id'],
              'provider': connection['provider'],
              'display_name': connection['display_name'],
              'auth_type': connection['auth_type'],
              'validation_status': connection['validation_status'],
              'last_validated_at': connection['last_validated_at'],
            };
      final scope = connection?['cloud_scope'] is Map
          ? Map<String, dynamic>.from(connection!['cloud_scope'] as Map)
          : const <String, dynamic>{};
      response
        ..['${prefix}_configured'] = configured
        ..['${prefix}_validated'] = connection?['validation_status'] == 'valid'
        ..['${prefix}_credential_source'] = configured
            ? 'cloud_connection'
            : null
        ..['${prefix}_cloud_connection_id'] = connectionId
        ..['${prefix}_region'] = raw['${prefix}_region'] ?? scope['region'];
      if (provider == CloudProvider.aws) {
        response['aws_sso_region'] = raw['aws_sso_region'];
      } else if (provider == CloudProvider.azure) {
        response
          ..['azure_region_iothub'] = raw['azure_region_iothub']
          ..['azure_region_digital_twin'] = raw['azure_region_digital_twin'];
      } else {
        final summary = connection?['payload_summary'] is Map
            ? Map<String, dynamic>.from(connection!['payload_summary'] as Map)
            : const <String, dynamic>{};
        response['gcp_project_id'] =
            raw['gcp_project_id'] ??
            scope['project_id'] ??
            summary['project_id'];
      }
    }
    response
      ..['configured_providers'] = configuredProviders
      ..['credential_sources'] = credentialSources
      ..['cloud_connections'] = boundConnections;
    return response;
  }

  Map<String, dynamic> _optimizerConfigResponse(String twinId) {
    final twin = store.twin(twinId);
    final raw = store.optimizerConfig(twinId) ?? <String, dynamic>{};
    final result = raw['result'] is Map ? _copyMap(raw['result'] as Map) : null;
    final context = raw['pricing_catalog_context'];
    return {
      'id': 'optimizer-$twinId',
      'twin_id': twinId,
      'params': raw['params'],
      'result': result,
      'cheapest_path': raw['cheapest_path'],
      'calculated_at': raw['calculated_at'],
      'pricing_catalog_context': context,
      'updated_at': raw['calculated_at'] ?? twin['updated_at'],
    };
  }

  Map<String, dynamic> _architectureProfileSummaryJson(
    String profileId,
    String profileVersion,
  ) {
    final profile = store.architectureProfile(profileId, profileVersion);
    final responsibilities =
        (profile['responsibilities'] as List)
            .cast<Map>()
            .map(Map<String, dynamic>.from)
            .toList()
          ..sort(
            (left, right) => (left['evaluation_order'] as int).compareTo(
              right['evaluation_order'] as int,
            ),
          );
    final providers =
        store.architectureProviderProfiles(profileId, profileVersion)..sort(
          (left, right) => left['provider'].toString().compareTo(
            right['provider'].toString(),
          ),
        );
    Map<String, dynamic> providerSummary(Map<String, dynamic> item) => {
      'provider': item['provider'],
      'supported': item['supported'],
      'profile_id': item['implementation_profile_id'],
      'profile_version': item['implementation_profile_version'],
      'reason_codes': [
        for (final reason in (item['unsupported_reasons'] as List).cast<Map>())
          reason['reason_code'],
      ],
    };
    final capabilityIds = <String>{
      for (final responsibility in responsibilities)
        for (final capability
            in (responsibility['capability_requirements'] as List))
          capability.toString(),
    }.toList()..sort();
    final extensionSlots =
        (profile['extension_slots'] as List)
            .cast<Map>()
            .map(Map<String, dynamic>.from)
            .toList()
          ..sort((left, right) {
            final idComparison = left['slot_id'].toString().compareTo(
              right['slot_id'].toString(),
            );
            if (idComparison != 0) return idComparison;
            return int.parse(
              left['slot_version'].toString(),
            ).compareTo(int.parse(right['slot_version'].toString()));
          });
    return {
      'profile_id': profile['profile_id'],
      'profile_version': profile['profile_version'],
      'profile_digest': profile['content_digest'],
      'display_name': profile['display_name'],
      'description': profile['description'],
      'lifecycle_status': 'active',
      'responsibilities': [
        for (final item in responsibilities)
          {
            'responsibility_id': item['responsibility_id'],
            'display_name': item['display_name'],
            'required': item['required'],
            'capability_ids': List<String>.from(
              item['capability_requirements'] as List,
            )..sort(),
            'workload_field_ids': List<String>.from(
              item['workload_field_refs'] as List,
            )..sort(),
          },
      ],
      'capability_ids': capabilityIds,
      'workload_contract_ref': _copyMap(
        profile['workload_contract_ref'] as Map,
      ),
      'available_providers': [
        for (final item in providers.where((item) => item['supported'] == true))
          providerSummary(item),
      ],
      'unsupported_providers': [
        for (final item in providers.where((item) => item['supported'] != true))
          providerSummary(item),
      ],
      'extension_slots': [
        for (final item in extensionSlots)
          {
            'slot_id': item['slot_id'],
            'slot_version': item['slot_version'],
            'logical_component_id': item['component_id'],
          },
      ],
    };
  }

  Map<String, dynamic> _architectureProfileDetailJson(
    String profileId,
    String profileVersion,
  ) {
    final profile = store.architectureProfile(profileId, profileVersion);
    final components = (profile['components'] as List)
        .cast<Map>()
        .map(Map<String, dynamic>.from)
        .toList();
    final edges = (profile['edges'] as List)
        .cast<Map>()
        .map(Map<String, dynamic>.from)
        .toList();
    return {
      ..._architectureProfileSummaryJson(profileId, profileVersion),
      'logical_components': components,
      'logical_edges': edges,
      'visualization': {
        'nodes': [
          for (final component in components)
            {
              'id': component['component_id'],
              'label': _componentLabel(component['component_id'].toString()),
              'responsibility_id': component['responsibility_id'],
            },
        ],
        'edges': [
          for (final edge in edges)
            {
              'id': edge['edge_id'],
              'source': edge['source_component_id'],
              'destination': edge['destination_component_id'],
            },
        ],
      },
    };
  }

  String _componentLabel(String componentId) => componentId
      .replaceFirst('component.', '')
      .split('-')
      .map(
        (part) => part.isEmpty
            ? part
            : '${part.substring(0, 1).toUpperCase()}${part.substring(1)}',
      )
      .join(' ');

  void _replaceCurrency(Object? value, String currency) {
    if (value is Map) {
      for (final entry in value.entries.toList()) {
        if (entry.key == 'currency' && entry.value is String) {
          value[entry.key] = currency;
        } else {
          _replaceCurrency(entry.value, currency);
        }
      }
    } else if (value is List) {
      for (final item in value) {
        _replaceCurrency(item, currency);
      }
    }
  }

  void _convertSixLayerArchitectureCurrency(
    Map<String, dynamic> architecture,
    String currency,
  ) {
    final rate = switch (currency) {
      'USD' => 1.0,
      'EUR' => _sixLayerEurPerUsd,
      _ => throw DemoApiException(
        'DEMO_CURRENCY_UNSUPPORTED',
        'The Six-layer demo currency "$currency" is unsupported.',
      ),
    };
    int convertedMicros(Object? value) =>
        (double.parse(value.toString()) * rate * 1000000).round();

    _replaceCurrency(architecture, currency);
    final componentMicros = <String, int>{};
    final responsibilityMicros = <String, int>{};
    for (final assignment in (architecture['component_assignments'] as List)) {
      final item = assignment as Map;
      final contribution = item['cost_contribution'] as Map;
      final micros = convertedMicros(contribution['monthly_amount']);
      contribution['monthly_amount'] = _demoMicrosText(micros);
      componentMicros[item['logical_component_id'].toString()] = micros;
      responsibilityMicros.update(
        item['responsibility_id'].toString(),
        (current) => current + micros,
        ifAbsent: () => micros,
      );
    }
    final edgeMicros = <String, int>{};
    for (final edge in (architecture['resolved_edges'] as List)) {
      final item = edge as Map;
      final contribution = item['cost_contribution'] as Map;
      final micros = convertedMicros(contribution['monthly_amount']);
      contribution['monthly_amount'] = _demoMicrosText(micros);
      edgeMicros[item['edge_id'].toString()] = micros;
    }
    final summary = architecture['cost_summary'] as Map;
    for (final entry in {
      'responsibility_totals': responsibilityMicros,
      'component_totals': componentMicros,
      'edge_totals': edgeMicros,
    }.entries) {
      final field = entry.key;
      for (final item in (summary[field] as List)) {
        final total = item as Map;
        final micros = entry.value[total['item_id'].toString()];
        if (micros == null) {
          throw const DemoApiException(
            'DEMO_SIX_LAYER_COST_INVALID',
            'The canonical demo cost summary is incomplete.',
          );
        }
        total['monthly_amount'] = _demoMicrosText(micros);
      }
    }
    final totalMicros = [
      ...componentMicros.values,
      ...edgeMicros.values,
    ].fold<int>(0, (total, micros) => total + micros);
    summary['monthly_total'] = _demoMicrosText(totalMicros);
  }

  List<String> _sixLayerCheapestPath(Map<String, dynamic> architecture) {
    final providers = <String, String>{};
    for (final raw in (architecture['component_assignments'] as List)) {
      final assignment = Map<String, dynamic>.from(raw as Map);
      providers[assignment['logical_component_id'].toString()] =
          assignment['provider'].toString();
    }
    String segment(String layer, String logicalComponentId) {
      final provider = providers[logicalComponentId];
      if (provider == null) {
        throw const DemoApiException(
          'DEMO_RESOLVED_ARCHITECTURE_INVALID',
          'The canonical demo architecture is missing a logical component.',
        );
      }
      final label = switch (provider) {
        'aws' => 'AWS',
        'azure' => 'Azure',
        'gcp' => 'GCP',
        _ => throw const DemoApiException(
          'DEMO_RESOLVED_ARCHITECTURE_INVALID',
          'The canonical demo architecture uses an unsupported provider.',
        ),
      };
      return '${layer}_$label';
    }

    return [
      segment('L1', 'component.ingestion'),
      segment('L2', 'component.processing'),
      segment('L3_hot', 'component.hot-storage'),
      segment('L3_cool', 'component.cool-storage'),
      segment('L3_archive', 'component.archive-storage'),
      segment('L4', 'component.twin-state'),
      segment('L5', 'component.visualization'),
    ];
  }

  Map<String, dynamic> _sixLayerCalculationResult(List<String> cheapestPath) {
    String providerFor(String prefix) => cheapestPath
        .firstWhere((segment) => segment.startsWith(prefix))
        .split('_')
        .last;
    return {
      'L1': providerFor('L1_'),
      'L2': providerFor('L2_'),
      'L3': {
        'Hot': providerFor('L3_hot_'),
        'Cool': providerFor('L3_cool_'),
        'Archive': providerFor('L3_archive_'),
      },
      'L4': providerFor('L4_'),
      'L5': providerFor('L5_'),
    };
  }

  String _demoMicrosText(int micros) {
    final whole = micros ~/ 1000000;
    final fraction = (micros % 1000000).abs().toString().padLeft(6, '0');
    final trimmed = fraction.replaceFirst(RegExp(r'0+$'), '');
    return trimmed.isEmpty ? '$whole' : '$whole.$trimmed';
  }

  String _nextDemoRunId() {
    final seed = store.nextId('demo-optimizer-run');
    final hex = sha256.convert(utf8.encode(seed)).toString();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '5${hex.substring(13, 16)}-a${hex.substring(17, 20)}-'
        '${hex.substring(20, 32)}';
  }

  Map<String, dynamic> _payloadSummary(CloudConnectionCreateRequest request) {
    return switch (request.provider) {
      CloudProvider.aws => {
        if (request.cloudScope['account_id'] != null)
          'account_id': request.cloudScope['account_id'],
      },
      CloudProvider.azure => {
        if (request.cloudScope['subscription_id'] != null)
          'subscription_id': request.cloudScope['subscription_id'],
      },
      CloudProvider.gcp => {
        if (request.cloudScope['project_id'] != null)
          'project_id': request.cloudScope['project_id'],
      },
    };
  }

  String _defaultAuthType(CloudProvider provider) {
    return switch (provider) {
      CloudProvider.aws => 'access_key',
      CloudProvider.azure => 'service_principal',
      CloudProvider.gcp => 'service_account_key',
    };
  }

  Map<String, dynamic> _jsonValidation(String content) {
    try {
      jsonDecode(content);
      return {'valid': true, 'message': 'Demo JSON validation passed.'};
    } on FormatException {
      return {'valid': false, 'message': 'Content is not valid JSON.'};
    }
  }

  Uint8List _bytes(dynamic value) {
    if (value is Uint8List) return value;
    if (value is List<int>) return Uint8List.fromList(value);
    return Uint8List(0);
  }

  Map<String, dynamic> _defaultCalculationResult(Map<String, dynamic> params) {
    return {
      'totalCost': 42.0,
      'awsCosts': {
        'L3_cool': {
          'cost': 3.0,
          'components': {'S3 Standard-IA': 3.0},
        },
        'L5': {
          'cost': 8.0,
          'components': {'Grafana': 8.0},
        },
      },
      'azureCosts': {
        'L2': {
          'cost': 7.0,
          'components': {'Functions': 7.0},
        },
        'L4': {
          'cost': 10.0,
          'components': {'Digital Twins': 10.0},
        },
      },
      'gcpCosts': {
        'L1': {
          'cost': 8.0,
          'components': {'Pub/Sub': 8.0},
        },
        'L3_hot': {
          'cost': 4.0,
          'components': {'Firestore': 4.0},
        },
        'L3_archive': {
          'cost': 2.0,
          'components': {'Cloud Storage Archive': 2.0},
        },
      },
      'cheapestPath': [
        'L1_GCP',
        'L2_Azure',
        'L3_hot_GCP',
        'L3_cool_AWS',
        'L3_archive_GCP',
        'L4_Azure',
        'L5_AWS',
      ],
      'pricingCatalogs': _demoPricingCatalogContext(store.clock()),
      'transferCosts': {'L1_to_L2': 0.0, 'L2_to_L3': 0.0},
      'inputParamsUsed': {'needs3DModel': params['needs3DModel'] == true},
    };
  }

  Map<String, dynamic> _defaultVerification() {
    return {
      'infrastructure': {
        'checks': [
          {
            'layer': 'L1-L5',
            'name': 'Demo infrastructure',
            'provider': 'multi-cloud',
            'status': 'pass',
            'detail': 'The in-memory deployment completed successfully.',
          },
        ],
        'summary': {
          'pass_count': 1,
          'fail_count': 0,
          'skip_count': 0,
          'total': 1,
          'healthy': true,
        },
      },
      'dataflow': {
        'pass_count': 1,
        'fail_count': 0,
        'skip_count': 0,
        'total': 1,
        'healthy': true,
      },
    };
  }

  Map<String, dynamic> _demoProviderCapabilities() {
    Map<String, dynamic> source({required bool available}) {
      return {
        'availability': available ? 'available' : 'unsupported',
        'reason_code': available ? null : 'DEPLOYMENT_PATH_NOT_IMPLEMENTED',
        'reason': available
            ? null
            : 'GCP capability is outside the implemented thesis path.',
        'verification_level': available ? 'contract_tested' : 'not_verified',
      };
    }

    return {
      'schema_version': 'platform-provider-capabilities.v1',
      'complete': true,
      'sources': {
        for (final service in const ['optimizer', 'deployer'])
          service: {
            'status': 'available',
            'schema_version': 'provider-service-capabilities.v1',
          },
      },
      'providers': [
        for (final provider in const ['aws', 'azure', 'gcp'])
          {
            'provider': provider,
            'layers': [
              for (final layer in const [
                'l1',
                'l2',
                'l3_hot',
                'l3_cool',
                'l3_archive',
                'l4',
                'l5',
              ])
                {
                  'layer': layer,
                  'availability':
                      provider == 'gcp' && {'l4', 'l5'}.contains(layer)
                      ? 'unsupported'
                      : 'available',
                  'reason_code':
                      provider == 'gcp' && {'l4', 'l5'}.contains(layer)
                      ? 'DEPLOYMENT_PATH_NOT_IMPLEMENTED'
                      : null,
                  'reason': provider == 'gcp' && {'l4', 'l5'}.contains(layer)
                      ? 'GCP capability is outside the implemented thesis path.'
                      : null,
                  'selectable':
                      !(provider == 'gcp' && {'l4', 'l5'}.contains(layer)),
                  'sources_agree': true,
                  'restriction_source':
                      provider == 'gcp' && {'l4', 'l5'}.contains(layer)
                      ? 'restricted_by_both'
                      : 'none',
                  'verification_level':
                      provider == 'gcp' && {'l4', 'l5'}.contains(layer)
                      ? 'not_verified'
                      : 'contract_tested',
                  'sources': {
                    'optimizer': source(
                      available:
                          !(provider == 'gcp' && {'l4', 'l5'}.contains(layer)),
                    ),
                    'deployer': source(
                      available:
                          !(provider == 'gcp' && {'l4', 'l5'}.contains(layer)),
                    ),
                  },
                },
            ],
          },
      ],
    };
  }

  Map<String, dynamic> _demoPricingCatalogContext(DateTime fetchedAt) {
    return {
      'schemaVersion': 'provider-pricing-catalog-context.v1',
      'catalogs': {
        for (final provider in const ['aws', 'azure', 'gcp'])
          provider: _demoPricingCatalogReference(provider, fetchedAt),
      },
    };
  }

  Map<String, dynamic> _demoPricingCatalogReference(
    String provider,
    DateTime fetchedAt,
  ) {
    final marker = switch (provider) {
      'aws' => 'a',
      'azure' => 'b',
      'gcp' => 'c',
      _ => throw const DemoApiException(
        'DEMO_PROVIDER_INVALID',
        'Unsupported demo pricing provider.',
      ),
    };
    final region = switch (provider) {
      'aws' => 'eu-central-1',
      'azure' => 'westeurope',
      'gcp' => 'europe-west1',
      _ => throw const DemoApiException(
        'DEMO_PROVIDER_INVALID',
        'Unsupported demo pricing provider.',
      ),
    };
    final identity = List.filled(64, marker).join();
    final fetchedAtUtc = fetchedAt.toUtc();
    const providerSchemaVersion = 'pricing-provider-schema.v1';
    const contractVersion = 'demo-contract.v1';
    const registryVersion = 'demo-registry.v1';
    const mappingVersions = ['demo-mapping.v1'];
    final contentDigest = 'sha256:$identity';
    final snapshotId = buildPricingCatalogSnapshotId(
      provider: provider,
      pricingRegion: region,
      providerSchemaVersion: providerSchemaVersion,
      contractVersion: contractVersion,
      registryVersion: registryVersion,
      mappingVersions: mappingVersions,
      fetchedAt: fetchedAtUtc,
      contentDigest: contentDigest,
      source: 'provider_api',
      reviewStatus: 'reviewed',
    );
    return {
      'schemaVersion': 'pricing-catalog-reference.v1',
      'snapshotId': snapshotId,
      'provider': provider,
      'pricingRegion': region,
      'providerSchemaVersion': providerSchemaVersion,
      'contractVersion': contractVersion,
      'registryVersion': registryVersion,
      'mappingVersions': mappingVersions,
      'fetchedAt': fetchedAtUtc.toIso8601String(),
      'contentDigest': contentDigest,
      'source': 'provider_api',
      'reviewStatus': 'reviewed',
      'publicationStatus': 'published',
      'calculationSource': 'fresh',
    };
  }

  static Map<String, dynamic> _copyMap(Map<dynamic, dynamic> value) {
    return Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
  }
}

Uint8List _encodePortableTwinDefinition(Map<String, dynamic> definition) {
  final definitionBytes = Uint8List.fromList(
    utf8.encode(jsonEncode(definition)),
  );
  final digest = 'sha256:${sha256.convert(definitionBytes)}';
  final manifestBytes = Uint8List.fromList(
    utf8.encode(
      jsonEncode({
        'schema_version': 'twin2multicloud-portable.v1',
        'files': {'twin-definition.json': digest},
      }),
    ),
  );
  final archive = Archive()
    ..addFile(ArchiveFile.bytes('manifest.json', manifestBytes))
    ..addFile(ArchiveFile.bytes('twin-definition.json', definitionBytes));
  return ZipEncoder().encodeBytes(archive, modified: DateTime.utc(2026));
}

Map<String, dynamic> _decodePortableTwinDefinition(Uint8List bytes) {
  try {
    final archive = ZipDecoder().decodeBytes(bytes, verify: true);
    final names = archive.map((file) => file.name).toSet();
    if (archive.length != 2 ||
        !names.containsAll(const {'manifest.json', 'twin-definition.json'})) {
      throw const FormatException('Portable Twin archive members are invalid.');
    }
    final manifestBytes = archive.find('manifest.json')?.readBytes();
    final definitionBytes = archive.find('twin-definition.json')?.readBytes();
    if (manifestBytes == null || definitionBytes == null) {
      throw const FormatException('Portable Twin archive is incomplete.');
    }
    final manifestValue = jsonDecode(utf8.decode(manifestBytes));
    final definitionValue = jsonDecode(utf8.decode(definitionBytes));
    if (manifestValue is! Map ||
        manifestValue['schema_version'] != 'twin2multicloud-portable.v1' ||
        manifestValue['files'] is! Map ||
        (manifestValue['files'] as Map)['twin-definition.json'] !=
            'sha256:${sha256.convert(definitionBytes)}' ||
        definitionValue is! Map ||
        definitionValue['schema_version'] != 'twin-definition.v1' ||
        definitionValue['source_name'] is! String ||
        definitionValue['provider_settings'] is! Map) {
      throw const FormatException('Portable Twin archive contract is invalid.');
    }
    return Map<String, dynamic>.from(definitionValue);
  } on DemoApiException {
    rethrow;
  } catch (_) {
    throw const DemoApiException(
      'DEMO_TWIN_ARCHIVE_INVALID',
      'Portable Twin archive contract is invalid.',
    );
  }
}

CloudProvider _demoProvider(Object? value, {required CloudProvider fallback}) {
  if (value == null) return fallback;
  try {
    return CloudProvider.fromApiValue(value.toString());
  } on ArgumentError {
    return fallback;
  }
}

Map<String, dynamic> _demoAccessSurface(
  DeploymentLayer layer,
  CloudProvider provider,
  String twinId,
) {
  final configuration = switch ((layer, provider)) {
    (DeploymentLayer.l4, CloudProvider.aws) => (
      'aws_iot_twinmaker',
      'AWS IoT TwinMaker workspace',
      'aws_identity_center',
      'demo@twin2multicloud.local',
      'none',
    ),
    (DeploymentLayer.l4, CloudProvider.azure) => (
      'azure_digital_twins',
      'Azure Digital Twins Explorer',
      'azure_entra',
      'demo@twin2multicloud.local',
      'none',
    ),
    (DeploymentLayer.l4, CloudProvider.gcp) => (
      'gcp_twin_explorer',
      'GCP Twin Explorer',
      'gcp_iap',
      'demo@twin2multicloud.local',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.aws) => (
      'aws_managed_grafana',
      'Amazon Managed Grafana',
      'aws_identity_center',
      'demo@twin2multicloud.local',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.azure) => (
      'azure_managed_grafana',
      'Azure Managed Grafana',
      'azure_entra',
      'demo@twin2multicloud.local',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.gcp) => (
      'gcp_grafana_oss',
      'Grafana OSS on GKE',
      'generated_viewer',
      'demo-viewer',
      'rotate',
    ),
  };
  return {
    'layer': layer.name,
    'provider': provider.apiValue,
    'service_id': configuration.$1,
    'display_name': configuration.$2,
    'url':
        'https://${layer.name}-${provider.apiValue}-$twinId.demo.twin2multicloud.local/',
    'auth': {
      'mode': configuration.$3,
      'principal_label': configuration.$4,
      'credential_action': configuration.$5,
    },
    'readiness': {
      'resource': 'ready',
      'access_binding': 'ready',
      'content': 'ready',
      'data_probe': 'ready',
      'browser_sign_in': 'unverified',
    },
    'capabilities': [
      layer == DeploymentLayer.l4
          ? 'Inspect the modeled twin surface.'
          : 'Inspect the provisioned thesis dashboard.',
    ],
    'limitations': ['Demo links do not create live cloud resources.'],
  };
}

int _deploymentLogEventId(Map<String, dynamic> item) {
  final value = item['event_id'] ?? item['id'];
  if (value is! int || value <= 0) {
    throw const DemoApiException(
      'DEMO_DEPLOYMENT_LOG_EVENT_INVALID',
      'Deployment log event IDs must be positive integers.',
    );
  }
  return value;
}
