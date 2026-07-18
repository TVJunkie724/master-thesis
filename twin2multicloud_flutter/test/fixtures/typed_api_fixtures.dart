import 'dart:convert';

import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployer_config.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/models/pricing_catalog.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';
import 'package:twin2multicloud_flutter/models/twin_config.dart';

import 'test_fixtures.dart';

abstract final class TypedApiFixtures {
  static final DateTime timestamp = DateTime.utc(2026, 7, 15, 10);

  static Twin twin({
    String id = 'twin-123',
    String name = 'Test Twin',
    String state = 'draft',
  }) => Twin(
    id: id,
    name: name,
    state: state,
    createdAt: timestamp,
    updatedAt: timestamp,
  );

  static TwinConfigData twinConfig({
    String twinId = 'twin-123',
    String twinState = 'draft',
    bool debugMode = false,
    int highestStepReached = 0,
    Set<CloudProvider> configuredProviders = const {},
    CalcParams? optimizerParams,
    OptimizationResultData? optimization,
  }) {
    return TwinConfigData(
      id: 'config-$twinId',
      twinId: twinId,
      twinState: twinState,
      debugMode: debugMode,
      providers: Map.unmodifiable({
        for (final provider in CloudProvider.values)
          provider: TwinProviderConfig(
            provider: provider,
            configured: configuredProviders.contains(provider),
            validated: configuredProviders.contains(provider),
            credentialSource: configuredProviders.contains(provider)
                ? TwinCredentialSource.cloudConnection
                : null,
            cloudConnectionId: configuredProviders.contains(provider)
                ? '${provider.apiValue}-connection'
                : null,
            region: provider == CloudProvider.aws ? 'eu-central-1' : null,
            secondaryRegion: switch (provider) {
              CloudProvider.aws => 'eu-central-1',
              CloudProvider.azure => 'westeurope',
              CloudProvider.gcp => null,
            },
            tertiaryRegion: provider == CloudProvider.azure
                ? 'westeurope'
                : null,
            projectId: provider == CloudProvider.gcp ? 'test-project' : null,
            billingAccountConfigured:
                provider == CloudProvider.gcp &&
                configuredProviders.contains(provider),
          ),
      }),
      highestStepReached: highestStepReached,
      optimizerParams: optimizerParams,
      optimization: optimization,
      updatedAt: timestamp,
    );
  }

  static OptimizationResultData optimization({
    List<String>? cheapestPath,
    double? totalCost,
  }) {
    final payload =
        jsonDecode(jsonEncode(TestFixtures.calcResultJson['result']))
            as Map<String, dynamic>;
    if (cheapestPath != null) payload['cheapestPath'] = cheapestPath;
    if (totalCost != null) payload['totalCost'] = totalCost;
    return OptimizationResultData.fromPayload(payload);
  }

  static OptimizerRunData optimizerRun({
    String id = 'run-123',
    String twinId = 'twin-123',
    OptimizationResultData? optimization,
  }) {
    final resolvedOptimization =
        optimization ?? TypedApiFixtures.optimization();
    return OptimizerRunData(
      id: id,
      twinId: twinId,
      optimization: resolvedOptimization,
      deploymentRun: deploymentRun(id: id, twinId: twinId),
      totalMonthlyCost: resolvedOptimization.result.totalCost,
      currency: 'USD',
      createdAt: timestamp,
      completedAt: timestamp.add(const Duration(seconds: 1)),
    );
  }

  static OptimizerDeploymentRunData deploymentRun({
    String id = 'run-123',
    String twinId = 'twin-123',
    DateTime? selectedForDeploymentAt,
  }) {
    final specification = deploymentSpecificationJson(runId: id);
    return OptimizerDeploymentRunData.fromDetailJson({
      'id': id,
      'twin_id': twinId,
      'status': 'succeeded',
      'deployment_compatibility_status': 'ready',
      'deployment_specification_digest': specification['digest'],
      'deployment_specification_version': specification['schema_version'],
      'resolved_deployment_specification': specification,
      'created_at': timestamp.toIso8601String(),
      'selected_for_deployment_at': selectedForDeploymentAt?.toIso8601String(),
    });
  }

