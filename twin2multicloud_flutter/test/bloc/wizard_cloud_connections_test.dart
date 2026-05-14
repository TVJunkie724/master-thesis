import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;

  setUpAll(() {
    registerFallbackValue(<String, dynamic>{});
    registerFallbackValue(
      const CloudConnectionCreateRequest(
        provider: CloudProvider.aws,
        displayName: 'fallback',
        credentials: {},
      ),
    );
  });

  setUp(() {
    api = MockApiService();
    when(() => api.listCloudConnections()).thenAnswer((_) async => []);
  });

  group('WizardBloc Cloud Connections', () {
    blocTest<WizardBloc, WizardState>(
      'create mode loads Cloud Connections',
      build: () => WizardBloc(api: api),
      act: (bloc) => bloc.add(const WizardInitCreate()),
      wait: const Duration(milliseconds: 1),
      expect: () => [
        isA<WizardState>().having(
          (state) => state.status,
          'status',
          WizardStatus.ready,
        ),
        isA<WizardState>().having(
          (state) => state.cloudConnectionLoading[CloudProvider.aws],
          'aws loading',
          true,
        ),
        isA<WizardState>().having(
          (state) => state.cloudConnectionLoading[CloudProvider.aws],
          'aws loading',
          false,
        ),
      ],
      verify: (_) {
        verify(() => api.listCloudConnections()).called(1);
      },
    );

    blocTest<WizardBloc, WizardState>(
      'selecting a Cloud Connection makes Step 1 proceedable',
      build: () => WizardBloc(api: api),
      seed: () => const WizardState(twinName: 'Twin'),
      act: (bloc) => bloc.add(
        const WizardCloudConnectionSelected(
          CloudProvider.aws,
          'connection-aws',
        ),
      ),
      expect: () => [
        isA<WizardState>()
            .having(
              (state) => state.selectedCloudConnectionIds[CloudProvider.aws],
              'selected aws id',
              'connection-aws',
            )
            .having((state) => state.canProceedToStep2, 'can proceed', true),
      ],
    );

    blocTest<WizardBloc, WizardState>(
      'saving CloudConnection-only draft sends cloud_connections without secrets',
      build: () {
        when(
          () => api.createTwin(any()),
        ).thenAnswer((_) async => {'id': 'new-twin-id'});
        when(
          () => api.updateTwinConfig(any(), any()),
        ).thenAnswer((_) async => {'twin_state': 'draft'});
        return WizardBloc(api: api);
      },
      seed: () => const WizardState(
        mode: WizardMode.create,
        twinName: 'Twin',
        selectedCloudConnectionIds: {CloudProvider.aws: 'connection-aws'},
      ),
      act: (bloc) => bloc.add(const WizardSaveDraft()),
      wait: const Duration(milliseconds: 1),
      verify: (_) {
        final captured =
            verify(
                  () => api.updateTwinConfig('new-twin-id', captureAny()),
                ).captured.single
                as Map<String, dynamic>;

        expect(captured['cloud_connections']['aws'], 'connection-aws');
        expect(captured.containsKey('aws'), false);
        expect(captured.containsKey('azure'), false);
        expect(captured.containsKey('gcp'), false);
      },
    );

    blocTest<WizardBloc, WizardState>(
      'saving cleared legacy credentials sends explicit provider null',
      build: () {
        when(
          () => api.updateTwinConfig(any(), any()),
        ).thenAnswer((_) async => {'twin_state': 'draft'});
        return WizardBloc(api: api);
      },
      seed: () => const WizardState(
        mode: WizardMode.edit,
        twinId: 'existing-twin-id',
        twinName: 'Twin',
        aws: ProviderCredentials(source: CredentialSource.cleared),
      ),
      act: (bloc) => bloc.add(const WizardSaveDraft()),
      wait: const Duration(milliseconds: 1),
      verify: (_) {
        final captured =
            verify(
                  () => api.updateTwinConfig('existing-twin-id', captureAny()),
                ).captured.single
                as Map<String, dynamic>;

        expect(captured['aws'], isNull);
        expect(captured.containsKey('azure'), false);
        expect(captured.containsKey('gcp'), false);
      },
    );

    blocTest<WizardBloc, WizardState>(
      'saving Step 3 draft persists payload-only deployer config',
      build: () {
        when(
          () => api.updateTwinConfig(any(), any()),
        ).thenAnswer((_) async => {'twin_state': 'draft'});
        when(
          () => api.updateDeployerConfig(any(), any()),
        ).thenAnswer((_) async => {'twin_state': 'draft'});
        return WizardBloc(api: api);
      },
      seed: () => const WizardState(
        mode: WizardMode.edit,
        twinId: 'existing-twin-id',
        twinName: 'Twin',
        currentStep: 2,
        highestStepReached: 2,
        payloadsJson: '{"device-1":{"temperature":21}}',
        payloadsValidated: true,
      ),
      act: (bloc) => bloc.add(const WizardSaveDraft()),
      wait: const Duration(milliseconds: 1),
      verify: (_) {
        final captured =
            verify(
                  () => api.updateDeployerConfig(
                    'existing-twin-id',
                    captureAny(),
                  ),
                ).captured.single
                as Map<String, dynamic>;

        expect(captured['payloads_json'], '{"device-1":{"temperature":21}}');
        expect(captured['payloads_validated'], true);
        expect(captured.containsKey('deployer_digital_twin_name'), true);
      },
    );

    blocTest<WizardBloc, WizardState>(
      'unbinding provider stores null selection',
      build: () => WizardBloc(api: api),
      seed: () => const WizardState(
        selectedCloudConnectionIds: {CloudProvider.aws: 'connection-aws'},
      ),
      act: (bloc) =>
          bloc.add(const WizardCloudConnectionUnbound(CloudProvider.aws)),
      expect: () => [
        isA<WizardState>().having(
          (state) => state.selectedCloudConnectionIds[CloudProvider.aws],
          'selected aws id',
          isNull,
        ),
      ],
    );
  });
}
