import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/helpers/wizard_config_request_builder.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard_state.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';

void main() {
  group('WizardConfigRequestBuilder.buildTwinConfigRequest', () {
    test('builds CloudConnection-only request without legacy secrets', () {
      final request = WizardConfigRequestBuilder.buildTwinConfigRequest(
        const WizardState(
          debugMode: false,
          highestStepReached: 1,
          selectedCloudConnectionIds: {CloudProvider.aws: 'connection-aws'},
          aws: ProviderCredentials(
            source: CredentialSource.newlyEntered,
            values: {
              'access_key_id': 'AKIAIOSFODNN7EXAMPLE',
              'secret_access_key': 'secret',
            },
          ),
        ),
      );

      final payload = request.toJson();
      expect(payload['debug_mode'], false);
      expect(payload['highest_step_reached'], 1);
      expect(payload['cloud_connections']['aws'], 'connection-aws');
      expect(payload.containsKey('aws'), false);
    });

    test(
      'builds legacy credential request when no CloudConnection is selected',
      () {
        final request = WizardConfigRequestBuilder.buildTwinConfigRequest(
          const WizardState(
            selectedCloudConnectionIds: {},
            azure: ProviderCredentials(
              source: CredentialSource.newlyEntered,
              values: {
                'subscription_id': 'sub',
                'client_id': 'client',
                'client_secret': 'secret',
                'tenant_id': 'tenant',
                'region': 'westeurope',
              },
            ),
          ),
        );

        final payload = request.toJson();
        expect(payload['azure']['subscription_id'], 'sub');
        expect(payload.containsKey('aws'), false);
        expect(payload.containsKey('gcp'), false);
      },
    );

    test('builds explicit nulls for cleared credentials', () {
      final request = WizardConfigRequestBuilder.buildTwinConfigRequest(
        const WizardState(
          aws: ProviderCredentials(source: CredentialSource.cleared),
          gcp: ProviderCredentials(source: CredentialSource.cleared),
        ),
      );

      final payload = request.toJson();
      expect(payload.containsKey('aws'), true);
      expect(payload['aws'], isNull);
      expect(payload.containsKey('gcp'), true);
      expect(payload['gcp'], isNull);
      expect(payload.containsKey('azure'), false);
    });
  });

  group('WizardConfigRequestBuilder.buildDeployerConfigRequest', () {
    test('builds typed Step 3 artifact request', () {
      final request = WizardConfigRequestBuilder.buildDeployerConfigRequest(
        const WizardState(
          payloadsJson: '{"device-1":{"temperature":21}}',
          payloadsValidated: true,
          processorContents: {'device-1': 'def process(event): return event'},
        ),
      );

      final payload = request.toJson();
      expect(payload['payloads_json'], '{"device-1":{"temperature":21}}');
      expect(payload['payloads_validated'], true);
      expect(payload['processor_contents'], {
        'device-1': 'def process(event): return event',
      });
      expect(request.hasMeaningfulValues, true);
    });
  });
}
