import 'dart:convert';
import 'dart:typed_data';

import '../core/result.dart';
import '../models/calc_params.dart';
import '../models/authentication.dart';
import '../models/cloud_access_inventory.dart';
import '../models/cloud_connection.dart';
import '../models/dashboard_stats.dart';
import '../models/deployment_operations.dart';
import '../models/deployment_readiness.dart';
import '../models/deployer_config.dart';
import '../models/optimizer_config.dart';
import '../models/pricing_candidate_review.dart';
import '../models/pricing_catalog.dart';
import '../models/pricing_health.dart';
import '../models/pricing_refresh_run.dart';
import '../models/provider_capability.dart';
import '../models/twin.dart';
import '../models/twin_config.dart';
import '../models/user.dart';
import '../models/wizard_config_requests.dart';
import '../services/management_api.dart';
import 'demo_fixture_store.dart';

class DemoManagementApi implements ManagementApi {
  final DemoFixtureStore store;
  final Duration latency;
  String? _token = 'demo-token';
  final List<Map<String, dynamic>> _decisions = [];
  final Map<String, Map<String, dynamic>> _deploymentReadinessCache = {};

  DemoManagementApi({
    required this.store,
    this.latency = const Duration(milliseconds: 120),
  });

  @override
  void setToken(String? token) => _token = token;

  @override
  void setUnauthorizedHandler(void Function()? handler) {}

  @override
  Future<String?> getAuthToken() async => _token;

  @override
  Future<List<AuthProviderCapability>> getAuthProviders() async => const [];

  @override
  Future<AuthLoginTransaction> startExternalLogin(IdentityProvider provider) =>
      throw StateError('External authentication is unavailable in demo mode.');

  @override
  Future<AuthExchangeResult> exchangeAuthSession(
    AuthLoginTransaction transaction,
  ) => throw StateError('External authentication is unavailable in demo mode.');

  @override
  Future<void> cancelAuthSession(AuthLoginTransaction transaction) async {}

