import 'package:equatable/equatable.dart';

class PricingReviewStateResponse extends Equatable {
  final String schemaVersion;
  final Map<String, ProviderPricingReviewState> providers;
  final Map<String, dynamic> optimizer;

  const PricingReviewStateResponse({
    required this.schemaVersion,
    required this.providers,
    this.optimizer = const {},
  });

  factory PricingReviewStateResponse.fromJson(Map<String, dynamic> json) {
    final providerJson = json['providers'] as Map<String, dynamic>? ?? {};
    return PricingReviewStateResponse(
      schemaVersion: json['schema_version']?.toString() ?? '',
      providers: providerJson.map(
        (key, value) => MapEntry(
          key,
          ProviderPricingReviewState.fromJson(
            Map<String, dynamic>.from(value as Map),
          ),
        ),
      ),
      optimizer: json['optimizer'] is Map
          ? Map<String, dynamic>.from(json['optimizer'] as Map)
          : const {},
    );
  }

  ProviderPricingReviewState? provider(String provider) {
    return providers[provider.toLowerCase()];
  }

  @override
  List<Object?> get props => [schemaVersion, providers, optimizer];
}

class ProviderPricingReviewState extends Equatable {
  final String provider;
  final String state;
  final bool reviewRequired;
  final bool canCalculate;
  final String calculationSource;
  final String pricingFreshness;
  final String? age;
  final String? status;
  final bool isFresh;
  final int? thresholdDays;
  final List<String> missingKeys;
  final List<PricingReviewReason> reviewReasons;
  final List<String> actions;
  final String? lastKnownGoodUpdatedAt;

  const ProviderPricingReviewState({
    required this.provider,
    required this.state,
    required this.reviewRequired,
    required this.canCalculate,
    required this.calculationSource,
    required this.pricingFreshness,
    this.age,
    this.status,
    required this.isFresh,
    this.thresholdDays,
    this.missingKeys = const [],
    this.reviewReasons = const [],
    this.actions = const [],
    this.lastKnownGoodUpdatedAt,
  });

  factory ProviderPricingReviewState.fromJson(Map<String, dynamic> json) {
    return ProviderPricingReviewState(
      provider: json['provider']?.toString() ?? '',
      state: json['state']?.toString() ?? 'failed',
      reviewRequired: _boolValue(json['review_required']),
      canCalculate: json['can_calculate'] as bool? ?? false,
      calculationSource:
          json['calculation_source']?.toString() ?? 'unavailable',
      pricingFreshness: json['pricing_freshness']?.toString() ?? 'unavailable',
      age: json['age']?.toString(),
      status: json['status']?.toString(),
      isFresh: _boolValue(json['is_fresh']),
      thresholdDays: _intValue(json['threshold_days']),
      missingKeys: _stringList(json['missing_keys']),
      reviewReasons: (json['review_reasons'] as List<dynamic>? ?? [])
          .whereType<Map>()
          .map((item) {
            return PricingReviewReason.fromJson(
              Map<String, dynamic>.from(item),
            );
          })
          .toList(),
      actions: _stringList(json['actions']),
      lastKnownGoodUpdatedAt: json['last_known_good_updated_at']?.toString(),
    );
  }

  String get badgeLabel {
    return switch (state) {
      'fresh' => 'Fresh',
      'stale' => 'Stale',
      'review_required' => 'Review',
      'missing' => 'Missing',
      'failed' => 'Failed',
      _ => 'Unknown',
    };
  }

  String get sourceLabel {
    return switch (calculationSource) {
      'fresh' => 'Fresh pricing',
      'stale' => 'Stale cached pricing',
      'last_known_good' => 'Using last-known-good',
      'fallback_static' => 'Using static fallback',
      _ => 'No calculation pricing',
    };
  }

  String get primaryMessage {
    if (reviewReasons.isNotEmpty) {
      return reviewReasons.first.reason;
    }
    return switch (state) {
      'fresh' => 'Ready for calculation',
      'stale' => 'Refresh recommended before calculation',
      'review_required' => 'Pricing needs review before publishing',
      'missing' => 'Pricing data is missing',
      'failed' => 'Pricing status failed',
      _ => 'Pricing status is unknown',
    };
  }

  @override
  List<Object?> get props => [
    provider,
    state,
    reviewRequired,
    canCalculate,
    calculationSource,
    pricingFreshness,
    age,
    status,
    isFresh,
    thresholdDays,
    missingKeys,
    reviewReasons,
    actions,
    lastKnownGoodUpdatedAt,
  ];
}

class PricingReviewReason extends Equatable {
  final String status;
  final String reason;
  final String? intentId;
  final List<String> errors;
  final List<String> missingKeys;

  const PricingReviewReason({
    required this.status,
    required this.reason,
    this.intentId,
    this.errors = const [],
    this.missingKeys = const [],
  });

  factory PricingReviewReason.fromJson(Map<String, dynamic> json) {
    return PricingReviewReason(
      status: json['status']?.toString() ?? '',
      reason: json['reason']?.toString() ?? '',
      intentId: json['intent_id']?.toString(),
      errors: _stringList(json['errors']),
      missingKeys: _stringList(json['missing_keys']),
    );
  }

  @override
  List<Object?> get props => [status, reason, intentId, errors, missingKeys];
}

List<String> _stringList(dynamic value) {
  if (value is! List) return const [];
  return value.map((item) => item.toString()).toList();
}

bool _boolValue(dynamic value) {
  if (value is bool) return value;
  if (value is String) return value.toLowerCase() == 'true';
  return false;
}

int? _intValue(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}
