import '../../../bloc/wizard/wizard_state.dart';
import '../../../models/deployer_config.dart';
import '../../../models/user_function_extension.dart';

enum ConfigurationPhaseId {
  defineTwin,
  architecture,
  workload,
  userLogic,
  optimizeAndReview,
  deploymentReview,
}

enum ConfigurationTaskId {
  defineTwin,
  selectProfile,
  understandArchitecture,
  scenarioAndCurrency,
  deviceTraffic,
  processing,
  retention,
  twinCapabilities,
  pricingReadiness,
  calculateAlternatives,
  compareAndSelect,
  cloudAccess,
  dataContracts,
  userLogic,
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
    ConfigurationTaskId.selectProfile,
    ConfigurationTaskId.understandArchitecture,
    ConfigurationTaskId.scenarioAndCurrency,
    ConfigurationTaskId.deviceTraffic,
    ConfigurationTaskId.processing,
    ConfigurationTaskId.retention,
    ConfigurationTaskId.twinCapabilities,
    ConfigurationTaskId.userLogic,
    ConfigurationTaskId.pricingReadiness,
    ConfigurationTaskId.calculateAlternatives,
    ConfigurationTaskId.compareAndSelect,
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
        _phase(ConfigurationPhaseId.defineTwin, 'Define twin', tasks, const [
          ConfigurationTaskId.defineTwin,
        ]),
        _phase(ConfigurationPhaseId.architecture, 'Architecture', tasks, const [
          ConfigurationTaskId.selectProfile,
          ConfigurationTaskId.understandArchitecture,
        ]),
        _phase(ConfigurationPhaseId.workload, 'Workload', tasks, const [
          ConfigurationTaskId.scenarioAndCurrency,
          ConfigurationTaskId.deviceTraffic,
          ConfigurationTaskId.processing,
          ConfigurationTaskId.retention,
          ConfigurationTaskId.twinCapabilities,
        ]),
        _phase(ConfigurationPhaseId.userLogic, 'User Logic', tasks, const [
          ConfigurationTaskId.userLogic,
        ]),
        _phase(
          ConfigurationPhaseId.optimizeAndReview,
          'Optimize and review',
          tasks,
          const [
            ConfigurationTaskId.pricingReadiness,
            ConfigurationTaskId.calculateAlternatives,
            ConfigurationTaskId.compareAndSelect,
          ],
        ),
        _phase(
          ConfigurationPhaseId.deploymentReview,
          'Deployment review',
          tasks,
          const [
            ConfigurationTaskId.cloudAccess,
            ConfigurationTaskId.dataContracts,
            ConfigurationTaskId.twinAssets,
            ConfigurationTaskId.summary,
            ConfigurationTaskId.readinessFindings,
            ConfigurationTaskId.validationAndPreflight,
          ],
        ),
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
    ConfigurationTaskId.defineTwin ||
    ConfigurationTaskId.selectProfile ||
    ConfigurationTaskId.understandArchitecture => 0,
    ConfigurationTaskId.scenarioAndCurrency ||
    ConfigurationTaskId.deviceTraffic ||
    ConfigurationTaskId.processing ||
    ConfigurationTaskId.retention ||
    ConfigurationTaskId.twinCapabilities ||
    ConfigurationTaskId.userLogic ||
    ConfigurationTaskId.pricingReadiness ||
    ConfigurationTaskId.calculateAlternatives ||
    ConfigurationTaskId.compareAndSelect => 1,
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
    final hasName = state.twinName?.trim().isNotEmpty == true;
    final twinPersisted = hasName && state.twinId != null;
    final architectureSelected = state.hasActiveArchitectureProfile;
    final architectureDetailLoaded =
        architectureSelected &&
        state.architectureDetailPhase == ArchitectureDetailPhase.ready &&
        state.architectureProfileDetail != null;
    final architectureReady = state.architectureWorkflowReady;
    final selectProfileStatus = !twinPersisted
        ? ConfigurationTaskStatus.blocked
        : state.architectureCatalogPhase == ArchitectureCatalogPhase.error ||
              state.architectureCatalogPhase == ArchitectureCatalogPhase.empty
        ? ConfigurationTaskStatus.attention
        : architectureSelected
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.available;
    final understandArchitectureStatus = !architectureSelected
        ? ConfigurationTaskStatus.blocked
        : state.architectureDetailPhase == ArchitectureDetailPhase.error
        ? ConfigurationTaskStatus.attention
        : architectureReady
        ? ConfigurationTaskStatus.complete
        : architectureDetailLoaded
        ? ConfigurationTaskStatus.available
        : ConfigurationTaskStatus.available;
    final architectureBlocker = !twinPersisted
        ? 'Save the Twin draft first'
        : !architectureSelected
        ? 'Select an active architecture profile first'
        : null;
    final workloadPresent = state.calcParams != null;
    final workloadComplete = workloadPresent && state.isCalcFormValid;
    final workloadStatus = !architectureReady
        ? ConfigurationTaskStatus.blocked
        : workloadComplete
        ? ConfigurationTaskStatus.complete
        : workloadPresent
        ? ConfigurationTaskStatus.attention
        : ConfigurationTaskStatus.available;
    final workloadBlocker = architectureReady
        ? null
        : 'Select and understand an active architecture profile first';

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
    final userLogicStatus = !architectureReady
        ? ConfigurationTaskStatus.blocked
        : !profileHasUserLogic
        ? ConfigurationTaskStatus.notRequired
        : state.architectureExtensionBindingsReady
        ? ConfigurationTaskStatus.complete
        : extensionNeedsAttention
        ? ConfigurationTaskStatus.attention
        : ConfigurationTaskStatus.available;
    final optimizerInputsReady =
        workloadComplete &&
        state.architectureExtensionBindingsReady &&
        state.architectureInvalidatedWorkloadFieldIds.isEmpty;

