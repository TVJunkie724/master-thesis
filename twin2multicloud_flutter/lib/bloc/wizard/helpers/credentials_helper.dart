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
  
  /// Build credentials for config update payload
  /// Only includes credentials that need updating
  static Map<String, dynamic> buildCredentialsPayload(WizardState state) {
    final config = <String, dynamic>{};
    
    if (state.aws.source == CredentialSource.newlyEntered) {
      config['aws'] = state.aws.values;
    } else if (state.aws.source == CredentialSource.cleared) {
      config['aws'] = null; // Delete from DB
    }
    
    if (state.azure.source == CredentialSource.newlyEntered) {
      config['azure'] = state.azure.values;
    } else if (state.azure.source == CredentialSource.cleared) {
      config['azure'] = null;
    }
    
    if (state.gcp.source == CredentialSource.newlyEntered) {
      config['gcp'] = state.gcp.values;
    } else if (state.gcp.source == CredentialSource.cleared) {
      config['gcp'] = null;
    }
    
    return config;
  }
  
  /// Check if any provider has valid credentials
  static bool hasAnyValidCredentials(WizardState state) {
    return state.aws.isValid || state.azure.isValid || state.gcp.isValid;
  }
  
  /// Get set of configured providers
  static Set<String> getConfiguredProviders(WizardState state) {
    final providers = <String>{};
    if (state.aws.isValid) providers.add('AWS');
    if (state.azure.isValid) providers.add('AZURE');
    if (state.gcp.isValid) providers.add('GCP');
    return providers;
  }
  
  /// Hydrate credentials from config response
  static Map<String, ProviderCredentials> hydrateCredentials(
    Map<String, dynamic> config
  ) {
    ProviderCredentials awsCreds = const ProviderCredentials();
    ProviderCredentials azureCreds = const ProviderCredentials();
    ProviderCredentials gcpCreds = const ProviderCredentials();
    
    final sources = config['credential_sources'];
    if (sources is Map && sources['aws'] == 'cloud_connection') {
      awsCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: extractCredentialsFromFlatConfig(config, 'aws'),
      );
    }
    if (sources is Map && sources['azure'] == 'cloud_connection') {
      azureCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: extractCredentialsFromFlatConfig(config, 'azure'),
      );
    }
    if (sources is Map && sources['gcp'] == 'cloud_connection') {
      gcpCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: extractCredentialsFromFlatConfig(config, 'gcp'),
      );
    }
    
    return {
      'aws': awsCreds,
      'azure': azureCreds,
      'gcp': gcpCreds,
    };
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
  static bool areAllRequiredFieldsFilled(String provider, Map<String, String>? credentials) {
    if (credentials == null) return false;
    final required = getRequiredFields(provider);
    for (final field in required) {
      if (!credentials.containsKey(field) || credentials[field]?.isEmpty == true) {
        return false;
      }
    }
    return true;
  }
}
