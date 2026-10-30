import 'dart:convert';
import 'dart:typed_data';

enum AzureCredentialFileKind { servicePrincipal, compatibilityBundle }

abstract class AzureCredentialFileErrorCode {
  static const invalidSize = 'azure_credential_invalid_size';
  static const invalidEncoding = 'azure_credential_invalid_encoding';
  static const invalidJson = 'azure_credential_invalid_json';
  static const unsupportedShape = 'azure_credential_unsupported_shape';
  static const missingAdministratorFields =
      'azure_credential_missing_administrator_fields';
  static const incompleteBundle = 'azure_credential_incomplete_bundle';
}

class AzureCredentialFileSelection {
  final Uint8List _normalizedUploadBytes;
  final String? displayName;
  final String? subscriptionId;
  final String? region;
  final String? regionIotHub;
  final String? regionDigitalTwin;
  final AzureCredentialFileKind kind;

  AzureCredentialFileSelection({
    required Uint8List normalizedUploadBytes,
    required this.displayName,
    required this.subscriptionId,
    required this.region,
    required this.regionIotHub,
    required this.regionDigitalTwin,
    required this.kind,
  }) : _normalizedUploadBytes = Uint8List.fromList(normalizedUploadBytes);

  Uint8List get normalizedUploadBytes =>
      Uint8List.fromList(_normalizedUploadBytes);
}

const _maxFileBytes = 128 * 1024;
const _standardFields = <String>{
  'appId',
  'clientId',
  'clientSecret',
  'displayName',
  'name',
  'password',
  'subscription',
  'subscriptionId',
  'tenant',
  'tenantId',
};
const _compatibilityRootFields = <String>{'aws', 'azure', 'gcp'};
const _compatibilityAzureFields = <String>{
  'azure_subscription_id',
  'azure_client_id',
  'azure_client_secret',
  'azure_preparation_client_id',
  'azure_preparation_client_secret',
  'azure_tenant_id',
  'azure_region',
  'azure_region_iothub',
  'azure_region_digital_twin',
};

AzureCredentialFileSelection parseAzureCredentialFileSelection(
  Uint8List bytes,
) {
  if (bytes.isEmpty || bytes.length > _maxFileBytes) {
    throw const FormatException(AzureCredentialFileErrorCode.invalidSize);
  }

  late final String text;
  try {
    text = utf8.decode(bytes).replaceFirst('\u{FEFF}', '');
  } on FormatException {
    throw const FormatException(AzureCredentialFileErrorCode.invalidEncoding);
  }
  if (text.contains('\u0000')) {
    throw const FormatException(AzureCredentialFileErrorCode.invalidEncoding);
  }

  late final Object? decoded;
  try {
    decoded = jsonDecode(text);
  } on FormatException {
    throw const FormatException(AzureCredentialFileErrorCode.invalidJson);
  }
  if (decoded is! Map<String, dynamic>) {
    throw const FormatException(AzureCredentialFileErrorCode.invalidJson);
  }

  if (decoded.containsKey('azure')) {
    return _parseWrappedCompatibilityBundle(decoded);
  }
  if (decoded.keys.any((field) => field.startsWith('azure_'))) {
    return _parseCompatibilityAzure(decoded);
  }
  return _parseStandardServicePrincipal(decoded);
}

AzureCredentialFileSelection _parseWrappedCompatibilityBundle(
  Map<String, dynamic> root,
) {
  if (!_hasOnlyFields(root, _compatibilityRootFields)) {
    throw const FormatException(AzureCredentialFileErrorCode.unsupportedShape);
  }
  final azure = root['azure'];
  if (azure is! Map<String, dynamic>) {
    throw const FormatException(AzureCredentialFileErrorCode.unsupportedShape);
  }
  return _parseCompatibilityAzure(azure);
}

