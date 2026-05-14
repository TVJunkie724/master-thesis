import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/helpers/deployer_helper.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard_state.dart';

void main() {
  group('DeployerHelper.buildDeployerConfigPayload', () {
    test('includes all Step 3 contract fields', () {
      final payload = DeployerHelper.buildDeployerConfigPayload(
        const WizardState(
          deployerDigitalTwinName: 'factory',
          configEventsJson: '[]',
          configIotDevicesJson: '[]',
          configJsonValidated: true,
          configEventsValidated: true,
          configIotDevicesValidated: true,
          payloadsJson: '{"device-1":{"temperature":21}}',
          payloadsValidated: true,
          processorContents: {'device-1': 'def process(event): return event'},
          processorValidated: {'device-1': true},
          processorRequirements: {'device-1': 'requests==2.32.3'},
          eventFeedbackContent: 'def feedback(event): return event',
          eventFeedbackValidated: true,
          eventFeedbackRequirements: 'requests==2.32.3',
          eventActionContents: {'overheat': 'def handle(event): return event'},
          eventActionValidated: {'overheat': true},
          eventActionRequirements: {'overheat': 'pydantic==2.11.0'},
          stateMachineContent: '{"StartAt":"Done"}',
          stateMachineValidated: true,
          hierarchyContent: '{"entities":[]}',
          hierarchyValidated: true,
          sceneGlbUploaded: true,
          sceneConfigContent: '{"scene":"factory"}',
          sceneConfigValidated: true,
          userConfigContent: '{"users":[]}',
          userConfigValidated: true,
        ),
      );

      expect(payload['deployer_digital_twin_name'], 'factory');
      expect(payload['config_events_json'], '[]');
      expect(payload['config_iot_devices_json'], '[]');
      expect(payload['config_json_validated'], true);
      expect(payload['config_events_validated'], true);
      expect(payload['config_iot_devices_validated'], true);
      expect(payload['payloads_json'], '{"device-1":{"temperature":21}}');
      expect(payload['payloads_validated'], true);
      expect(payload['processor_contents'], {
        'device-1': 'def process(event): return event',
      });
      expect(payload['processor_validated'], {'device-1': true});
      expect(payload['processor_requirements'], {
        'device-1': 'requests==2.32.3',
      });
      expect(
        payload['event_feedback_content'],
        'def feedback(event): return event',
      );
      expect(payload['event_feedback_validated'], true);
      expect(payload['event_feedback_requirements'], 'requests==2.32.3');
      expect(payload['event_action_contents'], {
        'overheat': 'def handle(event): return event',
      });
      expect(payload['event_action_validated'], {'overheat': true});
      expect(payload['event_action_requirements'], {
        'overheat': 'pydantic==2.11.0',
      });
      expect(payload['state_machine_content'], '{"StartAt":"Done"}');
      expect(payload['state_machine_validated'], true);
      expect(payload['hierarchy_content'], '{"entities":[]}');
      expect(payload['hierarchy_validated'], true);
      expect(payload['scene_glb_uploaded'], true);
      expect(payload['scene_config_content'], '{"scene":"factory"}');
      expect(payload['scene_config_validated'], true);
      expect(payload['user_config_content'], '{"users":[]}');
      expect(payload['user_config_validated'], true);
    });
  });
}
