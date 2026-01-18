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
    
    if (config['aws_configured'] == true) {
      awsCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: extractMaskedCredentials(config['aws']),
      );
    }
    if (config['azure_configured'] == true) {
      azureCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: extractMaskedCredentials(config['azure']),
      );
    }
    if (config['gcp_configured'] == true) {
      gcpCreds = ProviderCredentials(
        isValid: true,
        source: CredentialSource.inherited,
        values: extractMaskedCredentials(config['gcp']),
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