AzureCredentialFileSelection _parseCompatibilityAzure(
  Map<String, dynamic> value,
) {
  if (!_hasOnlyFields(value, _compatibilityAzureFields)) {
    throw const FormatException(AzureCredentialFileErrorCode.unsupportedShape);
  }

  final subscriptionId = _requiredString(
    value,
    'azure_subscription_id',
    maxLength: 256,
    errorCode: AzureCredentialFileErrorCode.incompleteBundle,
  );
  final administratorClientId = _requiredString(
    value,
    'azure_client_id',
    maxLength: 256,
    errorCode: AzureCredentialFileErrorCode.incompleteBundle,
  );
  final administratorClientSecret = _requiredString(
    value,
    'azure_client_secret',
    maxLength: 4096,
    errorCode: AzureCredentialFileErrorCode.incompleteBundle,
  );
  final tenantId = _requiredString(
    value,
    'azure_tenant_id',
    maxLength: 256,
    errorCode: AzureCredentialFileErrorCode.incompleteBundle,
  );

  return AzureCredentialFileSelection(
    normalizedUploadBytes: _normalizedBytes(
      clientId: administratorClientId,
      clientSecret: administratorClientSecret,
      tenantId: tenantId,
      subscriptionId: subscriptionId,
    ),
    displayName: null,
    subscriptionId: subscriptionId,
    region: _optionalString(value, 'azure_region', maxLength: 80),
    regionIotHub: _optionalString(value, 'azure_region_iothub', maxLength: 80),
    regionDigitalTwin: _optionalString(
      value,
      'azure_region_digital_twin',
      maxLength: 80,
    ),
    kind: AzureCredentialFileKind.compatibilityBundle,
  );
}

AzureCredentialFileSelection _parseStandardServicePrincipal(
  Map<String, dynamic> value,
) {
  if (!_hasOnlyFields(value, _standardFields)) {
    throw const FormatException(AzureCredentialFileErrorCode.unsupportedShape);
  }

  final administratorClientId = _requiredAlias(value, const [
    'clientId',
    'appId',
  ], maxLength: 256);
  final administratorClientSecret = _requiredAlias(value, const [
    'clientSecret',
    'password',
  ], maxLength: 4096);
  final tenantId = _requiredAlias(value, const [
    'tenantId',
    'tenant',
  ], maxLength: 256);
  final subscriptionId = _optionalAlias(value, const [
    'subscriptionId',
    'subscription',
  ], maxLength: 256);

  return AzureCredentialFileSelection(
    normalizedUploadBytes: _normalizedBytes(
      clientId: administratorClientId,
      clientSecret: administratorClientSecret,
      tenantId: tenantId,
      subscriptionId: subscriptionId,
    ),
    displayName: _optionalAlias(value, const [
      'displayName',
      'name',
    ], maxLength: 120),
    subscriptionId: subscriptionId,
    region: null,
    regionIotHub: null,
    regionDigitalTwin: null,
    kind: AzureCredentialFileKind.servicePrincipal,
  );
}

Uint8List _normalizedBytes({
  required String clientId,
  required String clientSecret,
  required String tenantId,
  required String? subscriptionId,
}) => Uint8List.fromList(
  utf8.encode(
    jsonEncode({
      'appId': clientId,
      'password': clientSecret,
      'tenant': tenantId,
      if (subscriptionId != null) 'subscriptionId': subscriptionId,
    }),
  ),
);

bool _hasOnlyFields(Map<String, dynamic> value, Set<String> allowed) =>
    value.keys.every(allowed.contains);

String _requiredAlias(
  Map<String, dynamic> value,
  List<String> aliases, {
  required int maxLength,
}) {
  final result = _optionalAlias(value, aliases, maxLength: maxLength);
  if (result == null) {
    throw const FormatException(
      AzureCredentialFileErrorCode.missingAdministratorFields,
    );
  }
  return result;
}

String? _optionalAlias(
  Map<String, dynamic> value,
  List<String> aliases, {
  required int maxLength,
}) {
  for (final alias in aliases) {
    if (!value.containsKey(alias)) continue;
    final candidate = _optionalString(value, alias, maxLength: maxLength);
    if (candidate != null) return candidate;
  }
  return null;
}

String _requiredString(
  Map<String, dynamic> value,
  String field, {
  required int maxLength,
  required String errorCode,
}) {
  final result = _optionalString(value, field, maxLength: maxLength);
  if (result == null) throw FormatException(errorCode);
  return result;
}

String? _optionalString(
  Map<String, dynamic> value,
  String field, {
  required int maxLength,
}) {
  final raw = value[field];
  if (raw == null) return null;
  if (raw is! String) {
    throw const FormatException(AzureCredentialFileErrorCode.unsupportedShape);
  }
  final normalized = raw.trim();
  if (normalized.isEmpty) return null;
  if (normalized.length > maxLength) {
    throw const FormatException(AzureCredentialFileErrorCode.unsupportedShape);
  }
  return normalized;
}
