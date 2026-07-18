import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:equatable/equatable.dart';

import 'cloud_connection.dart';
import 'json_contract.dart';

enum PricingCatalogSource {
  providerApi('provider_api', 'Provider API'),
  officialStaticDocumentation(
    'official_static_documentation',
    'Official static documentation',
  ),
  officialCalculatorReference(
    'official_calculator_reference',
    'Official calculator reference',
  ),
  curatedModelConstant('curated_model_constant', 'Curated model constant'),
  reviewedBaseline('reviewed_baseline', 'Reviewed baseline');

  final String apiValue;
  final String label;

  const PricingCatalogSource(this.apiValue, this.label);

  static PricingCatalogSource fromApiValue(String value) {
    return values.firstWhere(
      (source) => source.apiValue == value,
      orElse: () => throw const FormatException(
        'Invalid API contract: pricing catalog source is unsupported.',
      ),
    );
  }
}

enum PricingCatalogReviewStatus {
  reviewed('reviewed');

  final String apiValue;

  const PricingCatalogReviewStatus(this.apiValue);

  static PricingCatalogReviewStatus fromApiValue(String value) {
    if (value != reviewed.apiValue) {
      throw const FormatException(
        'Invalid API contract: pricing catalog is not reviewed.',
      );
    }
    return reviewed;
  }
}

enum PricingCatalogPublicationStatus {
  published('published');

  final String apiValue;

  const PricingCatalogPublicationStatus(this.apiValue);

  static PricingCatalogPublicationStatus fromApiValue(String value) {
    if (value != published.apiValue) {
      throw const FormatException(
        'Invalid API contract: pricing catalog is not published.',
      );
    }
    return published;
  }
}

enum PricingCatalogCalculationSource {
  fresh('fresh', 'Fresh provider catalog'),
  lastKnownGood('last_known_good', 'Last known good'),
  reviewedBaseline('reviewed_baseline', 'Reviewed baseline');

  final String apiValue;
  final String label;

  const PricingCatalogCalculationSource(this.apiValue, this.label);

  static PricingCatalogCalculationSource fromApiValue(String value) {
    return values.firstWhere(
      (source) => source.apiValue == value,
      orElse: () => throw const FormatException(
        'Invalid API contract: pricing calculation source is unsupported.',
      ),
    );
  }
}

class PricingCatalogReference extends Equatable {
  static const supportedSchemaVersion = 'pricing-catalog-reference.v1';
  static final RegExp _snapshotIdPattern = RegExp(r'^pcs_[0-9a-f]{64}$');
  static final RegExp _digestPattern = RegExp(r'^sha256:[0-9a-f]{64}$');
  static final RegExp _regionPattern = RegExp(r'^[a-z][a-z0-9-]{1,62}$');
  static final RegExp _awsRegionPattern = RegExp(
    r'^[a-z]{2}(?:-gov)?-[a-z0-9-]+-\d+$',
  );
  static final RegExp _awareTimestampPattern = RegExp(
    r'(?:Z|[+-]\d{2}:\d{2})$',
  );
  static const _fields = {
    'schemaVersion',
    'snapshotId',
    'provider',
    'pricingRegion',
    'providerSchemaVersion',
    'contractVersion',
    'registryVersion',
    'mappingVersions',
    'fetchedAt',
    'contentDigest',
    'source',
    'reviewStatus',
    'publicationStatus',
    'calculationSource',
  };

  final String schemaVersion;
  final String snapshotId;
  final CloudProvider provider;
  final String pricingRegion;
  final String providerSchemaVersion;
  final String contractVersion;
  final String registryVersion;
  final List<String> mappingVersions;
  final DateTime fetchedAt;
  final String contentDigest;
  final PricingCatalogSource source;
  final PricingCatalogReviewStatus reviewStatus;
  final PricingCatalogPublicationStatus publicationStatus;
  final PricingCatalogCalculationSource calculationSource;

  const PricingCatalogReference._({
    required this.schemaVersion,
    required this.snapshotId,
    required this.provider,
    required this.pricingRegion,
    required this.providerSchemaVersion,
    required this.contractVersion,
    required this.registryVersion,
    required this.mappingVersions,
    required this.fetchedAt,
    required this.contentDigest,
    required this.source,
    required this.reviewStatus,
    required this.publicationStatus,
    required this.calculationSource,
  });

