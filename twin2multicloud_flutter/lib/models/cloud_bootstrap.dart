import 'package:equatable/equatable.dart';

import 'cloud_connection.dart';
import 'json_contract.dart';

enum CloudBootstrapEntryPoint {
  settings,
  twinPrepare;

  String get apiValue => switch (this) {
    CloudBootstrapEntryPoint.settings => 'settings',
    CloudBootstrapEntryPoint.twinPrepare => 'twin_prepare',
  };
}

enum CloudBootstrapExecutionMode {
  disabled,
  deterministicFake;

  static CloudBootstrapExecutionMode parse(String value) => switch (value) {
    'disabled' => CloudBootstrapExecutionMode.disabled,
    'deterministic_fake' => CloudBootstrapExecutionMode.deterministicFake,
    _ => throw const FormatException(
      'Invalid API contract: unsupported bootstrap execution mode.',
    ),
  };

  String get label => switch (this) {
    CloudBootstrapExecutionMode.disabled => 'Disabled',
    CloudBootstrapExecutionMode.deterministicFake =>
      'Thesis simulation — no cloud resources are created',
  };
}

enum CloudBootstrapSessionState {
  draft,
  bootstrapRunning,
  generatedConnectionReady,
  disposalRunning,
  manualRevocationRequired,
  credentialReentryRequired,
  ready,
  failed,
  cancelled,
  expired;

  static CloudBootstrapSessionState parse(String value) => switch (value) {
    'draft' => CloudBootstrapSessionState.draft,
    'bootstrap_running' => CloudBootstrapSessionState.bootstrapRunning,
    'generated_connection_ready' =>
      CloudBootstrapSessionState.generatedConnectionReady,
    'disposal_running' => CloudBootstrapSessionState.disposalRunning,
    'manual_revocation_required' =>
      CloudBootstrapSessionState.manualRevocationRequired,
    'credential_reentry_required' =>
      CloudBootstrapSessionState.credentialReentryRequired,
    'ready' => CloudBootstrapSessionState.ready,
    'failed' => CloudBootstrapSessionState.failed,
    'cancelled' => CloudBootstrapSessionState.cancelled,
    'expired' => CloudBootstrapSessionState.expired,
    _ => throw const FormatException(
      'Invalid API contract: unsupported bootstrap session state.',
    ),
  };
}

enum CloudBootstrapCredentialOrigin {
  dedicatedDisposable,
  existingUserOwned;

  String get apiValue => switch (this) {
    CloudBootstrapCredentialOrigin.dedicatedDisposable =>
      'dedicated_disposable',
    CloudBootstrapCredentialOrigin.existingUserOwned => 'existing_user_owned',
  };

  static CloudBootstrapCredentialOrigin parse(String value) => switch (value) {
    'dedicated_disposable' =>
      CloudBootstrapCredentialOrigin.dedicatedDisposable,
    'existing_user_owned' => CloudBootstrapCredentialOrigin.existingUserOwned,
    _ => throw const FormatException(
      'Invalid API contract: unsupported bootstrap credential origin.',
    ),
  };
}

class CloudBootstrapTarget extends Equatable {
  final CloudProvider provider;
  final Map<String, dynamic> values;

  const CloudBootstrapTarget._(this.provider, this.values);

  factory CloudBootstrapTarget.aws({
    required String accountId,
    required String region,
    DateTime? sessionExpiresAt,
  }) {
    final normalizedAccount = accountId.trim();
    final normalizedRegion = region.trim();
    if (!RegExp(r'^\d{12}$').hasMatch(normalizedAccount) ||
        normalizedRegion.isEmpty) {
      throw ArgumentError('AWS account ID and region are required.');
    }
    return CloudBootstrapTarget._(
      CloudProvider.aws,
      Map.unmodifiable({
        'provider': 'aws',
        'account_id': normalizedAccount,
        'region': normalizedRegion,
        if (sessionExpiresAt != null)
          'session_expires_at': sessionExpiresAt.toUtc().toIso8601String(),
      }),
    );
  }

  factory CloudBootstrapTarget.azure({
    required String tenantId,
    required String subscriptionId,
    required String region,
    String? bootstrapCredentialKeyId,
  }) {
    final values = [tenantId, subscriptionId, region].map((e) => e.trim());
    if (values.any((value) => value.isEmpty)) {
      throw ArgumentError(
        'Azure tenant, subscription, and region are required.',
      );
    }
    return CloudBootstrapTarget._(
      CloudProvider.azure,
      Map.unmodifiable({
        'provider': 'azure',
        'tenant_id': tenantId.trim(),
        'subscription_id': subscriptionId.trim(),
        'region': region.trim(),
        if (bootstrapCredentialKeyId?.trim().isNotEmpty == true)
          'bootstrap_credential_key_id': bootstrapCredentialKeyId!.trim(),
      }),
    );
  }

