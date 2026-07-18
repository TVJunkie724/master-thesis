import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/pricing_catalog.dart';

/// Test fixtures for consistent testing across test files.
abstract class TestFixtures {
  // ============================================================
  // CalcParams Fixtures
  // ============================================================

  /// Default calculation parameters
  static CalcParams get defaultCalcParams => CalcParams.defaultParams();

  /// Calculation params with 3D model enabled
  static CalcParams get calcParamsWith3DModel => CalcParams(
    numberOfDevices: 100,
    deviceSendingIntervalInMinutes: 2.0,
    averageSizeOfMessageInKb: 0.25,
    hotStorageDurationInMonths: 1,
    coolStorageDurationInMonths: 3,
    archiveStorageDurationInMonths: 12,
    needs3DModel: true,
    entityCount: 5,
    average3DModelSizeInMB: 50.0,
    dashboardRefreshesPerHour: 2,
    amountOfActiveEditors: 2,
    amountOfActiveViewers: 10,
  );

  /// Calculation params with every supported optional feature enabled
  static CalcParams get calcParamsFullyConfigured => CalcParams(
    numberOfDevices: 1000,
    deviceSendingIntervalInMinutes: 1.0,
    averageSizeOfMessageInKb: 1.0,
    numberOfDeviceTypes: 5,
    useEventChecking: true,
    eventsPerMessage: 3,
    triggerNotificationWorkflow: true,
    orchestrationActionsPerMessage: 5,
    returnFeedbackToDevice: true,
    numberOfEventActions: 2,
    integrateErrorHandling: false,
    hotStorageDurationInMonths: 3,
    coolStorageDurationInMonths: 12,
    archiveStorageDurationInMonths: 36,
    needs3DModel: true,
    entityCount: 10,
    average3DModelSizeInMB: 200.0,
    dashboardRefreshesPerHour: 10,
    apiCallsPerDashboardRefresh: 5,
    dashboardActiveHoursPerDay: 12,
    amountOfActiveEditors: 5,
    amountOfActiveViewers: 50,
    currency: 'EUR',
  );

  // ============================================================
  // Twin Fixtures
  // ============================================================

  static Map<String, dynamic> get draftTwinJson => {
    'id': 'twin-001',
    'name': 'Test Twin',
    'state': 'draft',
    'providers': ['AWS', 'Azure'],
    'created_at': '2025-12-27T10:00:00Z',
    'updated_at': '2025-12-27T12:00:00Z',
    'last_deployed_at': null,
  };

  static Map<String, dynamic> get deployedTwinJson => {
    'id': 'twin-002',
    'name': 'Deployed Twin',
    'state': 'deployed',
    'providers': ['AWS', 'Azure', 'GCP'],
    'created_at': '2025-12-20T10:00:00Z',
    'updated_at': '2025-12-27T12:00:00Z',
    'last_deployed_at': '2025-12-27T11:00:00Z',
  };

  static Map<String, dynamic> get errorTwinJson => {
    'id': 'twin-003',
    'name': 'Error Twin',
    'state': 'error',
    'providers': ['AWS'],
    'created_at': '2025-12-25T10:00:00Z',
    'updated_at': '2025-12-27T12:00:00Z',
    'last_deployed_at': null,
  };

  static Map<String, dynamic> get minimalTwinJson => {
    'id': 'twin-min',
    'name': 'Minimal',
    'state': null,
    'providers': null,
    'created_at': null,
    'updated_at': null,
    'last_deployed_at': null,
  };

  // ============================================================
  // CalcResult Fixtures
  // ============================================================

  static Map<String, dynamic> get pricingCatalogContextJson => {
    'schemaVersion': 'provider-pricing-catalog-context.v1',
    'catalogs': {
      'aws': _pricingCatalogReference(
        provider: 'aws',
        region: 'eu-central-1',
        marker: 'a',
      ),
      'azure': _pricingCatalogReference(
        provider: 'azure',
        region: 'westeurope',
        marker: 'b',
      ),
      'gcp': _pricingCatalogReference(
        provider: 'gcp',
        region: 'europe-west1',
        marker: 'c',
      ),
    },
  };