  @override
  Future<void> logoutSession() async {}

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
  Future<CloudAccessInventory> getCloudAccessInventory() async {
    await _pause();
    final connections = store.cloudConnections;
    final providers = <String, dynamic>{};
    for (final provider in CloudProvider.values) {
      final providerConnections = connections
          .where((item) => item['provider'] == provider.apiValue)
          .toList(growable: false);
      final pricing = providerConnections
          .where((item) => item['purpose'] == 'pricing')
          .toList(growable: false);
      final deployment = providerConnections
          .where((item) => item['purpose'] == 'deployment')
          .toList(growable: false);
      final selectedPricing = pricing.isEmpty
          ? _missingOrPublicPricingEntry(provider)
          : _accessEntry(
              pricing.firstWhere(
                (item) => item['is_default_for_pricing'] == true,
                orElse: () => pricing.first,
              ),
            );
      providers[provider.apiValue] = {
        'provider': provider.apiValue,
        'pricing': selectedPricing,
        'pricing_options': pricing.map(_accessEntry).toList(),
        'deployment': deployment.map(_accessEntry).toList(),
      };
    }
    return CloudAccessInventory.fromJson({
      'schema_version': 'cloud-access-inventory.v1',
      'providers': providers,
    });
  }

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
    if (request.isDefaultForPricing &&
        request.purpose != CloudConnectionPurpose.pricing) {
      throw const DemoApiException(
        'DEMO_CONNECTION_DEFAULT_INVALID',
        'Only pricing connections can be the default pricing connection.',
      );
    }
    if (request.isDefaultForPricing) {
      for (final connection in store.cloudConnections.where(
        (item) =>
            item['provider'] == request.provider.apiValue &&
            item['purpose'] == 'pricing' &&
            item['is_default_for_pricing'] == true,
      )) {
        store.updateCloudConnection(connection['id'].toString(), {
          'is_default_for_pricing': false,
        });
      }
    }
    final payloadSummary = _payloadSummary(request);
    final value = <String, dynamic>{
      'id': id,
      'provider': request.provider.apiValue,
      'purpose': request.purpose.apiValue,
      'scope': 'user',
      'is_default_for_pricing': request.isDefaultForPricing,
      'display_name': request.displayName.trim(),
      'auth_type': request.authType ?? _defaultAuthType(request.provider),
      'permission_set_version': null,
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
  Future<CloudConnection> updateCloudConnection(
    String id, {
    String? displayName,
    Map<String, dynamic>? cloudScope,
    bool? isDefaultForPricing,
  }) async {
    await _pause();
    final current = store.cloudConnection(id);
    if (displayName != null && displayName.trim().isEmpty) {
      throw const DemoApiException(
        'DEMO_CONNECTION_NAME_REQUIRED',
        'Cloud connection display name is required.',
      );
    }
    if (isDefaultForPricing == true && current['purpose'] != 'pricing') {
      throw const DemoApiException(
        'DEMO_CONNECTION_DEFAULT_INVALID',
        'Only pricing connections can be the default pricing connection.',
      );
    }
    if (isDefaultForPricing == true) {
      for (final connection in store.cloudConnections.where(
        (item) =>
            item['provider'] == current['provider'] &&
            item['purpose'] == 'pricing' &&
            item['id'] != id,
      )) {
        store.updateCloudConnection(connection['id'].toString(), {
          'is_default_for_pricing': false,
        });
      }
    }
    store.updateCloudConnection(id, {
      if (displayName != null) 'display_name': displayName.trim(),
      if (cloudScope != null) 'cloud_scope': cloudScope,
      if (isDefaultForPricing != null)
        'is_default_for_pricing': isDefaultForPricing,
    });
    return CloudConnection.fromJson(store.cloudConnection(id));
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
      'optimizer': {'valid': true, 'message': 'Pricing access is ready.'},
      'deployer': {'valid': true, 'message': 'Deployment access is ready.'},
    });
  }

  @override
  Future<List<Twin>> getTwins() async {
    await _pause();
    return store.twins.map(Twin.fromJson).toList(growable: false);
  }

  @override
  Future<DashboardStats> getDashboardStats() async {
    await _pause();
    final twins = store.twins.map(Twin.fromJson).toList(growable: false);
    var monthlyCost = 0.0;
    for (final twin in twins.where((item) => item.isDeployed)) {
      final result = store.optimizerConfig(twin.id)?['result'];
      if (result is Map && result['totalCost'] is num) {
        monthlyCost += (result['totalCost'] as num).toDouble();
      }
    }
    return DashboardStats(
      deployedCount: twins.where((item) => item.isDeployed).length,
      draftCount: twins.where((item) => item.isDraft).length,
      totalTwins: twins.length,
      estimatedMonthlyCost: monthlyCost,
    );
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
  Future<Map<String, dynamic>> getPricingStatus() async {
    await _pause();
    final health = store.pricingHealth;
    return {
      'schema_version': health['schema_version'],
      'providers': (health['providers'] as Map).map(
        (key, value) => MapEntry(key.toString(), {
          'status': (value as Map)['state'],
          'updated_at': value['last_fetched_at'],
        }),
      ),
    };
  }

  @override
  Future<PricingHealthResponse> getPricingHealth() async {
    await _pause();
    return PricingHealthResponse.fromJson(store.pricingHealth);
  }

  @override
  Future<PricingRefreshRun> startPricingRefresh(
    String provider, {
    String? connectionId,
    bool force = true,
  }) async {
    await _pause();
    final normalized = _provider(provider);
    Map<String, dynamic>? connection;
    if (normalized != 'azure') {
      if (connectionId != null) {
        connection = store.cloudConnection(connectionId);
      } else {
        final candidates = store.cloudConnections.where(
          (item) =>
              item['provider'] == normalized &&
              item['purpose'] == 'pricing' &&
              item['is_default_for_pricing'] == true,
        );
        connection = candidates.isEmpty ? null : candidates.first;
      }
      if (connection == null ||
          connection['provider'] != normalized ||
          connection['purpose'] != 'pricing') {
        throw DemoApiException(
          'DEMO_PRICING_ACCESS_MISSING',
          '${normalized.toUpperCase()} pricing access is not configured.',
        );
      }
    }
    final now = store.clock();
    final runId = store.nextId('demo-run-$normalized');
    final activeReference = _demoPricingCatalogReference(normalized, now);
    final hasReview = store
        .pricingReports(normalized)
        .any((report) => report['review_state'] == 'review_required');
    store.updatePricingHealth(normalized, {
      'state': hasReview ? 'review_required' : 'fresh',
      'severity': hasReview ? 'warning' : 'success',
      'review_required': hasReview,
      'can_calculate': true,
      'calculation_source': hasReview ? 'last_known_good' : 'latest_verified',
      'pricing_freshness': 'fresh',
      'age': 'just now',
      'last_fetched_at': now.toIso8601String(),
      'primary_message': hasReview
          ? 'Pricing refresh completed and requires review.'
          : 'Pricing refresh completed successfully.',
    });
    return PricingRefreshRun.fromJson({
      'schema_version': 'pricing-refresh-run.v1',
      'refresh_run_id': runId,
      'provider': normalized,
      'status': 'succeeded',
      'credential_summary': connection == null
          ? {
              'connection_id': null,
              'identity_label': 'Azure Retail Prices API',
              'scope': 'public',
            }
          : {
              'connection_id': connection['id'],
              'identity_label': connection['display_name'],
              'scope': 'user',
              'provider_account_id':
                  (connection['payload_summary'] as Map?)?['account_id'],
              'provider_project_id':
                  (connection['payload_summary'] as Map?)?['project_id'],
              'provider_subscription_id':
                  (connection['payload_summary'] as Map?)?['subscription_id'],
            },
      'force': force,
      'sse_url': '/demo/pricing/$normalized/$runId',
      'result_summary': {
        'schemaVersion': 'pricing-catalog-refresh-result.v2',
        'status': 'published',
        'activeCalculationReference': activeReference,
        if (normalized == 'aws')
          'accountPricingContext': {
            'schema_version': 'aws-twinmaker-account-pricing-context.v1',
            'provider': 'aws',
            'service': 'iot_twinmaker',
            'region':
                (connection?['cloud_scope'] as Map?)?['region'] ??
                'eu-central-1',
            'verified_account_id':
                (connection?['payload_summary'] as Map?)?['account_id'],
            'catalog_snapshot_digest': activeReference['contentDigest'],
            'observed_at': now.toIso8601String(),
            'current_plan': {
              'mode': 'STANDARD',
              'billable_entity_count': 42,
              'effective_at': null,
              'updated_at': now.toIso8601String(),
              'update_reason': null,
              'bundle': null,
            },
            'pending_plan': null,
            'management_binding': {
              'schema_version': 'aws-twinmaker-management-binding.v1',
              'pricing_connection_id': connection?['id'],
              'connection_fingerprint':
                  'sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
              'verified_account_id':
                  (connection?['payload_summary'] as Map?)?['account_id'],
              'configured_account_id':
                  (connection?['payload_summary'] as Map?)?['account_id'],
            },
          },
      },
      'created_at': now.toIso8601String(),
      'started_at': now.toIso8601String(),
      'completed_at': now.toIso8601String(),
    });
  }

  @override
  Future<PricingCandidateReportList> listPricingCandidateReports(
    String provider,
    String refreshRunId,
  ) async {
    await _pause();
    final normalized = _provider(provider);
    final reports = store
        .pricingReports(normalized)
        .map((report) {
          return {...report, 'refresh_run_id': refreshRunId};
        })
        .toList(growable: false);
    return PricingCandidateReportList.fromJson({
      'schema_version': 'pricing-candidate-report-list.v1',
      'provider': normalized,
      'refresh_run_id': refreshRunId,
      'reports': reports,
    });
  }

  @override
  Future<PricingTrace> getPricingCandidateTrace(String reportId) async {
    await _pause();
    final trace = store.pricingTrace(reportId);
    if (trace == null) {
      throw DemoApiException(
        'DEMO_PRICING_TRACE_NOT_FOUND',
        'Pricing trace "$reportId" does not exist.',
      );
    }
    return PricingTrace.fromJson(trace);
  }

  @override
  Future<PricingReviewDecision> createPricingReviewDecision(
    String reportId,
    String decision, {
    String? candidateId,
    String? rationale,
  }) async {
    await _pause();
    final report = _findPricingReport(reportId);
    final allowedDecisions = {'approve', 'select_alternative', 'defer'};
    if (!allowedDecisions.contains(decision)) {
      throw DemoApiException(
        'DEMO_PRICING_DECISION_INVALID',
        'Pricing review decision "$decision" is unsupported.',
      );
    }
    if (decision != 'defer' && candidateId == null) {
      throw const DemoApiException(
        'DEMO_PRICING_CANDIDATE_REQUIRED',
        'A selected pricing candidate is required for this decision.',
      );
    }
    if (candidateId != null) {
      final candidates = report['candidates'] as List? ?? const [];
      if (!candidates.any(
        (item) => item is Map && item['candidate_id'] == candidateId,
      )) {
        throw DemoApiException(
          'DEMO_PRICING_CANDIDATE_NOT_FOUND',
          'Pricing candidate "$candidateId" does not exist.',
        );
      }
    }
    final value = <String, dynamic>{
      'schema_version': 'pricing-review-decision.v1',
      'decision_id': store.nextId('demo-decision'),
      'report_id': reportId,
      'provider': report['provider'],
      'intent_id': report['intent_id'],
      'decision': decision,
      'selected_candidate_id': candidateId,
      'rationale': rationale,
      'created_at': store.clock().toIso8601String(),
    };
    _decisions.add(value);
    return PricingReviewDecision.fromJson(value);
  }

  @override
  Future<Map<String, dynamic>> getRegionsStatus() async {
    await _pause();
    return {
      'providers': {
        for (final provider in CloudProvider.values)
          provider.apiValue: {'status': 'fresh', 'regions': 3},
      },
    };
  }

  @override
  Future<OptimizerRunData> createOptimizerRun(
    String twinId,
    CalcParams params,
  ) async {
    await _pause();
    store.twin(twinId);
    final paramsJson = params.toJson();
    final configured = store.optimizerConfig('demo-configured');
    final result = configured?['result'] is Map
        ? _copyMap(configured!['result'] as Map)
        : _defaultCalculationResult(paramsJson);
    result['pricingCatalogs'] = _demoPricingCatalogContext(store.clock());
    result['inputParamsUsed'] = {
      'useEventChecking': paramsJson['useEventChecking'] == true,
      'triggerNotificationWorkflow':
          paramsJson['triggerNotificationWorkflow'] == true,
      'returnFeedbackToDevice': paramsJson['returnFeedbackToDevice'] == true,
      'integrateErrorHandling': paramsJson['integrateErrorHandling'] == true,
      'needs3DModel': paramsJson['needs3DModel'] == true,
    };
    final optimization = OptimizationResultData.fromApiJson({'result': result});
    final now = store.clock().toUtc();
    final cheapestPath = CheapestPath.fromSegments(
      List<String>.from(result['cheapestPath'] as List),
    );
    final pricingCatalogContext = optimization.result.pricingCatalogContext!;
    store.setOptimizerConfig(twinId, {
      'params': _copyMap(paramsJson),
      'result': _copyMap(optimization.payload),
      'cheapest_path': cheapestPath.toJson(),
      'pricing_catalog_context': pricingCatalogContext.toJson(),
      'calculated_at': now.toIso8601String(),
    });
    final twinConfig = store.twinConfig(twinId) ?? <String, dynamic>{};
    twinConfig
      ..['optimizer_params'] = _copyMap(paramsJson)
      ..['optimizer_result'] = _copyMap(optimization.payload);
    store.setTwinConfig(twinId, twinConfig);

    return OptimizerRunData.fromJson({
      'id': store.nextId('demo-optimizer-run'),
      'twin_id': twinId,
      'status': 'succeeded',
      'result_summary': optimization.payload,
      'total_monthly_cost': optimization.result.totalCost,
      'currency': params.currency,
      'created_at': now.toIso8601String(),
      'completed_at': now.toIso8601String(),
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
  Future<Result<Map<String, dynamic>>> getPricingStatusResult() async {
    try {
      return Success(await getPricingStatus());
    } on DemoApiException catch (error) {
      return Failure(AppException(error.message, code: error.code));
    }
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
  Future<Map<String, dynamic>> verifyDataFlow(
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
    return {
      'session_id': sessionId,
      'sse_url': '/demo/verification/$twinId/$sessionId',
    };
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
    final expectedVersion = 'thesis-demo-v1';
    final suppliedVersion = connection?['permission_set_version']?.toString();
    final permissionStatus = suppliedVersion == null
        ? 'missing'
        : suppliedVersion == expectedVersion
        ? 'matched'
        : 'outdated';

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
    } else if (permissionStatus != 'matched') {
      failureCode = 'OUTDATED_PERMISSION_SET';
      failureMessage =
          'The deployment permission set does not match the active baseline.';
      failureAction = 'Re-run provider bootstrap, then run preflight again.';
    } else {
      return {
        'provider': provider,
        'connection_id': connectionId,
        'connection_display_name': connection['display_name'],
        'ready': true,
        'status': 'ready',
        'summary': 'Cloud connection preflight passed',
        'expected_permission_set_version': expectedVersion,
        'supplied_permission_set_version': suppliedVersion,
        'permission_set_status': permissionStatus,
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
      'expected_permission_set_version': expectedVersion,
      'supplied_permission_set_version': suppliedVersion,
      'permission_set_status': permissionStatus,
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
        response
          ..['gcp_project_id'] =
              raw['gcp_project_id'] ??
              scope['project_id'] ??
              summary['project_id']
          ..['gcp_billing_account_configured'] = false;
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

  Map<String, dynamic> _accessEntry(Map<String, dynamic> connection) {
    final id = connection['id'].toString();
    final summary = connection['payload_summary'] as Map? ?? const {};
    final scope = connection['cloud_scope'] as Map? ?? const {};
    final bound = store.twinsBoundToConnection(id);
    final validationStatus = connection['validation_status']?.toString();
    return {
      'connection_id': id,
      'provider': connection['provider'],
      'purpose': connection['purpose'],
      'scope': connection['scope'] ?? 'user',
      'identity_label': connection['display_name'],
      'status': switch (validationStatus) {
        'valid' => 'active',
        'invalid' => 'needs_validation',
        _ => 'needs_validation',
      },
      'provider_account_id': summary['account_id'] ?? scope['account_id'],
      'provider_project_id': summary['project_id'] ?? scope['project_id'],
      'provider_subscription_id':
          summary['subscription_id'] ?? scope['subscription_id'],
      'is_default_for_pricing': connection['is_default_for_pricing'] == true,
      'last_validated_at': connection['last_validated_at'],
      'last_used_at': connection['last_used_at'],
      'permission_set_status': validationStatus,
      'bound_twin_count': bound.length,
      'bound_twin_labels': bound.map((item) => item['name']).toList(),
      'actions': ['validate', 'edit', 'delete'],
      'primary_message': connection['validation_message'],
    };
  }

  Map<String, dynamic> _missingOrPublicPricingEntry(CloudProvider provider) {
    if (provider == CloudProvider.azure) {
      return {
        'connection_id': null,
        'provider': 'azure',
        'purpose': 'pricing',
        'scope': 'public',
        'identity_label': 'Azure Retail Prices API',
        'status': 'active',
        'bound_twin_count': 0,
        'bound_twin_labels': <String>[],
        'actions': ['refresh'],
        'primary_message': 'Public catalog access requires no credentials.',
      };
    }
    return {
      'connection_id': null,
      'provider': provider.apiValue,
      'purpose': 'pricing',
      'scope': 'user',
      'identity_label': '${provider.label} pricing access missing',
      'status': 'missing',
      'bound_twin_count': 0,
      'bound_twin_labels': <String>[],
      'actions': ['create'],
      'primary_message': 'Create pricing access to refresh this provider.',
    };
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

  Map<String, dynamic> _findPricingReport(String reportId) {
    for (final provider in CloudProvider.values) {
      for (final report in store.pricingReports(provider.apiValue)) {
        if (report['report_id'] == reportId) return report;
      }
    }
    throw DemoApiException(
      'DEMO_PRICING_REPORT_NOT_FOUND',
      'Pricing report "$reportId" does not exist.',
    );
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
        'L1': {
          'cost': 8.0,
          'components': {'IoT Core': 8.0},
        },
        'L4': {
          'cost': 10.0,
          'components': {'TwinMaker': 10.0},
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
      },
      'gcpCosts': {
        'L3_hot': {
          'cost': 4.0,
          'components': {'Cloud Storage': 4.0},
        },
        'L3_cool': {
          'cost': 3.0,
          'components': {'Nearline': 3.0},
        },
        'L3_archive': {
          'cost': 2.0,
          'components': {'Archive': 2.0},
        },
      },
      'cheapestPath': [
        'L1_AWS',
        'L2_Azure',
        'L3_hot_GCP',
        'L3_cool_GCP',
        'L3_archive_GCP',
        'L4_AWS',
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
    Map<String, dynamic> source({
      required bool available,
      required bool planned,
    }) {
      return {
        'availability': available ? 'available' : 'unsupported',
        'roadmap': planned ? 'planned' : 'none',
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
                  'roadmap': provider == 'gcp' && {'l4', 'l5'}.contains(layer)
                      ? 'planned'
                      : 'none',
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
                      planned:
                          provider == 'gcp' && {'l4', 'l5'}.contains(layer),
                    ),
                    'deployer': source(
                      available:
                          !(provider == 'gcp' && {'l4', 'l5'}.contains(layer)),
                      planned:
                          provider == 'gcp' && {'l4', 'l5'}.contains(layer),
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