  factory CloudBootstrapTarget.gcpExistingProject({
    required String projectId,
    required String region,
  }) {
    if (!RegExp(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$').hasMatch(projectId.trim()) ||
        region.trim().isEmpty) {
      throw ArgumentError('GCP project and region are required.');
    }
    return CloudBootstrapTarget._(
      CloudProvider.gcp,
      Map.unmodifiable({
        'provider': 'gcp',
        'mode': 'existing_project',
        'project_id': projectId.trim(),
        'region': region.trim(),
      }),
    );
  }

  factory CloudBootstrapTarget.fromJson(Map<String, dynamic> json) {
    _rejectSecretResponseKeys(json);
    final provider = _provider(JsonContract.requiredString(json, 'provider'));
    final allowed = switch (provider) {
      CloudProvider.aws => const {
        'provider',
        'account_id',
        'region',
        'session_expires_at',
      },
      CloudProvider.azure => const {
        'provider',
        'tenant_id',
        'subscription_id',
        'region',
        'bootstrap_credential_key_id',
      },
      CloudProvider.gcp =>
        json['mode'] == 'organization'
            ? const {
                'provider',
                'mode',
                'bootstrap_project_id',
                'organization_id',
                'folder_id',
                'billing_account_id',
                'region',
              }
            : const {'provider', 'mode', 'project_id', 'region'},
    };
    _expectAllowedKeys(json, allowed, 'bootstrap target');
    JsonContract.requiredString(json, 'region');
    switch (provider) {
      case CloudProvider.aws:
        final accountId = JsonContract.requiredString(json, 'account_id');
        if (!RegExp(r'^\d{12}$').hasMatch(accountId)) {
          throw const FormatException(
            'Invalid API contract: account_id has an invalid shape.',
          );
        }
        JsonContract.optionalDate(json, 'session_expires_at');
      case CloudProvider.azure:
        JsonContract.requiredString(json, 'tenant_id');
        JsonContract.requiredString(json, 'subscription_id');
        JsonContract.optionalString(json, 'bootstrap_credential_key_id');
      case CloudProvider.gcp:
        final mode = JsonContract.requiredString(json, 'mode');
        if (mode == 'existing_project') {
          final projectId = JsonContract.requiredString(json, 'project_id');
          if (!RegExp(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$').hasMatch(projectId)) {
            throw const FormatException(
              'Invalid API contract: GCP project ID has an invalid shape.',
            );
          }
        } else if (mode == 'organization') {
          final projectId = JsonContract.requiredString(
            json,
            'bootstrap_project_id',
          );
          final organizationId = JsonContract.requiredString(
            json,
            'organization_id',
          );
          final billingAccountId = JsonContract.requiredString(
            json,
            'billing_account_id',
          );
          final folderId = JsonContract.optionalString(json, 'folder_id');
          if (!RegExp(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$').hasMatch(projectId) ||
              !RegExp(r'^\d+$').hasMatch(organizationId) ||
              (folderId != null && !RegExp(r'^\d+$').hasMatch(folderId)) ||
              !RegExp(
                r'^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$',
              ).hasMatch(billingAccountId)) {
            throw const FormatException(
              'Invalid API contract: GCP organization target has an invalid shape.',
            );
          }
        } else {
          throw const FormatException(
            'Invalid API contract: unsupported GCP bootstrap target mode.',
          );
        }
    }
    return CloudBootstrapTarget._(
      provider,
      JsonContract.immutableObject(json, 'target'),
    );
  }

  Map<String, dynamic> toJson() => Map<String, dynamic>.from(values);

  String get summary => switch (provider) {
    CloudProvider.aws => '${values['account_id']} / ${values['region']}',
    CloudProvider.azure => '${values['subscription_id']} / ${values['region']}',
    CloudProvider.gcp =>
      '${values['project_id'] ?? values['bootstrap_project_id']} / ${values['region']}',
  };

  @override
  List<Object?> get props => [provider, values];
}

class CloudBootstrapPackReference extends Equatable {
  final String id;
  final String version;
  final String digest;
  final String? scopeSummary;
  final List<String> limitations;
  final Uri? artifactUrl;

  const CloudBootstrapPackReference({
    required this.id,
    required this.version,
    required this.digest,
    this.scopeSummary,
    this.limitations = const [],
    this.artifactUrl,
  });

  factory CloudBootstrapPackReference.fromJson(
    Map<String, dynamic> json, {
    required bool detailed,
  }) {
    _expectAllowedKeys(json, {
      'id',
      'version',
      'digest',
      if (detailed) ...{'scope_summary', 'limitations', 'artifact_url'},
    }, 'bootstrap pack');
    final digest = _digest(JsonContract.requiredString(json, 'digest'));
    final limitations = detailed
        ? _stringList(json, 'limitations')
        : const <String>[];
    final artifactUrl = detailed
        ? _httpsUri(JsonContract.requiredString(json, 'artifact_url'))
        : null;
    return CloudBootstrapPackReference(
      id: JsonContract.requiredString(json, 'id'),
      version: JsonContract.requiredString(json, 'version'),
      digest: digest,
      scopeSummary: detailed
          ? JsonContract.requiredString(json, 'scope_summary')
          : null,
      limitations: limitations,
      artifactUrl: artifactUrl,
    );
  }

  @override
  List<Object?> get props => [
    id,
    version,
    digest,
    scopeSummary,
    limitations,
    artifactUrl,
  ];
}

class CloudBootstrapApiBaseline extends Equatable {
  final String id;
  final String digest;
  final List<String> services;
  final bool retainEnabled;
  final String mutationSummary;
  final List<String> limitations;
  final Uri artifactUrl;

  const CloudBootstrapApiBaseline({
    required this.id,
    required this.digest,
    required this.services,
    required this.retainEnabled,
    required this.mutationSummary,
    required this.limitations,
    required this.artifactUrl,
  });

  factory CloudBootstrapApiBaseline.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'id',
      'digest',
      'services',
      'retain_enabled',
      'mutation_summary',
      'limitations',
      'artifact_url',
    }, 'GCP API baseline');
    final services = _stringList(json, 'services');
    final limitations = _stringList(json, 'limitations');
    final unique = services.toSet();
    if (json['id'] != 'gcp.phase8-api-baseline.v1' ||
        services.isEmpty ||
        services.length > 20 ||
        unique.length != services.length ||
        services.join('\n') != (services.toList()..sort()).join('\n') ||
        services.any(
          (service) =>
              !RegExp(r'^[a-z0-9-]+\.googleapis\.com$').hasMatch(service),
        ) ||
        limitations.isEmpty ||
        limitations.length != limitations.toSet().length ||
        limitations.any((limitation) => limitation.trim().isEmpty) ||
        json['retain_enabled'] != true) {
      throw const FormatException(
        'Invalid API contract: GCP API baseline is malformed.',
      );
    }
    return CloudBootstrapApiBaseline(
      id: JsonContract.requiredString(json, 'id'),
      digest: _digest(JsonContract.requiredString(json, 'digest')),
      services: List.unmodifiable(services),
      retainEnabled: true,
      mutationSummary: JsonContract.requiredString(json, 'mutation_summary'),
      limitations: List.unmodifiable(limitations),
      artifactUrl: _httpsUri(JsonContract.requiredString(json, 'artifact_url')),
    );
  }

