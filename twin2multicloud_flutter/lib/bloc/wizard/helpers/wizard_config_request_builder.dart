import '../../../models/cloud_connection.dart';
import '../../../models/wizard_config_requests.dart';
import '../wizard_state.dart';
import 'deployer_helper.dart';

class WizardConfigRequestBuilder {
  const WizardConfigRequestBuilder._();

  static TwinConfigUpdateRequest buildTwinConfigRequest(WizardState state) {
    return TwinConfigUpdateRequest(
      debugMode: state.debugMode,
      cloudConnections: {
        for (final provider in CloudProvider.values)
          provider.apiValue: state.selectedCloudConnectionIds[provider],
      },
      clearAws: state.aws.source == CredentialSource.cleared,
      clearAzure: state.azure.source == CredentialSource.cleared,
      clearGcp: state.gcp.source == CredentialSource.cleared,
      optimizerParams: state.calcParams?.toJson(),
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
}
