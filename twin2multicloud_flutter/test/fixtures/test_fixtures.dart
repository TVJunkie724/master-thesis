import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';

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
  
  /// Calculation params with all optional features enabled
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
    integrateErrorHandling: true,
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
  
  static Map<String, dynamic> get calcResultJson => <String, dynamic>{
    'result': <String, dynamic>{
      'awsCosts': <String, dynamic>{
        'L1': <String, dynamic>{'cost': 10.50, 'components': <String, dynamic>{'IoT Core': 5.0, 'Lambda': 5.5}},
        'L2': <String, dynamic>{'cost': 8.25, 'components': <String, dynamic>{'Step Functions': 8.25}},
        'L3_hot': <String, dynamic>{'cost': 2.0, 'components': <String, dynamic>{'S3': 2.0}},
        'L3_cool': <String, dynamic>{'cost': 1.0, 'components': <String, dynamic>{'S3 IA': 1.0}},
        'L3_archive': <String, dynamic>{'cost': 0.5, 'components': <String, dynamic>{'Glacier': 0.5}},
        'L4': <String, dynamic>{'cost': 15.0, 'components': <String, dynamic>{'IoT TwinMaker': 15.0}},
        'L5': <String, dynamic>{'cost': 20.0, 'components': <String, dynamic>{'Grafana': 20.0}},
      },
      'azureCosts': <String, dynamic>{
        'L1': <String, dynamic>{'cost': 12.00, 'components': <String, dynamic>{'IoT Hub': 7.0, 'Functions': 5.0}},
        'L2': <String, dynamic>{'cost': 9.50, 'components': <String, dynamic>{'Logic Apps': 9.5}},
        'L3_hot': <String, dynamic>{'cost': 2.5, 'components': <String, dynamic>{'Blob Hot': 2.5}},
        'L3_cool': <String, dynamic>{'cost': 1.2, 'components': <String, dynamic>{'Blob Cool': 1.2}},
        'L3_archive': <String, dynamic>{'cost': 0.6, 'components': <String, dynamic>{'Blob Archive': 0.6}},
        'L4': <String, dynamic>{'cost': 18.0, 'components': <String, dynamic>{'ADT': 18.0}},
        'L5': <String, dynamic>{'cost': 22.0, 'components': <String, dynamic>{'Managed Grafana': 22.0}},
      },
      'gcpCosts': <String, dynamic>{
        'L1': <String, dynamic>{'cost': 11.00, 'components': <String, dynamic>{'IoT Core': 6.0, 'Cloud Functions': 5.0}},
        'L2': <String, dynamic>{'cost': 7.00, 'components': <String, dynamic>{'Workflows': 7.0}},
        'L3_hot': <String, dynamic>{'cost': 1.8, 'components': <String, dynamic>{'GCS Standard': 1.8}},
        'L3_cool': <String, dynamic>{'cost': 0.9, 'components': <String, dynamic>{'GCS Nearline': 0.9}},
        'L3_archive': <String, dynamic>{'cost': 0.4, 'components': <String, dynamic>{'GCS Coldline': 0.4}},
      },
      'cheapestPath': <String>['L1_AWS', 'L2_GCP', 'L3_hot_GCP', 'L3_cool_GCP', 'L3_archive_GCP', 'L4_AWS', 'L5_AWS'],
      'transferCosts': <String, dynamic>{'L1_to_L2': 0.05, 'L2_to_L3': 0.02},
    }
  };
  
  static Map<String, dynamic> get emptyCalcResultJson => <String, dynamic>{
    'result': <String, dynamic>{
      'awsCosts': <String, dynamic>{},
      'azureCosts': <String, dynamic>{},
      'gcpCosts': <String, dynamic>{},
      'cheapestPath': <String>[],
    }
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