  @override
  List<Object?> get props => [
    id,
    digest,
    services,
    retainEnabled,
    mutationSummary,
    limitations,
    artifactUrl,
  ];
}

class CloudBootstrapCredentialField extends Equatable {
  final String id;
  final String label;
  final String inputType;
  final bool required;

  const CloudBootstrapCredentialField({
    required this.id,
    required this.label,
    required this.inputType,
    required this.required,
  });

  factory CloudBootstrapCredentialField.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'id',
      'label',
      'input_type',
      'required',
      'redaction_rule',
    }, 'bootstrap credential field');
    final inputType = JsonContract.requiredString(json, 'input_type');
    final redaction = JsonContract.requiredString(json, 'redaction_rule');
    if (!{'identifier', 'secret', 'json'}.contains(inputType) ||
        !{'identifier', 'secret', 'private_key_document'}.contains(redaction)) {
      throw const FormatException(
        'Invalid API contract: unsupported bootstrap field metadata.',
      );
    }
    return CloudBootstrapCredentialField(
      id: JsonContract.requiredString(json, 'id'),
      label: JsonContract.requiredString(json, 'label'),
      inputType: inputType,
      required: JsonContract.requiredBool(json, 'required'),
    );
  }

  @override
  List<Object?> get props => [id, label, inputType, required];
}

class CloudBootstrapInstruction extends Equatable {
  final String id;
  final String title;
  final String description;
  final String expectedOutcome;
  final Uri officialUrl;

  const CloudBootstrapInstruction({
    required this.id,
    required this.title,
    required this.description,
    required this.expectedOutcome,
    required this.officialUrl,
  });

  factory CloudBootstrapInstruction.fromJson(Map<String, dynamic> json) {
    _expectExactKeys(json, const {
      'id',
      'title',
      'description',
      'expected_outcome',
      'official_url',
    }, 'bootstrap instruction');
    return CloudBootstrapInstruction(
      id: JsonContract.requiredString(json, 'id'),
      title: JsonContract.requiredString(json, 'title'),
      description: JsonContract.requiredString(json, 'description'),
      expectedOutcome: JsonContract.requiredString(json, 'expected_outcome'),
      officialUrl: _httpsUri(JsonContract.requiredString(json, 'official_url')),
    );
  }

  @override
  List<Object?> get props => [
    id,
    title,
    description,
    expectedOutcome,
    officialUrl,
  ];
}

