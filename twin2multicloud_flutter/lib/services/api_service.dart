import 'dart:typed_data';

import 'package:dio/dio.dart';
import '../core/result.dart';
import '../models/calc_params.dart';
import '../models/calc_result.dart';
import '../models/cloud_access_inventory.dart';
import '../models/cloud_connection.dart';
import '../models/dashboard_stats.dart';
import '../models/deployment_operations.dart';
import '../models/deployment_readiness.dart';
import '../models/deployer_config.dart';
import '../models/optimizer_config.dart';
import '../models/pricing_candidate_review.dart';
import '../models/pricing_health.dart';
import '../models/pricing_refresh_run.dart';
import '../models/pricing_export_snapshot.dart';
import '../models/twin.dart';
import '../models/twin_config.dart';
import '../models/wizard_config_requests.dart';
import '../utils/api_error_handler.dart';
import 'management_api.dart';

Dio _resolveDio({required Dio? dio, required Uri? baseUri}) {
  if ((dio == null) == (baseUri == null)) {
    throw ArgumentError(
      'Provide exactly one ApiService transport source: dio or baseUri.',
    );
  }
  return dio ??
      Dio(
        BaseOptions(
          baseUrl: baseUri!.toString(),
          headers: {'Content-Type': 'application/json'},
        ),
      );
}

Uri _parseTransportBaseUri(String value) {
  final uri = Uri.tryParse(value);
  final hasRootPath = uri != null && (uri.path.isEmpty || uri.path == '/');
  if (uri == null ||
      !uri.isAbsolute ||
      uri.host.isEmpty ||
      !{'http', 'https'}.contains(uri.scheme.toLowerCase()) ||
      uri.userInfo.isNotEmpty ||
      uri.hasQuery ||
      uri.hasFragment ||
      !hasRootPath) {
    throw ArgumentError(
      'ApiService base URI must be an absolute HTTP(S) origin.',
    );
  }
  return uri.replace(path: '');
}

String? _normalizeToken(String? value) {
  if (value == null) return null;
  if (value.isEmpty || RegExp(r'[\x00-\x20\x7F]').hasMatch(value)) {
    throw ArgumentError('Authentication token must be non-empty and opaque.');
  }
  return value;
}

class ApiService implements ManagementApi {
  final Dio _dio;
  late final Uri _baseUri;
  String? _token;