  factory PricingCatalogReference.fromJson(Map<String, dynamic> json) {
    _rejectUnknownFields(json, _fields, 'pricing catalog reference');
    final schemaVersion = JsonContract.requiredString(json, 'schemaVersion');
    if (schemaVersion != supportedSchemaVersion) {
      throw const FormatException(
        'Invalid API contract: unsupported pricing catalog reference schema.',
      );
    }

    final provider = _parseProvider(
      JsonContract.requiredString(json, 'provider'),
    );
    final snapshotId = JsonContract.requiredString(json, 'snapshotId');
    final pricingRegion = JsonContract.requiredString(json, 'pricingRegion');
    final providerSchemaVersion = _boundedVersion(
      json,
      'providerSchemaVersion',
    );
    final contractVersion = _boundedVersion(json, 'contractVersion');
    final registryVersion = _boundedVersion(json, 'registryVersion');
    final contentDigest = JsonContract.requiredString(json, 'contentDigest');
    final source = PricingCatalogSource.fromApiValue(
      JsonContract.requiredString(json, 'source'),
    );
    final reviewStatus = PricingCatalogReviewStatus.fromApiValue(
      JsonContract.requiredString(json, 'reviewStatus'),
    );
    final publicationStatus = PricingCatalogPublicationStatus.fromApiValue(
      JsonContract.requiredString(json, 'publicationStatus'),
    );
    final calculationSource = PricingCatalogCalculationSource.fromApiValue(
      JsonContract.requiredString(json, 'calculationSource'),
    );
    final fetchedAt = _requiredAwareDate(json, 'fetchedAt');
    final mappingVersions = _mappingVersions(json);

    if (!_snapshotIdPattern.hasMatch(snapshotId)) {
      throw const FormatException(
        'Invalid API contract: snapshotId is not an immutable catalog ID.',
      );
    }
    if (!_regionPattern.hasMatch(pricingRegion) ||
        (provider == CloudProvider.aws &&
            !_awsRegionPattern.hasMatch(pricingRegion))) {
      throw const FormatException(
        'Invalid API contract: pricingRegion is invalid for its provider.',
      );
    }
    if (!_digestPattern.hasMatch(contentDigest)) {
      throw const FormatException(
        'Invalid API contract: contentDigest is not a SHA-256 digest.',
      );
    }
    if ((source == PricingCatalogSource.reviewedBaseline) !=
        (calculationSource ==
            PricingCatalogCalculationSource.reviewedBaseline)) {
      throw const FormatException(
        'Invalid API contract: baseline source metadata is inconsistent.',
      );
    }
    final expectedSnapshotId = buildPricingCatalogSnapshotId(
      provider: provider.apiValue,
      pricingRegion: pricingRegion,
      providerSchemaVersion: providerSchemaVersion,
      contractVersion: contractVersion,
      registryVersion: registryVersion,
      mappingVersions: mappingVersions,
      fetchedAt: fetchedAt,
      contentDigest: contentDigest,
      source: source.apiValue,
      reviewStatus: reviewStatus.apiValue,
    );
    if (snapshotId != expectedSnapshotId) {
      throw const FormatException(
        'Invalid API contract: snapshotId does not match catalog identity.',
      );
    }

    return PricingCatalogReference._(
      schemaVersion: schemaVersion,
      snapshotId: snapshotId,
      provider: provider,
      pricingRegion: pricingRegion,
      providerSchemaVersion: providerSchemaVersion,
      contractVersion: contractVersion,
      registryVersion: registryVersion,
      mappingVersions: mappingVersions,
      fetchedAt: fetchedAt,
      contentDigest: contentDigest,
      source: source,
      reviewStatus: reviewStatus,
      publicationStatus: publicationStatus,
      calculationSource: calculationSource,
    );
  }

  String get shortenedDigest => '${contentDigest.substring(0, 19)}...';

  String get calculationSourceLabel => calculationSource.label;