class CloudBootstrapFinding extends Equatable {
  final String code;
  final String severity;
  final String title;
  final String message;
  final bool blocking;
  final String action;
  final Uri? remediationUrl;

  const CloudBootstrapFinding({
    required this.code,
    required this.severity,
    required this.title,
    required this.message,
    required this.blocking,
    required this.action,
    this.remediationUrl,
  });

  factory CloudBootstrapFinding.fromJson(Map<String, dynamic> json) {
    _expectAllowedKeys(json, const {
      'code',
      'severity',
      'title',
      'message',
      'blocking',
      'action',
      'remediation_url',
    }, 'bootstrap finding');
    final code = JsonContract.requiredString(json, 'code');
    final severity = json['severity']?.toString() ?? 'error';
    if (!{'info', 'warning', 'error'}.contains(severity)) {
      throw const FormatException(
        'Invalid API contract: unsupported bootstrap finding severity.',
      );
    }
    if (!RegExp(r'^[A-Z0-9_]+$').hasMatch(code)) {
      throw const FormatException(
        'Invalid API contract: bootstrap finding code is invalid.',
      );
    }
    return CloudBootstrapFinding(
      code: code,
      severity: severity,
      title: JsonContract.requiredString(json, 'title'),
      message: JsonContract.requiredString(json, 'message'),
      blocking: JsonContract.requiredBool(json, 'blocking'),
      action: JsonContract.requiredString(json, 'action'),
      remediationUrl: json['remediation_url'] == null
          ? null
          : _httpsUri(JsonContract.requiredString(json, 'remediation_url')),
    );
  }

  @override
  List<Object?> get props => [
    code,
    severity,
    title,
    message,
    blocking,
    action,
    remediationUrl,
  ];
}

class CloudBootstrapGuide extends Equatable {
  final String guideDigest;
  final CloudProvider provider;
  final CloudBootstrapExecutionMode executionMode;
  final CloudBootstrapTarget target;
  final CloudBootstrapPackReference bootstrapAuthorityPack;
  final CloudBootstrapPackReference generatedDeploymentPack;
  final CloudBootstrapApiBaseline? apiBaseline;
  final List<CloudBootstrapCredentialField> credentialFields;
  final List<CloudBootstrapCredentialOrigin> credentialOrigins;
  final List<CloudBootstrapInstruction> preparationSteps;
  final List<CloudBootstrapFinding> knownBlockers;

  const CloudBootstrapGuide({
    required this.guideDigest,
    required this.provider,
    required this.executionMode,
    required this.target,
    required this.bootstrapAuthorityPack,
    required this.generatedDeploymentPack,
    required this.apiBaseline,
    required this.credentialFields,
    required this.credentialOrigins,
    required this.preparationSteps,
    required this.knownBlockers,
  });

  factory CloudBootstrapGuide.fromJson(Map<String, dynamic> json) {
    _rejectSecretResponseKeys(json);
    _expectExactKeys(json, const {
      'schema_version',
      'guide_digest',
      'provider',
      'execution_mode',
      'target',
      'bootstrap_authority_pack',
      'generated_deployment_pack',
      'api_baseline',
      'credential_fields',
      'credential_origins',
      'preparation_steps',
      'known_blockers',
      'legacy_fallback_available',
    }, 'bootstrap guide');
    if (json['schema_version'] != 'cloud-bootstrap-guide.v1' ||
        json['legacy_fallback_available'] != true) {
      throw const FormatException(
        'Invalid API contract: unsupported bootstrap guide.',
      );
    }
    final provider = _provider(JsonContract.requiredString(json, 'provider'));
    final target = CloudBootstrapTarget.fromJson(
      JsonContract.requiredObject(json, 'target'),
    );
    if (target.provider != provider) {
      throw const FormatException(
        'Invalid API contract: bootstrap guide provider mismatch.',
      );
    }
    if (provider == CloudProvider.gcp &&
        target.values['mode'] != 'existing_project') {
      throw const FormatException(
        'Invalid API contract: GCP guide supports existing project only.',
      );
    }
    final fields = _objectList(
      json,
      'credential_fields',
    ).map(CloudBootstrapCredentialField.fromJson).toList(growable: false);
    final origins = _stringList(
      json,
      'credential_origins',
    ).map(CloudBootstrapCredentialOrigin.parse).toList(growable: false);
    if (origins.length != 2 || origins.toSet().length != 2) {
      throw const FormatException(
        'Invalid API contract: bootstrap credential origins are incomplete.',
      );
    }
    final blockers = _objectList(
      json,
      'known_blockers',
    ).map(CloudBootstrapFinding.fromJson).toList(growable: false);
    if (blockers.map((item) => item.code).toSet().length != blockers.length) {
      throw const FormatException(
        'Invalid API contract: duplicate bootstrap findings.',
      );
    }
    final rawApiBaseline = json['api_baseline'];
    if (rawApiBaseline != null && rawApiBaseline is! Map) {
      throw const FormatException(
        'Invalid API contract: api_baseline must be an object or null.',
      );
    }
    final apiBaseline = rawApiBaseline == null
        ? null
        : CloudBootstrapApiBaseline.fromJson(
            Map<String, dynamic>.from(rawApiBaseline as Map),
          );
    if ((provider == CloudProvider.gcp) != (apiBaseline != null)) {
      throw const FormatException(
        'Invalid API contract: GCP API baseline provider mismatch.',
      );
    }
    return CloudBootstrapGuide(
      guideDigest: _digest(JsonContract.requiredString(json, 'guide_digest')),
      provider: provider,
      executionMode: CloudBootstrapExecutionMode.parse(
        JsonContract.requiredString(json, 'execution_mode'),
      ),
      target: target,
      bootstrapAuthorityPack: CloudBootstrapPackReference.fromJson(
        JsonContract.requiredObject(json, 'bootstrap_authority_pack'),
        detailed: true,
      ),
      generatedDeploymentPack: CloudBootstrapPackReference.fromJson(
        JsonContract.requiredObject(json, 'generated_deployment_pack'),
        detailed: true,
      ),
      apiBaseline: apiBaseline,
      credentialFields: List.unmodifiable(fields),
      credentialOrigins: List.unmodifiable(origins),
      preparationSteps: List.unmodifiable(
        _objectList(
          json,
          'preparation_steps',
        ).map(CloudBootstrapInstruction.fromJson),
      ),
      knownBlockers: List.unmodifiable(blockers),
    );
  }