  static Map<String, dynamic> get calcResultJson => <String, dynamic>{
    'result': <String, dynamic>{
      'awsCosts': <String, dynamic>{
        'L1': <String, dynamic>{
          'cost': 10.50,
          'components': <String, dynamic>{'IoT Core': 5.0, 'Lambda': 5.5},
        },
        'L2': <String, dynamic>{
          'cost': 8.25,
          'components': <String, dynamic>{'Step Functions': 8.25},
        },
        'L3_hot': <String, dynamic>{
          'cost': 2.0,
          'components': <String, dynamic>{'S3': 2.0},
        },
        'L3_cool': <String, dynamic>{
          'cost': 1.0,
          'components': <String, dynamic>{'S3 IA': 1.0},
        },
        'L3_archive': <String, dynamic>{
          'cost': 0.5,
          'components': <String, dynamic>{'Glacier': 0.5},
        },
        'L4': <String, dynamic>{
          'cost': 15.0,
          'components': <String, dynamic>{'IoT TwinMaker': 15.0},
        },
        'L5': <String, dynamic>{
          'cost': 20.0,
          'components': <String, dynamic>{'Grafana': 20.0},
        },
      },
      'azureCosts': <String, dynamic>{
        'L1': <String, dynamic>{
          'cost': 12.00,
          'components': <String, dynamic>{'IoT Hub': 7.0, 'Functions': 5.0},
        },
        'L2': <String, dynamic>{
          'cost': 9.50,
          'components': <String, dynamic>{'Logic Apps': 9.5},
        },
        'L3_hot': <String, dynamic>{
          'cost': 2.5,
          'components': <String, dynamic>{'Blob Hot': 2.5},
        },
        'L3_cool': <String, dynamic>{
          'cost': 1.2,
          'components': <String, dynamic>{'Blob Cool': 1.2},
        },
        'L3_archive': <String, dynamic>{
          'cost': 0.6,
          'components': <String, dynamic>{'Blob Archive': 0.6},
        },
        'L4': <String, dynamic>{
          'cost': 18.0,
          'components': <String, dynamic>{'ADT': 18.0},
        },
        'L5': <String, dynamic>{
          'cost': 22.0,
          'components': <String, dynamic>{'Managed Grafana': 22.0},
        },
      },
      'gcpCosts': <String, dynamic>{
        'L1': <String, dynamic>{
          'cost': 11.00,
          'components': <String, dynamic>{
            'IoT Core': 6.0,
            'Cloud Functions': 5.0,
          },
        },
        'L2': <String, dynamic>{
          'cost': 7.00,
          'components': <String, dynamic>{'Workflows': 7.0},
        },
        'L3_hot': <String, dynamic>{
          'cost': 1.8,
          'components': <String, dynamic>{'GCS Standard': 1.8},
        },
        'L3_cool': <String, dynamic>{
          'cost': 0.9,
          'components': <String, dynamic>{'GCS Nearline': 0.9},
        },
        'L3_archive': <String, dynamic>{
          'cost': 0.4,
          'components': <String, dynamic>{'GCS Coldline': 0.4},
        },
      },
      'cheapestPath': <String>[
        'L1_AWS',
        'L2_GCP',
        'L3_hot_GCP',
        'L3_cool_GCP',
        'L3_archive_GCP',
        'L4_AWS',
        'L5_AWS',
      ],
      'transferCosts': <String, dynamic>{'L1_to_L2': 0.05, 'L2_to_L3': 0.02},
      'pricingCatalogs': pricingCatalogContextJson,
      'trace_schema_version': 'intent-result-trace.v1',
      'optimizationProfile': <String, dynamic>{
        'profile_id': 'cost_minimization_v1',
        'objective': 'cost',
        'metric_provider_ids': <String>['cost'],
        'calculation_model_ids': <String>['cost_model_v1'],
        'scoring_strategy_id': 'min_total_cost_v1',
        'intent_group_ids': <String>['cost'],
        'result_schema_version': 'cost-result.v1',
        'pricing_registry_version': 'pricing-registry.v1',
      },
      'evidenceReferences': <String, dynamic>{
        'pricing_registry': 'pricing_registry:pricing-registry.v1',
      },
      'intentTrace': <String, dynamic>{
        'schema_version': 'intent-result-trace.v1',
        'profile': <String, dynamic>{
          'profile_id': 'cost_minimization_v1',
          'objective': 'cost',
          'metric_provider_ids': <String>['cost'],
          'calculation_model_ids': <String>['cost_model_v1'],
          'scoring_strategy_id': 'min_total_cost_v1',
          'intent_group_ids': <String>['cost'],
          'result_schema_version': 'cost-result.v1',
          'pricing_registry_version': 'pricing-registry.v1',
        },
        'workload': <String, dynamic>{
          'inputs': <String, dynamic>{'numberOfDevices': 100},
          'derived': <String, dynamic>{'total_messages_per_month': 2160000},
        },
        'selected_path': <Map<String, dynamic>>[
          <String, dynamic>{
            'result_path': 'L1',
            'layer_cost_key': 'L1',
            'provider': 'AWS',
            'path_key': 'L1_AWS',
            'cost': 10.5,
          },
        ],
        'transfer_trace': <Map<String, dynamic>>[
          <String, dynamic>{
            'segment': 'L1_to_L2',
            'source_layer': 'L1',
            'target_layer': 'L2',
            'source_provider': 'AWS',
            'target_provider': 'GCP',
            'cost': 0.05,
            'source_intent_id': 'aws.transfer.egress',
            'evidence_reference_ids': <String>[
              'pricing_registry:pricing-registry.v1/aws.transfer.egress',
            ],
          },
        ],
        'records': <Map<String, dynamic>>[
          <String, dynamic>{
            'trace_id': 'trace:aws.l1.iot_core.message_tiers',
            'record_id': 'aws.l1.iot_core.message_tiers',
            'intent_id': 'aws.l1.iot_core',
            'provider': 'aws',
            'layer': 'L1_INGESTION',
            'service_key': 'iot_core',
            'field_id': 'message_tiers',
            'source': <String, dynamic>{
              'primary_source_type': 'provider_api',
              'refreshability': 'refreshable',
            },
            'pricing': <String, dynamic>{
              'canonical_unit': 'usd/message',
              'source_unit': 'tier_table',
            },
            'formula': <String, dynamic>{'binding_id': 'cost.l1.ingestion'},
            'contribution': <String, dynamic>{
              'selected': true,
              'path_key': 'L1_AWS',
              'cost': 10.5,
            },
            'verification': <String, dynamic>{
              'status': 'ready',
              'review_required': false,
              'publishable': true,
              'evidence_reference_id':
                  'pricing_registry:pricing-registry.v1/aws.l1.iot_core.message_tiers',
            },
          },
        ],
        'summary': <String, dynamic>{
          'record_count': 1,
          'selected_record_count': 1,
          'review_required_count': 0,
          'unsupported_count': 0,
          'selected_path_count': 1,
          'transfer_segment_count': 1,
          'publishable': true,
        },
      },
      'totalCost': 55.67,
    },
  };

