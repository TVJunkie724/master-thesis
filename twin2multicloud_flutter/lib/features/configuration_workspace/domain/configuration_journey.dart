import '../../../bloc/wizard/wizard_state.dart';
import '../../../models/deployer_config.dart';
import '../../../models/user_function_extension.dart';

enum ConfigurationPhaseId { scenario, optimize, prepare, review }

enum ConfigurationTaskId {
  defineTwin,
  scenarioAndCurrency,
  deviceTraffic,
  processing,
  retention,
  twinCapabilities,
  userLogic,
  calculateCostAllocation,
  reviewImmutableResult,
  cloudAccess,
  dataContracts,
  twinAssets,
  summary,
  readinessFindings,
  validationAndPreflight,
}

enum ConfigurationTaskStatus {
  complete,
  current,
  attention,
  available,
  blocked,
  notRequired,
}

class ConfigurationTask {
  final ConfigurationTaskId id;
  final ConfigurationPhaseId phaseId;
  final String label;
  final ConfigurationTaskStatus status;
  final String? blockingReason;

  const ConfigurationTask({
    required this.id,
    required this.phaseId,
    required this.label,
    required this.status,
    this.blockingReason,
  });

  bool get isNavigable => switch (status) {
    ConfigurationTaskStatus.complete ||
    ConfigurationTaskStatus.current ||
    ConfigurationTaskStatus.attention ||
    ConfigurationTaskStatus.available => true,
    ConfigurationTaskStatus.blocked ||
    ConfigurationTaskStatus.notRequired => false,
  };
}

class ConfigurationPhase {
  final ConfigurationPhaseId id;
  final String label;
  final List<ConfigurationTask> tasks;

  const ConfigurationPhase({
    required this.id,
    required this.label,
    required this.tasks,
  });

  bool get complete => tasks.every(
    (task) =>
        task.status == ConfigurationTaskStatus.complete ||
        task.status == ConfigurationTaskStatus.notRequired,
  );

  bool get requiresAttention =>
      tasks.any((task) => task.status == ConfigurationTaskStatus.attention);
}

class ConfigurationJourney {
  static const orderedTaskIds = <ConfigurationTaskId>[
    ConfigurationTaskId.defineTwin,
    ConfigurationTaskId.scenarioAndCurrency,
    ConfigurationTaskId.deviceTraffic,
    ConfigurationTaskId.processing,
    ConfigurationTaskId.retention,
    ConfigurationTaskId.twinCapabilities,
    ConfigurationTaskId.userLogic,
    ConfigurationTaskId.calculateCostAllocation,
    ConfigurationTaskId.reviewImmutableResult,
    ConfigurationTaskId.cloudAccess,
    ConfigurationTaskId.dataContracts,
    ConfigurationTaskId.twinAssets,
    ConfigurationTaskId.summary,
    ConfigurationTaskId.readinessFindings,
    ConfigurationTaskId.validationAndPreflight,
  ];

  final List<ConfigurationPhase> phases;
  final ConfigurationTaskId currentTaskId;
  final ConfigurationTaskId recommendedTaskId;

  const ConfigurationJourney({
    required this.phases,
    required this.currentTaskId,
    required this.recommendedTaskId,
  });

