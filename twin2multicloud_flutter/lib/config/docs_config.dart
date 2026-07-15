abstract final class DocsConfig {
  static const String _configuredBaseUrl = String.fromEnvironment(
    'DOCS_BASE_URL',
    defaultValue: 'http://localhost:5010',
  );

  static String get baseUrl {
    return normalizeBaseUrl(_configuredBaseUrl);
  }

  static String normalizeBaseUrl(String value) {
    final normalized = value.trim().replaceFirst(RegExp(r'/+$'), '');
    if (normalized.isEmpty) {
      throw StateError('DOCS_BASE_URL must not be empty.');
    }
    final uri = Uri.tryParse(normalized);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      throw StateError('DOCS_BASE_URL must be an absolute HTTP(S) URL.');
    }
    if (uri.scheme != 'http' && uri.scheme != 'https') {
      throw StateError('DOCS_BASE_URL must use HTTP or HTTPS.');
    }
    return normalized;
  }

  static String get cloudSetupUrl => '$baseUrl/cloud-setup/';

  static String getProviderLinksUrl(String provider, {String? baseUrl}) {
    final fragment = switch (provider.trim().toLowerCase()) {
      'aws' => 'aws',
      'azure' => 'azure',
      'gcp' || 'google' => 'gcp',
      _ => throw ArgumentError.value(
        provider,
        'provider',
        'Unsupported provider',
      ),
    };
    final normalizedBase = normalizeBaseUrl(baseUrl ?? DocsConfig.baseUrl);
    return Uri.parse(
      '$normalizedBase/cloud-setup/provider-links/',
    ).replace(fragment: fragment).toString();
  }
}
