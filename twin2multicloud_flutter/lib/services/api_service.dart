import 'dart:typed_data';

import 'package:dio/dio.dart';
import '../core/result.dart';
import '../models/architecture_profile.dart';
import '../models/calc_params.dart';
import '../models/authentication.dart';
import '../models/cloud_connection.dart';
import '../models/deployment_access.dart';
import '../models/deployment_operations.dart';
import '../models/deployment_readiness.dart';
import '../models/deployment_verification.dart';
import '../models/deployer_config.dart';
import '../models/optimizer_config.dart';
import '../models/provider_capability.dart';
import '../models/resolved_deployment_specification.dart';
import '../models/resolved_twin_architecture.dart';
import '../models/twin.dart';
import '../models/twin_config.dart';
import '../models/twin_transfer.dart';
import '../models/user_function_extension.dart';
import '../models/user.dart';
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

String _managementPathSegment(String value, String label) {
  if (value.isEmpty || RegExp(r'[\x00-\x1F\x7F]').hasMatch(value)) {
    throw AppException(
      '$label must be a non-empty opaque identifier.',
      code: 'DEPLOYMENT_REQUEST_INVALID',
    );
  }
  return Uri.encodeComponent(value);
}

class ApiService implements ManagementApi {
  final Dio _dio;
  late final Uri _baseUri;
  String? _token;
  void Function()? _unauthorizedHandler;

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
        onError: (error, handler) {
          if (error.response?.statusCode == 401 && _token != null) {
            _token = null;
            _unauthorizedHandler?.call();
          }
          return handler.next(error);
        },
      ),
    );
  }

  @override
  void setToken(String? token) => _token = _normalizeToken(token);

  @override
  void setUnauthorizedHandler(void Function()? handler) {
    _unauthorizedHandler = handler;
  }

  /// Get current auth token for SSE connections
  @override
  Future<String?> getAuthToken() async => _token;

  @override
  Future<List<AuthProviderCapability>> getAuthProviders() async {
    final response = await _dio.get('/auth/providers');
    final body = _contractMap(response.data, 'auth providers');
    final providers = body['providers'];
    if (providers is! List) {
      throw const FormatException(
        'Invalid API contract: auth providers must be an array.',
      );
    }
    return List<AuthProviderCapability>.unmodifiable(
      providers.indexed.map(
        (entry) => AuthProviderCapability.fromJson(
          _contractMap(entry.$2, 'auth providers[${entry.$1}]'),
        ),
      ),
    );
  }

  @override
  Future<AuthLoginTransaction> startExternalLogin(
    IdentityProvider provider,
  ) async {
    final response = await _dio.post(
      '/auth/providers/${provider.apiValue}/login',
    );
    return AuthLoginTransaction.fromJson(
      _contractMap(response.data, 'authentication start'),
    );
  }

  @override
  Future<AuthExchangeResult> exchangeAuthSession(
    AuthLoginTransaction transaction,
  ) async {
    final response = await _dio.post(
      '/auth/session/exchange',
      data: transaction.toCommandJson(),
    );
    return AuthExchangeResult.fromJson(
      _contractMap(response.data, 'authentication exchange'),
    );
  }

  @override
  Future<void> cancelAuthSession(AuthLoginTransaction transaction) async {
    await _dio.post('/auth/session/cancel', data: transaction.toCommandJson());
  }

  @override
  Future<void> logoutSession() async {
    await _dio.post('/auth/logout');
  }

  @override
  Future<User> getCurrentUser() async {
    final response = await _dio.get('/auth/me');
    return User.fromJson(_contractMap(response.data, 'current user'));
  }

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
  Future<CloudConnection> importCloudConnection(
    CloudConnectionImportRequest request,
  ) async {
    final response = await _dio.post(
      '/cloud-connections/import',
      data: FormData.fromMap({
        'metadata': request.metadataJson,
        'file': MultipartFile.fromBytes(
          request.bytes,
          filename: request.filename,
        ),
      }),
    );
    return CloudConnection.fromJson(
      _contractMap(response.data, 'cloud connection import'),
    );
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
  Future<List<ExtensionSlot>> listExtensionSlots() async {
    final response = await _dio.get('/architecture/extension-slots');
    final body = _contractMap(response.data, 'extension slots');
    _requireContractFields(body, const {
      'schema_version',
      'slots',
    }, 'extension slots');
    if (body['schema_version'] != 'user-function-extension-slot-list.v1') {
      throw const FormatException(
        'Unsupported extension-slot list schema version.',
      );
    }
    final slots = body['slots'];
    if (slots is! List) {
      throw const FormatException(
        'Invalid API contract: extension slots must be an array.',
      );
    }
    return List.unmodifiable(
      slots.indexed.map(
        (entry) => ExtensionSlot.fromJson(
          _contractMap(entry.$2, 'extension slots[${entry.$1}]'),
        ),
      ),
    );
  }

  @override
  Future<UserFunctionValidationResult> validateUserFunctionArtifact(
    UserFunctionArtifactUpload upload,
  ) async {
    final response = await _dio.post(
      '/user-function-artifacts/validate',
      data: _extensionMultipart(upload),
      options: Options(contentType: 'multipart/form-data'),
    );
    return UserFunctionValidationResult.fromJson(
      _contractMap(response.data, 'user-function validation'),
    );
  }

  @override
  Future<UserFunctionArtifact> createUserFunctionArtifact(
    UserFunctionArtifactUpload upload,
  ) async {
    final response = await _dio.post(
      '/user-function-artifacts',
      data: _extensionMultipart(upload),
      options: Options(contentType: 'multipart/form-data'),
    );
    return UserFunctionArtifact.fromJson(
      _contractMap(response.data, 'user-function artifact'),
    );
  }

  @override
  Future<List<UserFunctionArtifact>> listUserFunctionArtifacts() async {
    final response = await _dio.get('/user-function-artifacts');
    final body = _contractMap(response.data, 'user-function artifacts');
    _requireContractFields(body, const {
      'schema_version',
      'items',
      'total',
      'limit',
      'offset',
    }, 'user-function artifacts');
    if (body['schema_version'] != 'user-function-artifact-list.v1') {
      throw const FormatException(
        'Unsupported user-function artifact list schema version.',
      );
    }
    final items = body['items'];
    if (items is! List) {
      throw const FormatException(
        'Invalid API contract: user-function artifacts must be an array.',
      );
    }
    return List.unmodifiable(
      items.indexed.map(
        (entry) => UserFunctionArtifact.fromJson(
          _contractMap(entry.$2, 'user-function artifacts[${entry.$1}]'),
        ),
      ),
    );
  }

  @override
  Future<List<TwinExtensionBinding>> listTwinExtensionBindings(
    String twinId,
  ) async {
    final response = await _dio.get('/twins/$twinId/extension-bindings');
    final body = _contractMap(response.data, 'extension bindings');
    _requireContractFields(body, const {
      'schema_version',
      'items',
    }, 'extension bindings');
    if (body['schema_version'] != 'twin-extension-binding-list.v1') {
      throw const FormatException(
        'Unsupported extension-binding list schema version.',
      );
    }
    final items = body['items'];
    if (items is! List) {
      throw const FormatException(
        'Invalid API contract: extension bindings must be an array.',
      );
    }
    return List.unmodifiable(
      items.indexed.map(
        (entry) => TwinExtensionBinding.fromJson(
          _contractMap(entry.$2, 'extension bindings[${entry.$1}]'),
        ),
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
    final response = await _dio.put(
      '/twins/$twinId/extension-bindings/${slot.slotId}',
      data: {
        'artifact_id': artifactId,
        'slot_version': slot.slotVersion,
        if (expectedRevision != null) 'expected_revision': expectedRevision,
      },
    );
    return TwinExtensionBinding.fromJson(
      _contractMap(response.data, 'extension binding'),
    );
  }

  @override
  Future<void> unbindTwinExtensionArtifact(
    String twinId,
    ExtensionSlot slot, {
    int? expectedRevision,
  }) async {
    await _dio.delete(
      '/twins/$twinId/extension-bindings/${slot.slotId}',
      queryParameters: {
        'slot_version': slot.slotVersion,
        if (expectedRevision != null) 'expected_revision': expectedRevision,
      },
    );
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
    if (data.length > 32) {
      throw const FormatException(
        'Invalid API contract: architecture profile catalog is too large.',
      );
    }
    return List<Twin>.unmodifiable(
      data.indexed.map(
        (entry) => Twin.fromJson(_contractMap(entry.$2, 'twins[${entry.$1}]')),
      ),
    );
  }

  @override
  Future<PlatformProviderCapabilities> getProviderCapabilities() async {
    final response = await _dio.get('/platform/provider-capabilities');
    return PlatformProviderCapabilities.fromJson(
      _contractMap(response.data, 'platform provider capabilities'),
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
  Future<Twin> duplicateTwin(
    String twinId,
    TwinDuplicateRequest request,
  ) async {
    final id = _managementPathSegment(twinId, 'Twin ID');
    final response = await _dio.post(
      '/twins/$id/duplicate',
      data: request.toJson(),
    );
    return Twin.fromJson(_contractMap(response.data, 'duplicated twin'));
  }

  @override
  Future<Twin> importTwin(TwinImportRequest request) async {
    final response = await _dio.post(
      '/twins/import',
      data: FormData.fromMap({
        'new_name': request.newName,
        'archive': MultipartFile.fromBytes(
          request.bytes,
          filename: request.filename,
        ),
      }),
    );
    return Twin.fromJson(_contractMap(response.data, 'imported twin'));
  }

  @override
  Future<PortableTwinDownload> exportTwin(String twinId) async {
    final id = _managementPathSegment(twinId, 'Twin ID');
    final response = await _dio.get(
      '/twins/$id/export',
      options: Options(
        responseType: ResponseType.bytes,
        receiveTimeout: const Duration(seconds: 60),
      ),
    );
    final bytes = switch (response.data) {
      Uint8List value => value,
      List<int> value => Uint8List.fromList(value),
      _ => throw const FormatException(
        'Invalid portable Twin contract: response must be binary.',
      ),
    };
    return PortableTwinDownload(
      filename: _attachmentFilename(
        response.headers.value('content-disposition'),
      ),
      mediaType:
          response.headers.value(Headers.contentTypeHeader) ??
          PortableTwinDownload.mediaTypeZip,
      bytes: bytes,
    );
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

  @override
  Future<ArchitectureProfileDetail> getArchitectureProfile(
    String profileId,
    String profileVersion,
  ) async {
    final response = await _dio.get(
      '/architecture-profiles/$profileId/versions/$profileVersion',
    );
    final detail = ArchitectureProfileDetail.fromJson(
      _contractMap(response.data, 'architecture profile detail'),
    );
    if (detail.summary.profileId != profileId ||
        detail.summary.profileVersion != profileVersion) {
      throw const FormatException(
        'Invalid API contract: architecture profile identity differs.',
      );
    }
    return detail;
  }

  @override
  Future<TwinArchitectureSelection> getTwinArchitectureSelection(
    String twinId,
  ) async {
    final response = await _dio.get('/twins/$twinId/architecture-profile');
    final selection = TwinArchitectureSelection.fromJson(
      _contractMap(response.data, 'Twin architecture selection'),
    );
    if (selection.twinId != twinId) {
      throw const FormatException(
        'Invalid API contract: architecture selection Twin differs.',
      );
    }
    return selection;
  }

  @override
  Future<ResolvedTwinArchitectureRead> getSelectedResolvedArchitecture(
    String twinId,
  ) async {
    final response = await _dio.get('/twins/$twinId/resolved-architecture');
    final resolved = ResolvedTwinArchitectureRead.fromJson(
      _contractMap(response.data, 'selected resolved architecture'),
    );
    if (resolved.twinId != twinId) {
      throw const FormatException(
        'Invalid API contract: resolved architecture Twin differs.',
      );
    }
    return resolved;
  }

  @override
  Future<ResolvedTwinArchitectureRead> getRunResolvedArchitecture(
    String runId,
  ) async {
    final response = await _dio.get(
      '/optimizer-runs/$runId/resolved-architecture',
    );
    final resolved = ResolvedTwinArchitectureRead.fromJson(
      _contractMap(response.data, 'run resolved architecture'),
    );
    if (resolved.calculationRunId != runId) {
      throw const FormatException(
        'Invalid API contract: resolved architecture run differs.',
      );
    }
    return resolved;
  }

  /// Run, validate, and persist one optimizer calculation through Management.
  @override
  Future<OptimizerRunData> createOptimizerRun(
    String twinId,
    CalcParams params,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/optimizer-runs/',
      data: {'params': params.toJson()},
    );
    final run = OptimizerRunData.fromJson(
      _contractMap(response.data, 'optimizer run'),
    );
    if (run.twinId != twinId || run.currency != params.currency) {
      throw const FormatException(
        'Invalid API contract: optimizer run request context is inconsistent.',
      );
    }
    return run;
  }

  @override
  Future<OptimizerDeploymentRunData?> getLatestOptimizerRun(
    String twinId,
  ) async {
    final listResponse = await _dio.get('/twins/$twinId/optimizer-runs/');
    final rawSummaries = listResponse.data;
    if (rawSummaries is! List) {
      throw const FormatException(
        'Invalid API contract: optimizer runs must be an array.',
      );
    }
    final summaries = rawSummaries.indexed
        .map(
          (entry) => OptimizerRunSummaryData.fromJson(
            _contractMap(entry.$2, 'optimizer runs[${entry.$1}]'),
          ),
        )
        .toList(growable: false);
    if (summaries.any((summary) => summary.twinId != twinId) ||
        summaries.map((summary) => summary.id).toSet().length !=
            summaries.length) {
      throw const FormatException(
        'Invalid API contract: optimizer run collection identity is inconsistent.',
      );
    }
    if (summaries
            .where((summary) => summary.selectedForDeploymentAt != null)
            .length >
        1) {
      throw const FormatException(
        'Invalid API contract: multiple optimizer runs are selected for deployment.',
      );
    }
    if (summaries.isEmpty) return null;

    final ordered = [...summaries]
      ..sort((left, right) {
        final timestamp = right.createdAt.compareTo(left.createdAt);
        return timestamp != 0 ? timestamp : right.id.compareTo(left.id);
      });
    final latest = ordered.first;
    final detailResponse = await _dio.get(
      '/twins/$twinId/optimizer-runs/${latest.id}',
    );
    final detail = OptimizerDeploymentRunData.fromDetailJson(
      _contractMap(detailResponse.data, 'optimizer run detail'),
    );
    if (detail.summary != latest) {
      throw const FormatException(
        'Invalid API contract: optimizer run list and detail differ.',
      );
    }
    return detail;
  }

  @override
  Future<OptimizerRunSelectionData> selectOptimizerRunForDeployment(
    String twinId,
    String runId,
  ) async {
    final response = await _dio.post(
      '/twins/$twinId/optimizer-runs/$runId/select-for-deployment',
    );
    final selection = OptimizerRunSelectionData.fromJson(
      _contractMap(response.data, 'optimizer run selection'),
    );
    if (selection.run.twinId != twinId || selection.run.id != runId) {
      throw const FormatException(
        'Invalid API contract: optimizer run selection context is inconsistent.',
      );
    }
    return selection;
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
  Future<DeploymentAccessSnapshot> getDeploymentAccess(String twinId) async {
    final twinPath = _managementPathSegment(twinId, 'Twin ID');
    final response = await _dio.get('/twins/$twinPath/deployment-access');
    return DeploymentAccessSnapshot.fromJson(
      _responseMap(response.data),
      expectedTwinId: twinId,
    );
  }

  @override
  Future<DeploymentAccessCredential> rotateGcpGrafanaViewerCredential(
    String twinId,
  ) async {
    final twinPath = _managementPathSegment(twinId, 'Twin ID');
    final response = await _dio.post(
      '/twins/$twinPath/deployment-access/l5/credentials:rotate',
    );
    return DeploymentAccessCredential.fromJson(_responseMap(response.data));
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

  /// Run structured infrastructure verification for the selected architecture.
  /// Returns {checks: List, summary: {pass_count, fail_count, skip_count, total, healthy}}
  @override
  Future<Map<String, dynamic>> verifyInfrastructure(String twinId) async {
    final response = await _dio.post(
      '/twins/$twinId/verify/infrastructure',
      options: Options(receiveTimeout: const Duration(seconds: 60)),
    );
    return response.data as Map<String, dynamic>;
  }

  /// Start one persisted data-flow verification with SSE streaming.
  @override
  Future<TelemetryVerificationStart> verifyDataFlow(
    String twinId,
    Map<String, dynamic> payload,
  ) async {
    final id = _managementPathSegment(twinId, 'Twin ID');
    final response = await _dio.post(
      '/twins/$id/verify/dataflow',
      data: {'payload': payload},
      options: Options(receiveTimeout: const Duration(seconds: 30)),
    );
    return TelemetryVerificationStart.fromJson(
      _contractMap(response.data, 'telemetry verification session'),
    );
  }

  @override
  Future<TelemetryVerificationHistory> listDataFlowVerifications(
    String twinId, {
    int limit = 25,
  }) async {
    _validateRange(
      'Telemetry verification history limit',
      limit,
      minimum: 1,
      maximum: 25,
    );
    final id = _managementPathSegment(twinId, 'Twin ID');
    final response = await _dio.get(
      '/twins/$id/verify/dataflow',
      queryParameters: {'limit': limit},
    );
    return TelemetryVerificationHistory.fromJson(
      _contractMap(response.data, 'telemetry verification history'),
    );
  }

  @override
  Future<TelemetryVerificationRecord> getDataFlowVerification(
    String twinId,
    String verificationId,
  ) async {
    final id = _managementPathSegment(twinId, 'Twin ID');
    final recordId = _managementPathSegment(
      verificationId,
      'Telemetry verification ID',
    );
    final response = await _dio.get('/twins/$id/verify/dataflow/$recordId');
    return TelemetryVerificationRecord.fromJson(
      _contractMap(response.data, 'telemetry verification record'),
    );
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

FormData _extensionMultipart(UserFunctionArtifactUpload upload) {
  return FormData.fromMap({
    'metadata': MultipartFile.fromBytes(
      upload.metadataBytes,
      filename: 'metadata.json',
    ),
    'source_archive': MultipartFile.fromBytes(
      upload.draft.bytes,
      filename: upload.draft.filename,
    ),
  });
}

Map<String, dynamic> _contractMap(Object? value, String field) {
  if (value is! Map) {
    throw FormatException('Invalid API contract: $field must be an object.');
  }
  return Map<String, dynamic>.from(value);
}

void _requireContractFields(
  Map<String, dynamic> value,
  Set<String> expected,
  String contract,
) {
  if (value.keys.toSet().difference(expected).isNotEmpty ||
      expected.difference(value.keys.toSet()).isNotEmpty) {
    throw FormatException(
      'Invalid API contract: $contract fields do not match v1.',
    );
  }
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