  factory ConfigurationJourney.fromWizardState(
    WizardState state, {
    ConfigurationTaskId? requestedTaskId,
  }) {
    final baseTasks = _projectTasks(state);
    final recommended = _recommendedTask(baseTasks);
    final requested = requestedTaskId == null
        ? null
        : baseTasks[requestedTaskId];
    final current = requested?.isNavigable == true
        ? requestedTaskId!
        : recommended;
    final tasks = {
      for (final entry in baseTasks.entries)
        entry.key: entry.key == current
            ? ConfigurationTask(
                id: entry.value.id,
                phaseId: entry.value.phaseId,
                label: entry.value.label,
                status: ConfigurationTaskStatus.current,
                blockingReason: entry.value.blockingReason,
              )
            : entry.value,
    };

    return ConfigurationJourney(
      phases: [
        _phase(ConfigurationPhaseId.scenario, 'Scenario', tasks, const [
          ConfigurationTaskId.defineTwin,
          ConfigurationTaskId.scenarioAndCurrency,
          ConfigurationTaskId.deviceTraffic,
          ConfigurationTaskId.processing,
          ConfigurationTaskId.retention,
          ConfigurationTaskId.twinCapabilities,
          ConfigurationTaskId.userLogic,
        ]),
        _phase(ConfigurationPhaseId.optimize, 'Optimize', tasks, const [
          ConfigurationTaskId.calculateCostAllocation,
          ConfigurationTaskId.reviewImmutableResult,
        ]),
        _phase(ConfigurationPhaseId.prepare, 'Prepare', tasks, const [
          ConfigurationTaskId.cloudAccess,
          ConfigurationTaskId.dataContracts,
          ConfigurationTaskId.twinAssets,
        ]),
        _phase(ConfigurationPhaseId.review, 'Review', tasks, const [
          ConfigurationTaskId.summary,
          ConfigurationTaskId.readinessFindings,
          ConfigurationTaskId.validationAndPreflight,
        ]),
      ],
      currentTaskId: current,
      recommendedTaskId: recommended,
    );
  }

  ConfigurationTask task(ConfigurationTaskId id) =>
      phases.expand((phase) => phase.tasks).firstWhere((task) => task.id == id);

  ConfigurationPhase get currentPhase =>
      phases.firstWhere((phase) => phase.id == task(currentTaskId).phaseId);

  ConfigurationTaskId? get previousNavigableTaskId {
    final index = orderedTaskIds.indexOf(currentTaskId);
    for (var candidate = index - 1; candidate >= 0; candidate--) {
      final id = orderedTaskIds[candidate];
      if (task(id).isNavigable) return id;
    }
    return null;
  }

  ConfigurationTaskId? get nextNavigableTaskId {
    final index = orderedTaskIds.indexOf(currentTaskId);
    for (
      var candidate = index + 1;
      candidate < orderedTaskIds.length;
      candidate++
    ) {
      final id = orderedTaskIds[candidate];
      if (task(id).isNavigable) return id;
    }
    return null;
  }

  static int legacyStepFor(ConfigurationTaskId taskId) => switch (taskId) {
    ConfigurationTaskId.defineTwin => 0,
    ConfigurationTaskId.scenarioAndCurrency ||
    ConfigurationTaskId.deviceTraffic ||
    ConfigurationTaskId.processing ||
    ConfigurationTaskId.retention ||
    ConfigurationTaskId.twinCapabilities ||
    ConfigurationTaskId.userLogic ||
    ConfigurationTaskId.calculateCostAllocation ||
    ConfigurationTaskId.reviewImmutableResult => 1,
    ConfigurationTaskId.cloudAccess ||
    ConfigurationTaskId.dataContracts ||
    ConfigurationTaskId.twinAssets ||
    ConfigurationTaskId.summary ||
    ConfigurationTaskId.readinessFindings ||
    ConfigurationTaskId.validationAndPreflight => 2,
  };

