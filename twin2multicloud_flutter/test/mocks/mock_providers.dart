// Mock Providers for Flutter Testing
// Provides Riverpod provider overrides for widget testing

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';
import 'package:twin2multicloud_flutter/models/user.dart';

/// Creates a ProviderContainer with common mocks for testing.
/// 
/// Usage:
/// ```dart
/// final container = createMockProviderContainer(
///   twins: [mockTwin1, mockTwin2],
///   user: mockUser,
/// );
/// ```
ProviderContainer createMockProviderContainer({
  List<Twin>? twins,
  User? user,
  String? themeMode,
}) {
  return ProviderContainer();
}

/// Mock user for testing
User createMockUser({
  String id = 'test-user-id',
  String email = 'test@example.com',
  String? name,
  String? themePreference,
}) {
  return User(
    id: id,
    email: email,
    name: name,
    themePreference: themePreference ?? 'dark',
  );
}

/// Mock twin for testing
Twin createMockTwin({
  String id = 'test-twin-id',
  String name = 'Test Twin',
  String state = 'draft',
  List<String>? providers,
  DateTime? createdAt,
  DateTime? updatedAt,
  DateTime? lastDeployedAt,
}) {
  return Twin.fromJson({
    'id': id,
    'name': name,
    'state': state,
    'providers': providers ?? ['AWS', 'Azure'],
    'created_at': createdAt?.toIso8601String() ?? DateTime.now().toIso8601String(),
    'updated_at': updatedAt?.toIso8601String() ?? DateTime.now().toIso8601String(),
    if (lastDeployedAt != null) 'last_deployed_at': lastDeployedAt.toIso8601String(),
  });
}

/// Sample twins for list testing
List<Twin> createMockTwinsList() {
  return [
    createMockTwin(
      id: 'twin-1',
      name: 'Production Twin',
      state: 'deployed',
      providers: ['AWS', 'Azure', 'GCP'],
    ),
    createMockTwin(
      id: 'twin-2',
      name: 'Development Twin',
      state: 'draft',
      providers: ['AWS'],
    ),
    createMockTwin(
      id: 'twin-3',
      name: 'Error Twin',
      state: 'error',
      providers: ['Azure'],
    ),
  ];
}

/// Mock credentials for testing
Map<String, dynamic> createMockAwsCredentials({
  bool valid = true,
}) {
  return {
    'aws_access_key_id': 'AKIAXXXXXXXXXXXXXXXX',
    'aws_secret_access_key': 'secret-key-12345',
    'aws_region': 'eu-central-1',
    if (!valid) 'aws_access_key_id': '', // Invalid if empty
  };
}

Map<String, dynamic> createMockAzureCredentials({
  bool valid = true,
}) {
  return {
    'azure_subscription_id': 'sub-12345',
    'azure_client_id': 'client-12345',
    'azure_client_secret': 'secret-12345',
    'azure_tenant_id': 'tenant-12345',
    'azure_location': 'westeurope',
    if (!valid) 'azure_subscription_id': '', // Invalid if empty
  };
}

Map<String, dynamic> createMockGcpCredentials({
  bool valid = true,
  bool asJson = false,
}) {
  final baseCredentials = {
    'gcp_project_id': 'my-project-id',
    'gcp_region': 'europe-west1',
    if (!valid) 'gcp_project_id': '', // Invalid if empty
  };
  
  if (asJson) {
    baseCredentials['gcp_credentials_file'] = '''{
      "type": "service_account",
      "project_id": "my-project-id",
      "private_key_id": "key-12345",
      "private_key": "-----BEGIN PRIVATE KEY-----\\nMOCK\\n-----END PRIVATE KEY-----",
      "client_email": "sa@my-project-id.iam.gserviceaccount.com",
      "client_id": "123456789"
    }''';
  } else {
    baseCredentials['gcp_credentials_file'] = '/path/to/credentials.json';
  }
  
  return baseCredentials;
}

/// Mock calculation result for optimizer testing
Map<String, dynamic> createMockCalcResult({
  bool includeGcpL4L5 = false,
}) {
  return {
    'result': {
      'awsCosts': {
        'L1': {'cost': 10.50, 'components': {'IoT Core': 5.0, 'Lambda': 5.5}},
        'L2': {'cost': 8.25, 'components': {'Step Functions': 8.25}},
        'L3_hot': {'cost': 2.0, 'components': {'DynamoDB': 2.0}},
        'L3_cool': {'cost': 1.0, 'components': {'S3 IA': 1.0}},
        'L3_archive': {'cost': 0.5, 'components': {'Glacier': 0.5}},
        'L4': {'cost': 15.0, 'components': {'IoT TwinMaker': 15.0}},
        'L5': {'cost': 20.0, 'components': {'Managed Grafana': 20.0}},
      },
      'azureCosts': {
        'L1': {'cost': 12.00, 'components': {'IoT Hub': 7.0, 'Functions': 5.0}},
        'L2': {'cost': 9.50, 'components': {'Logic Apps': 9.5}},
        'L3_hot': {'cost': 2.5, 'components': {'Cosmos DB': 2.5}},
        'L3_cool': {'cost': 1.2, 'components': {'Blob Cool': 1.2}},
        'L3_archive': {'cost': 0.6, 'components': {'Blob Archive': 0.6}},
        'L4': {'cost': 18.0, 'components': {'ADT': 18.0}},
        'L5': {'cost': 22.0, 'components': {'Managed Grafana': 22.0}},
      },
      'gcpCosts': {
        'L1': {'cost': 11.00, 'components': {'IoT Core': 6.0, 'Cloud Functions': 5.0}},
        'L2': {'cost': 7.00, 'components': {'Workflows': 7.0}},
        'L3_hot': {'cost': 1.8, 'components': {'Firestore': 1.8}},
        'L3_cool': {'cost': 0.9, 'components': {'GCS Nearline': 0.9}},
        'L3_archive': {'cost': 0.4, 'components': {'GCS Coldline': 0.4}},
        if (includeGcpL4L5) 'L4': {'cost': 20.0, 'components': {'Custom': 20.0}},
        if (includeGcpL4L5) 'L5': {'cost': 25.0, 'components': {'Custom': 25.0}},
      },
      'cheapestPath': ['L1_AWS', 'L2_GCP', 'L3_hot_GCP', 'L3_cool_GCP', 'L3_archive_GCP', 'L4_AWS', 'L5_AWS'],
      'transferCosts': {'L1_to_L2': 0.05, 'L2_to_L3': 0.02},
    }
  };
}

/// Mock deployer config for Step 3 testing
Map<String, dynamic> createMockDeployerConfig({
  bool withL2 = false,
  bool withL4 = false,
  bool withL5 = false,
}) {
  return {
    'twin_id': 'test-twin-id',
    'config_json': '{"version": "1.0"}',
    'config_events': '{"events": []}',
    'config_iot_devices': '{"devices": []}',
    if (withL2) 'processor_aws': 'def handler(event): pass',
    if (withL2) 'processor_azure': 'def main(req): pass',
    if (withL4) 'hierarchy_aws': '{"entities": []}',
    if (withL4) 'hierarchy_azure': '{"entities": []}',
    if (withL5) 'user_config_json': '{"panels": []}',
  };
}
