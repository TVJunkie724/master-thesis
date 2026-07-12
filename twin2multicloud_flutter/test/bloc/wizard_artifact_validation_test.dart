import 'dart:async';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/deployer_artifact_validation.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;

  setUp(() => api = MockApiService());

  group('DeployerArtifactValidationRequest', () {
    test('derives stable endpoint and artifact mappings', () {
      const request = DeployerArtifactValidationRequest(
        type: DeployerArtifactType.processor,
        content: 'def handler(): pass',
        provider: 'AWS',
        entityId: 'sensor-1',
      );

      expect(request.artifactId, 'processor:sensor-1');
      expect(request.validationType, 'function-code');
      expect(request.boundary, DeployerValidationBoundary.layer2);
      expect(request.validationError, isNull);
    });

    test('fails closed for empty content and missing context', () {
      const empty = DeployerArtifactValidationRequest(
        type: DeployerArtifactType.events,
        content: ' ',
      );
      const missingProvider = DeployerArtifactValidationRequest(
        type: DeployerArtifactType.hierarchy,
        content: '{}',
      );
      const missingEntity = DeployerArtifactValidationRequest(
        type: DeployerArtifactType.eventAction,
        content: 'code',
        provider: 'azure',
      );

      expect(empty.validationError, 'No content to validate');
      expect(missingProvider.validationError, 'Provider context is missing');
      expect(missingEntity.validationError, 'Artifact identity is missing');
    });
  });

  blocTest<WizardBloc, WizardState>(
    'validates config through the Management API and stores feedback',
    build: () {
      when(
        () => api.validateDeployerConfig('twin-1', 'events', '[]'),
      ).thenAnswer((_) async => {'valid': true, 'message': 'Events valid'});
      return WizardBloc(api: api);
    },
    seed: () => const WizardState(twinId: 'twin-1'),
    act: (bloc) => bloc.add(
      const WizardArtifactValidationRequested(
        DeployerArtifactValidationRequest(
          type: DeployerArtifactType.events,
          content: '[]',
        ),
      ),
    ),
    expect: () => [
      isA<WizardState>().having(
        (state) => state.isArtifactValidating('config:events'),
        'busy',
        true,
      ),
      isA<WizardState>()
          .having((state) => state.configEventsValidated, 'validated', true)
          .having(
            (state) => state.artifactFeedback('config:events')?.message,
            'feedback',
            'Events valid',
          )
          .having(
            (state) => state.isArtifactValidating('config:events'),
            'busy cleared',
            false,
          ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'maps processor validation to its entity and provider',
    build: () {
      when(
        () => api.validateL2Content('twin-1', 'function-code', 'code', 'AWS'),
      ).thenAnswer((_) async => {'valid': true, 'message': 'Code valid'});
      return WizardBloc(api: api);
    },
    seed: () => const WizardState(twinId: 'twin-1'),
    act: (bloc) => bloc.add(
      const WizardArtifactValidationRequested(
        DeployerArtifactValidationRequest(
          type: DeployerArtifactType.processor,
          content: 'code',
          provider: 'AWS',
          entityId: 'sensor-1',
        ),
      ),
    ),
    skip: 1,
    expect: () => [
      isA<WizardState>().having(
        (state) => state.processorValidated['sensor-1'],
        'processor valid',
        true,
      ),
    ],
  );

  blocTest<WizardBloc, WizardState>(
    'invalid request returns feedback without calling the API',
    build: () => WizardBloc(api: api),
    seed: () => const WizardState(twinId: 'twin-1', userConfigValidated: true),
    act: (bloc) => bloc.add(
      const WizardArtifactValidationRequested(
        DeployerArtifactValidationRequest(
          type: DeployerArtifactType.userConfig,
          content: '{}',
        ),
      ),
    ),
    expect: () => [
      isA<WizardState>()
          .having(
            (state) => state.artifactFeedback('user-config')?.valid,
            'invalid feedback',
            false,
          )
          .having(
            (state) => state.userConfigValidated,
            'stale validity cleared',
            false,
          ),
    ],
    verify: (_) =>
        verifyNever(() => api.validateL4Content(any(), any(), any(), any())),
  );

  test('ignores a duplicate request for an in-flight artifact', () async {
    final response = Completer<Map<String, dynamic>>();
    when(
      () => api.validateDeployerConfig('twin-1', 'events', '[]'),
    ).thenAnswer((_) => response.future);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    bloc.emit(const WizardState(twinId: 'twin-1'));
    const event = WizardArtifactValidationRequested(
      DeployerArtifactValidationRequest(
        type: DeployerArtifactType.events,
        content: '[]',
      ),
    );

    bloc.add(event);
    await bloc.stream.firstWhere(
      (state) => state.isArtifactValidating('config:events'),
    );
    bloc.add(event);
    await Future<void>.delayed(Duration.zero);
    response.complete({'valid': true, 'message': 'Valid'});
    await bloc.stream.firstWhere((state) => state.configEventsValidated);

    verify(
      () => api.validateDeployerConfig('twin-1', 'events', '[]'),
    ).called(1);
  });

  test(
    'editing cancels an in-flight result and clears stale feedback',
    () async {
      final response = Completer<Map<String, dynamic>>();
      when(
        () => api.validateDeployerConfig('twin-1', 'payloads', '{}'),
      ).thenAnswer((_) => response.future);
      final bloc = WizardBloc(api: api);
      addTearDown(bloc.close);
      bloc.emit(
        const WizardState(
          twinId: 'twin-1',
          artifactValidationFeedback: {
            'payloads': DeployerArtifactValidationFeedback(
              valid: false,
              message: 'Old result',
            ),
          },
        ),
      );

      bloc.add(
        const WizardArtifactValidationRequested(
          DeployerArtifactValidationRequest(
            type: DeployerArtifactType.payloads,
            content: '{}',
          ),
        ),
      );
      await bloc.stream.firstWhere(
        (state) => state.isArtifactValidating('payloads'),
      );
      bloc.add(const WizardPayloadsChanged('{"changed": true}'));
      await bloc.stream.firstWhere(
        (state) => !state.isArtifactValidating('payloads'),
      );
      response.complete({'valid': true, 'message': 'Stale success'});
      await Future<void>.delayed(Duration.zero);

      expect(bloc.state.payloadsValidated, isFalse);
      expect(bloc.state.artifactFeedback('payloads'), isNull);
    },
  );
}
