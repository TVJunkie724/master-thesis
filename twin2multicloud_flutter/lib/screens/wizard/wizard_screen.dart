import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../bloc/wizard/wizard.dart';
import '../../features/configuration_workspace/domain/configuration_journey.dart';
import '../../features/configuration_workspace/presentation/cloud_access_task.dart';
import '../../features/configuration_workspace/presentation/configuration_alert_stack.dart';
import '../../features/configuration_workspace/presentation/configuration_navigation_bar.dart';
import '../../features/configuration_workspace/presentation/configuration_review_task.dart';
import '../../features/configuration_workspace/presentation/configuration_workspace_app_bar.dart';
import '../../features/configuration_workspace/presentation/configuration_workspace_dialogs.dart';
import '../../features/configuration_workspace/presentation/configuration_workspace_header.dart';
import '../../features/configuration_workspace/presentation/configuration_workspace_scaffold.dart';
import '../../features/configuration_workspace/presentation/configuration_workspace_shell.dart';
import '../../providers/auth_provider.dart';
import '../../providers/theme_provider.dart';
import '../../providers/twins_provider.dart';
import 'step1_configuration.dart';
import 'step2_optimizer.dart';
import 'step3_deployer.dart';

class WizardScreen extends ConsumerWidget {
  final String? twinId;

  const WizardScreen({super.key, this.twinId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(apiServiceProvider);
    return BlocProvider(
      create: (context) {
        final bloc = WizardBloc(api: api);
        bloc.add(
          twinId == null ? const WizardInitCreate() : WizardInitEdit(twinId!),
        );
        return bloc;
      },
      child: WizardView(twinId: twinId),
    );
  }
}

class WizardView extends ConsumerStatefulWidget {
  final String? twinId;

  const WizardView({super.key, this.twinId});

  @override
  ConsumerState<WizardView> createState() => _WizardViewState();
}

class _WizardViewState extends ConsumerState<WizardView> {
  ConfigurationTaskId? _currentTaskId;
  _WorkspaceExitDestination? _pendingExitDestination;
  Timer? _notificationTimer;

  @override
  void dispose() {
    _notificationTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<WizardBloc, WizardState>(
      listenWhen: (previous, current) =>
          previous.status != current.status ||
          previous.successMessage != current.successMessage ||
          previous.errorMessage != current.errorMessage,
      listener: _handleStateSideEffects,
      builder: (context, state) {
        final commandInProgress = _commandInProgress(state);
        final appBar = ConfigurationWorkspaceAppBar(
          isDarkMode: ref.watch(themeProvider) == ThemeMode.dark,
          navigationEnabled: !commandInProgress,
          onToggleTheme: () => ref.read(themeProvider.notifier).toggle(),
          onOpenSettings: () =>
              _requestExit(context, state, _WorkspaceExitDestination.settings),
          onLogout: () =>
              _requestExit(context, state, _WorkspaceExitDestination.logout),
        );
        if (state.status == WizardStatus.loading) {
          return ConfigurationWorkspaceScaffold(
            appBar: appBar,
            isLoading: true,
            header: const SizedBox.shrink(),
            alerts: const SizedBox.shrink(),
            workspace: const SizedBox.shrink(),
            navigation: const SizedBox.shrink(),
          );
        }

        final journey = ConfigurationJourney.fromWizardState(
          state,
          requestedTaskId: _currentTaskId,
        );
        _synchronizeCurrentTask(context, journey);
        return ConfigurationWorkspaceScaffold(
          appBar: appBar,
          isLoading: false,
          header: ConfigurationWorkspaceHeader(
            isCreateMode: state.mode == WizardMode.create,
            phaseLabel: journey.currentPhase.label,
            taskLabel: journey.task(journey.currentTaskId).label,
            onClose: commandInProgress
                ? null
                : () => _requestExit(
                    context,
                    state,
                    _WorkspaceExitDestination.dashboard,
                  ),
            closeDisabledReason: 'Wait for the current command to finish',
          ),
          alerts: ConfigurationAlertStack(
            errorMessage: state.errorMessage,
            successMessage: state.successMessage,
            warningMessage: state.warningMessage,
            onDismissError: () =>
                context.read<WizardBloc>().add(const WizardDismissError()),
            onDismissNotification: () => context.read<WizardBloc>().add(
              const WizardClearNotifications(),
            ),
          ),
          workspace: ConfigurationWorkspaceShell(
            journey: journey,
            onTaskSelected: (taskId) => _selectTask(context, taskId),
            child: _buildTaskContent(context, journey.currentTaskId),
          ),
          navigation: _buildNavigation(context, state, journey),
        );
      },
    );
  }

