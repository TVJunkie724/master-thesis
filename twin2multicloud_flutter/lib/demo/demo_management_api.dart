import 'dart:convert';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';

import '../core/result.dart';
import '../models/architecture_profile.dart';
import '../models/calc_params.dart';
import '../models/authentication.dart';
import '../models/cloud_access_inventory.dart';
import '../models/cloud_bootstrap.dart';
import '../models/cloud_connection.dart';
import '../models/dashboard_stats.dart';
import '../models/deployment_access.dart';
import '../models/deployment_operations.dart';
import '../models/deployment_readiness.dart';
import '../models/deployer_config.dart';
import '../models/optimizer_config.dart';
import '../models/pricing_candidate_review.dart';
import '../models/pricing_catalog.dart';
import '../models/pricing_health.dart';
import '../models/pricing_refresh_run.dart';
import '../models/provider_capability.dart';
import '../models/resolved_deployment_specification.dart';
import '../models/resolved_twin_architecture.dart';
import '../models/twin.dart';
import '../models/twin_config.dart';
import '../models/user_function_extension.dart';
import '../models/user.dart';
import '../models/wizard_config_requests.dart';
import '../services/management_api.dart';
import 'demo_fixture_store.dart';

class DemoManagementApi implements ManagementApi {
  static const double _fiveLayerV2EurPerUsd = 0.865948;

  final DemoFixtureStore store;
  final Duration latency;
  String? _token = 'demo-token';
  final List<Map<String, dynamic>> _decisions = [];
  final Map<String, Map<String, dynamic>> _deploymentReadinessCache = {};
  final List<UserFunctionArtifact> _extensionArtifacts = [];
  final Map<String, TwinExtensionBinding> _extensionBindings = {};
  final Map<String, Map<String, dynamic>> _bootstrapSessions = {};
  final Map<String, ResolvedTwinArchitectureRead> _resolvedArchitectures = {};
  final Map<String, TwinArchitectureSelection> _architectureSelections = {};

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
  Future<List<ArchitectureProfileSummary>> listArchitectureProfiles() async {
    await _pause();
    return [
      for (final profile in const [
        ('five-layer-baseline', '2'),
        ('six-layer-eventing', '1'),
      ])
        ArchitectureProfileSummary.fromJson(
          _architectureProfileSummaryJson(profile.$1, profile.$2),
        ),
    ];
  }

  @override
  Future<ArchitectureProfileDetail> getArchitectureProfile(
    String profileId,
    String profileVersion,
  ) async {
    await _pause();
    store.architectureProfile(profileId, profileVersion);
    return ArchitectureProfileDetail.fromJson(
      _architectureProfileDetailJson(profileId, profileVersion),
    );
  }