  static Map<String, dynamic> get calcResultWithTransferEvidenceJson {
    final result = Map<String, dynamic>.from(
      calcResultJson['result'] as Map<String, dynamic>,
    );
    final calculationResult = <String, dynamic>{
      'L1': 'AWS',
      'L2': 'GCP',
      'L3': {'Hot': 'GCP', 'Cool': 'GCP', 'Archive': 'GCP'},
      'L4': 'AWS',
      'L5': 'AWS',
    };
    final providerByLayer = <String, String>{
      'L1': 'aws',
      'L2': 'gcp',
      'L3_hot': 'gcp',
      'L3_cool': 'gcp',
      'L3_archive': 'gcp',
      'L4': 'aws',
      'L5': 'aws',
    };
    final regions = <String, String>{
      'aws': 'eu-central-1',
      'azure': 'westeurope',
      'gcp': 'europe-west1',
    };
    final snapshots = <String, String>{
      for (final entry
          in (pricingCatalogContextJson['catalogs'] as Map).entries)
        entry.key.toString(): (entry.value as Map)['snapshotId'].toString(),
    };
    final policies = <String, Map<String, dynamic>>{
      'aws': {
        'networkTier': 'provider_default',
        'billingScope': 'account_aggregate_public_egress',
        'billingUnit': 'gb',
        'bytesPerBillingUnit': 1000000000,
      },
      'azure': {
        'networkTier': 'microsoft_premium_global_network',
        'billingScope': 'account_aggregate_public_egress',
        'billingUnit': 'gb',
        'bytesPerBillingUnit': 1000000000,
      },
      'gcp': {
        'networkTier': 'premium',
        'billingScope': 'sku_account_aggregate_public_egress',
        'billingUnit': 'gib',
        'bytesPerBillingUnit': 1073741824,
      },
    };
    final edges = <(String, String, String, String, String)>[
      ('L1_to_L2', 'L1', 'L2', 'L1_INGESTION', 'L2_PROCESSING'),
      ('L2_to_L3_hot', 'L2', 'L3_hot', 'L2_PROCESSING', 'L3_HOT_STORAGE'),
      (
        'L3_hot_to_L3_cool',
        'L3_hot',
        'L3_cool',
        'L3_HOT_STORAGE',
        'L3_COOL_STORAGE',
      ),
      (
        'L3_cool_to_L3_archive',
        'L3_cool',
        'L3_archive',
        'L3_COOL_STORAGE',
        'L3_ARCHIVE_STORAGE',
      ),
      ('L3_hot_to_L4', 'L3_hot', 'L4', 'L3_HOT_STORAGE', 'L4_TWIN_MANAGEMENT'),
      ('L4_to_L5', 'L4', 'L5', 'L4_TWIN_MANAGEMENT', 'L5_VISUALIZATION'),
    ];
    final routes = <Map<String, dynamic>>[];
    final routesByProvider = <String, List<Map<String, dynamic>>>{};
    for (final edge in edges) {
      final sourceProvider = providerByLayer[edge.$2]!;
      final destinationProvider = providerByLayer[edge.$3]!;
      final sameProvider = sourceProvider == destinationProvider;
      final policy = policies[sourceProvider]!;
      final volumeBytes = policy['bytesPerBillingUnit'] as int;
      final route = <String, dynamic>{
        'segmentId': edge.$1,
        'source': {
          'layer': edge.$4,
          'provider': sourceProvider,
          'region': regions[sourceProvider],
          'geography': 'europe',
        },
        'destination': {
          'layer': edge.$5,
          'provider': destinationProvider,
          'region': regions[destinationProvider],
          'geography': 'europe',
        },
        'routeClass': sameProvider
            ? 'same_provider_same_region'
            : 'cross_provider_public_internet',
        'networkTier': sameProvider ? 'not_applicable' : policy['networkTier'],
        'volumeBytes': volumeBytes,
        'poolId': sameProvider ? null : 'pool:$sourceProvider:test',
        'catalogSnapshotId': sameProvider ? null : snapshots[sourceProvider],
        'evidenceId': sameProvider ? null : 'transfer.$sourceProvider.test.v1',
        'tierContributions': sameProvider
            ? <Map<String, dynamic>>[]
            : [
                {
                  'tierId': 'free_${edge.$1}',
                  'fromQuantity': 0,
                  'toQuantity': 1,
                  'billableQuantity': 1,
                  'unitPrice': 0,
                  'cost': 0,
                },
              ],
        'egressCost': 0,
        'glueCost': 0,
        'totalCost': 0,
        'assumptions': ['fixture_edge=${edge.$1}'],
      };
      routes.add(route);
      if (!sameProvider) {
        routesByProvider.putIfAbsent(sourceProvider, () => []).add(route);
      }
    }
    final pools = <Map<String, dynamic>>[
      for (final provider in routesByProvider.keys)
        {
          'poolId': 'pool:$provider:test',
          'provider': provider,
          'routeClass': 'cross_provider_public_internet',
          'sourceGeography': 'europe',
          'destinationGeography': 'europe',
          'networkTier': policies[provider]!['networkTier'],
          'billingScope': policies[provider]!['billingScope'],
          'billingUnit': policies[provider]!['billingUnit'],
          'bytesPerBillingUnit': policies[provider]!['bytesPerBillingUnit'],
          'catalogSnapshotId': snapshots[provider],
          'evidenceId': 'transfer.$provider.test.v1',
          'aggregateVolumeBytes': routesByProvider[provider]!.fold<int>(
            0,
            (sum, route) => sum + route['volumeBytes'] as int,
          ),
          'aggregateEgressCost': 0,
        },
    ];
    return {
      'result': {
        ...result,
        'calculationResult': calculationResult,
        'currency': 'USD',
        'transferCosts': {
          for (final route in routes.where(
            (route) => route['routeClass'] == 'cross_provider_public_internet',
          ))
            route['segmentId'].toString(): route['totalCost'],
        },
        'transferPricingContext': {
          'schemaVersion': 'complete-path-transfer-pricing.v1',
          'currency': 'USD',
          'assumptions': ['deterministic_flutter_fixture'],
          'routes': routes,
          'pools': pools,
        },
        'optimizationDiagnostics': {
          'schemaVersion': 'complete-path-optimization.v1',
          'enumeratedPathCount': 972,
          'evaluatedPathCount': 972,
          'rejectedPathCount': 0,
          'rejectedByErrorCode': <String, int>{},
          'winningCandidateId': 'aws|gcp|gcp|gcp|gcp|aws|aws',
          'winningScore': result['totalCost'],
          'winningLayerCost': result['totalCost'],
          'winningTransferCost': 0,
          'tieBreakPolicy': 'canonical_provider_order',
          'canonicalProviderOrder': ['aws', 'azure', 'gcp'],
          'scoreUnit': 'USD/month',
        },
      },
    };
  }

