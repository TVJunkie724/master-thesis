import '../../../../bloc/wizard/wizard.dart';
import '../../../../models/deployer_artifact_validation.dart';

typedef WizardEventSink = void Function(WizardEvent event);

enum DeploymentTaskFocus { all, dataContracts, userLogic, twinAssets }

DeployerArtifactValidationRequest buildDeploymentValidationRequest({
  required WizardState state,
  required DeployerArtifactType type,
  required String content,
  String? entityId,
  String? providerOverride,
}) {
  final provider = switch (type.boundary) {
    DeployerValidationBoundary.config => null,
    DeployerValidationBoundary.layer2 => state.layer2Provider,
    DeployerValidationBoundary.layer4Or5 =>
      providerOverride ?? state.layer4Provider,
  };

  return DeployerArtifactValidationRequest(
    type: type,
    content: content,
    provider: provider,
    entityId: entityId,
  );
}
