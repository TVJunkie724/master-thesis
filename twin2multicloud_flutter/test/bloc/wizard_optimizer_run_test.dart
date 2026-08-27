import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/core/app_logger.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';
import 'package:twin2multicloud_flutter/models/wizard_config_requests.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

import '../fixtures/typed_api_fixtures.dart';
import '../fixtures/architecture_wizard_fixture.dart';

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
    when(() => api.getRunResolvedArchitecture(any())).thenAnswer((invocation) {
      final runId = invocation.positionalArguments.single as String;
      return Future.value(
        resolvedArchitectureFixture(runId: runId, twinId: 'new-twin'),
      );
    });
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
    final bloc = _bloc(api);
    addTearDown(bloc.close);
    await _prepare(bloc);

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere(
      (state) => state.deploymentReview.ready || state.errorMessage != null,
    );

    expect(bloc.state.errorMessage, isNull);
    expect(bloc.state.deploymentReview.ready, isTrue);
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
      final bloc = _bloc(api);
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
    final bloc = _bloc(api);
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
      final bloc = _bloc(api, logger: AppLogger(sink: logSink));
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

  test(
    'six-layer v2 offline evidence loads for review without deployment selection',
    () async {
      final run = _sixLayerOptimizerRun();
      final profile =
          (run.deploymentRun.specification as ResolvedDeploymentSpecificationV2)
              .architectureProfileRef;
      when(() => api.createTwin('Factory twin')).thenAnswer(
        (_) async =>
            TypedApiFixtures.twin(id: 'new-twin', name: 'Factory twin'),
      );
      when(
        () => api.createOptimizerRun('new-twin', any()),
      ).thenAnswer((_) async => run);
      when(
        () => api.getRunResolvedArchitecture(run.id),
      ).thenAnswer((_) async => _sixLayerResolvedArchitecture());
      final bloc = _bloc(
        api,
        initialState: architectureReadyWizardState(
          persisted: false,
          profileId: profile.id,
          profileVersion: profile.version,
          profileDigest: profile.digest,
        ),
      );
      addTearDown(bloc.close);
      await _prepare(
        bloc,
        params: CalcParams.sixLayer(scenario: SixLayerWorkloadScenario.small),
      );

      bloc.add(const WizardCalculateRequested());
      await bloc.stream.firstWhere(
        (state) =>
            state.deploymentReview.state ==
                ResolvedDeploymentReviewState.evaluationOnly &&
            state.resolvedArchitecturePhase == ResolvedArchitecturePhase.ready,
      );

      expect(bloc.state.deploymentReview.ready, isFalse);
      expect(bloc.state.resolvedArchitectureReadyForSelectedRun, isTrue);
      expect(bloc.state.canProceedToStep3, isFalse);
      expect(bloc.state.warningMessage, contains('evaluation-only'));
      verifyNever(
        () => api.selectOptimizerRunForDeployment('new-twin', run.id),
      );
      verify(() => api.getRunResolvedArchitecture(run.id)).called(1);
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
    final bloc = _bloc(api);
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
    final bloc = _bloc(api);
    addTearDown(bloc.close);
    await _prepare(bloc);

    bloc.add(const WizardCalculateRequested());
    final resolvedState = await bloc.stream.firstWhere(
      (state) =>
          state.resolvedArchitecturePhase == ResolvedArchitecturePhase.ready ||
          state.resolvedArchitecturePhase ==
              ResolvedArchitecturePhase.incompatible ||
          state.resolvedArchitecturePhase == ResolvedArchitecturePhase.error,
    );
    expect(
      resolvedState.resolvedArchitectureReadyForSelectedRun,
      isTrue,
      reason: resolvedState.resolvedArchitectureError,
    );
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
      final bloc = _bloc(api);
      addTearDown(bloc.close);
      await _prepare(bloc);

      bloc.add(const WizardCalculateRequested());
      final resolvedState = await bloc.stream.firstWhere(
        (state) =>
            state.resolvedArchitecturePhase ==
                ResolvedArchitecturePhase.ready ||
            state.resolvedArchitecturePhase ==
                ResolvedArchitecturePhase.incompatible ||
            state.resolvedArchitecturePhase == ResolvedArchitecturePhase.error,
      );
      expect(
        resolvedState.resolvedArchitectureReadyForSelectedRun,
        isTrue,
        reason: resolvedState.resolvedArchitectureError,
      );
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
      final bloc = _bloc(api);
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
      final bloc = _bloc(api);
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
      final bloc = _bloc(api);
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
    final bloc = _bloc(api);
    addTearDown(bloc.close);
    await _prepare(bloc, twinName: '   ');

    bloc.add(const WizardCalculateRequested());
    await bloc.stream.firstWhere((state) => state.errorMessage != null);

    expect(bloc.state.errorMessage, 'Twin name is required');
    verifyNever(() => api.createTwin(any()));
    verifyNever(() => api.createOptimizerRun(any(), any()));
  });
}

WizardBloc _bloc(
  _MockApiService api, {
  AppLogger logger = const AppLogger(),
  WizardState? initialState,
}) => WizardBloc(
  api: api,
  logger: logger,
  initialState: initialState ?? architectureReadyWizardState(persisted: false),
);

Future<void> _prepare(
  WizardBloc bloc, {
  String twinName = 'Factory twin',
  CalcParams? params,
}) async {
  bloc
    ..add(WizardTwinNameChanged(twinName))
    ..add(WizardCalcParamsChanged(params ?? CalcParams.defaultParams()));
  await bloc.stream.firstWhere(
    (state) => state.twinName == twinName && state.calcParams != null,
  );
}

OptimizerRunData _sixLayerOptimizerRun() {
  final specification = _jsonFixture(
    '../contracts/resolved-deployment-specification/v2/fixtures/valid/'
    'six-layer-aws-azure-eventing-small.json',
  );
  final runId = specification['calculation_run_id']! as String;
  final optimization = TypedApiFixtures.optimization();
  final deploymentRun = OptimizerDeploymentRunData.fromDetailJson({
    'id': runId,
    'twin_id': 'new-twin',
    'status': 'succeeded',
    'deployment_compatibility_status': 'ready',
    'deployment_specification_digest': specification['digest'],
    'deployment_specification_version': specification['schema_version'],
    'resolved_deployment_specification': specification,
    'created_at': TypedApiFixtures.timestamp.toIso8601String(),
    'selected_for_deployment_at': null,
  });
  return OptimizerRunData(
    id: runId,
    twinId: 'new-twin',
    optimization: optimization,
    deploymentRun: deploymentRun,
    totalMonthlyCost: optimization.result.totalCost,
    currency: 'USD',
    createdAt: TypedApiFixtures.timestamp,
    completedAt: TypedApiFixtures.timestamp.add(const Duration(seconds: 1)),
  );
}

ResolvedTwinArchitectureRead _sixLayerResolvedArchitecture() {
  final architecture = _jsonFixture(
    '../contracts/architecture-profiles/v2/fixtures/valid/'
    'six-layer-aws-azure-eventing-small-resolved.json',
  );
  return ResolvedTwinArchitectureRead.fromJson({
    'twin_id': 'new-twin',
    'calculation_run_id': architecture['calculation_run_id'],
    'selected_for_deployment_at': null,
    'architecture_compatibility_status': 'ready',
    'origin': 'native_v2',
    'architecture': architecture,
  });
}

Map<String, dynamic> _jsonFixture(String path) =>
    jsonDecode(File(path).readAsStringSync()) as Map<String, dynamic>;
