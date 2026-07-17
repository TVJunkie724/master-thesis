import 'package:equatable/equatable.dart';

import 'pricing_catalog.dart';

class PricingRefreshRun extends Equatable {
  final String schemaVersion;
  final String refreshRunId;
  final String provider;
  final String status;
  final PricingRefreshCredentialSummary credentialSummary;
  final bool force;
  final String sseUrl;
  final Map<String, dynamic>? resultSummary;
  final PricingCatalogReference? activeCalculationReference;
  final AwsTwinMakerPricingContext? awsTwinMakerContext;
  final String? errorCode;
  final String? errorMessage;
  final DateTime createdAt;
  final DateTime? startedAt;
  final DateTime? completedAt;

  const PricingRefreshRun({
    required this.schemaVersion,
    required this.refreshRunId,
    required this.provider,
    required this.status,
    required this.credentialSummary,
    required this.force,
    required this.sseUrl,
    this.resultSummary,
    this.activeCalculationReference,
    this.awsTwinMakerContext,
    this.errorCode,
    this.errorMessage,
    required this.createdAt,
    this.startedAt,
    this.completedAt,
  });

  factory PricingRefreshRun.fromJson(Map<String, dynamic> json) {
    final provider = json['provider']?.toString() ?? '';
    final credentialSummary = PricingRefreshCredentialSummary.fromJson(
      _map(json['credential_summary']),
    );
    final resultSummary = json['result_summary'] is Map
        ? Map<String, dynamic>.from(json['result_summary'] as Map)
        : null;
    return PricingRefreshRun(
      schemaVersion: json['schema_version']?.toString() ?? '',
      refreshRunId: json['refresh_run_id']?.toString() ?? '',
      provider: provider,
      status: json['status']?.toString() ?? 'failed',
      credentialSummary: credentialSummary,
      force: json['force'] as bool? ?? true,
      sseUrl: json['sse_url']?.toString() ?? '',
      resultSummary: resultSummary,
      activeCalculationReference: _optionalCatalogReference(
        resultSummary?['activeCalculationReference'],
        provider,
      ),
      awsTwinMakerContext: provider.toLowerCase() == 'aws'
          ? AwsTwinMakerPricingContext.tryFromJson(
              resultSummary?['accountPricingContext'],
              credentialConnectionId: credentialSummary.connectionId,
              credentialAccountId: credentialSummary.providerAccountId,
            )
          : null,
      errorCode: _string(json['error_code']),
      errorMessage: _string(json['error_message']),
      createdAt:
          _date(json['created_at']) ?? DateTime.fromMillisecondsSinceEpoch(0),
      startedAt: _date(json['started_at']),
      completedAt: _date(json['completed_at']),
    );
  }

  bool get succeeded => status == 'succeeded';

  @override
  List<Object?> get props => [
    schemaVersion,
    refreshRunId,
    provider,
    status,
    credentialSummary,
    force,
    sseUrl,
    resultSummary,
    activeCalculationReference,
    awsTwinMakerContext,
    errorCode,
    errorMessage,
    createdAt,
    startedAt,
    completedAt,
  ];
}

PricingCatalogReference? _optionalCatalogReference(
  dynamic value,
  String expectedProvider,
) {
  if (value is! Map) return null;
  try {
    final reference = PricingCatalogReference.fromJson(
      Map<String, dynamic>.from(value),
    );
    return reference.provider.apiValue == expectedProvider.toLowerCase()
        ? reference
        : null;
  } on FormatException {
    return null;
  } on TypeError {
    return null;
  }
}

class PricingRefreshCredentialSummary extends Equatable {
  final String? connectionId;
  final String identityLabel;
  final String scope;
  final String? providerAccountId;
  final String? providerProjectId;
  final String? providerSubscriptionId;

  const PricingRefreshCredentialSummary({
    this.connectionId,
    required this.identityLabel,
    required this.scope,
    this.providerAccountId,
    this.providerProjectId,
    this.providerSubscriptionId,
  });

  factory PricingRefreshCredentialSummary.fromJson(Map<String, dynamic> json) {
    return PricingRefreshCredentialSummary(
      connectionId: _string(json['connection_id']),
      identityLabel: json['identity_label']?.toString() ?? '',
      scope: json['scope']?.toString() ?? 'user',
      providerAccountId: _string(json['provider_account_id']),
      providerProjectId: _string(json['provider_project_id']),
      providerSubscriptionId: _string(json['provider_subscription_id']),
    );
  }