  ApiService({Dio? dio, Uri? baseUri, String? initialAuthToken})
    : _dio = _resolveDio(dio: dio, baseUri: baseUri),
      _token = _normalizeToken(initialAuthToken) {
    _baseUri = _parseTransportBaseUri(_dio.options.baseUrl);
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          if (_token != null) {
            options.headers['Authorization'] = 'Bearer $_token';
          }
          return handler.next(options);
        },
      ),
    );
  }

  @override
  void setToken(String? token) => _token = _normalizeToken(token);

  /// Get current auth token for SSE connections
  @override
  Future<String?> getAuthToken() async => _token;

  @override
  Future<List<CloudConnection>> listCloudConnections({
    CloudProvider? provider,
  }) async {
    final response = await _dio.get(
      '/cloud-connections/',
      queryParameters: {if (provider != null) 'provider': provider.apiValue},
    );
    final data = response.data as List<dynamic>;
    return data
        .map((json) => CloudConnection.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<CloudAccessInventory> getCloudAccessInventory() async {
    final response = await _dio.get('/cloud-access');
    return CloudAccessInventory.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  @override
  Future<CloudConnection> createCloudConnection(
    CloudConnectionCreateRequest request,
  ) async {
    final response = await _dio.post(
      '/cloud-connections/',
      data: request.toJson(),
    );
    return CloudConnection.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<CloudConnection> updateCloudConnection(
    String id, {
    String? displayName,
    Map<String, dynamic>? cloudScope,
    bool? isDefaultForPricing,
  }) async {
    final response = await _dio.patch(
      '/cloud-connections/$id',
      data: {
        if (displayName != null) 'display_name': displayName,
        if (cloudScope != null) 'cloud_scope': cloudScope,
        if (isDefaultForPricing != null)
          'is_default_for_pricing': isDefaultForPricing,
      },
    );
    return CloudConnection.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<void> deleteCloudConnection(String id) async {
    await _dio.delete('/cloud-connections/$id');
  }

  @override
  Future<CloudConnectionValidationResult> validateCloudConnection(
    String id,
  ) async {
    final response = await _dio.post('/cloud-connections/$id/validate');
    return CloudConnectionValidationResult.fromJson(
      response.data as Map<String, dynamic>,
    );
  }

  /// Update current user's preferences (e.g., theme)
  @override
  Future<Map<String, dynamic>> updateUserPreferences({
    String? themePreference,
  }) async {
    final data = <String, dynamic>{};
    if (themePreference != null) data['theme_preference'] = themePreference;
    final response = await _dio.patch('/auth/me', data: data);
    return response.data;
  }

  @override
  Future<List<Twin>> getTwins() async {
    final response = await _dio.get('/twins/');
    final data = response.data;
    if (data is! List) {
      throw const FormatException(
        'Invalid API contract: twins response must be an array.',
      );
    }
    return List<Twin>.unmodifiable(
      data.indexed.map(
        (entry) => Twin.fromJson(_contractMap(entry.$2, 'twins[${entry.$1}]')),
      ),
    );
  }

  @override
  Future<DashboardStats> getDashboardStats() async {
    final response = await _dio.get('/dashboard/stats');
    return DashboardStats.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  @override
  Future<Twin> getTwin(String twinId) async {
    final response = await _dio.get('/twins/$twinId');
    return Twin.fromJson(_contractMap(response.data, 'twin'));
  }

  @override
  Future<Twin> createTwin(String name) async {
    final response = await _dio.post('/twins/', data: {'name': name});
    return Twin.fromJson(_contractMap(response.data, 'twin'));
  }

  @override
  Future<Twin> updateTwin(String twinId, {String? name, String? state}) async {
    final data = <String, dynamic>{};
    if (name != null) data['name'] = name;
    if (state != null) data['state'] = state;

    final response = await _dio.put('/twins/$twinId', data: data);
    return Twin.fromJson(_contractMap(response.data, 'twin'));
  }

  @override
  Future<void> deleteTwin(String twinId) async {
    await _dio.delete('/twins/$twinId');
  }

  @override
  Future<TwinConfigData> getTwinConfig(String twinId) async {
    final response = await _dio.get('/twins/$twinId/config/');
    return TwinConfigData.fromJson(_contractMap(response.data, 'twin_config'));
  }

  @override
  Future<TwinConfigData> updateTwinConfig(
    String twinId,
    Map<String, dynamic> config,
  ) async {
    final response = await _dio.put('/twins/$twinId/config/', data: config);
    return TwinConfigData.fromJson(_contractMap(response.data, 'twin_config'));
  }

  @override
  Future<TwinConfigData> updateTwinConfigRequest(
    String twinId,
    TwinConfigUpdateRequest request,
  ) {
    return updateTwinConfig(twinId, request.toJson());
  }

  // ============================================================
  // Optimizer Endpoints (Step 2)
  // ============================================================

  /// Get pricing data freshness status for all providers
  @override
  Future<Map<String, dynamic>> getPricingStatus() async {
    final response = await _dio.get('/optimizer/pricing-status');
    return response.data;
  }

  @override
  Future<PricingHealthResponse> getPricingHealth() async {
    final response = await _dio.get('/optimizer/pricing-health');
    return PricingHealthResponse.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  @override
  Future<PricingRefreshRun> startPricingRefresh(
    String provider, {
    String? connectionId,
    bool force = true,
  }) async {
    final response = await _dio.post(
      '/optimizer/pricing-refresh/${provider.toLowerCase()}',
      data: {'pricing_connection_id': connectionId, 'force': force},
      options: Options(receiveTimeout: const Duration(minutes: 20)),
    );
    return PricingRefreshRun.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  @override
  Future<PricingCandidateReportList> listPricingCandidateReports(
    String provider,
    String refreshRunId,
  ) async {
    final response = await _dio.get(
      '/optimizer/pricing-review/${provider.toLowerCase()}/candidate-reports',
      queryParameters: {'refresh_run_id': refreshRunId},
    );
    return PricingCandidateReportList.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  @override
  Future<PricingTrace> getPricingCandidateTrace(String reportId) async {
    final response = await _dio.get(
      '/optimizer/pricing-review/candidate-reports/$reportId/trace',
    );
    return PricingTrace.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  @override
  Future<PricingReviewDecision> createPricingReviewDecision(
    String reportId,
    String decision, {
    String? candidateId,
    String? rationale,
  }) async {
    final response = await _dio.post(
      '/optimizer/pricing-review/decisions',
      data: {
        'report_id': reportId,
        'decision': decision,
        if (candidateId != null) 'selected_candidate_id': candidateId,
        if (rationale != null && rationale.trim().isNotEmpty)
          'rationale': rationale.trim(),
      },
    );
    return PricingReviewDecision.fromJson(
      Map<String, dynamic>.from(response.data as Map),
    );
  }

  /// Get regions data freshness status for all providers
  @override
  Future<Map<String, dynamic>> getRegionsStatus() async {
    final response = await _dio.get('/optimizer/regions-status');
    return response.data;
  }

  /// Calculate costs using Optimizer
  /// Returns full result including costs, cheapest path, and overrides
  @override
  Future<OptimizationResultData> calculateCosts(CalcParams params) async {
    final response = await _dio.put(
      '/optimizer/calculate',
      data: params.toJson(),
    );
    return OptimizationResultData.fromApiJson(
      _contractMap(response.data, 'calculation'),
    );
  }

  // ============================================================
  // Optimizer Config Persistence (Step 2)
  // ============================================================

  /// Get optimizer config (params + result + cheapest path)
  @override
  Future<OptimizerConfigData?> getOptimizerConfig(String twinId) async {
    try {
      final response = await _dio.get('/twins/$twinId/optimizer-config');
      return OptimizerConfigData.fromJson(
        _contractMap(response.data, 'optimizer_config'),
      );
    } on DioException catch (error) {
      if (error.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  /// Save params only (before calculation)
  @override
  Future<void> saveOptimizerParams(String twinId, CalcParams params) async {
    await _dio.put(
      '/twins/$twinId/optimizer-config/params',
      data: {'params': params.toJson()},
    );
  }

  /// Save full result with pricing snapshots (after calculation)
  @override
  Future<void> saveOptimizerResult(
    String twinId, {
    required CalcParams params,
    required OptimizationResultData optimization,
    required CheapestPath cheapestPath,
    required Map<CloudProvider, PricingExportSnapshot> pricingSnapshots,
  }) async {
    await _dio.put(
      '/twins/$twinId/optimizer-config/result',
      data: {
        'params': params.toJson(),
        'result': optimization.payload,
        'cheapest_path': cheapestPath.toJson(),
        'pricing_snapshots': {
          for (final entry in pricingSnapshots.entries)
            entry.key.apiValue: entry.value.payload,
        },
        'pricing_timestamps': {
          for (final entry in pricingSnapshots.entries)
            entry.key.apiValue: entry.value.updatedAt.toIso8601String(),
        },
      },
    );
  }

  /// Export pricing data from Optimizer (for snapshotting)
  @override
  Future<PricingExportSnapshot> exportPricing(String provider) async {
    final response = await _dio.get('/optimizer/pricing/export/$provider');
    return PricingExportSnapshot.fromJson(
      _contractMap(response.data, 'pricing_export'),
    );
  }

  // ============================================================
  // Deployer Config Endpoints (Step 3 Section 2)
  // ============================================================

  /// Get deployer config for a twin
  @override
  Future<DeployerConfigData?> getDeployerConfig(String twinId) async {
    try {
      final response = await _dio.get('/twins/$twinId/deployer/config');
      return DeployerConfigData.fromJson(
        _contractMap(response.data, 'deployer_config'),
      );
    } on DioException catch (error) {
      if (error.response?.statusCode == 404) return null;
      rethrow;
    }
  }

  /// Update deployer config for a twin
  @override
  Future<DeployerConfigData> updateDeployerConfig(
    String twinId,
    Map<String, dynamic> config,
  ) async {
    final response = await _dio.put(
      '/twins/$twinId/deployer/config',
      data: config,
    );
    return DeployerConfigData.fromJson(
      _contractMap(response.data, 'deployer_config'),
    );
  }

  @override
  Future<DeployerConfigData> updateDeployerConfigRequest(
    String twinId,
    DeployerConfigUpdateRequest request,
  ) {
    return updateDeployerConfig(twinId, request.toJson());
  }

  /// Validate deployer config via Management API (proxies to Deployer)
  @override
  Future<Map<String, dynamic>> validateDeployerConfig(
    String twinId,
    String configType, // 'config', 'events', or 'iot'
    String content,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/deployer/validate/$configType',
      data: {'content': content},
    );
    return response.data;
  }

  /// Validate L2 function code or state machine (proxies to Deployer)
  /// Returns normalized {valid: bool, message: String}
  @override
  Future<Map<String, dynamic>> validateL2Content(
    String twinId,
    String type, // 'function-code' or 'state-machine'
    String content,
    String provider, // 'aws', 'azure', 'gcp'
  ) async {
    // Map Flutter provider names to Deployer enum values
    final deployerProvider = provider.toLowerCase() == 'gcp'
        ? 'google'
        : provider.toLowerCase();
    final response = await _dio.post(
      '/twins/$twinId/deployer/validate/$type',
      data: {'content': content, 'provider': deployerProvider},
    );
    return response.data;
  }

  /// Validate L4/L5 content (hierarchy, scene-config, user-config)
  /// Returns normalized {valid: bool, message: String}
  @override
  Future<Map<String, dynamic>> validateL4Content(
    String twinId,
    String type, // 'hierarchy', 'scene-config', 'user-config'
    String content,
    String provider, // 'aws', 'azure'
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/deployer/validate/$type',
      data: {'content': content, 'provider': provider.toLowerCase()},
    );
    return response.data;
  }

  // ============================================================
  // GLB File Upload/Delete (L4 Scene)
  // ============================================================

  /// Upload scene.glb file for 3D visualization
  /// Returns {message: String, size_mb: double}
  @override
  Future<Map<String, dynamic>> uploadSceneGlb(
    String twinId,
    Uint8List fileBytes,
    String filename,
  ) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(fileBytes, filename: filename),
    });
    final response = await _dio.post(
      '/twins/$twinId/deployer/upload-glb',
      data: formData,
    );
    return response.data;
  }

  /// Delete scene.glb file for a twin
  @override
  Future<void> deleteSceneGlb(String twinId) async {
    await _dio.delete('/twins/$twinId/deployer/upload-glb');
  }

  // ============================================================
  // Zip Upload and Extraction (Step 3 Auto-Population)
  // ============================================================

  /// Upload project.zip and extract contents for wizard auto-population.
  ///
  /// Returns extracted config files, function code, and assets.
  /// GLB files are automatically saved to the server if present.
  ///
  /// Validation errors are aggregated (not fail-fast) to provide
  /// maximum feedback on first upload.
  @override
  Future<Map<String, dynamic>> uploadProjectZip(
    String twinId,
    Uint8List fileBytes,
    String filename,
  ) async {
    final formData = FormData.fromMap({
      'file': MultipartFile.fromBytes(fileBytes, filename: filename),
    });
    final response = await _dio.post(
      '/twins/$twinId/deployer/upload-zip',
      data: formData,
      options: Options(
        sendTimeout: const Duration(seconds: 120),
        receiveTimeout: const Duration(seconds: 120),
      ),
    );
    return response.data;
  }

  // ============================================================
  // Result-Returning Methods (Type-Safe Error Handling)
  // ============================================================

  /// Calculate costs with structured error handling.
  ///
  /// Returns [Success] with [CalcResult] on success,
  /// or [Failure] with [AppException] on error.
  @override
  Future<Result<CalcResult>> calculateCostsResult(CalcParams params) async {
    try {
      final response = await calculateCosts(params);
      return Success(response.result);
    } on DioException catch (e) {
      return Failure(AppException.fromDioError(e));
    } catch (e) {
      return Failure(
        AppException(
          'Calculation failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  /// Get pricing status with structured error handling.
  @override
  Future<Result<Map<String, dynamic>>> getPricingStatusResult() async {
    try {
      final data = await getPricingStatus();
      return Success(data);
    } on DioException catch (e) {
      return Failure(AppException.fromDioError(e));
    } catch (e) {
      return Failure(
        AppException(
          'Failed to load pricing status: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  /// Get twin config with structured error handling.
  @override
  Future<Result<TwinConfigData>> getTwinConfigResult(String twinId) async {
    try {
      final data = await getTwinConfig(twinId);
      return Success(data);
    } on DioException catch (e) {
      return Failure(AppException.fromDioError(e));
    } catch (e) {
      return Failure(
        AppException(
          'Failed to load twin config: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  // ==========================================================================
  // Deployment Operations
  // ==========================================================================

  @override
  Future<DeploymentReadinessSnapshot> getDeploymentReadiness(
    String twinId,
  ) async {
    final response = await _dio.get('/twins/$twinId/deployment-readiness');
    return DeploymentReadinessSnapshot.fromCachedJson(
      _responseMap(response.data),
      expectedTwinId: twinId,
    );
  }

  @override
  Future<DeploymentReadinessSnapshot> runDeploymentPreflight(
    String twinId,
  ) async {
    final response = await _dio.post('/twins/$twinId/deployment-preflight');
    return DeploymentReadinessSnapshot.fromPreflightJson(
      _responseMap(response.data),
      expectedTwinId: twinId,
    );
  }

  /// Deploy a twin's infrastructure
  @override
  Future<OperationSession> deployTwin(String twinId) async {
    final response = await _dio.post('/twins/$twinId/deploy');
    return OperationSession.fromJson(_responseMap(response.data));
  }

  /// Destroy a twin's infrastructure
  @override
  Future<OperationSession> destroyTwin(String twinId) async {
    final response = await _dio.post('/twins/$twinId/destroy');
    return OperationSession.fromJson(_responseMap(response.data));
  }

  /// Get deployment status (polling fallback)
  @override
  Future<DeploymentStatusSnapshot> getDeploymentStatus(String twinId) async {
    final response = await _dio.get('/twins/$twinId/deployment-status');
    return DeploymentStatusSnapshot.fromJson(_responseMap(response.data));
  }

  /// Get terraform outputs from most recent successful deployment
  @override
  Future<DeploymentOutputsSnapshot> getDeploymentOutputs(String twinId) async {
    final response = await _dio.get('/twins/$twinId/outputs');
    return DeploymentOutputsSnapshot.fromJson(_responseMap(response.data));
  }

  @override
  Future<DeploymentHistory> getDeploymentHistory(
    String twinId, {
    int limit = 10,
  }) async {
    _validateRange('limit', limit, minimum: 1, maximum: 50);
    final response = await _dio.get(
      '/twins/$twinId/deployments',
      queryParameters: {'limit': limit},
    );
    return DeploymentHistory.fromJson(_responseMap(response.data));
  }

  // ==========================================================================
  // SSE Streaming and Logs
  // ==========================================================================

  /// Get full SSE URL for streaming deployment logs
  @override
  String getSseUrl(String sseUrl, {int? lastEventId}) {
    final relative = Uri.tryParse(sseUrl);
    if (relative == null ||
        relative.isAbsolute ||
        !sseUrl.startsWith('/') ||
        sseUrl.startsWith('//') ||
        relative.path != sseUrl ||
        relative.pathSegments.any(
          (segment) => segment == '.' || segment == '..',
        ) ||
        relative.hasQuery ||
        relative.hasFragment) {
      throw const AppException(
        'SSE path must be an absolute-path relative Management API route.',
        code: 'DEPLOYMENT_CONTRACT_INVALID',
      );
    }
    if (lastEventId != null && lastEventId < 0) {
      throw const AppException(
        'SSE cursor cannot be negative.',
        code: 'DEPLOYMENT_CONTRACT_INVALID',
      );
    }
    final base = _baseUri.resolveUri(relative);
    if (lastEventId != null && lastEventId > 0) {
      return base
          .replace(queryParameters: {'last_event_id': lastEventId.toString()})
          .toString();
    }
    return base.toString();
  }

  /// Get deployment logs from database (for catchup after reconnection)
  @override
  Future<DeploymentLogPage> getDeploymentLogs(
    String twinId, {
    String? sessionId,
    int? afterEventId,
    int limit = 100,
  }) async {
    _validateRange('limit', limit, minimum: 1, maximum: 500);
    if (afterEventId != null) {
      _validateRange('afterEventId', afterEventId, minimum: 0);
    }
    if (sessionId != null && sessionId.trim().isEmpty) {
      throw const AppException(
        'sessionId must be a non-empty string when provided.',
        code: 'DEPLOYMENT_REQUEST_INVALID',
      );
    }
    final queryParams = <String, dynamic>{'limit': limit};
    if (sessionId != null) queryParams['session_id'] = sessionId;
    if (afterEventId != null) queryParams['after_event_id'] = afterEventId;

    final response = await _dio.get(
      '/twins/$twinId/logs',
      queryParameters: queryParams,
    );
    return DeploymentLogPage.fromJson(_responseMap(response.data));
  }

  // ==========================================================================
  // Log Trace (Live Log Tracing)
  // ==========================================================================

  /// Start a log trace test for a deployed twin
  ///
  /// Sends a test IoT message with a unique trace_id and returns
  /// the trace_id for SSE streaming.
  ///
  @override
  Future<LogTraceStartResult> startLogTrace(String twinId) async {
    final response = await _dio.post('/twins/$twinId/log-trace/start');
    return LogTraceStartResult.fromJson(_responseMap(response.data));
  }

  // ==========================================================================
  // Deployment Verification
  // ==========================================================================

  /// Run structured infrastructure verification (L0-L5 checks)
  /// Returns {checks: List, summary: {pass_count, fail_count, skip_count, total, healthy}}
  @override
  Future<Map<String, dynamic>> verifyInfrastructure(String twinId) async {
    final response = await _dio.post(
      '/twins/$twinId/verify/infrastructure',
      options: Options(receiveTimeout: const Duration(seconds: 60)),
    );
    return response.data as Map<String, dynamic>;
  }

  /// Start data flow verification with SSE streaming.
  /// Returns {session_id, sse_url} for connecting to SSE.
  @override
  Future<Map<String, dynamic>> verifyDataFlow(
    String twinId,
    Map<String, dynamic> payload,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/verify/dataflow',
      data: {'payload': payload},
      options: Options(receiveTimeout: const Duration(seconds: 30)),
    );
    return response.data as Map<String, dynamic>;
  }

  /// Download IoT simulator package (L1 provider determined by backend).
  @override
  Future<BinaryDownload> downloadSimulator(String twinId) async {
    final response = await _dio.get(
      '/twins/$twinId/simulator/download',
      options: Options(
        responseType: ResponseType.bytes,
        receiveTimeout: const Duration(seconds: 60),
      ),
    );
    final data = response.data;
    final bytes = switch (data) {
      Uint8List value => value,
      List<int> value => Uint8List.fromList(value),
      _ => throw const AppException(
        'Simulator response was not a binary archive.',
        code: 'DEPLOYMENT_CONTRACT_INVALID',
      ),
    };
    final contentDisposition = response.headers.value('content-disposition');
    return BinaryDownload(
      bytes: bytes,
      filename: _attachmentFilename(contentDisposition),
      mediaType:
          response.headers.value(Headers.contentTypeHeader) ??
          'application/zip',
    );
  }
}

Map<String, dynamic> _responseMap(Object? value) {
  if (value is! Map) {
    throw const AppException(
      'Management API returned an invalid deployment response.',
      code: 'DEPLOYMENT_CONTRACT_INVALID',
    );
  }
  return Map<String, dynamic>.from(value);
}

Map<String, dynamic> _contractMap(Object? value, String field) {
  if (value is! Map) {
    throw FormatException('Invalid API contract: $field must be an object.');
  }
  return Map<String, dynamic>.from(value);
}

String _attachmentFilename(String? contentDisposition) {
  if (contentDisposition == null) {
    throw const AppException(
      'Simulator response did not include a filename.',
      code: 'DEPLOYMENT_CONTRACT_INVALID',
    );
  }
  final match = RegExp(
    r'(?:^|;)\s*filename\s*=\s*(?:"([^"]+)"|([^;\s]+))',
    caseSensitive: false,
  ).firstMatch(contentDisposition);
  final filename = match?.group(1) ?? match?.group(2);
  if (filename == null || filename.trim().isEmpty) {
    throw const AppException(
      'Simulator response contained an invalid filename.',
      code: 'DEPLOYMENT_CONTRACT_INVALID',
    );
  }
  return filename;
}

void _validateRange(
  String field,
  int value, {
  required int minimum,
  int? maximum,
}) {
  if (value < minimum || (maximum != null && value > maximum)) {
    final range = maximum == null
        ? 'at least $minimum'
        : 'between $minimum and $maximum';
    throw AppException(
      '$field must be $range.',
      code: 'DEPLOYMENT_REQUEST_INVALID',
    );
  }
}