    final pricingStatus = !optimizerInputsReady
        ? ConfigurationTaskStatus.blocked
        : state.isPricingHealthLoading
        ? ConfigurationTaskStatus.available
        : state.pricingHealthError != null || !state.pricingCanCalculate
        ? ConfigurationTaskStatus.attention
        : ConfigurationTaskStatus.complete;
    final calculationReady = state.calcResult != null;
    final calculationStatus = !optimizerInputsReady
        ? ConfigurationTaskStatus.blocked
        : calculationReady
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.available;
    final optimizerBlocker = optimizerInputsReady
        ? null
        : 'Complete workload and required user logic first';
    final deploymentSelectionReady =
        calculationReady && state.canProceedToStep3;
    final recommendationStatus = !calculationReady
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
        ? 'Calculate an architecture first'
        : !deploymentSelectionReady
        ? 'Confirm the resolved architecture first'
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
        state.architectureExtensionBindingsReady &&
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

    const define = ConfigurationPhaseId.defineTwin;
    const architecture = ConfigurationPhaseId.architecture;
    const workload = ConfigurationPhaseId.workload;
    const userLogic = ConfigurationPhaseId.userLogic;
    const optimization = ConfigurationPhaseId.optimizeAndReview;
    const deployment = ConfigurationPhaseId.deploymentReview;

    return {
      ConfigurationTaskId.defineTwin: task(
        ConfigurationTaskId.defineTwin,
        define,
        'Identity and mode',
        twinPersisted
            ? ConfigurationTaskStatus.complete
            : ConfigurationTaskStatus.available,
      ),
      ConfigurationTaskId.selectProfile: task(
        ConfigurationTaskId.selectProfile,
        architecture,
        'Select profile',
        selectProfileStatus,
        blocker: twinPersisted ? null : 'Save the Twin draft first',
      ),
      ConfigurationTaskId.understandArchitecture: task(
        ConfigurationTaskId.understandArchitecture,
        architecture,
        'Understand architecture',
        understandArchitectureStatus,
        blocker: architectureBlocker,
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
          workload,
          entry.value,
          workloadStatus,
          blocker: workloadBlocker,
        ),
      ConfigurationTaskId.pricingReadiness: task(
        ConfigurationTaskId.pricingReadiness,
        optimization,
        'Pricing readiness',
        pricingStatus,
        blocker: optimizerBlocker,
      ),
      ConfigurationTaskId.calculateAlternatives: task(
        ConfigurationTaskId.calculateAlternatives,
        optimization,
        'Calculate alternatives',
        calculationStatus,
        blocker: optimizerBlocker,
      ),
      ConfigurationTaskId.compareAndSelect: task(
        ConfigurationTaskId.compareAndSelect,
        optimization,
        'Review recommendation',
        recommendationStatus,
        blocker: optimizerBlocker,
      ),
      ConfigurationTaskId.cloudAccess: task(
        ConfigurationTaskId.cloudAccess,
        deployment,
        'Cloud access',
        cloudAccessStatus,
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.dataContracts: task(
        ConfigurationTaskId.dataContracts,
        deployment,
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
      ConfigurationTaskId.userLogic: task(
        ConfigurationTaskId.userLogic,
        userLogic,
        'Bind user logic',
        userLogicStatus,
        blocker: architectureReady
            ? null
            : 'Select and understand an active architecture profile first',
      ),
      ConfigurationTaskId.twinAssets: task(
        ConfigurationTaskId.twinAssets,
        deployment,
        'Twin assets',
        deploymentStatus(assets),
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.summary: task(
        ConfigurationTaskId.summary,
        deployment,
        'Configuration summary',
        reviewStatus,
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.readinessFindings: task(
        ConfigurationTaskId.readinessFindings,
        deployment,
        'Readiness findings',
        readinessStatus,
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.validationAndPreflight: task(
        ConfigurationTaskId.validationAndPreflight,
        deployment,
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
      if (status == ConfigurationTaskStatus.attention) return id;
      if (status == ConfigurationTaskStatus.available) return id;
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
