// lib/bloc/wizard/helpers/credentials_helper.dart
// Extracted credential management logic

import '../../../models/cloud_connection.dart';
import '../../../models/twin_config.dart';
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

  static Map<String, String> _credentialDisplayValues(
    TwinProviderConfig config,
  ) {
    final result = <String, String>{};
    void add(String key, String? value) {
      if (value != null && value.isNotEmpty) result[key] = value;
    }

    add('region', config.region);
    switch (config.provider) {
      case CloudProvider.aws:
        add('sso_region', config.secondaryRegion);
      case CloudProvider.azure:
        add('region_iothub', config.secondaryRegion);
        add('region_digital_twin', config.tertiaryRegion);
      case CloudProvider.gcp:
        add('project_id', config.projectId);
    }

    const secretFields = <CloudProvider, List<String>>{
      CloudProvider.aws: [
        'access_key_id',
        'secret_access_key',
        'session_token',
      ],
      CloudProvider.azure: [
        'subscription_id',
        'client_id',
        'client_secret',
        'tenant_id',
      ],
      CloudProvider.gcp: ['billing_account', 'service_account_json'],
    };
    for (final field in secretFields[config.provider] ?? const []) {
      result.putIfAbsent(field, () => '••••••••');
    }
    return result;
  }

  /// Hydrate credentials from config response
  static Map<String, ProviderCredentials> hydrateCredentials(
    TwinConfigData config,
  ) {
    return {
      for (final provider in CloudProvider.values)
        provider.apiValue: hydrateProviderCredentials(config, provider),
    };
  }

  /// Hydrate one provider from the canonical CloudConnection read model.
  static ProviderCredentials hydrateProviderCredentials(
    TwinConfigData config,
    CloudProvider provider,
  ) {
    final providerConfig = config.provider(provider);
    if (!providerConfig.usesCloudConnection) {
      return const ProviderCredentials();
    }
    return ProviderCredentials(
      isValid: true,
      source: CredentialSource.inherited,
      values: _credentialDisplayValues(providerConfig),
    );
  }

  /// True when the canonical CloudConnection model configures the provider.
  static bool isProviderConfigured(
    TwinConfigData config,
    CloudProvider provider,
  ) => config.provider(provider).usesCloudConnection;

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
