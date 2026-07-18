import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/core/app_logger.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/models/wizard_config_requests.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

import '../fixtures/typed_api_fixtures.dart';

final class _MockApiService extends Mock implements ApiService {}

final class _RecordingLogSink implements AppLogSink {
  final records = <AppLogRecord>[];

  @override
  void write(AppLogRecord record) => records.add(record);
}

void main() {
  late _MockApiService api;

  setUpAll(() {
    registerFallbackValue(CalcParams.defaultParams());
    registerFallbackValue(const TwinConfigUpdateRequest());
  });
  setUp(() {
    api = _MockApiService();
    when(() => api.getPricingHealth()).thenAnswer((_) async => _health());
    when(() => api.selectOptimizerRunForDeployment(any(), any())).thenAnswer((
      invocation,
    ) async {
      final twinId = invocation.positionalArguments[0] as String;
      final runId = invocation.positionalArguments[1] as String;
      final selectedAt = TypedApiFixtures.timestamp.add(
        const Duration(seconds: 2),
      );
      return OptimizerRunSelectionData(
        run: TypedApiFixtures.deploymentRun(
          id: runId,
          twinId: twinId,
          selectedForDeploymentAt: selectedAt,
        ),
        selectedForDeploymentAt: selectedAt,
      );
    });
  });

  test('create mode creates one draft and one durable optimizer run', () async {
    final run = TypedApiFixtures.optimizerRun(twinId: 'new-twin');
    when(() => api.createTwin('Factory twin')).thenAnswer(
      (_) async => TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
    );
    when(
      () => api.createOptimizerRun('new-twin', any()),
    ).thenAnswer((_) async => run);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    await _prepare(bloc);

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere((state) => state.deploymentReview.ready);

    expect(bloc.state.twinId, 'new-twin');
    expect(bloc.state.calcResult, run.optimization.result);
    expect(bloc.state.optimizationResultData, run.optimization);
    expect(bloc.state.deploymentRun?.id, run.id);
    verify(() => api.createTwin('Factory twin')).called(1);
    verify(() => api.createOptimizerRun('new-twin', any())).called(1);
  });

  test(
    'create mode retains draft identity after run failure and reuses it',
    () async {
      var runAttempts = 0;
      when(() => api.createTwin('Factory twin')).thenAnswer(
        (_) async =>
            TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
      );
      when(() => api.createOptimizerRun('new-twin', any())).thenAnswer((
        _,
      ) async {
        runAttempts += 1;
        if (runAttempts == 1) throw Exception('optimizer unavailable');
        return TypedApiFixtures.optimizerRun(twinId: 'new-twin');
      });
      final bloc = WizardBloc(api: api);
      addTearDown(bloc.close);
      await _prepare(bloc);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere(
        (state) => state.errorMessage != null && !state.isCalculating,
      );

      expect(bloc.state.twinId, 'new-twin');
      expect(bloc.state.calcResult, isNull);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere((state) => state.deploymentReview.ready);

      verify(() => api.createTwin('Factory twin')).called(1);
      verify(() => api.createOptimizerRun('new-twin', any())).called(2);
    },
  );

  test('duplicate calculate command cannot create duplicate runs', () async {
    final completer = Completer<OptimizerRunData>();
    when(() => api.createTwin('Factory twin')).thenAnswer(
      (_) async => TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
    );
    when(
      () => api.createOptimizerRun('new-twin', any()),
    ).thenAnswer((_) => completer.future);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    await _prepare(bloc);

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere(
      (state) => state.isCalculating && state.twinId == 'new-twin',
    );
    bloc.add(const WizardGoToStep(2));
    await Future<void>.delayed(Duration.zero);
    expect(bloc.state.currentStep, isNot(2));
    bloc.add(const WizardCalculateRequested());
    await Future<void>.delayed(Duration.zero);

    verify(() => api.createOptimizerRun('new-twin', any())).called(1);

    completer.complete(TypedApiFixtures.optimizerRun(twinId: 'new-twin'));
    await bloc.stream.firstWhere((state) => state.deploymentReview.ready);
  });

  test(
    'selection failure keeps calculation visible and retry reaches ready',
    () async {
      final logSink = _RecordingLogSink();
      var attempts = 0;
      when(() => api.createTwin('Factory twin')).thenAnswer(
        (_) async =>
            TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
      );
      when(() => api.createOptimizerRun('new-twin', any())).thenAnswer(
        (_) async => TypedApiFixtures.optimizerRun(twinId: 'new-twin'),
      );
      when(
        () => api.selectOptimizerRunForDeployment('new-twin', 'run-123'),
      ).thenAnswer((_) async {
        attempts += 1;
        if (attempts == 1) throw Exception('verification unavailable');
        final selectedAt = TypedApiFixtures.timestamp.add(
          const Duration(seconds: 2),
        );
        return OptimizerRunSelectionData(
          run: TypedApiFixtures.deploymentRun(
            id: 'run-123',
            twinId: 'new-twin',
            selectedForDeploymentAt: selectedAt,
          ),
          selectedForDeploymentAt: selectedAt,
        );
      });
      final bloc = WizardBloc(
        api: api,
        logger: AppLogger(sink: logSink),
      );
      addTearDown(bloc.close);
      await _prepare(bloc);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere(
        (state) =>
            state.deploymentReview.state ==
            ResolvedDeploymentReviewState.failed,
      );

      expect(bloc.state.calcResult, isNotNull);
      expect(bloc.state.canProceedToStep3, isFalse);
      expect(
        logSink.records.single.event,
        AppLogEvent.deploymentRunSelectionFailed,
      );
      bloc.add(const WizardGoToStep(2));
      await Future<void>.delayed(Duration.zero);
      expect(bloc.state.currentStep, isNot(2));

      bloc.add(const WizardDeploymentRunSelectionRequested());
      await bloc.stream.firstWhere((state) => state.deploymentReview.ready);

      expect(attempts, 2);
      expect(bloc.state.deploymentRunSelectionError, isNull);
    },
  );

  test('changed inputs invalidate a verified deployment run', () async {
    final run = TypedApiFixtures.optimizerRun(twinId: 'new-twin');
    when(() => api.createTwin('Factory twin')).thenAnswer(
      (_) async => TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
    );
    when(
      () => api.createOptimizerRun('new-twin', any()),
    ).thenAnswer((_) async => run);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    await _prepare(bloc);

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere((state) => state.deploymentReview.ready);

    final equivalent = CalcParams.fromJson(bloc.state.calcParams!.toJson());
    bloc.add(WizardCalcParamsChanged(equivalent));
    await bloc.stream.firstWhere((state) => state.calcParams == equivalent);
    expect(bloc.state.deploymentReview.ready, isTrue);

    final changed = CalcParams.fromJson({
      ...equivalent.toJson(),
      'numberOfDevices': equivalent.numberOfDevices + 1,
    });
    bloc.add(WizardCalcParamsChanged(changed));
    await bloc.stream.firstWhere((state) => state.calcParams == changed);

    expect(bloc.state.calcResult, isNull);
    expect(bloc.state.optimizationResultData, isNull);
    expect(bloc.state.deploymentRun, isNull);
    expect(bloc.state.canProceedToStep3, isFalse);
  });

  test('direct deployment navigation snapshots the verified run', () async {
    final run = TypedApiFixtures.optimizerRun(twinId: 'new-twin');
    when(() => api.createTwin('Factory twin')).thenAnswer(
      (_) async => TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
    );
    when(
      () => api.createOptimizerRun('new-twin', any()),
    ).thenAnswer((_) async => run);
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    await _prepare(bloc);

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere((state) => state.deploymentReview.ready);
    bloc.add(const WizardGoToStep(2));
    await bloc.stream.firstWhere((state) => state.currentStep == 2);

    expect(
      bloc.state.savedCalcParams?.hasSameCalculationInputs(
        bloc.state.calcParams!,
      ),
      isTrue,
    );
    expect(bloc.state.savedCalcResult, run.optimization.result);
    expect(bloc.state.savedOptimizationResultData, run.optimization);
    expect(bloc.state.savedDeploymentRun?.id, run.id);
  });

  test(
    'restore returns inputs, result, and deployment run atomically',
    () async {
      final run = TypedApiFixtures.optimizerRun(twinId: 'new-twin');
      when(() => api.createTwin('Factory twin')).thenAnswer(
        (_) async =>
            TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
      );
      when(
        () => api.createOptimizerRun('new-twin', any()),
      ).thenAnswer((_) async => run);
      final bloc = WizardBloc(api: api);
      addTearDown(bloc.close);
      await _prepare(bloc);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere((state) => state.deploymentReview.ready);
      final originalParams = bloc.state.calcParams!;
      bloc.add(const WizardNextStep());
      await bloc.stream.firstWhere((state) => state.currentStep == 1);
      bloc.add(const WizardNextStep());
      await bloc.stream.firstWhere((state) => state.currentStep == 2);

      final changed = CalcParams.fromJson({
        ...originalParams.toJson(),
        'numberOfDevices': originalParams.numberOfDevices + 1,
      });
      bloc.add(WizardCalcParamsChanged(changed));
      await bloc.stream.firstWhere((state) => state.calcParams == changed);
      expect(bloc.state.deploymentRun, isNull);

      bloc.add(const WizardRestoreOldResults());
      await bloc.stream.firstWhere(
        (state) =>
            state.calcParams?.hasSameCalculationInputs(originalParams) ==
                true &&
            state.deploymentReview.ready,
      );

      expect(bloc.state.calcResult, run.optimization.result);
      expect(bloc.state.optimizationResultData, run.optimization);
      expect(bloc.state.deploymentRun?.id, run.id);
    },
  );

  test(
    'input changes during calculation prevent stale run selection',
    () async {
      final pendingRun = Completer<OptimizerRunData>();
      when(() => api.createTwin('Factory twin')).thenAnswer(
        (_) async =>
            TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
      );
      when(
        () => api.createOptimizerRun('new-twin', any()),
      ).thenAnswer((_) => pendingRun.future);
      final bloc = WizardBloc(api: api);
      addTearDown(bloc.close);
      await _prepare(bloc);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere(
        (state) => state.isCalculating && state.twinId == 'new-twin',
      );
      final changed = CalcParams.fromJson({
        ...bloc.state.calcParams!.toJson(),
        'numberOfDevices': bloc.state.calcParams!.numberOfDevices + 1,
      });
      bloc.add(WizardCalcParamsChanged(changed));
      await bloc.stream.firstWhere((state) => state.calcParams == changed);
      pendingRun.complete(TypedApiFixtures.optimizerRun(twinId: 'new-twin'));
      await bloc.stream.firstWhere(
        (state) => !state.isCalculating && state.errorMessage != null,
      );

      expect(bloc.state.deploymentRun, isNull);
      expect(bloc.state.canProceedToStep3, isFalse);
      expect(
        bloc.state.errorMessage,
        contains('inputs changed while the optimizer was running'),
      );
      verifyNever(
        () => api.selectOptimizerRunForDeployment('new-twin', 'run-123'),
      );
    },
  );

  test(
    'input changes during selection ignore the stale selection response',
    () async {
      final pendingSelection = Completer<OptimizerRunSelectionData>();
      when(() => api.createTwin('Factory twin')).thenAnswer(
        (_) async =>
            TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
      );
      when(() => api.createOptimizerRun('new-twin', any())).thenAnswer(
        (_) async => TypedApiFixtures.optimizerRun(twinId: 'new-twin'),
      );
      when(
        () => api.selectOptimizerRunForDeployment('new-twin', 'run-123'),
      ).thenAnswer((_) => pendingSelection.future);
      final bloc = WizardBloc(api: api);
      addTearDown(bloc.close);
      await _prepare(bloc);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere((state) => state.isSelectingDeploymentRun);
      expect(bloc.state.canRequestCalculation, isFalse);
      expect(bloc.state.canProceedToStep3, isFalse);
      bloc
        ..add(const WizardCalculateRequested())
        ..add(const WizardSaveDraft())
        ..add(const WizardFinish());
      await Future<void>.delayed(Duration.zero);
      verify(() => api.createOptimizerRun('new-twin', any())).called(1);
      verifyNever(() => api.updateTwinConfigRequest(any(), any()));

      final changed = CalcParams.fromJson({
        ...bloc.state.calcParams!.toJson(),
        'numberOfDevices': bloc.state.calcParams!.numberOfDevices + 1,
      });
      bloc.add(WizardCalcParamsChanged(changed));
      await bloc.stream.firstWhere(
        (state) =>
            state.calcParams == changed &&
            !state.isSelectingDeploymentRun &&
            state.deploymentRun == null,
      );

      final selectedAt = TypedApiFixtures.timestamp.add(
        const Duration(seconds: 2),
      );
      pendingSelection.complete(
        OptimizerRunSelectionData(
          run: TypedApiFixtures.deploymentRun(
            id: 'run-123',
            twinId: 'new-twin',
            selectedForDeploymentAt: selectedAt,
          ),
          selectedForDeploymentAt: selectedAt,
        ),
      );
      await Future<void>.delayed(Duration.zero);
      await Future<void>.delayed(Duration.zero);

      expect(bloc.state.calcResult, isNull);
      expect(bloc.state.deploymentRun, isNull);
      expect(bloc.state.canProceedToStep3, isFalse);
      expect(bloc.state.errorMessage, isNull);
    },
  );

  test(
    'duplicate selection retries cannot create concurrent requests',
    () async {
      var attempts = 0;
      final retry = Completer<OptimizerRunSelectionData>();
      when(() => api.createTwin('Factory twin')).thenAnswer(
        (_) async =>
            TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
      );
      when(() => api.createOptimizerRun('new-twin', any())).thenAnswer(
        (_) async => TypedApiFixtures.optimizerRun(twinId: 'new-twin'),
      );
      when(
        () => api.selectOptimizerRunForDeployment('new-twin', 'run-123'),
      ).thenAnswer((_) {
        attempts += 1;
        if (attempts == 1) throw Exception('verification unavailable');
        return retry.future;
      });
      final bloc = WizardBloc(api: api);
      addTearDown(bloc.close);
      await _prepare(bloc);

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere(
        (state) =>
            state.deploymentReview.state ==
            ResolvedDeploymentReviewState.failed,
      );

      bloc
        ..add(const WizardDeploymentRunSelectionRequested())
        ..add(const WizardDeploymentRunSelectionRequested());
      await bloc.stream.firstWhere((state) => state.isSelectingDeploymentRun);
      await Future<void>.delayed(Duration.zero);
      expect(attempts, 2);

      final selectedAt = TypedApiFixtures.timestamp.add(
        const Duration(seconds: 2),
      );
      retry.complete(
        OptimizerRunSelectionData(
          run: TypedApiFixtures.deploymentRun(
            id: 'run-123',
            twinId: 'new-twin',
            selectedForDeploymentAt: selectedAt,
          ),
          selectedForDeploymentAt: selectedAt,
        ),
      );
      await bloc.stream.firstWhere((state) => state.deploymentReview.ready);
      expect(attempts, 2);
    },
  );

  test('blank create-mode name blocks twin and optimizer calls', () async {
    final bloc = WizardBloc(api: api);
    addTearDown(bloc.close);
    await _prepare(bloc, twinName: '   ');

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere((state) => state.errorMessage != null);

    expect(bloc.state.errorMessage, 'Twin name is required');
    verifyNever(() => api.createTwin(any()));
    verifyNever(() => api.createOptimizerRun(any(), any()));
  });
}

Future<void> _prepare(
  WizardBloc bloc, {
  String twinName = 'Factory twin',
}) async {
  bloc
    ..add(WizardTwinNameChanged(twinName))
    ..add(WizardCalcParamsChanged(CalcParams.defaultParams()))
    ..add(const WizardPricingHealthLoadRequested());
  await bloc.stream.firstWhere(
    (state) =>
        state.twinName == twinName &&
        state.calcParams != null &&
        state.pricingHealth != null,
  );
}

PricingHealthResponse _health() => PricingHealthResponse.fromJson({
  'schema_version': 'pricing-health.v1',
  'providers': {
    for (final provider in const ['aws', 'azure', 'gcp'])
      provider: {
        'provider': provider,
        'state': 'fresh',
        'severity': 'success',
        'review_required': false,
        'can_calculate': true,
        'calculation_source': 'fresh',
        'pricing_freshness': 'fresh',
        'source_label': '${provider.toUpperCase()} source',
        'credential_summary': {
          'provider': provider,
          'purpose': 'pricing',
          'scope': 'user',
          'identity_label': '${provider.toUpperCase()} pricing',
          'status': 'active',
        },
        'primary_message': '$provider pricing is ready',
      },
  },
});