  @override
  List<Object?> get props => [
    connectionId,
    identityLabel,
    scope,
    providerAccountId,
    providerProjectId,
    providerSubscriptionId,
  ];
}

enum AwsTwinMakerPricingPlanMode {
  basic('BASIC'),
  standard('STANDARD'),
  tieredBundle('TIERED_BUNDLE');

  final String apiValue;

  const AwsTwinMakerPricingPlanMode(this.apiValue);

  static AwsTwinMakerPricingPlanMode parse(dynamic value) {
    return values.firstWhere(
      (mode) => mode.apiValue == value,
      orElse: () => throw const FormatException(
        'Unsupported AWS TwinMaker pricing mode.',
      ),
    );
  }
}

enum AwsTwinMakerBundleTier {
  tier1('TIER_1'),
  tier2('TIER_2'),
  tier3('TIER_3'),
  tier4('TIER_4');

  final String apiValue;

  const AwsTwinMakerBundleTier(this.apiValue);

  static AwsTwinMakerBundleTier parse(dynamic value) {
    return values.firstWhere(
      (tier) => tier.apiValue == value,
      orElse: () =>
          throw const FormatException('Unsupported AWS TwinMaker bundle tier.'),
    );
  }
}

class AwsTwinMakerPricingBundle extends Equatable {
  final AwsTwinMakerBundleTier tier;
  final List<String> names;

  const AwsTwinMakerPricingBundle({required this.tier, required this.names});

  factory AwsTwinMakerPricingBundle._fromJson(dynamic value) {
    final json = _requiredMap(value);
    final rawNames = json['names'];
    if (rawNames is! List || rawNames.length > 20) {
      throw const FormatException('Invalid AWS TwinMaker bundle names.');
    }
    final names = rawNames
        .map((name) {
          final normalized = _requiredString(name);
          if (normalized.length > 128) {
            throw const FormatException('Invalid AWS TwinMaker bundle name.');
          }
          return normalized;
        })
        .toList(growable: false);
    return AwsTwinMakerPricingBundle(
      tier: AwsTwinMakerBundleTier.parse(json['tier']),
      names: List.unmodifiable(names),
    );
  }

  @override
  List<Object?> get props => [tier, names];
}

class AwsTwinMakerPricingPlan extends Equatable {
  final AwsTwinMakerPricingPlanMode mode;
  final int billableEntityCount;
  final DateTime? effectiveAt;
  final DateTime? updatedAt;
  final String? updateReason;
  final AwsTwinMakerPricingBundle? bundle;

  const AwsTwinMakerPricingPlan({
    required this.mode,
    required this.billableEntityCount,
    this.effectiveAt,
    this.updatedAt,
    this.updateReason,
    this.bundle,
  });

  factory AwsTwinMakerPricingPlan._fromJson(dynamic value) {
    final json = _requiredMap(value);
    final mode = AwsTwinMakerPricingPlanMode.parse(json['mode']);
    final count = json['billable_entity_count'];
    if (count is! int || count < 0) {
      throw const FormatException(
        'Invalid AWS TwinMaker billable entity count.',
      );
    }
    final rawBundle = json['bundle'];
    final bundle = rawBundle == null
        ? null
        : AwsTwinMakerPricingBundle._fromJson(rawBundle);
    if ((mode == AwsTwinMakerPricingPlanMode.tieredBundle) !=
        (bundle != null)) {
      throw const FormatException(
        'AWS TwinMaker bundle metadata does not match its pricing mode.',
      );
    }
    final updateReason = _optionalStrictString(json['update_reason']);
    if (updateReason != null && updateReason.length > 500) {
      throw const FormatException('Invalid AWS TwinMaker update reason.');
    }
    return AwsTwinMakerPricingPlan(
      mode: mode,
      billableEntityCount: count,
      effectiveAt: _optionalAwareDate(json['effective_at']),
      updatedAt: _optionalAwareDate(json['updated_at']),
      updateReason: updateReason,
      bundle: bundle,
    );
  }

  @override
  List<Object?> get props => [
    mode,
    billableEntityCount,
    effectiveAt,
    updatedAt,
    updateReason,
    bundle,
  ];
}

class AwsTwinMakerPricingContext extends Equatable {
  static const supportedSchemaVersion =
      'aws-twinmaker-account-pricing-context.v1';
  static final RegExp _regionPattern = RegExp(
    r'^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$',
  );
  static final RegExp _accountPattern = RegExp(r'^\d{12}$');