  @override
  List<Object?> get props => [
    guideDigest,
    provider,
    executionMode,
    target,
    bootstrapAuthorityPack,
    generatedDeploymentPack,
    apiBaseline,
    credentialFields,
    credentialOrigins,
    preparationSteps,
    knownBlockers,
  ];
}

class CloudBootstrapConnectionSummary extends Equatable {
  final String id;
  final CloudProvider provider;
  final String displayName;
  final Map<String, dynamic> cloudScope;
  final String permissionSetVersion;
  final String validationStatus;

  const CloudBootstrapConnectionSummary({
    required this.id,
    required this.provider,
    required this.displayName,
    required this.cloudScope,
    required this.permissionSetVersion,
    required this.validationStatus,
  });

  factory CloudBootstrapConnectionSummary.fromJson(Map<String, dynamic> json) {
    _rejectSecretResponseKeys(json);
    _expectExactKeys(json, const {
      'id',
      'provider',
      'purpose',
      'display_name',
      'cloud_scope',
      'permission_set_version',
      'validation_status',
    }, 'bootstrap connection');
    if (json['purpose'] != 'deployment' ||
        !{'valid', 'invalid', 'untested'}.contains(json['validation_status'])) {
      throw const FormatException(
        'Invalid API contract: bootstrap connection is not deployment-ready.',
      );
    }
    return CloudBootstrapConnectionSummary(
      id: JsonContract.requiredString(json, 'id'),
      provider: _provider(JsonContract.requiredString(json, 'provider')),
      displayName: JsonContract.requiredString(json, 'display_name'),
      cloudScope: JsonContract.requiredObject(json, 'cloud_scope'),
      permissionSetVersion: JsonContract.requiredString(
        json,
        'permission_set_version',
      ),
      validationStatus: JsonContract.requiredString(json, 'validation_status'),
    );
  }

  @override
  List<Object?> get props => [
    id,
    provider,
    displayName,
    cloudScope,
    permissionSetVersion,
    validationStatus,
  ];
}

class CloudBootstrapSession extends Equatable {
  final String id;
  final CloudProvider provider;
  final CloudBootstrapTarget target;
  final CloudBootstrapEntryPoint entryPoint;
  final String? twinId;
  final String displayName;
  final int revision;
  final CloudBootstrapSessionState state;
  final String guideDigest;
  final CloudBootstrapPackReference bootstrapAuthorityPack;
  final CloudBootstrapPackReference generatedDeploymentPack;
  final CloudBootstrapCredentialOrigin? credentialOrigin;
  final String? disposalStatus;
  final DateTime? credentialExpiresAt;
  final String? safeCredentialIdentifier;
  final CloudBootstrapFinding? finding;
  final CloudBootstrapConnectionSummary? connection;
  final Set<String> commandPermissions;
  final DateTime createdAt;
  final DateTime updatedAt;

  const CloudBootstrapSession({
    required this.id,
    required this.provider,
    required this.target,
    required this.entryPoint,
    this.twinId,
    required this.displayName,
    required this.revision,
    required this.state,
    required this.guideDigest,
    required this.bootstrapAuthorityPack,
    required this.generatedDeploymentPack,
    this.credentialOrigin,
    this.disposalStatus,
    this.credentialExpiresAt,
    this.safeCredentialIdentifier,
    this.finding,
    this.connection,
    required this.commandPermissions,
    required this.createdAt,
    required this.updatedAt,
  });