  static Map<ConfigurationTaskId, ConfigurationTask> _projectTasks(
    WizardState state,
  ) {
    final twinPersisted =
        state.twinName?.trim().isNotEmpty == true && state.twinId != null;
    final canonicalReady = state.architectureWorkflowReady;
    final canonicalFailed =
        state.architectureDetailPhase == ArchitectureDetailPhase.error;
    final workloadPresent = state.calcParams != null;
    final workloadComplete = workloadPresent && state.isCalcFormValid;
    final scenarioBlocker = !twinPersisted
        ? 'Save the Twin draft first'
        : !canonicalReady
        ? 'The canonical six-layer-eventing@1 contract must be verified first'
        : null;
    final workloadStatus = scenarioBlocker != null
        ? ConfigurationTaskStatus.blocked
        : workloadComplete
        ? ConfigurationTaskStatus.complete
        : workloadPresent
        ? ConfigurationTaskStatus.attention
        : ConfigurationTaskStatus.available;

    final profileHasUserLogic =
        state.architectureProfileDetail?.summary.extensionSlots.isNotEmpty ==
        true;
    final extensionNeedsAttention =
        state.extensionErrors.containsKey('_catalog') ||
        state.extensionSlots.any((slot) {
          final phase = state.extensionPhase(slot.slotId);
          return phase == UserFunctionWorkflowPhase.invalid ||
              phase == UserFunctionWorkflowPhase.stale ||
              phase == UserFunctionWorkflowPhase.error;
        });
    final userLogicStatus = !canonicalReady
        ? ConfigurationTaskStatus.blocked
        : !profileHasUserLogic
        ? ConfigurationTaskStatus.notRequired
        : state.architectureUserFunctionsReady
        ? ConfigurationTaskStatus.complete
        : extensionNeedsAttention
        ? ConfigurationTaskStatus.attention
        : ConfigurationTaskStatus.available;
    final optimizerInputsReady =
        workloadComplete && state.architectureUserFunctionsReady;
    final calculationReady = state.calcResult != null;
    final calculationStatus = !optimizerInputsReady
        ? ConfigurationTaskStatus.blocked
        : calculationReady
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.available;
    final optimizerBlocker = optimizerInputsReady
        ? null
        : 'Complete the scenario and required user logic first';
    final deploymentSelectionReady =
        calculationReady && state.canProceedToStep3;
    final resultStatus = !calculationReady
        ? ConfigurationTaskStatus.blocked
        : deploymentSelectionReady
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.attention;

    final requiredProvidersConfigured =
        calculationReady && state.unconfiguredProviders.isEmpty;
    final cloudAccessStatus = !deploymentSelectionReady
        ? ConfigurationTaskStatus.blocked
        : requiredProvidersConfigured
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.attention;
    final deploymentBlocker = !calculationReady
        ? 'Calculate the cost allocation first'
        : !deploymentSelectionReady
        ? 'Verify the immutable optimization result first'
        : null;

    final readiness = state.deployerReadiness;
    final config = readiness.section(DeployerSectionId.configuration);
    final payloads = readiness.section(DeployerSectionId.payloads);
    final assets = readiness.section(DeployerSectionId.digitalTwinAssets);

    ConfigurationTaskStatus deploymentStatus(DeployerSectionReadiness section) {
      if (!deploymentSelectionReady) return ConfigurationTaskStatus.blocked;
      if (section.artifacts.every((artifact) => !artifact.required)) {
        return ConfigurationTaskStatus.notRequired;
      }
      if (section.ready) return ConfigurationTaskStatus.complete;
      final hasAnyContent = section.artifacts.any(
        (artifact) => artifact.required && artifact.hasContent,
      );
      return hasAnyContent
          ? ConfigurationTaskStatus.attention
          : ConfigurationTaskStatus.available;
    }

    final allReady =
        deploymentSelectionReady &&
        requiredProvidersConfigured &&
        readiness.ready &&
        state.architectureUserFunctionsReady &&
        !state.step3Invalidated;
    final reviewStatus = !calculationReady
        ? ConfigurationTaskStatus.blocked
        : allReady
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.available;
    final readinessStatus = !calculationReady
        ? ConfigurationTaskStatus.blocked
        : state.step3Invalidated
        ? ConfigurationTaskStatus.attention
        : allReady
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.available;

    ConfigurationTask task(
      ConfigurationTaskId id,
      ConfigurationPhaseId phase,
      String label,
      ConfigurationTaskStatus status, {
      String? blocker,
    }) => ConfigurationTask(
      id: id,
      phaseId: phase,
      label: label,
      status: status,
      blockingReason: blocker,
    );

    return {
      ConfigurationTaskId.defineTwin: task(
        ConfigurationTaskId.defineTwin,
        ConfigurationPhaseId.scenario,
        'Define Twin',
        canonicalFailed
            ? ConfigurationTaskStatus.attention
            : twinPersisted
            ? ConfigurationTaskStatus.complete
            : ConfigurationTaskStatus.available,
        blocker: canonicalFailed ? state.architectureDetailError : null,
      ),
      for (final entry in const {
        ConfigurationTaskId.scenarioAndCurrency: 'Scenario and currency',
        ConfigurationTaskId.deviceTraffic: 'Device traffic',
        ConfigurationTaskId.processing: 'Processing',
        ConfigurationTaskId.retention: 'Retention',
        ConfigurationTaskId.twinCapabilities: 'Twin capabilities',
      }.entries)
        entry.key: task(
          entry.key,
          ConfigurationPhaseId.scenario,
          entry.value,
          workloadStatus,
          blocker: scenarioBlocker,
        ),
      ConfigurationTaskId.userLogic: task(
        ConfigurationTaskId.userLogic,
        ConfigurationPhaseId.scenario,
        'User logic',
        userLogicStatus,
        blocker: canonicalReady ? null : scenarioBlocker,
      ),
      ConfigurationTaskId.calculateCostAllocation: task(
        ConfigurationTaskId.calculateCostAllocation,
        ConfigurationPhaseId.optimize,
        'Calculate cost allocation',
        calculationStatus,
        blocker: optimizerBlocker,
      ),
      ConfigurationTaskId.reviewImmutableResult: task(
        ConfigurationTaskId.reviewImmutableResult,
        ConfigurationPhaseId.optimize,
        'Review immutable result',
        resultStatus,
        blocker: calculationReady
            ? null
            : 'Calculate the cost allocation first',
      ),
      ConfigurationTaskId.cloudAccess: task(
        ConfigurationTaskId.cloudAccess,
        ConfigurationPhaseId.prepare,
        'Cloud access',
        cloudAccessStatus,
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.dataContracts: task(
        ConfigurationTaskId.dataContracts,
        ConfigurationPhaseId.prepare,
        'Data contracts',
        deploymentStatus(config) == ConfigurationTaskStatus.complete &&
                deploymentStatus(payloads) == ConfigurationTaskStatus.complete
            ? ConfigurationTaskStatus.complete
            : deploymentStatus(config) == ConfigurationTaskStatus.attention ||
                  deploymentStatus(payloads) ==
                      ConfigurationTaskStatus.attention
            ? ConfigurationTaskStatus.attention
            : deploymentStatus(config),
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.twinAssets: task(
        ConfigurationTaskId.twinAssets,
        ConfigurationPhaseId.prepare,
        'Twin assets',
        deploymentStatus(assets),
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.summary: task(
        ConfigurationTaskId.summary,
        ConfigurationPhaseId.review,
        'Summary',
        reviewStatus,
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.readinessFindings: task(
        ConfigurationTaskId.readinessFindings,
        ConfigurationPhaseId.review,
        'Readiness findings',
        readinessStatus,
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.validationAndPreflight: task(
        ConfigurationTaskId.validationAndPreflight,
        ConfigurationPhaseId.review,
        'Validation and preflight',
        allReady
            ? ConfigurationTaskStatus.complete
            : calculationReady
            ? ConfigurationTaskStatus.available
            : ConfigurationTaskStatus.blocked,
        blocker: deploymentBlocker,
      ),
    };
  }

  static ConfigurationTaskId _recommendedTask(
    Map<ConfigurationTaskId, ConfigurationTask> tasks,
  ) {
    for (final id in orderedTaskIds) {
      final status = tasks[id]!.status;
      if (status == ConfigurationTaskStatus.attention ||
          status == ConfigurationTaskStatus.available) {
        return id;
      }
    }
    return ConfigurationTaskId.summary;
  }

  static ConfigurationPhase _phase(
    ConfigurationPhaseId id,
    String label,
    Map<ConfigurationTaskId, ConfigurationTask> tasks,
    List<ConfigurationTaskId> taskIds,
  ) => ConfigurationPhase(
    id: id,
    label: label,
    tasks: List.unmodifiable(taskIds.map((taskId) => tasks[taskId]!)),
  );
}