  final String schemaVersion;
  final String provider;
  final String service;
  final String region;
  final String? verifiedAccountId;
  final DateTime observedAt;
  final AwsTwinMakerPricingPlan currentPlan;
  final AwsTwinMakerPricingPlan? pendingPlan;
  final String? connectionId;

  const AwsTwinMakerPricingContext({
    required this.schemaVersion,
    required this.provider,
    required this.service,
    required this.region,
    required this.verifiedAccountId,
    required this.observedAt,
    required this.currentPlan,
    required this.pendingPlan,
    required this.connectionId,
  });

  static AwsTwinMakerPricingContext? tryFromJson(
    dynamic value, {
    String? credentialConnectionId,
    String? credentialAccountId,
  }) {
    try {
      final json = _requiredMap(value);
      final schemaVersion = _requiredString(json['schema_version']);
      final provider = _requiredString(json['provider']);
      final service = _requiredString(json['service']);
      final region = _requiredString(json['region']);
      if (schemaVersion != supportedSchemaVersion ||
          provider != 'aws' ||
          service != 'iot_twinmaker' ||
          !_regionPattern.hasMatch(region)) {
        throw const FormatException(
          'Unsupported AWS TwinMaker pricing context.',
        );
      }
      final verifiedAccountId = _optionalStrictString(
        json['verified_account_id'],
      );
      if (verifiedAccountId != null &&
          !_accountPattern.hasMatch(verifiedAccountId)) {
        throw const FormatException('Invalid verified AWS account ID.');
      }
      if (credentialAccountId != null &&
          verifiedAccountId != null &&
          credentialAccountId != verifiedAccountId) {
        throw const FormatException(
          'AWS TwinMaker pricing account binding mismatch.',
        );
      }

      final rawBinding = json['management_binding'];
      String? connectionId;
      if (rawBinding != null) {
        connectionId = _optionalStrictString(
          _requiredMap(rawBinding)['pricing_connection_id'],
        );
      }
      if (credentialConnectionId != null &&
          connectionId != null &&
          credentialConnectionId != connectionId) {
        throw const FormatException(
          'AWS TwinMaker pricing connection binding mismatch.',
        );
      }

      final rawPendingPlan = json['pending_plan'];
      return AwsTwinMakerPricingContext(
        schemaVersion: schemaVersion,
        provider: provider,
        service: service,
        region: region,
        verifiedAccountId: verifiedAccountId,
        observedAt: _requiredAwareDate(json['observed_at']),
        currentPlan: AwsTwinMakerPricingPlan._fromJson(json['current_plan']),
        pendingPlan: rawPendingPlan == null
            ? null
            : AwsTwinMakerPricingPlan._fromJson(rawPendingPlan),
        connectionId: connectionId,
      );
    } on FormatException {
      return null;
    } on TypeError {
      return null;
    }
  }

  @override
  List<Object?> get props => [
    schemaVersion,
    provider,
    service,
    region,
    verifiedAccountId,
    observedAt,
    currentPlan,
    pendingPlan,
    connectionId,
  ];
}

Map<String, dynamic> _map(dynamic value) {
  return value is Map ? Map<String, dynamic>.from(value) : const {};
}

Map<String, dynamic> _requiredMap(dynamic value) {
  if (value is! Map) {
    throw const FormatException('Expected a JSON object.');
  }
  return Map<String, dynamic>.from(value);
}

String? _string(dynamic value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

String _requiredString(dynamic value) {
  if (value is! String) {
    throw const FormatException('Expected a non-empty string.');
  }
  final result = _string(value);
  if (result == null) {
    throw const FormatException('Expected a non-empty string.');
  }
  return result;
}

String? _optionalStrictString(dynamic value) {
  return value == null ? null : _requiredString(value);
}

DateTime? _date(dynamic value) {
  return value == null ? null : DateTime.tryParse(value.toString());
}

DateTime _requiredAwareDate(dynamic value) {
  if (value is! String || !RegExp(r'(?:Z|[+-]\d{2}:\d{2})$').hasMatch(value)) {
    throw const FormatException('Expected a timezone-aware timestamp.');
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null || !parsed.isUtc) {
    throw const FormatException('Expected a timezone-aware timestamp.');
  }
  return parsed;
}

DateTime? _optionalAwareDate(dynamic value) {
  return value == null ? null : _requiredAwareDate(value);
}