  static Map<String, dynamic> deploymentSpecificationJson({
    String runId = 'run-123',
  }) {
    final specification = <String, dynamic>{
      'schema_version': 'resolved-deployment-specification.v1',
      'calculation_run_id': runId,
      'architecture_profile': {
        'profile_id': 'five-layer-baseline',
        'profile_version': '1',
      },
      'optimization_context': {
        'optimization_profile_id': 'cost_minimization_v1',
        'optimization_profile_version': '2026.07.17',
        'calculation_strategy_id': 'cost_calculation_v2',
        'formula_set_id': 'cost_formula_set_v1',
        'workload_contract_id': 'digital_twin_workload_v1',
        'pricing_registry_version': '2026.07.17',
        'catalog_references': {
          for (final provider in CloudProvider.values)
            provider.apiValue: {
              'snapshot_id':
                  'pcs_${provider.apiValue.padRight(64, provider.apiValue[0]).substring(0, 64)}',
              'pricing_region': switch (provider) {
                CloudProvider.aws => 'eu-central-1',
                CloudProvider.azure => 'westeurope',
                CloudProvider.gcp => 'europe-west1',
              },
              'content_digest':
                  'sha256:${List.filled(64, switch (provider) {
                    CloudProvider.aws => '1',
                    CloudProvider.azure => '2',
                    CloudProvider.gcp => '3',
                  }).join()}',
            },
        },
      },
      'currency': 'USD',
      'components': [
        for (final slot in ResolvedDeploymentSlot.values.where(
          (item) => item.isArchitectureSlot,
        ))
          {
            'component_id': '${slot.apiValue}.aws.test',
            'slot_id': slot.apiValue,
            'provider': 'aws',
            'service_id': 'aws.test',
            'required': true,
            'dimensions': [
              {
                'dimension_id': '${slot.apiValue}.tier',
                'classification': 'deployable_selection',
                'value': 'standard',
                'formula_reference': 'formula_set:cost_formula_set_v1',
                'evidence_reference':
                    'deployment_registry:resolved-deployment-dimensions.v1',
                'terraform_target': '${slot.apiValue}_tier',
              },
            ],
          },
      ],
    };
    specification['digest'] =
        ResolvedDeploymentSpecificationData.calculateDigest(specification);
    return specification;
  }

  static OptimizerConfigData optimizerConfig({
    String twinId = 'twin-123',
    CalcParams? params,
    OptimizationResultData? optimization,
    CheapestPath? cheapestPath,
    PricingCatalogContext? pricingCatalogContext,
  }) {
    final resolvedOptimization =
        optimization ?? TypedApiFixtures.optimization();
    final resolvedPricingContext =
        pricingCatalogContext ??
        resolvedOptimization.result.pricingCatalogContext;
    return OptimizerConfigData(
      id: 'optimizer-$twinId',
      twinId: twinId,
      params: params ?? TestFixtures.defaultCalcParams,
      optimization: resolvedOptimization,
      cheapestPath:
          cheapestPath ??
          CheapestPath.fromSegments(resolvedOptimization.result.cheapestPath),
      calculatedAt: timestamp,
      pricingCatalogContext: resolvedPricingContext,
      updatedAt: timestamp,
    );
  }

  static PricingCatalogContext pricingCatalogContext() =>
      PricingCatalogContext.fromJson(TestFixtures.pricingCatalogContextJson);

  static const DeployerConfigData deployerConfig = DeployerConfigData(
    deployerDigitalTwinName: 'Test Twin',
    configEventsJson: '{"events":[]}',
    configIotDevicesJson: '{"devices":[]}',
    payloadsJson: '{"payloads":[]}',
    stateMachineContent: 'workflow',
    hierarchyContent: '{"hierarchy":[]}',
    sceneConfigContent: '{"scenes":[]}',
    userConfigContent: '{"users":[]}',
    processorContents: {'processor-a': 'def handler(): pass'},
  );
}