  factory CloudBootstrapSession.fromJson(Map<String, dynamic> json) {
    _rejectSecretResponseKeys(json);
    _expectAllowedKeys(json, const {
      'schema_version',
      'id',
      'provider',
      'target',
      'entry_point',
      'twin_id',
      'display_name',
      'revision',
      'state',
      'guide_digest',
      'bootstrap_authority_pack',
      'generated_deployment_pack',
      'credential_origin',
      'disposal_status',
      'credential_expires_at',
      'safe_credential_identifier',
      'finding',
      'connection',
      'command_permissions',
      'created_at',
      'updated_at',
    }, 'bootstrap session');
    if (json['schema_version'] != 'cloud-bootstrap-session.v1') {
      throw const FormatException(
        'Invalid API contract: unsupported bootstrap session.',
      );
    }
    final provider = _provider(JsonContract.requiredString(json, 'provider'));
    final target = CloudBootstrapTarget.fromJson(
      JsonContract.requiredObject(json, 'target'),
    );
    final entryPoint = switch (json['entry_point']) {
      'settings' => CloudBootstrapEntryPoint.settings,
      'twin_prepare' => CloudBootstrapEntryPoint.twinPrepare,
      _ => throw const FormatException(
        'Invalid API contract: unsupported bootstrap entry point.',
      ),
    };
    final twinId = JsonContract.optionalString(json, 'twin_id');
    if (provider != target.provider ||
        (entryPoint == CloudBootstrapEntryPoint.settings && twinId != null) ||
        (entryPoint == CloudBootstrapEntryPoint.twinPrepare &&
            twinId == null)) {
      throw const FormatException(
        'Invalid API contract: bootstrap session scope mismatch.',
      );
    }
    final commands = _stringList(json, 'command_permissions').toSet();
    const supportedCommands = {
      'execute',
      'recheck',
      'acknowledge_manual_revocation',
      'cancel',
      'start_new',
    };
    if (commands.length != _stringList(json, 'command_permissions').length ||
        !supportedCommands.containsAll(commands)) {
      throw const FormatException(
        'Invalid API contract: unsupported bootstrap command permission.',
      );
    }
    final state = CloudBootstrapSessionState.parse(
      JsonContract.requiredString(json, 'state'),
    );
    final findingJson = JsonContract.optionalObject(json, 'finding');
    final connectionJson = JsonContract.optionalObject(json, 'connection');
    final connection = connectionJson == null
        ? null
        : CloudBootstrapConnectionSummary.fromJson(connectionJson);
    final revision = JsonContract.requiredInt(json, 'revision');
    final createdAt = JsonContract.requiredDate(json, 'created_at');
    final updatedAt = JsonContract.requiredDate(json, 'updated_at');
    final expectedCommands = switch (state) {
      CloudBootstrapSessionState.draft ||
      CloudBootstrapSessionState.credentialReentryRequired => const {
        'execute',
        'cancel',
      },
      CloudBootstrapSessionState.bootstrapRunning ||
      CloudBootstrapSessionState.generatedConnectionReady ||
      CloudBootstrapSessionState.disposalRunning => const {'recheck', 'cancel'},
      CloudBootstrapSessionState.manualRevocationRequired => const {
        'acknowledge_manual_revocation',
      },
      CloudBootstrapSessionState.failed ||
      CloudBootstrapSessionState.cancelled ||
      CloudBootstrapSessionState.expired => const {'start_new'},
      CloudBootstrapSessionState.ready => const <String>{},
    };
    const connectionStates = {
      CloudBootstrapSessionState.generatedConnectionReady,
      CloudBootstrapSessionState.disposalRunning,
      CloudBootstrapSessionState.manualRevocationRequired,
      CloudBootstrapSessionState.ready,
    };
    if (commands.difference(expectedCommands).isNotEmpty ||
        expectedCommands.difference(commands).isNotEmpty ||
        connectionStates.contains(state) != (connection != null) ||
        ({
              CloudBootstrapSessionState.ready,
              CloudBootstrapSessionState.manualRevocationRequired,
            }.contains(state) &&
            connection?.validationStatus != 'valid') ||
        (connection != null && connection.provider != provider)) {
      throw const FormatException(
        'Invalid API contract: bootstrap session state is inconsistent.',
      );
    }
    const disposalStatuses = {
      'revoked',
      'expires_at_provider',
      'manual_revocation_required',
      'not_retained_user_managed',
      'released_after_failure',
    };
    final disposalStatus = JsonContract.optionalString(json, 'disposal_status');
    if (disposalStatus != null && !disposalStatuses.contains(disposalStatus)) {
      throw const FormatException(
        'Invalid API contract: bootstrap disposal status is unsupported.',
      );
    }
    final disposalIsConsistent = switch (state) {
      CloudBootstrapSessionState.draft => disposalStatus == null,
      CloudBootstrapSessionState.credentialReentryRequired =>
        disposalStatus == 'released_after_failure',
      CloudBootstrapSessionState.manualRevocationRequired =>
        disposalStatus == 'manual_revocation_required',
      CloudBootstrapSessionState.ready => const {
        'revoked',
        'expires_at_provider',
        'not_retained_user_managed',
      }.contains(disposalStatus),
      _ => true,
    };
    if (!disposalIsConsistent ||
        revision < 1 ||
        updatedAt.isBefore(createdAt)) {
      throw const FormatException(
        'Invalid API contract: bootstrap session lifecycle is inconsistent.',
      );
    }
    final generatedPack = CloudBootstrapPackReference.fromJson(
      JsonContract.requiredObject(json, 'generated_deployment_pack'),
      detailed: false,
    );
    if (connection != null &&
        connection.permissionSetVersion != generatedPack.version) {
      throw const FormatException(
        'Invalid API contract: connection permission pack is inconsistent.',
      );
    }
    return CloudBootstrapSession(
      id: JsonContract.requiredString(json, 'id'),
      provider: provider,
      target: target,
      entryPoint: entryPoint,
      twinId: twinId,
      displayName: JsonContract.requiredString(json, 'display_name'),
      revision: revision,
      state: state,
      guideDigest: _digest(JsonContract.requiredString(json, 'guide_digest')),
      bootstrapAuthorityPack: CloudBootstrapPackReference.fromJson(
        JsonContract.requiredObject(json, 'bootstrap_authority_pack'),
        detailed: false,
      ),
      generatedDeploymentPack: generatedPack,
      credentialOrigin: json['credential_origin'] == null
          ? null
          : CloudBootstrapCredentialOrigin.parse(
              JsonContract.requiredString(json, 'credential_origin'),
            ),
      disposalStatus: disposalStatus,
      credentialExpiresAt: JsonContract.optionalDate(
        json,
        'credential_expires_at',
      ),
      safeCredentialIdentifier: JsonContract.optionalString(
        json,
        'safe_credential_identifier',
      ),
      finding: findingJson == null
          ? null
          : CloudBootstrapFinding.fromJson(findingJson),
      connection: connection,
      commandPermissions: Set.unmodifiable(commands),
      createdAt: createdAt,
      updatedAt: updatedAt,
    );
  }

