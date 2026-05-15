import '../../../models/cloud_connection.dart';
import '../../../models/wizard_config_requests.dart';
import '../wizard_state.dart';
import 'deployer_helper.dart';

class WizardConfigRequestBuilder {
  const WizardConfigRequestBuilder._();

  static TwinConfigUpdateRequest buildTwinConfigRequest(WizardState state) {
    final optimizerResult = state.calcResultRaw?['result'];
    return TwinConfigUpdateRequest(
      debugMode: state.debugMode,
      cloudConnections: {
        for (final provider in CloudProvider.values)
          provider.apiValue: state.selectedCloudConnectionIds[provider],
      },
      aws: _legacyCredentialsFor(state, CloudProvider.aws),
      azure: _legacyCredentialsFor(state, CloudProvider.azure),
      gcp: _legacyCredentialsFor(state, CloudProvider.gcp),
      clearAws: state.aws.source == CredentialSource.cleared,
      clearAzure: state.azure.source == CredentialSource.cleared,
      clearGcp: state.gcp.source == CredentialSource.cleared,
      optimizerParams: state.calcParams?.toJson(),
      optimizerResult: optimizerResult is Map
          ? Map<String, dynamic>.from(optimizerResult)
          : null,
      highestStepReached: state.highestStepReached,
    );
  }

  static DeployerConfigUpdateRequest buildDeployerConfigRequest(
    WizardState state,
  ) {
    return DeployerHelper.buildDeployerConfigRequest(state);
  }

  static bool shouldPersistDeployerConfig(WizardState state) {
    if (state.currentStep >= 2 || state.highestStepReached >= 2) {
      return true;
    }
    return buildDeployerConfigRequest(state).hasMeaningfulValues;
  }

  static Map<String, dynamic>? _legacyCredentialsFor(
    WizardState state,
    CloudProvider provider,
  ) {
    if (state.selectedCloudConnectionIds[provider] != null) {
      return null;
    }

    final credentials = switch (provider) {
      CloudProvider.aws => state.aws,
      CloudProvider.azure => state.azure,
      CloudProvider.gcp => state.gcp,
    };

    if (credentials.source != CredentialSource.newlyEntered) {
      return null;
    }

    return Map<String, dynamic>.from(credentials.values);
  }
}
