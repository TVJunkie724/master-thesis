// test/bloc/wizard/services/wizard_init_service_test.dart
// Unit tests for WizardInitService (stateless, no mocks required)

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/deployer_config.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/services/wizard_init_service.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard_state.dart';

import '../../../fixtures/typed_api_fixtures.dart';

void main() {
  late WizardInitService service;

  setUp(() {
    service = WizardInitService();
  });

  group('WizardInitService', () {
    group('initializeCreateMode', () {
      test('returns fresh state with create mode', () {
        final state = service.initializeCreateMode();

        expect(state.mode, WizardMode.create);
        expect(state.status, WizardStatus.ready);
        expect(state.currentStep, 0);
        expect(state.twinId, isNull);
      });
    });

    group('initializeEditMode', () {
      test('hydrates state from twin data', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'TestTwin'),
          config: TypedApiFixtures.twinConfig(
            highestStepReached: 1,
            configuredProviders: const {CloudProvider.aws},
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.success, true);
        expect(result.state.mode, WizardMode.edit);
        expect(result.state.twinId, 'twin-123');
        expect(result.state.twinName, 'TestTwin');
        expect(result.state.twinState, 'draft');
        expect(result.state.debugMode, false);
        expect(result.state.currentStep, 1);
      });

      test('hydrates AWS credentials as inherited', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            configuredProviders: const {CloudProvider.aws},
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.aws.isValid, true);
        expect(result.state.aws.source, CredentialSource.inherited);
      });

      test('hydrates Azure and GCP credentials', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            configuredProviders: const {CloudProvider.azure, CloudProvider.gcp},
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.azure.isValid, true);
        expect(result.state.azure.source, CredentialSource.inherited);
        expect(result.state.gcp.isValid, true);
        expect(result.state.gcp.source, CredentialSource.inherited);
      });

      test('restores workload step without deployment credentials', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(highestStepReached: 2),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.currentStep, 1);
      });

      test('resets step to 1 if step >= 2 but no optimizer result', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            highestStepReached: 2,
            configuredProviders: const {CloudProvider.aws},
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.currentStep, 1);
      });

      test('hydrates deployer config from DeployerConfigData', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(),
          deployerConfig: const DeployerConfigData(
            deployerDigitalTwinName: 'MyTwin',
            configEventsJson: '{"events": []}',
            configEventsValidated: true,
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.deployerDigitalTwinName, 'MyTwin');
        expect(result.state.configEventsJson, '{"events": []}');
        expect(result.state.configEventsValidated, true);
      });

      test('hydrates a selected latest deployment run as ready', () {
        final optimization = TypedApiFixtures.optimization(
          cheapestPath: const [
            'L1_AWS',
            'L2_AWS',
            'L3_hot_AWS',
            'L3_cool_AWS',
            'L3_archive_AWS',
            'L4_AWS',
            'L5_AWS',
          ],
        );
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            highestStepReached: 2,
            optimization: optimization,
          ),
          deploymentRun: TypedApiFixtures.deploymentRun(
            selectedForDeploymentAt: TypedApiFixtures.timestamp,
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.currentStep, 2);
        expect(result.state.deploymentReview.ready, isTrue);
        expect(result.state.savedDeploymentRun, data.deploymentRun);
      });

      test('moves an unselected latest deployment run back to review', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            highestStepReached: 2,
            optimization: TypedApiFixtures.optimization(
              cheapestPath: const [
                'L1_AWS',
                'L2_AWS',
                'L3_hot_AWS',
                'L3_cool_AWS',
                'L3_archive_AWS',
                'L4_AWS',
                'L5_AWS',
              ],
            ),
          ),
          deploymentRun: TypedApiFixtures.deploymentRun(),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.currentStep, 1);
        expect(result.state.deploymentReview.ready, isFalse);
      });

      test('rejects optimizer and deployment provider drift', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            highestStepReached: 2,
            optimization: TypedApiFixtures.optimization(
              cheapestPath: const [
                'L1_AZURE',
                'L2_AWS',
                'L3_hot_AWS',
                'L3_cool_AWS',
                'L3_archive_AWS',
                'L4_AWS',
                'L5_AWS',
              ],
            ),
          ),
          deploymentRun: TypedApiFixtures.deploymentRun(
            selectedForDeploymentAt: TypedApiFixtures.timestamp,
          ),
        );

        expect(
          () => service.initializeEditMode(twinId: 'twin-123', data: data),
          throwsFormatException,
        );
      });
    });

    group('DeployerConfigData.fromJson', () {
      test('parses all fields from JSON', () {
        final json = {
          'deployer_digital_twin_name': 'TestTwin',
          'config_events_json': '{}',
          'config_iot_devices_json': '{}',
          'config_json_validated': true,
          'config_events_validated': true,
          'config_iot_devices_validated': true,
          'payloads_json': '{}',
          'payloads_validated': true,
          'processor_contents': {'device1': 'code'},
          'processor_validated': {'device1': true},
          'hierarchy_content': '{}',
          'hierarchy_validated': true,
        };

        final data = DeployerConfigData.fromJson(json);

        expect(data.deployerDigitalTwinName, 'TestTwin');
        expect(data.configJsonValidated, true);
        expect(data.processorContents['device1'], 'code');
        expect(data.processorValidated['device1'], true);
        expect(data.hierarchyValidated, true);
      });

      test('handles missing optional fields with defaults', () {
        final data = DeployerConfigData.fromJson({});

        expect(data.deployerDigitalTwinName, isNull);
        expect(data.configJsonValidated, false);
        expect(data.processorContents, isEmpty);
        expect(data.hierarchyValidated, false);
      });
    });

    group('WizardInitResult factories', () {
      test('ok factory creates successful result', () {
        final state = const WizardState(mode: WizardMode.create);
        final result = WizardInitResult.ok(state);

        expect(result.success, true);
        expect(result.state.mode, WizardMode.create);
      });
    });

    group('TwinEditData', () {
      test('can be constructed with all fields', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(debugMode: true),
          deployerConfig: const DeployerConfigData(
            deployerDigitalTwinName: 'Name',
          ),
        );

        expect(data.twin.name, 'Test');
        expect(data.config.debugMode, true);
        expect(data.deployerConfig?.deployerDigitalTwinName, 'Name');
      });

      test('deployerConfig is optional', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(),
        );

        expect(data.deployerConfig, isNull);
      });
    });

    group('unconfigured provider warning (GAP 3)', () {
      test('generates warning when optimal path has unconfigured provider', () {
        // AWS configured, Azure not configured, optimal path uses both
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            configuredProviders: const {CloudProvider.aws},
            optimization: TypedApiFixtures.optimization(
              cheapestPath: ['L1_AWS', 'L2_AZURE', 'L3_AWS_HOT'],
            ),
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.warningMessage, isNotNull);
        expect(result.state.warningMessage, contains('AZURE'));
        expect(result.state.warningMessage, contains('Deployment access'));
        expect(result.state.warningMessage, isNot(contains('HOT')));
      });

      test('no warning when all providers in path are configured', () {
        // AWS & Azure both configured
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            configuredProviders: const {CloudProvider.aws, CloudProvider.azure},
            optimization: TypedApiFixtures.optimization(
              cheapestPath: ['L1_AWS', 'L2_AZURE'],
            ),
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.warningMessage, isNull);
      });

      test('handles empty optimal path gracefully', () {
        final data = TwinEditData(
          twin: TypedApiFixtures.twin(name: 'Test'),
          config: TypedApiFixtures.twinConfig(
            configuredProviders: const {CloudProvider.aws},
            optimization: TypedApiFixtures.optimization(cheapestPath: const []),
          ),
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        // No crash, no warning (empty path)
        expect(result.success, true);
        expect(result.state.warningMessage, isNull);
      });
    });
  });
}
