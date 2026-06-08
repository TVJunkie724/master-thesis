// lib/bloc/wizard/helpers/credentials_helper.dart
// Extracted credential management logic

import '../wizard_state.dart';

/// Helper class for credential-related operations
/// Extracts logic from WizardBloc to improve maintainability
class CredentialsHelper {
  /// Extract masked credential values from config response
  static Map<String, String> extractMaskedCredentials(dynamic config) {
    if (config == null || config is! Map) return {};
    final result = <String, String>{};
    for (final entry in config.entries) {
      if (entry.value != null) {
        result[entry.key.toString()] = '••••••••'; // Masked
      }
    }
    return result;
  }

  /// Extract non-secret credential fields (regions, etc.) from the FLAT
  /// config response (`{aws_region: ..., aws_sso_region: ..., ...}`).
  ///
  /// The backend never returns secret fields like access keys, so we mask them
  /// with bullets when the provider is configured. Public/non-secret fields
  /// (regions, project_id) are returned as their actual values so the form
  /// reflects what's stored in the DB.
  static Map<String, String> extractCredentialsFromFlatConfig(
    Map<String, dynamic> config,
    String provider,
  ) {
    final prefix = '${provider}_';
    final result = <String, String>{};

    // Per-provider list of non-secret fields the backend exposes by name.
    // Field names are stored WITHOUT the provider prefix to match the form's
    // CredentialField.name (e.g. "region", "sso_region", "region_iothub").
    const nonSecretFields = <String, List<String>>{
      'aws': ['region', 'sso_region'],
      'azure': ['region', 'region_iothub', 'region_digital_twin'],
      'gcp': ['project_id', 'region'],
    };

    for (final field in nonSecretFields[provider] ?? const []) {
      final value = config['$prefix$field'];
      if (value != null && value.toString().isNotEmpty) {
        result[field] = value.toString();
      }
    }

    // Mask secret fields only for active CloudConnection-backed providers.
    // Older per-twin credential rows are intentionally ignored by the backend
    // read model and should not hydrate as usable configuration.
    const secretFields = <String, List<String>>{
      'aws': ['access_key_id', 'secret_access_key', 'session_token'],
      'azure': ['subscription_id', 'client_id', 'client_secret', 'tenant_id'],
      'gcp': ['billing_account', 'service_account_json'],
    };

    final sources = config['credential_sources'];
    final source = sources is Map ? sources[provider] : null;
    if (source == 'cloud_connection') {
      for (final field in secretFields[provider] ?? const []) {
        result.putIfAbsent(field, () => '••••••••');
      }
    }

    return result;
  }

  /// Hydrate credentials from config response
  static Map<String, ProviderCredentials> hydrateCredentials(
    Map<String, dynamic> config,
  ) {
    final awsCreds = hydrateProviderCredentials(config, 'aws');
    final azureCreds = hydrateProviderCredentials(config, 'azure');
    final gcpCreds = hydrateProviderCredentials(config, 'gcp');

    return {'aws': awsCreds, 'azure': azureCreds, 'gcp': gcpCreds};
  }

  /// Hydrate one provider from the canonical CloudConnection read model or
  /// from legacy per-twin credential flags while old drafts still exist.
  static ProviderCredentials hydrateProviderCredentials(
    Map<String, dynamic> config,
    String provider,
  ) {
    if (!isProviderConfigured(config, provider)) {
      return const ProviderCredentials();
    }
    return ProviderCredentials(
      isValid: true,
      source: CredentialSource.inherited,
      values: {
        ...extractCredentialsFromFlatConfig(config, provider),
        ...extractCredentialsFromNestedConfig(config, provider),
      },
    );
  }

  /// True when either the canonical CloudConnection model or legacy config says
  /// this provider is configured. The legacy branch is a read-only compatibility
  /// bridge for existing drafts; new saves still use CloudConnection ids.
  static bool isProviderConfigured(
    Map<String, dynamic> config,
    String provider,
  ) {
    if (config['${provider}_cloud_connection_id'] != null) {
      return true;
    }
    final sources = config['credential_sources'];
    if (sources is Map && sources[provider] == 'cloud_connection') {
      return true;
    }
    if (config['${provider}_configured'] == true) {
      return true;
    }
    final nested = config[provider];
    return nested is Map && nested.isNotEmpty;
  }

  /// Extract legacy nested credential fields returned by older edit-mode
  /// payloads. Values are masked because they represent stored credentials.
  static Map<String, String> extractCredentialsFromNestedConfig(
    Map<String, dynamic> config,
    String provider,
  ) {
    final nested = config[provider];
    if (nested is! Map) return {};
    return extractMaskedCredentials(nested);
  }

  /// Check if a credentials map has stored values
  static bool hasStoredCredentials(Map<String, String>? credentials) {
    if (credentials == null) return false;
    return credentials.isNotEmpty;
  }

  /// Get required fields for a provider
  static List<String> getRequiredFields(String provider) {
    switch (provider.toLowerCase()) {
      case 'aws':
        return ['access_key_id', 'secret_access_key', 'region'];
      case 'azure':
        return ['subscription_id', 'client_id', 'client_secret', 'tenant_id'];
      case 'gcp':
        return ['project_id', 'service_account_json'];
      default:
        return [];
    }
  }

  /// Check if all required fields for a provider are filled
  static bool areAllRequiredFieldsFilled(
    String provider,
    Map<String, String>? credentials,
  ) {
    if (credentials == null) return false;
    final required = getRequiredFields(provider);
    for (final field in required) {
      if (!credentials.containsKey(field) ||
          credentials[field]?.isEmpty == true) {
        return false;
      }
    }
    return true;
  }
}
