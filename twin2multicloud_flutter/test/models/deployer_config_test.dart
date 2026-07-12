import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/deployer_config.dart';

void main() {
  group('DeployerConfigData', () {
    test('hydrates typed maps and preserves the update wire contract', () {
      final data = DeployerConfigData.fromJson({
        'deployer_digital_twin_name': 'factory',
        'config_events_json': '[]',
        'config_iot_devices_json': '[]',
        'config_json_validated': true,
        'config_events_validated': true,
        'config_iot_devices_validated': true,
        'payloads_json': '{}',
        'payloads_validated': true,
        'processor_contents': {'sensor': 'code'},
        'processor_validated': {'sensor': true},
        'processor_requirements': {'sensor': 'requests==2.0'},
        'event_feedback_content': 'feedback',
        'event_feedback_validated': true,
        'event_feedback_requirements': 'httpx==1.0',
        'event_action_contents': {'notify': 'action'},
        'event_action_validated': {'notify': true},
        'event_action_requirements': {'notify': 'pydantic==2.0'},
        'state_machine_content': '{}',
        'state_machine_validated': true,
        'hierarchy_content': '{}',
        'hierarchy_validated': true,
        'scene_glb_uploaded': true,
        'scene_config_content': '{}',
        'scene_config_validated': true,
        'user_config_content': '{}',
        'user_config_validated': true,
      });

      expect(data.processorContents, {'sensor': 'code'});
      expect(data.eventActionValidated, {'notify': true});
      expect(data.toUpdateRequest().toJson(), {
        'deployer_digital_twin_name': 'factory',
        'config_events_json': '[]',
        'config_iot_devices_json': '[]',
        'config_json_validated': true,
        'config_events_validated': true,
        'config_iot_devices_validated': true,
        'payloads_json': '{}',
        'payloads_validated': true,
        'processor_contents': {'sensor': 'code'},
        'processor_validated': {'sensor': true},
        'processor_requirements': {'sensor': 'requests==2.0'},
        'event_feedback_content': 'feedback',
        'event_feedback_validated': true,
        'event_feedback_requirements': 'httpx==1.0',
        'event_action_contents': {'notify': 'action'},
        'event_action_validated': {'notify': true},
        'event_action_requirements': {'notify': 'pydantic==2.0'},
        'state_machine_content': '{}',
        'state_machine_validated': true,
        'hierarchy_content': '{}',
        'hierarchy_validated': true,
        'scene_glb_uploaded': true,
        'scene_config_content': '{}',
        'scene_config_validated': true,
        'user_config_content': '{}',
        'user_config_validated': true,
      });
    });

    test('uses safe defaults for absent fields', () {
      final data = DeployerConfigData.fromJson(const {});

      expect(data.deployerDigitalTwinName, isNull);
      expect(data.processorContents, isEmpty);
      expect(data.processorValidated, isEmpty);
      expect(data.sceneGlbUploaded, isFalse);
    });

    test('rejects incompatible map shapes', () {
      expect(
        () => DeployerConfigData.fromJson({
          'processor_contents': ['not', 'an', 'object'],
        }),
        throwsFormatException,
      );
      expect(
        () => DeployerConfigData.fromJson({
          'processor_validated': {'sensor': 'yes'},
        }),
        throwsFormatException,
      );
    });
  });

  group('DeployerConfigRequirements', () {
    test('derives mixed-cloud requirements case-insensitively', () {
      final params = CalcParams.fromJson({
        'returnFeedbackToDevice': true,
        'useEventChecking': true,
        'triggerNotificationWorkflow': true,
        'needs3DModel': true,
      });
      final requirements = DeployerConfigRequirements.fromContext(
        calcParams: params,
        layer4Provider: 'azure',
        layer5Provider: 'AWS',
        deviceIds: const ['sensor'],
        eventActionNames: const ['notify'],
      );

      expect(requirements.eventFeedbackRequired, isTrue);
      expect(requirements.eventActionsRequired, isTrue);
      expect(requirements.stateMachineRequired, isTrue);
      expect(requirements.hierarchyRequired, isTrue);
      expect(requirements.sceneRequired, isTrue);
      expect(requirements.userConfigRequired, isTrue);
    });

    test('does not require AWS/Azure assets for GCP', () {
      final requirements = DeployerConfigRequirements.fromContext(
        calcParams: CalcParams.fromJson({'needs3DModel': true}),
        layer4Provider: 'GCP',
        layer5Provider: 'gcp',
        deviceIds: const [],
        eventActionNames: const [],
      );

      expect(requirements.hierarchyRequired, isFalse);
      expect(requirements.sceneRequired, isFalse);
      expect(requirements.userConfigRequired, isFalse);
    });
  });

  group('DeployerConfigReadiness', () {
    test('blocks an AWS 3D configuration until the GLB is uploaded', () {
      const requirements = DeployerConfigRequirements(
        hierarchyRequired: true,
        sceneRequired: true,
      );
      const withoutGlb = DeployerConfigData(
        deployerDigitalTwinName: 'factory',
        configEventsJson: '[]',
        configIotDevicesJson: '[]',
        configJsonValidated: true,
        configEventsValidated: true,
        configIotDevicesValidated: true,
        payloadsJson: '{}',
        payloadsValidated: true,
        hierarchyContent: '{}',
        hierarchyValidated: true,
        sceneConfigContent: '{}',
        sceneConfigValidated: true,
      );

      final blocked = DeployerConfigReadiness.fromData(
        data: withoutGlb,
        requirements: requirements,
      );
      final ready = DeployerConfigReadiness.fromData(
        data: const DeployerConfigData(
          deployerDigitalTwinName: 'factory',
          configEventsJson: '[]',
          configIotDevicesJson: '[]',
          configJsonValidated: true,
          configEventsValidated: true,
          configIotDevicesValidated: true,
          payloadsJson: '{}',
          payloadsValidated: true,
          hierarchyContent: '{}',
          hierarchyValidated: true,
          sceneConfigContent: '{}',
          sceneConfigValidated: true,
          sceneGlbUploaded: true,
        ),
        requirements: requirements,
      );

      expect(blocked.ready, isFalse);
      expect(
        blocked.section(DeployerSectionId.digitalTwinAssets).missingArtifactIds,
        contains('scene-glb'),
      );
      expect(ready.ready, isTrue);
    });

    test('requires each dynamic processor and enabled event action', () {
      const requirements = DeployerConfigRequirements(
        deviceIds: ['sensor-a', 'sensor-b'],
        eventActionNames: ['notify'],
        eventActionsRequired: true,
      );
      const data = DeployerConfigData(
        deployerDigitalTwinName: 'factory',
        configEventsJson: '[]',
        configIotDevicesJson: '[]',
        configJsonValidated: true,
        configEventsValidated: true,
        configIotDevicesValidated: true,
        payloadsJson: '{}',
        payloadsValidated: true,
        processorContents: {'sensor-a': 'code', 'sensor-b': 'code'},
        processorValidated: {'sensor-a': true, 'sensor-b': false},
        eventActionContents: {'notify': 'code'},
        eventActionValidated: {'notify': false},
      );

      final readiness = DeployerConfigReadiness.fromData(
        data: data,
        requirements: requirements,
      );
      final logic = readiness.section(DeployerSectionId.userLogic);

      expect(logic.ready, isFalse);
      expect(logic.invalidArtifactIds, [
        'processor:sensor-b',
        'event-action:notify',
      ]);
    });

    test('marks generated and user-authored ownership explicitly', () {
      final readiness = DeployerConfigReadiness.fromData(
        data: const DeployerConfigData(),
        requirements: const DeployerConfigRequirements(),
      );
      final configuration = readiness.section(DeployerSectionId.configuration);

      expect(
        configuration.artifacts.first.source,
        DeployerArtifactSource.generated,
      );
      expect(
        configuration.artifacts[1].source,
        DeployerArtifactSource.userAuthored,
      );
    });
  });
}
