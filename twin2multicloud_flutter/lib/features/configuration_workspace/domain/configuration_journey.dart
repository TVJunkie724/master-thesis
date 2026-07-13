import '../../../bloc/wizard/wizard_state.dart';
import '../../../models/deployer_config.dart';

enum ConfigurationPhaseId {
  defineTwin,
  describeWorkload,
  chooseArchitecture,
  prepareDeployment,
  reviewConfiguration,
}

enum ConfigurationTaskId {
  defineTwin,
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
    ConfigurationTaskId.scenarioAndCurrency,
    ConfigurationTaskId.deviceTraffic,
    ConfigurationTaskId.processing,
    ConfigurationTaskId.retention,
    ConfigurationTaskId.twinCapabilities,
    ConfigurationTaskId.pricingReadiness,
    ConfigurationTaskId.calculateAlternatives,
    ConfigurationTaskId.compareAndSelect,
    ConfigurationTaskId.cloudAccess,
    ConfigurationTaskId.dataContracts,
    ConfigurationTaskId.userLogic,
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
        _phase(
          ConfigurationPhaseId.describeWorkload,
          'Describe workload',
          tasks,
          const [
            ConfigurationTaskId.scenarioAndCurrency,
            ConfigurationTaskId.deviceTraffic,
            ConfigurationTaskId.processing,
            ConfigurationTaskId.retention,
            ConfigurationTaskId.twinCapabilities,
          ],
        ),
        _phase(
          ConfigurationPhaseId.chooseArchitecture,
          'Choose architecture',
          tasks,
          const [
            ConfigurationTaskId.pricingReadiness,
            ConfigurationTaskId.calculateAlternatives,
            ConfigurationTaskId.compareAndSelect,
          ],
        ),
        _phase(
          ConfigurationPhaseId.prepareDeployment,
          'Prepare deployment',
          tasks,
          const [
            ConfigurationTaskId.cloudAccess,
            ConfigurationTaskId.dataContracts,
            ConfigurationTaskId.userLogic,
            ConfigurationTaskId.twinAssets,
          ],
        ),
        _phase(
          ConfigurationPhaseId.reviewConfiguration,
          'Review configuration',
          tasks,
          const [
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
    ConfigurationTaskId.defineTwin => 0,
    ConfigurationTaskId.scenarioAndCurrency ||
    ConfigurationTaskId.deviceTraffic ||
    ConfigurationTaskId.processing ||
    ConfigurationTaskId.retention ||
    ConfigurationTaskId.twinCapabilities ||
    ConfigurationTaskId.pricingReadiness ||
    ConfigurationTaskId.calculateAlternatives ||
    ConfigurationTaskId.compareAndSelect => 1,
    ConfigurationTaskId.cloudAccess ||
    ConfigurationTaskId.dataContracts ||
    ConfigurationTaskId.userLogic ||
    ConfigurationTaskId.twinAssets ||
    ConfigurationTaskId.summary ||
    ConfigurationTaskId.readinessFindings ||
    ConfigurationTaskId.validationAndPreflight => 2,
  };

  static Map<ConfigurationTaskId, ConfigurationTask> _projectTasks(
    WizardState state,
  ) {
    final hasName = state.twinName?.trim().isNotEmpty == true;
    final workloadPresent = state.calcParams != null;
    final workloadComplete = workloadPresent && state.isCalcFormValid;
    final workloadStatus = !hasName
        ? ConfigurationTaskStatus.blocked
        : workloadComplete
        ? ConfigurationTaskStatus.complete
        : workloadPresent
        ? ConfigurationTaskStatus.attention
        : ConfigurationTaskStatus.available;
    final workloadBlocker = hasName ? null : 'Define the twin first';

    final pricingStatus = !workloadComplete
        ? ConfigurationTaskStatus.blocked
        : state.isPricingHealthLoading
        ? ConfigurationTaskStatus.available
        : state.pricingHealthError != null || !state.pricingCanCalculate
        ? ConfigurationTaskStatus.attention
        : ConfigurationTaskStatus.complete;
    final architectureReady = state.calcResult != null;
    final architectureStatus = !workloadComplete
        ? ConfigurationTaskStatus.blocked
        : architectureReady
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.available;
    final architectureBlocker = workloadComplete
        ? null
        : 'Complete the workload description first';

    final requiredProvidersConfigured =
        architectureReady && state.unconfiguredProviders.isEmpty;
    final cloudAccessStatus = !architectureReady
        ? ConfigurationTaskStatus.blocked
        : requiredProvidersConfigured
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.attention;
    final deploymentBlocker = architectureReady
        ? null
        : 'Select an architecture first';

    final readiness = state.deployerReadiness;
    final config = readiness.section(DeployerSectionId.configuration);
    final payloads = readiness.section(DeployerSectionId.payloads);
    final logic = readiness.section(DeployerSectionId.userLogic);
    final assets = readiness.section(DeployerSectionId.digitalTwinAssets);

    ConfigurationTaskStatus deploymentStatus(DeployerSectionReadiness section) {
      if (!architectureReady) return ConfigurationTaskStatus.blocked;
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
        architectureReady &&
        requiredProvidersConfigured &&
        readiness.ready &&
        !state.step3Invalidated;
    final reviewStatus = !architectureReady
        ? ConfigurationTaskStatus.blocked
        : allReady
        ? ConfigurationTaskStatus.complete
        : ConfigurationTaskStatus.available;
    final readinessStatus = !architectureReady
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
    const workload = ConfigurationPhaseId.describeWorkload;
    const architecture = ConfigurationPhaseId.chooseArchitecture;
    const deployment = ConfigurationPhaseId.prepareDeployment;
    const review = ConfigurationPhaseId.reviewConfiguration;

    return {
      ConfigurationTaskId.defineTwin: task(
        ConfigurationTaskId.defineTwin,
        define,
        'Identity and mode',
        hasName
            ? ConfigurationTaskStatus.complete
            : ConfigurationTaskStatus.available,
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
        architecture,
        'Pricing readiness',
        pricingStatus,
        blocker: architectureBlocker,
      ),
      ConfigurationTaskId.calculateAlternatives: task(
        ConfigurationTaskId.calculateAlternatives,
        architecture,
        'Calculate alternatives',
        architectureStatus,
        blocker: architectureBlocker,
      ),
      ConfigurationTaskId.compareAndSelect: task(
        ConfigurationTaskId.compareAndSelect,
        architecture,
        'Compare and select',
        architectureStatus,
        blocker: architectureBlocker,
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
        deployment,
        'User logic',
        deploymentStatus(logic),
        blocker: deploymentBlocker,
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
        review,
        'Configuration summary',
        reviewStatus,
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.readinessFindings: task(
        ConfigurationTaskId.readinessFindings,
        review,
        'Readiness findings',
        readinessStatus,
        blocker: deploymentBlocker,
      ),
      ConfigurationTaskId.validationAndPreflight: task(
        ConfigurationTaskId.validationAndPreflight,
        review,
        'Validation and preflight',
        allReady
            ? ConfigurationTaskStatus.complete
            : architectureReady
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