  bool get isMutating => {
    CloudBootstrapSessionState.bootstrapRunning,
    CloudBootstrapSessionState.disposalRunning,
  }.contains(state);

  @override
  List<Object?> get props => [
    id,
    provider,
    target,
    entryPoint,
    twinId,
    displayName,
    revision,
    state,
    guideDigest,
    bootstrapAuthorityPack,
    generatedDeploymentPack,
    credentialOrigin,
    disposalStatus,
    credentialExpiresAt,
    safeCredentialIdentifier,
    finding,
    connection,
    commandPermissions,
    createdAt,
    updatedAt,
  ];
}

/// One-use request body. It deliberately has no diagnostic serialization.
final class CloudBootstrapExecuteRequest {
  final int expectedRevision;
  final String idempotencyKey;
  final CloudBootstrapCredentialOrigin credentialOrigin;
  final CloudProvider provider;
  Map<String, dynamic>? _credential;

  CloudBootstrapExecuteRequest({
    required this.expectedRevision,
    required this.idempotencyKey,
    required this.credentialOrigin,
    required Map<String, dynamic> credential,
  }) : provider = _requestCredentialProvider(credential),
       _credential = _validatedCredentialRequest(
         expectedRevision,
         idempotencyKey,
         credential,
       );

  Map<String, dynamic> takeJson() {
    final credential = _credential;
    if (credential == null) {
      throw StateError(
        'Bootstrap credential request has already been consumed.',
      );
    }
    _credential = null;
    return {
      'expected_revision': expectedRevision,
      'idempotency_key': idempotencyKey,
      'credential_origin': credentialOrigin.apiValue,
      'credential': credential,
    };
  }

  void dispose() => _credential = null;

  @override
  String toString() => 'CloudBootstrapExecuteRequest(<write-only>)';
}

CloudProvider _requestCredentialProvider(Map<String, dynamic> credential) {
  return switch (credential['provider']) {
    'aws' => CloudProvider.aws,
    'azure' => CloudProvider.azure,
    'gcp' => CloudProvider.gcp,
    _ => throw ArgumentError('Invalid bootstrap credential provider.'),
  };
}