  @override
  Future<TwinArchitectureSelection> getTwinArchitectureSelection(
    String twinId,
  ) async {
    await _pause();
    final existing = _architectureSelections[twinId];
    if (existing != null) return existing;
    final twin = store.twin(twinId);
    final selectedAt = DateTime.parse(twin['created_at'].toString()).toUtc();
    final updatedAt = DateTime.parse(twin['updated_at'].toString()).toUtc();
    final profile = store.fiveLayerV2Profile();
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
  Future<ArchitectureProfileChangePreview> previewTwinArchitectureProfileChange(
    String twinId,
    ArchitectureProfileChangePreviewRequest request,
  ) async {
    await _pause();
    store.twin(twinId);
    final current = await getTwinArchitectureSelection(twinId);
    final target = _profileReference(request.profileId, request.profileVersion);
    if (request.expectedRevision != current.revision) {
      throw const DemoApiException(
        'ARCH_SELECTION_REVISION_CONFLICT',
        'The architecture selection revision is stale.',
      );
    }
    return ArchitectureProfileChangePreview.fromJson(
      _architecturePreviewJson(current, target),
    );
  }

  @override
  Future<ArchitectureProfileSelectionResult> selectTwinArchitectureProfile(
    String twinId,
    ArchitectureProfileSelectRequest request,
  ) async {
    await _pause();
    store.twin(twinId);
    final current = await getTwinArchitectureSelection(twinId);
    final target = _profileReference(request.profileId, request.profileVersion);
    final preview = _architecturePreviewJson(current, target);
    if (request.expectedRevision != current.revision) {
      throw const DemoApiException(
        'ARCH_SELECTION_REVISION_CONFLICT',
        'The architecture selection revision is stale.',
      );
    }
    if (request.invalidationDigest != preview['invalidation_digest']) {
      throw const DemoApiException(
        'ARCH_SELECTION_INVALIDATION_STALE',
        'The profile-change preview is stale.',
      );
    }
    final unchanged = current.profileRef == target;
    final now = store.clock().toUtc();
    final selection = unchanged
        ? current
        : TwinArchitectureSelection(
            twinId: twinId,
            profileRef: target,
            revision: current.revision + 1,
            selectedAt: now,
            updatedAt: now,
            selectedByUserId: store.user['id'].toString(),
          );
    _architectureSelections[twinId] = selection;
    return ArchitectureProfileSelectionResult.fromJson({
      'selection': _architectureSelectionJson(selection),
      'revision': selection.revision,
      'invalidated_calculation_run_id': null,
      'unbound_extension_slot_ids': <String>[],
      'cleared_workload_field_ids': <String>[],
      'deployment_readiness_state': 'unchanged',
    });
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
  Future<CloudBootstrapGuide> getCloudBootstrapGuide(
    CloudProvider provider,
    CloudBootstrapTarget target,
  ) async {
    await _pause();
    if (provider != target.provider) {
      throw const DemoApiException(
        'BOOTSTRAP_TARGET_INVALID',
        'Bootstrap provider and target must match.',
      );
    }
    return CloudBootstrapGuide.fromJson(_demoBootstrapGuide(provider, target));
  }

  @override
  Future<CloudBootstrapSession> createCloudBootstrapSession({
    required CloudBootstrapGuide guide,
    required CloudBootstrapEntryPoint entryPoint,
    required String displayName,
    String? twinId,
    required String idempotencyKey,
  }) async {
    await _pause();
    final replay = _bootstrapSessions.values.where(
      (item) => item['_idempotency_key'] == idempotencyKey,
    );
    if (replay.isNotEmpty) {
      return CloudBootstrapSession.fromJson(
        _demoBootstrapResponse(replay.first),
      );
    }
    final existing = _bootstrapSessions.values.where(
      (item) =>
          item['provider'] == guide.provider.apiValue &&
          item['target'].toString() == guide.target.toJson().toString() &&
          !{'ready', 'failed', 'cancelled', 'expired'}.contains(item['state']),
    );
    if (existing.isNotEmpty) {
      return CloudBootstrapSession.fromJson(
        _demoBootstrapResponse(existing.first),
      );
    }
    if (entryPoint == CloudBootstrapEntryPoint.twinPrepare) {
      if (twinId == null) {
        throw const DemoApiException(
          'BOOTSTRAP_TWIN_REQUIRED',
          'Prepare deployment requires a Twin.',
        );
      }
      store.twin(twinId);
    }
    final sequence = store.nextId('bootstrap').hashCode.abs().toString();
    final id =
        '00000000-0000-4000-8000-${sequence.padLeft(12, '0').substring(0, 12)}';
    final now = store.clock().toUtc().toIso8601String();
    final session = <String, dynamic>{
      'schema_version': 'cloud-bootstrap-session.v1',
      'id': id,
      'provider': guide.provider.apiValue,
      'target': guide.target.toJson(),
      'entry_point': entryPoint.apiValue,
      if (twinId != null) 'twin_id': twinId,
      'display_name': displayName,
      'revision': 1,
      'state': 'draft',
      'guide_digest': guide.guideDigest,
      'bootstrap_authority_pack': _demoBootstrapPack(
        guide.provider,
        authority: true,
        detailed: false,
      ),
      'generated_deployment_pack': _demoBootstrapPack(
        guide.provider,
        authority: false,
        detailed: false,
      ),
      'command_permissions': ['execute', 'cancel'],
      'created_at': now,
      'updated_at': now,
      '_idempotency_key': idempotencyKey,
    };
    _bootstrapSessions[id] = session;
    return CloudBootstrapSession.fromJson(_demoBootstrapResponse(session));
  }

  @override
  Future<List<CloudBootstrapSession>> listCloudBootstrapSessions({
    CloudProvider? provider,
    bool active = true,
  }) async {
    await _pause();
    final terminal = {'ready', 'failed', 'cancelled', 'expired'};
    return _bootstrapSessions.values
        .where(
          (item) =>
              (provider == null || item['provider'] == provider.apiValue) &&
              (active
                  ? !terminal.contains(item['state'])
                  : terminal.contains(item['state'])),
        )
        .map(
          (item) =>
              CloudBootstrapSession.fromJson(_demoBootstrapResponse(item)),
        )
        .toList(growable: false);
  }

  @override
  Future<CloudBootstrapSession> getCloudBootstrapSession(
    String sessionId,
  ) async {
    await _pause();
    return _demoBootstrapSession(sessionId);
  }

  @override
  Future<CloudBootstrapSession> executeCloudBootstrapSession(
    String sessionId,
    CloudBootstrapExecuteRequest request,
  ) async {
    await _pause();
    final session = _bootstrapSessions[sessionId];
    if (session == null) {
      request.dispose();
      throw const DemoApiException(
        'BOOTSTRAP_SESSION_NOT_FOUND',
        'Bootstrap session was not found.',
      );
    }
    late final Map<String, dynamic> command;
    try {
      command = request.takeJson();
    } finally {
      request.dispose();
    }
    final expectedRevision = command['expected_revision'];
    final idempotencyKey = command['idempotency_key']?.toString();
    final origin = command['credential_origin'].toString();
    final submittedCredential = command['credential'];
    if (session['_execute_idempotency_key'] == idempotencyKey) {
      if (submittedCredential is Map) submittedCredential.clear();
      command.clear();
      return _demoBootstrapSession(sessionId);
    }
    if (expectedRevision != session['revision']) {
      if (submittedCredential is Map) submittedCredential.clear();
      command.clear();
      throw const DemoApiException(
        'BOOTSTRAP_SESSION_CONFLICT',
        'Bootstrap session changed; check the latest result.',
      );
    }
    if (!(session['command_permissions'] as List).contains('execute') ||
        submittedCredential is! Map) {
      if (submittedCredential is Map) submittedCredential.clear();
      command.clear();
      throw const DemoApiException(
        'BOOTSTRAP_SESSION_CONFLICT',
        'Bootstrap execution is no longer available.',
      );
    }
    final provider = CloudProvider.fromApiValue(session['provider'].toString());
    final credential = Map<String, dynamic>.from(submittedCredential);
    final target = Map<String, dynamic>.from(session['target'] as Map);
    final safeIdentifier = _demoBootstrapSafeIdentifier(
      provider,
      target,
      credential,
    );
    final failure = _demoBootstrapCredentialFailure(
      provider,
      target,
      credential,
    );
    final manualCleanup = _demoBootstrapNeedsManualCleanup(
      provider,
      target,
      safeIdentifier,
    );
    final hasProviderExpiry =
        provider == CloudProvider.aws &&
        credential['session_token'] != null &&
        target['session_expires_at'] != null;
    submittedCredential.clear();
    credential.clear();
    command.clear();
    session['_execute_idempotency_key'] = idempotencyKey;
    if (failure != null) {
      final now = store.clock().toUtc().toIso8601String();
      session
        ..['revision'] = (session['revision'] as int) + 2
        ..['state'] = 'credential_reentry_required'
        ..['credential_origin'] = origin
        ..['disposal_status'] = 'released_after_failure'
        ..['safe_credential_identifier'] = safeIdentifier
        ..['finding'] = {
          'code': 'BOOTSTRAP_CREDENTIAL_INVALID',
          'severity': 'error',
          'title': 'Bootstrap could not complete',
          'message': failure,
          'blocking': true,
          'action': 'Review the target and explicitly re-enter the credential.',
        }
        ..['command_permissions'] = ['execute', 'cancel']
        ..['updated_at'] = now;
      return _demoBootstrapSession(sessionId);
    }
    final connectionId = store.nextId('demo-${provider.apiValue}-bootstrap');
    final now = store.clock().toUtc().toIso8601String();
    final connection = <String, dynamic>{
      'id': connectionId,
      'provider': provider.apiValue,
      'purpose': 'deployment',
      'scope': 'user',
      'is_default_for_pricing': false,
      'display_name': session['display_name'],
      'auth_type': _defaultAuthType(provider),
      'permission_set_version': 'thesis-demo-v2',
      'cloud_scope': Map<String, dynamic>.from(session['target'] as Map)
        ..remove('provider'),
      'payload_fingerprint': '$connectionId-fingerprint',
      'payload_summary': {'generated_by': 'demo_bootstrap'},
      'validation_status': 'valid',
      'validation_message': 'Demo bootstrap validation passed.',
      'last_validated_at': now,
      'last_used_at': null,
      'created_at': now,
      'updated_at': now,
    };
    store.addCloudConnection(connection);
    final disposable = origin == 'dedicated_disposable';
    final disposalStatus = !disposable
        ? 'not_retained_user_managed'
        : hasProviderExpiry
        ? 'expires_at_provider'
        : manualCleanup
        ? 'manual_revocation_required'
        : 'revoked';
    session
      ..['revision'] = (session['revision'] as int) + 2
      ..['state'] = disposalStatus == 'manual_revocation_required'
          ? 'manual_revocation_required'
          : 'ready'
      ..['credential_origin'] = origin
      ..['disposal_status'] = disposalStatus
      ..['safe_credential_identifier'] = safeIdentifier
      ..['credential_expires_at'] = hasProviderExpiry
          ? target['session_expires_at']
          : null
      ..['finding'] = disposalStatus == 'manual_revocation_required'
          ? {
              'code': 'BOOTSTRAP_MANUAL_REVOCATION_REQUIRED',
              'severity': 'error',
              'title': 'Manual credential cleanup required',
              'message':
                  'Provider-side deletion of the displayed temporary credential was not durably confirmed.',
              'blocking': true,
              'action':
                  'Delete the displayed credential in the provider console, then acknowledge the cleanup.',
              'remediation_url': _demoBootstrapRemediationUrl(provider),
            }
          : null
      ..['connection'] = {
        'id': connectionId,
        'provider': provider.apiValue,
        'purpose': 'deployment',
        'display_name': session['display_name'],
        'cloud_scope': connection['cloud_scope'],
        'permission_set_version': 'thesis-demo-v2',
        'validation_status': 'valid',
      }
      ..['command_permissions'] = disposalStatus == 'manual_revocation_required'
          ? ['acknowledge_manual_revocation']
          : <String>[]
      ..['updated_at'] = now;
    return _demoBootstrapSession(sessionId);
  }

  @override
  Future<CloudBootstrapSession> acknowledgeCloudBootstrapRevocation(
    String sessionId,
    int expectedRevision,
  ) async {
    await _pause();
    final session = _bootstrapSessions[sessionId];
    if (session == null ||
        session['state'] != 'manual_revocation_required' ||
        session['revision'] != expectedRevision) {
      throw const DemoApiException(
        'BOOTSTRAP_SESSION_CONFLICT',
        'Bootstrap cleanup acknowledgement is no longer available.',
      );
    }
    session
      ..['revision'] = expectedRevision + 1
      ..['state'] = 'ready'
      ..['disposal_status'] = 'revoked'
      ..['command_permissions'] = <String>[]
      ..['updated_at'] = store.clock().toUtc().toIso8601String();
    return _demoBootstrapSession(sessionId);
  }

  @override
  Future<CloudBootstrapSession> cancelCloudBootstrapSession(
    String sessionId,
    int expectedRevision,
  ) async {
    await _pause();
    final session = _bootstrapSessions[sessionId];
    if (session == null ||
        session['revision'] != expectedRevision ||
        !(session['command_permissions'] as List).contains('cancel')) {
      throw const DemoApiException(
        'BOOTSTRAP_SESSION_CONFLICT',
        'Bootstrap session changed before cancellation.',
      );
    }
    session
      ..['revision'] = expectedRevision + 1
      ..['state'] = 'cancelled'
      ..['command_permissions'] = ['start_new']
      ..['updated_at'] = store.clock().toUtc().toIso8601String();
    return _demoBootstrapSession(sessionId);
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
    final selectedProfile = _architectureSelections[twinId]?.profileRef;
    if (selectedProfile != null &&
        (selectedProfile.id != 'five-layer-baseline' ||
            selectedProfile.version != '2')) {
      throw const DemoApiException(
        'DEMO_PROFILE_CALCULATION_UNAVAILABLE',
        'Six-layer calculations require the connected local stack; demo mode '
            'currently provides profile comparison only.',
      );
    }
    if (!params.isFiveLayerV2) {
      throw const DemoApiException(
        'ARCH_WORKLOAD_INCOMPATIBLE',
        'New demo calculations require a frozen Five-layer v2 workload scenario.',
      );
    }
    final paramsJson = params.toJson();
    final now = store.clock().toUtc();
    final runId = _nextDemoRunId();
    final scenario = params.scenario!.name;
    final specification = store.fiveLayerV2DeploymentSpecification(scenario)
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
        'The canonical Five-layer v2 demo specification is unsupported.',
      );
    }

    final architecture = store.fiveLayerV2ResolvedArchitecture(scenario)
      ..['calculation_run_id'] = runId;
    _replaceCurrency(architecture, params.currency);
    final deploymentRef =
        _copyMap(architecture['deployment_specification_ref'] as Map)
          ..['calculation_run_id'] = runId
          ..['digest'] = parsedSpecification.digest;
    architecture['deployment_specification_ref'] = deploymentRef;
    final configured = store.optimizerConfig('demo-configured');
    final result = configured?['result'] is Map
        ? _copyMap(configured!['result'] as Map)
        : _defaultCalculationResult(paramsJson);
    final cheapestPath = _fiveLayerV2CheapestPath(architecture);
    _reallocateDemoCosts(result, cheapestPath);
    _convertFiveLayerV2DemoCurrency(result, params.currency);
    final totalCostExact = _applyFiveLayerV2DemoArchitectureCosts(
      architecture,
      result,
      params.currency,
    );
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
      ..['calculationResult'] = _fiveLayerV2CalculationResult(cheapestPath)
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
    var runs = store.optimizerRuns(twinId);
    if (runs.isEmpty && store.optimizerConfig(twinId) != null) {
      _seedExistingOptimizerRun(twinId);
      runs = store.optimizerRuns(twinId);
    }
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
        'The Five-layer v2 result is evaluation-only until its live-capacity gates are evidenced.',
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

  Map<String, dynamic> _architectureSelectionJson(
    TwinArchitectureSelection selection,
  ) => {
    'twin_id': selection.twinId,
    'profile_id': selection.profileRef.id,
    'profile_version': selection.profileRef.version,
    'profile_digest': selection.profileRef.digest,
    'revision': selection.revision,
    'selected_at': selection.selectedAt.toIso8601String(),
    'updated_at': selection.updatedAt.toIso8601String(),
    'selected_by_user_id': selection.selectedByUserId,
  };

  PinnedArchitectureReference _profileReference(
    String profileId,
    String profileVersion,
  ) {
    final profile = store.architectureProfile(profileId, profileVersion);
    return PinnedArchitectureReference(
      id: profileId,
      version: profileVersion,
      digest: profile['content_digest'].toString(),
    );
  }

  Map<String, dynamic> _architecturePreviewJson(
    TwinArchitectureSelection selection,
    PinnedArchitectureReference target,
  ) {
    final currentReference = {
      'id': selection.profileRef.id,
      'version': selection.profileRef.version,
      'digest': selection.profileRef.digest,
    };
    final targetReference = {
      'id': target.id,
      'version': target.version,
      'digest': target.digest,
    };
    final digestSeed = jsonEncode({
      'profile_ref': targetReference,
      'expected_revision': selection.revision,
      'incompatible_workload_fields': <String>[],
      'incompatible_extension_bindings': <String>[],
    });
    return {
      'current': currentReference,
      'target': targetReference,
      'expected_revision': selection.revision,
      'incompatible_workload_fields': <Map<String, dynamic>>[],
      'incompatible_extension_bindings': <Map<String, dynamic>>[],
      'selected_calculation_run_id': null,
      'deployment_readiness_sections': <String>[],
      'invalidation_digest':
          'sha256:${sha256.convert(utf8.encode(digestSeed))}',
    };
  }

  void _seedExistingOptimizerRun(String twinId) {
    final raw = store.optimizerConfig(twinId);
    if (raw == null) return;
    final runId = _nextDemoRunId();
    final createdAt =
        DateTime.tryParse(raw['calculated_at']?.toString() ?? '')?.toUtc() ??
        store.clock().toUtc();
    store.addOptimizerRun(twinId, {
      'id': runId,
      'twin_id': twinId,
      'status': 'succeeded',
      'deployment_compatibility_status': 'legacy_not_deployable',
      'deployment_specification_digest': null,
      'deployment_specification_version': null,
      'resolved_deployment_specification': null,
      'selected_for_deployment_at': null,
      'created_at': createdAt.toIso8601String(),
    });
  }

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

  void _convertFiveLayerV2DemoCurrency(
    Map<String, dynamic> result,
    String currency,
  ) {
    final rate = switch (currency) {
      'USD' => 1.0,
      'EUR' => _fiveLayerV2EurPerUsd,
      _ => throw DemoApiException(
        'DEMO_CURRENCY_UNSUPPORTED',
        'The Five-layer v2 demo currency "$currency" is unsupported.',
      ),
    };
    double converted(Object? value) => (value as num).toDouble() * rate;

    for (final providerKey in const ['awsCosts', 'azureCosts', 'gcpCosts']) {
      final providerCosts = result[providerKey];
      if (providerCosts is! Map) continue;
      for (final rawLayer in providerCosts.values) {
        if (rawLayer is! Map || rawLayer['cost'] is! num) continue;
        rawLayer['cost'] = converted(rawLayer['cost']);
        final components = rawLayer['components'];
        if (components is Map) {
          for (final entry in components.entries.toList()) {
            if (entry.value is num) {
              components[entry.key] = converted(entry.value);
            }
          }
        }
      }
    }
    if (result['totalCost'] is num) {
      result['totalCost'] = converted(result['totalCost']);
    }
    final diagnostics = result['optimizationDiagnostics'];
    if (diagnostics is Map) {
      for (final key in const [
        'winningLayerCost',
        'winningTransferCost',
        'winningScore',
      ]) {
        if (diagnostics[key] is num) {
          diagnostics[key] = converted(diagnostics[key]);
        }
      }
    }
  }

  List<String> _fiveLayerV2CheapestPath(Map<String, dynamic> architecture) {
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

  Map<String, dynamic> _fiveLayerV2CalculationResult(
    List<String> cheapestPath,
  ) {
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

  String _applyFiveLayerV2DemoArchitectureCosts(
    Map<String, dynamic> architecture,
    Map<String, dynamic> result,
    String currency,
  ) {
    const layerByComponent = {
      'component.ingestion': 'L1',
      'component.processing': 'L2',
      'component.hot-storage': 'L3_hot',
      'component.cool-storage': 'L3_cool',
      'component.archive-storage': 'L3_archive',
      'component.twin-state': 'L4',
      'component.visualization': 'L5',
    };
    const costsByProvider = {
      'aws': 'awsCosts',
      'azure': 'azureCosts',
      'gcp': 'gcpCosts',
    };
    final componentMicros = <String, int>{};
    final responsibilityMicros = <String, int>{};
    for (final raw in (architecture['component_assignments'] as List)) {
      final assignment = raw as Map;
      final componentId = assignment['logical_component_id'].toString();
      final responsibilityId = assignment['responsibility_id'].toString();
      final provider = assignment['provider'].toString();
      final layer = layerByComponent[componentId];
      final providerCosts = result[costsByProvider[provider]];
      final layerCost = providerCosts is Map && layer != null
          ? providerCosts[layer]
          : null;
      if (layerCost is! Map || layerCost['cost'] is! num) {
        throw const DemoApiException(
          'DEMO_FIVE_LAYER_V2_COST_INVALID',
          'The demo result cannot be paired with its resolved architecture.',
        );
      }
      final micros = ((layerCost['cost'] as num).toDouble() * 1000000).round();
      componentMicros[componentId] = micros;
      responsibilityMicros.update(
        responsibilityId,
        (current) => current + micros,
        ifAbsent: () => micros,
      );
      final contribution = assignment['cost_contribution'] as Map;
      contribution
        ..['currency'] = currency
        ..['monthly_amount'] = _demoMicrosText(micros);
    }
    for (final raw in (architecture['resolved_edges'] as List)) {
      final contribution = (raw as Map)['cost_contribution'] as Map;
      contribution
        ..['currency'] = currency
        ..['monthly_amount'] = '0';
    }
    final summary = architecture['cost_summary'] as Map;
    summary['currency'] = currency;
    void replaceTotals(String field, Map<String, int> amounts) {
      for (final raw in (summary[field] as List)) {
        final item = raw as Map;
        final amount = amounts[item['item_id'].toString()];
        if (amount == null) {
          throw const DemoApiException(
            'DEMO_FIVE_LAYER_V2_COST_INVALID',
            'The demo cost summary contains an unresolved item.',
          );
        }
        item['monthly_amount'] = _demoMicrosText(amount);
      }
    }

    replaceTotals('component_totals', componentMicros);
    replaceTotals('responsibility_totals', responsibilityMicros);
    replaceTotals('edge_totals', {
      for (final raw in (architecture['resolved_edges'] as List))
        (raw as Map)['edge_id'].toString(): 0,
    });
    final totalMicros = componentMicros.values.fold<int>(0, (a, b) => a + b);
    final total = _demoMicrosText(totalMicros);
    summary['monthly_total'] = total;
    return total;
  }

  String _demoMicrosText(int micros) {
    final whole = micros ~/ 1000000;
    final fraction = (micros % 1000000).abs().toString().padLeft(6, '0');
    final trimmed = fraction.replaceFirst(RegExp(r'0+$'), '');
    return trimmed.isEmpty ? '$whole' : '$whole.$trimmed';
  }

  void _reallocateDemoCosts(
    Map<String, dynamic> result,
    List<String> cheapestPath,
  ) {
    const providerKeys = {
      'aws': 'awsCosts',
      'azure': 'azureCosts',
      'gcp': 'gcpCosts',
    };
    final original = {
      for (final entry in providerKeys.entries)
        entry.key: result[entry.value] is Map
            ? _copyMap(result[entry.value] as Map)
            : <String, dynamic>{},
    };
    final reassigned = {
      for (final provider in providerKeys.keys) provider: <String, dynamic>{},
    };
    for (final segment in cheapestPath) {
      final separator = segment.lastIndexOf('_');
      final layer = segment.substring(0, separator);
      final provider = segment.substring(separator + 1).toLowerCase();
      Map<String, dynamic>? layerCost;
      for (final costs in original.values) {
        if (costs[layer] is Map) {
          layerCost = _copyMap(costs[layer] as Map);
          break;
        }
      }
      reassigned[provider]![layer] =
          layerCost ??
          {
            'cost': 0.0,
            'components': {'Five-layer v2 contract fixture': 0.0},
          };
    }
    for (final entry in providerKeys.entries) {
      result[entry.value] = reassigned[entry.key]!;
    }
  }

  String _nextDemoRunId() {
    final seed = store.nextId('demo-optimizer-run');
    final hex = sha256.convert(utf8.encode(seed)).toString();
    return '${hex.substring(0, 8)}-${hex.substring(8, 12)}-'
        '5${hex.substring(13, 16)}-a${hex.substring(17, 20)}-'
        '${hex.substring(20, 32)}';
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

  Map<String, dynamic> _demoBootstrapGuide(
    CloudProvider provider,
    CloudBootstrapTarget target,
  ) {
    return {
      'schema_version': 'cloud-bootstrap-guide.v1',
      'guide_digest': _demoBootstrapDigest('${provider.apiValue}-guide'),
      'provider': provider.apiValue,
      'execution_mode': 'deterministic_fake',
      'target': target.toJson(),
      'bootstrap_authority_pack': _demoBootstrapPack(
        provider,
        authority: true,
        detailed: true,
      ),
      'generated_deployment_pack': _demoBootstrapPack(
        provider,
        authority: false,
        detailed: true,
      ),
      'credential_fields': switch (provider) {
        CloudProvider.aws => [
          _demoCredentialField('access_key_id', 'Access key ID', 'identifier'),
          _demoCredentialField(
            'secret_access_key',
            'Secret access key',
            'secret',
          ),
          _demoCredentialField(
            'session_token',
            'Session token',
            'secret',
            required: false,
          ),
        ],
        CloudProvider.azure => [
          _demoCredentialField('tenant_id', 'Tenant ID', 'identifier'),
          _demoCredentialField(
            'subscription_id',
            'Subscription ID',
            'identifier',
          ),
          _demoCredentialField('client_id', 'Client ID', 'identifier'),
          _demoCredentialField('client_secret', 'Client secret', 'secret'),
        ],
        CloudProvider.gcp => [
          _demoCredentialField(
            'service_account_json',
            'Service-account JSON',
            'json',
          ),
        ],
      },
      'credential_origins': ['dedicated_disposable', 'existing_user_owned'],
      'preparation_steps': [
        {
          'id': 'prepare_authority',
          'title': 'Prepare temporary authority',
          'description':
              'Follow the provider instructions and create a dedicated short-lived bootstrap credential.',
          'expected_outcome':
              'The temporary authority is ready for one request.',
          'official_url': 'https://example.com/${provider.apiValue}/bootstrap',
        },
      ],
      'known_blockers': <Map<String, dynamic>>[],
      'legacy_fallback_available': true,
    };
  }

  Map<String, dynamic> _demoBootstrapPack(
    CloudProvider provider, {
    required bool authority,
    required bool detailed,
  }) {
    const authorityVersion = '2';
    final version = authority ? authorityVersion : 'thesis-demo-v2';
    return {
      'id': authority
          ? 'bootstrap.${provider.apiValue}.admin-v$authorityVersion'
          : provider == CloudProvider.aws
          ? 'aws.thesis-demo-v2.iam-user-v1'
          : provider == CloudProvider.azure
          ? 'azure.thesis-demo-v2.service-principal-v1'
          : '${provider.apiValue}.thesis-demo-v2',
      'version': version,
      'digest': _demoBootstrapDigest('${provider.apiValue}-$version'),
      if (detailed) ...{
        'scope_summary': authority
            ? 'Temporary demo bootstrap authority.'
            : 'Bounded demo deployment identity.',
        'limitations': ['Demo mode creates no provider resources.'],
        'artifact_url': 'https://example.com/${provider.apiValue}/permissions',
      },
    };
  }

  Map<String, dynamic> _demoCredentialField(
    String id,
    String label,
    String inputType, {
    bool required = true,
  }) {
    return {
      'id': id,
      'label': label,
      'input_type': inputType,
      'required': required,
      'redaction_rule': inputType == 'json'
          ? 'private_key_document'
          : inputType == 'secret'
          ? 'secret'
          : 'identifier',
    };
  }

  String _demoBootstrapDigest(String value) =>
      'sha256:${sha256.convert(utf8.encode(value))}';

  String _demoBootstrapRemediationUrl(
    CloudProvider provider,
  ) => switch (provider) {
    CloudProvider.aws =>
      'https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html',
    CloudProvider.azure =>
      'https://learn.microsoft.com/en-us/entra/identity-platform/howto-create-service-principal-portal',
    CloudProvider.gcp => 'https://cloud.google.com/iam/docs/keys-create-delete',
  };

  CloudBootstrapSession _demoBootstrapSession(String sessionId) {
    final session = _bootstrapSessions[sessionId];
    if (session == null) {
      throw const DemoApiException(
        'BOOTSTRAP_SESSION_NOT_FOUND',
        'Bootstrap session was not found.',
      );
    }
    return CloudBootstrapSession.fromJson(_demoBootstrapResponse(session));
  }

  Map<String, dynamic> _demoBootstrapResponse(Map<dynamic, dynamic> session) {
    return _copyMap(session)
      ..remove('_idempotency_key')
      ..remove('_execute_idempotency_key');
  }

  String _demoBootstrapSafeIdentifier(
    CloudProvider provider,
    Map<String, dynamic> target,
    Map<String, dynamic> credential,
  ) => switch (provider) {
    CloudProvider.aws => credential['access_key_id']?.toString() ?? 'unknown',
    CloudProvider.azure =>
      target['bootstrap_credential_key_id']?.toString() ??
          credential['client_id']?.toString() ??
          'unknown',
    CloudProvider.gcp => credential['private_key_id']?.toString() ?? 'unknown',
  };

  String? _demoBootstrapCredentialFailure(
    CloudProvider provider,
    Map<String, dynamic> target,
    Map<String, dynamic> credential,
  ) {
    if (credential['provider'] != provider.apiValue) {
      return 'The submitted credential provider does not match the target.';
    }
    return switch (provider) {
      CloudProvider.aws
          when !(credential['access_key_id']?.toString().startsWith('AKIA') ==
                  true ||
              credential['access_key_id']?.toString().startsWith('ASIA') ==
                  true) =>
        'The AWS access-key identifier has an unsupported shape.',
      CloudProvider.aws
          when credential['session_token'] != null &&
              target['session_expires_at'] == null =>
        'An AWS session credential requires its provider-issued expiry.',
      CloudProvider.azure
          when credential['tenant_id'] != target['tenant_id'] ||
              credential['subscription_id'] != target['subscription_id'] =>
        'The Azure credential scope does not match the selected tenant and subscription.',
      CloudProvider.gcp
          when credential['project_id'] !=
              (target['project_id'] ?? target['bootstrap_project_id']) =>
        'The GCP credential project does not match the selected bootstrap project.',
      _ => null,
    };
  }

  bool _demoBootstrapNeedsManualCleanup(
    CloudProvider provider,
    Map<String, dynamic> target,
    String safeIdentifier,
  ) => switch (provider) {
    CloudProvider.aws => safeIdentifier.toUpperCase().contains('MANUAL'),
    CloudProvider.azure =>
      target['bootstrap_credential_key_id'] == null ||
          (target['bootstrap_credential_key_id'] as String)
              .toLowerCase()
              .contains('manual'),
    CloudProvider.gcp => safeIdentifier.toLowerCase().contains('manual'),
  };

  static Map<String, dynamic> _copyMap(Map<dynamic, dynamic> value) {
    return Map<String, dynamic>.from(jsonDecode(jsonEncode(value)) as Map);
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
