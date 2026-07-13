// lib/bloc/wizard/helpers/deployer_helper.dart
// Extracted deployer/Step 3 config logic

import '../wizard_state.dart';
import '../../../models/wizard_config_requests.dart';

/// Helper class for deployer configuration operations
/// Extracts logic from WizardBloc to improve maintainability
class DeployerHelper {
  /// Build deployer config payload for API update
  static Map<String, dynamic> buildDeployerConfigPayload(WizardState state) {
    return buildDeployerConfigRequest(state).toJson();
  }

  /// Build typed deployer config request for API update.
  static DeployerConfigUpdateRequest buildDeployerConfigRequest(
    WizardState state,
  ) => state.deployerConfigData.toUpdateRequest();
}