Map<String, dynamic> _validatedCredentialRequest(
  int expectedRevision,
  String idempotencyKey,
  Map<String, dynamic> credential,
) {
  if (expectedRevision < 1 ||
      !RegExp(r'^[A-Za-z0-9._:-]{16,128}$').hasMatch(idempotencyKey)) {
    throw ArgumentError('Invalid bootstrap command metadata.');
  }
  final provider = credential['provider'];
  final allowed = switch (provider) {
    'aws' => const {
      'provider',
      'access_key_id',
      'secret_access_key',
      'session_token',
    },
    'azure' => const {
      'provider',
      'tenant_id',
      'subscription_id',
      'client_id',
      'client_secret',
    },
    'gcp' => const {
      'provider',
      'type',
      'project_id',
      'private_key_id',
      'private_key',
      'client_email',
      'client_id',
      'auth_uri',
      'token_uri',
      'auth_provider_x509_cert_url',
      'client_x509_cert_url',
      'universe_domain',
    },
    _ => throw ArgumentError('Invalid bootstrap credential provider.'),
  };
  if (credential.keys.toSet().difference(allowed).isNotEmpty) {
    throw ArgumentError('Invalid bootstrap credential fields.');
  }
  String required(String key, {int minimumLength = 1, int? maximumLength}) {
    final value = credential[key];
    if (value is! String ||
        value.length < minimumLength ||
        (maximumLength != null && value.length > maximumLength)) {
      throw ArgumentError('Invalid bootstrap credential shape.');
    }
    return value;
  }

  switch (provider) {
    case 'aws':
      required('access_key_id', minimumLength: 16, maximumLength: 128);
      required('secret_access_key', minimumLength: 16, maximumLength: 256);
      if (credential['session_token'] != null) {
        required('session_token', minimumLength: 16, maximumLength: 4096);
      }
      break;
    case 'azure':
      required('tenant_id', maximumLength: 128);
      required('subscription_id', maximumLength: 128);
      required('client_id', maximumLength: 128);
      required('client_secret', minimumLength: 8, maximumLength: 4096);
      break;
    case 'gcp':
      if (credential['type'] != 'service_account') {
        throw ArgumentError('Invalid bootstrap credential shape.');
      }
      required('project_id');
      required('private_key_id', maximumLength: 256);
      required('private_key', minimumLength: 16, maximumLength: 16384);
      required('client_email');
      required('client_id', maximumLength: 256);
      break;
  }
  return Map<String, dynamic>.from(credential);
}

CloudProvider _provider(String value) {
  try {
    return CloudProvider.fromApiValue(value);
  } on ArgumentError {
    throw const FormatException(
      'Invalid API contract: unsupported cloud provider.',
    );
  }
}

String _digest(String value) {
  if (!RegExp(r'^sha256:[a-f0-9]{64}$').hasMatch(value)) {
    throw const FormatException(
      'Invalid API contract: digest must be canonical SHA-256.',
    );
  }
  return value;
}

Uri _httpsUri(String value) {
  final uri = Uri.tryParse(value);
  if (uri == null || uri.scheme != 'https' || uri.host.isEmpty) {
    throw const FormatException(
      'Invalid API contract: bootstrap link must use HTTPS.',
    );
  }
  return uri;
}

List<String> _stringList(Map<String, dynamic> json, String field) {
  final value = json[field];
  if (value is! List || value.any((item) => item is! String)) {
    throw FormatException(
      'Invalid API contract: $field must be a string array.',
    );
  }
  return List<String>.unmodifiable(value.cast<String>());
}

List<Map<String, dynamic>> _objectList(
  Map<String, dynamic> json,
  String field,
) {
  final value = json[field];
  if (value is! List || value.any((item) => item is! Map)) {
    throw FormatException(
      'Invalid API contract: $field must be an object array.',
    );
  }
  return List.unmodifiable(
    value.map((item) => JsonContract.immutableObject(item, field)),
  );
}

void _expectExactKeys(
  Map<String, dynamic> json,
  Set<String> expected,
  String context,
) {
  if (json.keys.toSet().difference(expected).isNotEmpty ||
      expected.difference(json.keys.toSet()).isNotEmpty) {
    throw FormatException('Invalid API contract: $context fields differ.');
  }
}

void _expectAllowedKeys(
  Map<String, dynamic> json,
  Set<String> allowed,
  String context,
) {
  if (json.keys.toSet().difference(allowed).isNotEmpty) {
    throw FormatException('Invalid API contract: $context has unknown fields.');
  }
}

void _rejectSecretResponseKeys(Object? value) {
  if (value is Map) {
    for (final entry in value.entries) {
      final key = entry.key.toString().toLowerCase();
      if ({
        'secret_access_key',
        'client_secret',
        'private_key',
        'session_token',
        'service_account_json',
        'password',
      }.contains(key)) {
        throw const FormatException(
          'Invalid API contract: bootstrap response contains a secret field.',
        );
      }
      _rejectSecretResponseKeys(entry.value);
    }
  } else if (value is List) {
    for (final item in value) {
      _rejectSecretResponseKeys(item);
    }
  }
}