  String get sourceSummary => source.label == calculationSourceLabel
      ? source.label
      : '${source.label} · $calculationSourceLabel';

  Map<String, dynamic> toJson() => {
    'schemaVersion': schemaVersion,
    'snapshotId': snapshotId,
    'provider': provider.apiValue,
    'pricingRegion': pricingRegion,
    'providerSchemaVersion': providerSchemaVersion,
    'contractVersion': contractVersion,
    'registryVersion': registryVersion,
    'mappingVersions': mappingVersions,
    'fetchedAt': fetchedAt.toUtc().toIso8601String(),
    'contentDigest': contentDigest,
    'source': source.apiValue,
    'reviewStatus': reviewStatus.apiValue,
    'publicationStatus': publicationStatus.apiValue,
    'calculationSource': calculationSource.apiValue,
  };

  @override
  List<Object?> get props => [
    schemaVersion,
    snapshotId,
    provider,
    pricingRegion,
    providerSchemaVersion,
    contractVersion,
    registryVersion,
    mappingVersions,
    fetchedAt,
    contentDigest,
    source,
    reviewStatus,
    publicationStatus,
    calculationSource,
  ];
}

/// Builds the cross-runtime immutable pricing catalog identity.
String buildPricingCatalogSnapshotId({
  required String provider,
  required String pricingRegion,
  required String providerSchemaVersion,
  required String contractVersion,
  required String registryVersion,
  required List<String> mappingVersions,
  required DateTime fetchedAt,
  required String contentDigest,
  required String source,
  required String reviewStatus,
}) {
  final identity = <String, dynamic>{
    'content_digest': contentDigest,
    'contract_version': contractVersion,
    'fetched_at': _pythonUtcIso(fetchedAt),
    'mapping_versions': mappingVersions,
    'pricing_region': pricingRegion,
    'provider': provider,
    'provider_schema_version': providerSchemaVersion,
    'registry_version': registryVersion,
    'review_status': reviewStatus,
    'source': source,
  };
  final canonicalJson = _ensureAscii(jsonEncode(identity));
  return 'pcs_${sha256.convert(utf8.encode(canonicalJson))}';
}

class PricingCatalogContext extends Equatable {
  static const supportedSchemaVersion = 'provider-pricing-catalog-context.v1';
  static const _fields = {'schemaVersion', 'catalogs'};

  final String schemaVersion;
  final Map<CloudProvider, PricingCatalogReference> catalogs;

  const PricingCatalogContext._({
    required this.schemaVersion,
    required this.catalogs,
  });

  factory PricingCatalogContext.fromJson(Map<String, dynamic> json) {
    _rejectUnknownFields(json, _fields, 'pricing catalog context');
    final schemaVersion = JsonContract.requiredString(json, 'schemaVersion');
    if (schemaVersion != supportedSchemaVersion) {
      throw const FormatException(
        'Invalid API contract: unsupported pricing catalog context schema.',
      );
    }
    final rawCatalogs = JsonContract.requiredObject(json, 'catalogs');
    final expectedKeys = CloudProvider.values
        .map((provider) => provider.apiValue)
        .toSet();
    if (rawCatalogs.keys.toSet().difference(expectedKeys).isNotEmpty ||
        expectedKeys.difference(rawCatalogs.keys.toSet()).isNotEmpty) {
      throw const FormatException(
        'Invalid API contract: pricing catalogs must contain AWS, Azure, and GCP.',
      );
    }

    final catalogs = <CloudProvider, PricingCatalogReference>{};
    for (final provider in CloudProvider.values) {
      final rawReference = rawCatalogs[provider.apiValue];
      if (rawReference is! Map) {
        throw FormatException(
          'Invalid API contract: catalogs.${provider.apiValue} must be an object.',
        );
      }
      final reference = PricingCatalogReference.fromJson(
        Map<String, dynamic>.from(rawReference),
      );
      if (reference.provider != provider) {
        throw const FormatException(
          'Invalid API contract: pricing catalog key and provider do not match.',
        );
      }
      catalogs[provider] = reference;
    }

    return PricingCatalogContext._(
      schemaVersion: schemaVersion,
      catalogs: Map.unmodifiable(catalogs),
    );
  }