  static Map<String, dynamic> get emptyCalcResultJson => <String, dynamic>{
    'result': <String, dynamic>{
      'awsCosts': <String, dynamic>{},
      'azureCosts': <String, dynamic>{},
      'gcpCosts': <String, dynamic>{},
      'cheapestPath': <String>[],
      'totalCost': 0.0,
    },
  };

  // ============================================================
  // Credential Fixtures
  // ============================================================

  static Map<String, String> get awsCredentials => {
    'access_key_id': 'AKIAXXXXXXXXXXXXXXXX',
    'secret_access_key': 'secretkey1234567890',
    'region': 'eu-central-1',
  };

  static Map<String, String> get azureCredentials => {
    'subscription_id': 'sub-12345',
    'client_id': 'client-12345',
    'client_secret': 'secret-12345',
    'tenant_id': 'tenant-12345',
    'region': 'westeurope',
  };

  static Map<String, String> get gcpCredentials => {
    'project_id': 'my-project',
    'billing_account': 'billing-12345',
    'region': 'europe-west1',
  };
}

Map<String, dynamic> _pricingCatalogReference({
  required String provider,
  required String region,
  required String marker,
}) {
  final identity = List.filled(64, marker).join();
  final fetchedAt = DateTime.utc(2026, 7, 17, 10);
  const providerSchemaVersion = 'pricing-provider-schema.v1';
  const contractVersion = '2026.07.17';
  const registryVersion = '2026.07.17';
  const mappingVersions = ['2026.07.17'];
  final contentDigest = 'sha256:$identity';
  final snapshotId = buildPricingCatalogSnapshotId(
    provider: provider,
    pricingRegion: region,
    providerSchemaVersion: providerSchemaVersion,
    contractVersion: contractVersion,
    registryVersion: registryVersion,
    mappingVersions: mappingVersions,
    fetchedAt: fetchedAt,
    contentDigest: contentDigest,
    source: 'reviewed_baseline',
    reviewStatus: 'reviewed',
  );
  return {
    'schemaVersion': 'pricing-catalog-reference.v1',
    'snapshotId': snapshotId,
    'provider': provider,
    'pricingRegion': region,
    'providerSchemaVersion': providerSchemaVersion,
    'contractVersion': contractVersion,
    'registryVersion': registryVersion,
    'mappingVersions': mappingVersions,
    'fetchedAt': fetchedAt.toIso8601String(),
    'contentDigest': contentDigest,
    'source': 'reviewed_baseline',
    'reviewStatus': 'reviewed',
    'publicationStatus': 'published',
    'calculationSource': 'reviewed_baseline',
  };
}
