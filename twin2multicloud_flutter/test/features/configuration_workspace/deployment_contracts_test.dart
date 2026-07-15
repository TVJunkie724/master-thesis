import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/deployment/deployment_contracts.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';
import 'package:twin2multicloud_flutter/models/deployer_artifact_validation.dart';

void main() {
  final state = WizardState(
    calcResult: CalcResult(
      totalCost: 0,
      awsCosts: ProviderCosts(),
      azureCosts: ProviderCosts(),
      gcpCosts: ProviderCosts(),
      cheapestPath: const ['L2_GCP', 'L4_AWS', 'L5_AZURE'],
      inputParamsUsed: const InputParamsUsed(),
    ),
  );

  test('maps each validation boundary to its authoritative provider', () {
    expect(
      buildDeploymentValidationRequest(
        state: state,
        type: DeployerArtifactType.config,
        content: '{}',
      ).provider,
      isNull,
    );
    expect(
      buildDeploymentValidationRequest(
        state: state,
        type: DeployerArtifactType.processor,
        content: 'def handler(): pass',
        entityId: 'sensor-1',
      ),
      isA<DeployerArtifactValidationRequest>()
          .having((request) => request.provider, 'provider', 'GCP')
          .having((request) => request.entityId, 'entity', 'sensor-1'),
    );
    expect(
      buildDeploymentValidationRequest(
        state: state,
        type: DeployerArtifactType.sceneConfig,
        content: '{}',
      ).provider,
      'AWS',
    );
    expect(
      buildDeploymentValidationRequest(
        state: state,
        type: DeployerArtifactType.userConfig,
        content: '{}',
        providerOverride: state.layer5Provider,
      ).provider,
      'AZURE',
    );
  });
}