  PricingCatalogReference reference(CloudProvider provider) =>
      catalogs[provider] ??
      (throw StateError('Pricing catalog context is incomplete.'));

  Map<String, dynamic> toJson() => {
    'schemaVersion': schemaVersion,
    'catalogs': {
      for (final provider in CloudProvider.values)
        provider.apiValue: reference(provider).toJson(),
    },
  };

  @override
  List<Object?> get props => [schemaVersion, catalogs];
}

CloudProvider _parseProvider(String value) {
  try {
    return CloudProvider.fromApiValue(value);
  } on ArgumentError {
    throw const FormatException(
      'Invalid API contract: pricing catalog contains an unknown provider.',
    );
  }
}

DateTime _requiredAwareDate(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  if (!PricingCatalogReference._awareTimestampPattern.hasMatch(value)) {
    throw FormatException(
      'Invalid API contract: $field must include a timezone.',
    );
  }
  final parsed = DateTime.tryParse(value);
  if (parsed == null) {
    throw FormatException(
      'Invalid API contract: $field must be an ISO-8601 timestamp.',
    );
  }
  return parsed.toUtc();
}

String _boundedVersion(Map<String, dynamic> json, String field) {
  final value = JsonContract.requiredString(json, field);
  if (value.length > 128) {
    throw FormatException(
      'Invalid API contract: $field exceeds its size limit.',
    );
  }
  return value;
}

List<String> _mappingVersions(Map<String, dynamic> json) {
  final value = json['mappingVersions'];
  if (value is! List ||
      value.isEmpty ||
      value.any(
        (item) => item is! String || item.isEmpty || item.length > 128,
      )) {
    throw const FormatException(
      'Invalid API contract: mappingVersions must be a non-empty string array.',
    );
  }
  final versions = List<String>.from(value);
  final sortedUnique = versions.toSet().toList()..sort();
  if (versions.length != sortedUnique.length ||
      !_sameStrings(versions, sortedUnique)) {
    throw const FormatException(
      'Invalid API contract: mappingVersions must be sorted and unique.',
    );
  }
  return List.unmodifiable(versions);
}

bool _sameStrings(List<String> left, List<String> right) {
  if (left.length != right.length) return false;
  for (var index = 0; index < left.length; index++) {
    if (left[index] != right[index]) return false;
  }
  return true;
}

String _pythonUtcIso(DateTime value) {
  final utc = value.toUtc();
  final date =
      '${utc.year.toString().padLeft(4, '0')}-'
      '${utc.month.toString().padLeft(2, '0')}-'
      '${utc.day.toString().padLeft(2, '0')}T'
      '${utc.hour.toString().padLeft(2, '0')}:'
      '${utc.minute.toString().padLeft(2, '0')}:'
      '${utc.second.toString().padLeft(2, '0')}';
  final microseconds =
      utc.millisecond * Duration.microsecondsPerMillisecond + utc.microsecond;
  final fraction = microseconds == 0
      ? ''
      : '.${microseconds.toString().padLeft(6, '0')}';
  return '$date${fraction}Z';
}

String _ensureAscii(String value) {
  final output = StringBuffer();
  for (final rune in value.runes) {
    if (rune <= 0x7f) {
      output.writeCharCode(rune);
    } else if (rune <= 0xffff) {
      output
        ..write(r'\u')
        ..write(rune.toRadixString(16).padLeft(4, '0'));
    } else {
      final adjusted = rune - 0x10000;
      final high = 0xd800 + (adjusted >> 10);
      final low = 0xdc00 + (adjusted & 0x3ff);
      output
        ..write(r'\u')
        ..write(high.toRadixString(16).padLeft(4, '0'))
        ..write(r'\u')
        ..write(low.toRadixString(16).padLeft(4, '0'));
    }
  }
  return output.toString();
}

void _rejectUnknownFields(
  Map<String, dynamic> json,
  Set<String> allowed,
  String contract,
) {
  if (json.keys.any((key) => !allowed.contains(key))) {
    throw FormatException(
      'Invalid API contract: $contract contains unsupported fields.',
    );
  }
}