  void _handleStateSideEffects(BuildContext context, WizardState state) {
    if (state.status == WizardStatus.error || state.errorMessage != null) {
      _pendingExitDestination = null;
    }
    if (state.successMessage == 'configured' && state.twinId != null) {
      _pendingExitDestination = null;
      ref.invalidate(twinsProvider);
      context.go('/twins/${state.twinId}/overview');
      return;
    }
    final exitDestination = _pendingExitDestination;
    final exitSaveCompleted =
        exitDestination != null &&
        state.status == WizardStatus.ready &&
        state.errorMessage == null &&
        !state.hasUnsavedChanges;
    if (exitSaveCompleted) {
      _pendingExitDestination = null;
      unawaited(_executeExit(context, exitDestination));
      return;
    }

    if (state.successMessage != 'Draft saved!') return;

    _notificationTimer?.cancel();
    _notificationTimer = Timer(const Duration(seconds: 3), () {
      if (!mounted) return;
      final bloc = context.read<WizardBloc>();
      if (bloc.state.successMessage == 'Draft saved!') {
        bloc.add(const WizardClearNotifications());
      }
    });
  }

  void _synchronizeCurrentTask(
    BuildContext context,
    ConfigurationJourney journey,
  ) {
    if (_currentTaskId == journey.currentTaskId) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _currentTaskId == journey.currentTaskId) return;
      _selectTask(context, journey.currentTaskId);
    });
  }

  ConfigurationNavigationBar _buildNavigation(
    BuildContext context,
    WizardState state,
    ConfigurationJourney journey,
  ) {
    final bloc = context.read<WizardBloc>();
    final isSaving = state.status == WizardStatus.saving;
    final commandInProgress = _commandInProgress(state);
    final isFinish =
        journey.currentTaskId == ConfigurationTaskId.validationAndPreflight;
    final nextTask = journey.nextNavigableTaskId;
    final canFinish = state.canModify && state.isConfigurationReadyForFinish;
    final forwardDisabledReason = isFinish
        ? !state.canModify
              ? 'Cannot modify a deployed twin'
              : !state.isConfigurationReadyForFinish
              ? 'Complete and validate all required fields before finishing'
              : ''
        : nextTask == null
        ? 'No next task is available'
        : '';

    return ConfigurationNavigationBar(
      backLabel: journey.previousNavigableTaskId == null ? 'Exit' : 'Back',
      backDisabledReason: commandInProgress
          ? 'Wait for the current command to finish'
          : '',
      onBack: commandInProgress
          ? null
          : () => _handleTaskBack(context, state, journey),
      showCalculation:
          journey.currentTaskId == ConfigurationTaskId.calculateAlternatives,
      isCalculating: state.isCalculating,
      calculationDisabledReason: _calculationDisabledReason(state),
      onCalculate: !commandInProgress && state.canRequestCalculation
          ? () => bloc.add(const WizardCalculateRequested())
          : null,
      isSaving: isSaving,
      hasUnsavedChanges: state.hasUnsavedChanges,
      saveDisabledReason: commandInProgress
          ? 'Wait for the current command to finish'
          : !state.canModify
          ? 'Cannot modify a deployed twin'
          : '',
      onSave: commandInProgress || !state.canModify
          ? null
          : () => _handleSaveDraft(context, state),
      showFinish: isFinish,
      forwardDisabledReason: commandInProgress
          ? 'Wait for the current command to finish'
          : forwardDisabledReason,
      onForward: isFinish
          ? canFinish && !commandInProgress
                ? () => _handleFinishConfiguration(context, bloc, state)
                : null
          : nextTask == null || commandInProgress
          ? null
          : () => _selectTask(context, nextTask),
    );
  }

  String _calculationDisabledReason(WizardState state) {
    if (state.status == WizardStatus.saving) return 'Save in progress';
    if (state.isCalculating) return 'Calculation in progress';
    if (state.isPricingHealthLoading) return 'Checking pricing readiness';
    if (state.pricingHealthError != null) {
      return 'Retry pricing readiness before calculating';
    }
    if (!state.pricingCanCalculate) {
      final providers = state.pricingBlockingProviders
          .map((provider) => provider.toUpperCase())
          .join(', ');
      return providers.isEmpty
          ? 'Pricing readiness is unavailable'
          : 'Pricing unavailable for $providers';
    }
    if (!state.isCalcFormValid) return 'Fix form errors before calculating';
    if (state.calcParams == null) return 'Configure parameters first';
    return '';
  }

  void _handleFinishConfiguration(
    BuildContext context,
    WizardBloc bloc,
    WizardState state,
  ) {
    final unconfigured = state.unconfiguredProviders;
    if (unconfigured.isNotEmpty) {
      ConfigurationWorkspaceDialogs.showUnconfiguredProviders(
        context,
        unconfigured,
      );
      return;
    }
    bloc.add(const WizardFinish());
  }

  Widget _buildTaskContent(BuildContext context, ConfigurationTaskId taskId) {
    return switch (taskId) {
      ConfigurationTaskId.cloudAccess => const CloudAccessTask(),
      ConfigurationTaskId.scenarioAndCurrency ||
      ConfigurationTaskId.deviceTraffic ||
      ConfigurationTaskId.processing ||
      ConfigurationTaskId.retention ||
      ConfigurationTaskId.twinCapabilities => Step2Optimizer(taskId: taskId),
      ConfigurationTaskId.dataContracts ||
      ConfigurationTaskId.userLogic ||
      ConfigurationTaskId.twinAssets => Step3Deployer(taskId: taskId),
      ConfigurationTaskId.summary ||
      ConfigurationTaskId.readinessFindings ||
      ConfigurationTaskId.validationAndPreflight => ConfigurationReviewTask(
        taskId: taskId,
        onOpenTask: (target) => _selectTask(context, target),
      ),
      _ => switch (ConfigurationJourney.legacyStepFor(taskId)) {
        0 => const Step1Configuration(),
        1 => const Step2Optimizer(),
        2 => const Step3Deployer(),
        _ => const SizedBox.shrink(),
      },
    };
  }

  bool _commandInProgress(WizardState state) =>
      state.status == WizardStatus.loading ||
      state.status == WizardStatus.saving ||
      state.isCalculating;

  Future<void> _requestExit(
    BuildContext context,
    WizardState state,
    _WorkspaceExitDestination destination,
  ) async {
    if (_commandInProgress(state)) return;
    if (!state.hasUnsavedChanges && !state.step3Invalidated) {
      unawaited(_executeExit(context, destination));
      return;
    }

    final choice = state.step3Invalidated
        ? await ConfigurationWorkspaceDialogs.showInvalidatedExit(context)
        : await ConfigurationWorkspaceDialogs.showUnsavedExit(context);
    if (!context.mounted) return;
    switch (choice) {
      case WorkspaceExitChoice.discard:
        unawaited(_executeExit(context, destination));
      case WorkspaceExitChoice.save:
        _pendingExitDestination = destination;
        context.read<WizardBloc>().add(
          state.step3Invalidated
              ? const WizardProceedAndSave()
              : const WizardSaveDraft(),
        );
      case null:
        return;
    }
  }

  Future<WorkspaceInvalidationChoice?> _showInvalidationConfirmation(
    BuildContext context,
    WizardState state,
  ) {
    return ConfigurationWorkspaceDialogs.showInvalidationChoice(
      context,
      canRestore: state.savedCalcResult != null,
    );
  }

  Future<void> _handleSaveDraft(BuildContext context, WizardState state) async {
    if (!state.step3Invalidated) {
      context.read<WizardBloc>().add(const WizardSaveDraft());
      return;
    }

    final choice = await _showInvalidationConfirmation(context, state);
    if (!context.mounted) return;
    switch (choice) {
      case WorkspaceInvalidationChoice.proceed:
        context.read<WizardBloc>().add(const WizardProceedAndSave());
      case WorkspaceInvalidationChoice.restore:
        context.read<WizardBloc>().add(const WizardRestoreOldResults());
      case null:
        return;
    }
  }

  Future<void> _handleTaskBack(
    BuildContext context,
    WizardState state,
    ConfigurationJourney journey,
  ) async {
    final previous = journey.previousNavigableTaskId;
    if (previous == null) {
      await _requestExit(context, state, _WorkspaceExitDestination.dashboard);
      return;
    }
    await _selectTask(context, previous);
  }

  Future<void> _selectTask(
    BuildContext context,
    ConfigurationTaskId taskId,
  ) async {
    if (_currentTaskId == taskId) return;
    final bloc = context.read<WizardBloc>();
    final state = bloc.state;
    final targetStep = ConfigurationJourney.legacyStepFor(taskId);
    final isInitialSelection = _currentTaskId == null;

    if (!isInitialSelection &&
        state.step3Invalidated &&
        targetStep != state.currentStep) {
      final choice = await _showInvalidationConfirmation(context, state);
      if (!context.mounted) return;
      switch (choice) {
        case WorkspaceInvalidationChoice.proceed:
          bloc.add(const WizardClearInvalidation());
        case WorkspaceInvalidationChoice.restore:
          bloc.add(const WizardRestoreOldResults());
        case null:
          return;
      }
    }

    if (mounted) setState(() => _currentTaskId = taskId);
    bloc.add(WizardGoToStep(targetStep));
  }

  Future<void> _executeExit(
    BuildContext context,
    _WorkspaceExitDestination destination,
  ) async {
    ref.invalidate(twinsProvider);
    switch (destination) {
      case _WorkspaceExitDestination.dashboard:
        context.go('/dashboard');
      case _WorkspaceExitDestination.settings:
        context.go('/settings');
      case _WorkspaceExitDestination.logout:
        await ref.read(authProvider.notifier).logout();
        if (context.mounted) context.go('/login');
    }
  }
}

enum _WorkspaceExitDestination { dashboard, settings, logout }
