// test/bloc/wizard/services/wizard_init_service_test.dart
// Unit tests for WizardInitService (stateless, no mocks required)

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/deployer_config.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/services/wizard_init_service.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard_state.dart';

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
          twin: {'name': 'TestTwin', 'state': 'draft'},
          config: {
            'debug_mode': false,
            'highest_step_reached': 1,
            'aws_configured': true,
            'aws': {'access_key': '***'},
          },
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
          twin: {'name': 'Test', 'state': 'draft'},
          config: {
            'aws_configured': true,
            'aws': {'access_key': '***MASKED***', 'secret_key': '***MASKED***'},
          },
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
          twin: {'name': 'Test', 'state': 'draft'},
          config: {
            'azure_configured': true,
            'azure': {'subscription_id': '***'},
            'gcp_configured': true,
            'gcp': {'project_id': '***'},
          },
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

      test('resets step to 0 if no credentials configured but step > 0', () {
        final data = TwinEditData(
          twin: {'name': 'Test', 'state': 'draft'},
          config: {
            'highest_step_reached': 2,
            // No credentials configured
          },
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.currentStep, 0);
      });

      test('resets step to 1 if step >= 2 but no optimizer result', () {
        final data = TwinEditData(
          twin: {'name': 'Test', 'state': 'draft'},
          config: {
            'aws_configured': true,
            'aws': {'key': 'value'},
            'highest_step_reached': 2,
            // No optimizer_result
          },
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.currentStep, 1);
      });

      test('hydrates deployer config from DeployerConfigData', () {
        final data = TwinEditData(
          twin: {'name': 'Test', 'state': 'draft'},
          config: {},
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
          twin: {'name': 'Test'},
          config: {'debug_mode': true},
          deployerConfig: const DeployerConfigData(
            deployerDigitalTwinName: 'Name',
          ),
        );

        expect(data.twin['name'], 'Test');
        expect(data.config['debug_mode'], true);
        expect(data.deployerConfig?.deployerDigitalTwinName, 'Name');
      });

      test('deployerConfig is optional', () {
        final data = TwinEditData(twin: {'name': 'Test'}, config: {});

        expect(data.deployerConfig, isNull);
      });
    });

    group('unconfigured provider warning (GAP 3)', () {
      // Helper to build valid optimizer_result structure
      Map<String, dynamic> buildOptimizerResult(List<String> cheapestPath) {
        return <String, dynamic>{
          'awsCosts': <String, dynamic>{
            'L1': <String, dynamic>{
              'cost': 10.0,
              'components': <String, double>{},
            },
          },
          'azureCosts': <String, dynamic>{
            'L2': <String, dynamic>{
              'cost': 20.0,
              'components': <String, double>{},
            },
          },
          'gcpCosts': <String, dynamic>{},
          'cheapestPath': cheapestPath,
          'inputParamsUsed': <String, dynamic>{},
        };
      }

      test('generates warning when optimal path has unconfigured provider', () {
        // AWS configured, Azure not configured, optimal path uses both
        final data = TwinEditData(
          twin: {'name': 'Test', 'state': 'draft'},
          config: {
            'aws_configured': true,
            'aws': {'access_key': '***'},
            // Azure NOT configured
            'optimizer_result': buildOptimizerResult([
              'L1_AWS',
              'L2_AZURE',
              'L3_AWS_HOT',
            ]),
          },
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.warningMessage, isNotNull);
        expect(result.state.warningMessage, contains('AZURE'));
        expect(result.state.warningMessage, contains('Unconfigured'));
      });

      test('no warning when all providers in path are configured', () {
        // AWS & Azure both configured
        final data = TwinEditData(
          twin: {'name': 'Test', 'state': 'draft'},
          config: {
            'aws_configured': true,
            'aws': {'access_key': '***'},
            'azure_configured': true,
            'azure': {'subscription_id': '***'},
            'optimizer_result': buildOptimizerResult(['L1_AWS', 'L2_AZURE']),
          },
        );

        final result = service.initializeEditMode(
          twinId: 'twin-123',
          data: data,
        );

        expect(result.state.warningMessage, isNull);
      });

      test('handles empty optimal path gracefully', () {
        final data = TwinEditData(
          twin: {'name': 'Test', 'state': 'draft'},
          config: {
            'aws_configured': true,
            'aws': {'key': '***'},
            'optimizer_result': buildOptimizerResult([]),
          },
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
