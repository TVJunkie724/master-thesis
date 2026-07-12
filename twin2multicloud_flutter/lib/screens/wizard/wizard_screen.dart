import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'step1_configuration.dart';
import 'step2_optimizer.dart';
import 'step3_deployer.dart';
import '../../bloc/wizard/wizard.dart';
import '../../providers/twins_provider.dart';
import '../../providers/theme_provider.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/branded_app_bar.dart';
import '../../widgets/selectable_scaffold.dart';
import '../../features/configuration_workspace/domain/configuration_journey.dart';
import '../../features/configuration_workspace/presentation/cloud_access_task.dart';
import '../../features/configuration_workspace/presentation/configuration_workspace_shell.dart';

/// Wizard screen using BLoC pattern for state management
///
/// This widget provides the BlocProvider wrapper and delegates to WizardView.
class WizardScreen extends ConsumerWidget {
  final String? twinId; // null for new, set for edit

  const WizardScreen({super.key, this.twinId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(apiServiceProvider);

    return BlocProvider(
      create: (context) {
        final bloc = WizardBloc(api: api);
        // Initialize based on whether editing or creating
        if (twinId != null) {
          bloc.add(WizardInitEdit(twinId!));
        } else {
          bloc.add(const WizardInitCreate());
        }
        return bloc;
      },
      child: WizardView(twinId: twinId),
    );
  }
}

/// Main wizard view that consumes BLoC state
class WizardView extends ConsumerStatefulWidget {
  final String? twinId;

  const WizardView({super.key, this.twinId});

  @override
  ConsumerState<WizardView> createState() => _WizardViewState();
}

class _WizardViewState extends ConsumerState<WizardView> {
  ConfigurationTaskId? _currentTaskId;

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<WizardBloc, WizardState>(
      listenWhen: (prev, curr) =>
          prev.status != curr.status ||
          prev.successMessage != curr.successMessage,
      listener: (context, state) {
        // Handle navigation on finish - navigate to overview page
        if (state.successMessage == 'configured' && state.twinId != null) {
          ref.invalidate(twinsProvider);
          context.go('/twins/${state.twinId}/overview');
        }
        // Auto-dismiss success messages after 3 seconds
        else if (state.successMessage == 'Draft saved!') {
          Future.delayed(const Duration(seconds: 3), () {
            if (context.mounted) {
              context.read<WizardBloc>().add(const WizardClearNotifications());
            }
          });
        }
      },
      builder: (context, state) {
        if (state.status == WizardStatus.loading) {
          return SelectableScaffold(
            appBar: _buildAppBar(context, state),
            body: const Center(child: CircularProgressIndicator()),
          );
        }

        final journey = ConfigurationJourney.fromWizardState(
          state,
          requestedTaskId: _currentTaskId,
        );
        if (_currentTaskId != journey.currentTaskId) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted || _currentTaskId == journey.currentTaskId) return;
            _selectTask(context, journey.currentTaskId);
          });
        }

        return SelectableScaffold(
          appBar: _buildAppBar(context, state),
          body: Column(
            children: [
              // Header area with subtle shadow for visual separation
              Container(
                decoration: BoxDecoration(
                  color: Theme.of(context).scaffoldBackgroundColor,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.08),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Column(
                  children: [_buildHeader(context, state, journey)],
                ),
              ),
              _buildAlertBanners(context, state),
              Expanded(
                child: ConfigurationWorkspaceShell(
                  journey: journey,
                  onTaskSelected: (taskId) => _selectTask(context, taskId),
                  child: _buildTaskContent(journey.currentTaskId),
                ),
              ),
              _buildNavigationBar(context, state, journey),
            ],
          ),
        );
      },
    );
  }

  PreferredSizeWidget _buildAppBar(BuildContext context, WizardState state) {
    return BrandedAppBar(
      title: 'Twin2MultiCloud',
      actions: [
        IconButton(
          icon: Icon(
            ref.watch(themeProvider) == ThemeMode.dark
                ? Icons.light_mode
                : Icons.dark_mode,
          ),
          onPressed: () => ref.read(themeProvider.notifier).toggle(),
          tooltip: 'Toggle theme',
        ),
        const SizedBox(width: 8),
        PopupMenuButton<String>(
          offset: const Offset(0, 56),
          tooltip: 'Profile menu',
          onSelected: (value) {
            switch (value) {
              case 'settings':
                context.go('/settings');
                break;
              case 'logout':
                ref.read(authProvider.notifier).logout();
                context.go('/login');
                break;
            }
          },
          itemBuilder: (context) => [
            const PopupMenuItem(
              value: 'settings',
              child: Row(
                children: [
                  Icon(Icons.settings, size: 20),
                  SizedBox(width: 12),
                  Text('Settings'),
                ],
              ),
            ),
            const PopupMenuDivider(),
            PopupMenuItem(
              value: 'logout',
              child: Row(
                children: [
                  Icon(Icons.logout, size: 20, color: Colors.red),
                  const SizedBox(width: 12),
                  Text('Logout', style: TextStyle(color: Colors.red)),
                ],
              ),
            ),
          ],
          child: const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: CircleAvatar(child: Icon(Icons.person)),
          ),
        ),
        const SizedBox(width: 8),
      ],
    );
  }

  Widget _buildHeader(
    BuildContext context,
    WizardState state,
    ConfigurationJourney journey,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.close),
            onPressed: () => _showExitConfirmation(context, state),
            tooltip: 'Close',
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  state.mode == WizardMode.create
                      ? 'Create Digital Twin'
                      : 'Edit Digital Twin',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 2),
                Text(
                  '${journey.currentPhase.label} · ${journey.task(journey.currentTaskId).label}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildAlertBanners(BuildContext context, WizardState state) {
    if (state.errorMessage != null) {
      return _buildBanner(
        context,
        message: state.errorMessage!,
        color: Colors.red,
        icon: Icons.error,
        onDismiss: () =>
            context.read<WizardBloc>().add(const WizardDismissError()),
      );
    } else if (state.successMessage != null) {
      return _buildBanner(
        context,
        message: state.successMessage!,
        color: Colors.green,
        icon: Icons.check_circle,
        onDismiss: () =>
            context.read<WizardBloc>().add(const WizardClearNotifications()),
      );
    } else if (state.warningMessage != null) {
      return _buildBanner(
        context,
        message: state.warningMessage!,
        color: Colors.orange,
        icon: Icons.warning_amber_rounded,
        onDismiss: () =>
            context.read<WizardBloc>().add(const WizardClearNotifications()),
      );
    }
    return const SizedBox.shrink();
  }

  Widget _buildBanner(
    BuildContext context, {
    required String message,
    required MaterialColor color,
    required IconData icon,
    required VoidCallback onDismiss,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      decoration: BoxDecoration(
        color: color.shade50,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.08),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1000),
          child: Row(
            children: [
              Icon(icon, color: color.shade700),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  message,
                  style: TextStyle(
                    color: color.shade700,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              IconButton(
                icon: Icon(Icons.close, color: color.shade700, size: 20),
                onPressed: onDismiss,
                tooltip: 'Dismiss',
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildNavigationBar(
    BuildContext context,
    WizardState state,
    ConfigurationJourney journey,
  ) {
    final bloc = context.read<WizardBloc>();
    final isSaving = state.status == WizardStatus.saving;

    return Column(
      children: [
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1000),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 24),
                child: Row(
                  children: [
                    // Left: Back button
                    Expanded(
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: OutlinedButton.icon(
                          onPressed: () =>
                              _handleTaskBack(context, state, journey),
                          icon: const Icon(Icons.arrow_back),
                          label: Text(
                            journey.previousNavigableTaskId == null
                                ? 'Exit'
                                : 'Back',
                          ),
                        ),
                      ),
                    ),
                    // Center: Calculate button (only on Step 2)
                    if (journey.currentTaskId ==
                        ConfigurationTaskId.calculateAlternatives)
                      Tooltip(
                        message: _calculationDisabledReason(state),
                        child: ElevatedButton.icon(
                          onPressed: state.canRequestCalculation
                              ? () => bloc.add(const WizardCalculateRequested())
                              : null,
                          icon: state.isCalculating
                              ? const SizedBox(
                                  width: 22,
                                  height: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2.5,
                                    color: Colors.white,
                                  ),
                                )
                              : const Icon(Icons.calculate, size: 22),
                          label: Text(
                            state.isCalculating
                                ? 'CALCULATING...'
                                : 'CALCULATE',
                            style: const TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w800,
                              letterSpacing: 1.0,
                            ),
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor:
                                Theme.of(context).brightness == Brightness.dark
                                ? Colors.white
                                : Colors.grey.shade900,
                            foregroundColor:
                                Theme.of(context).brightness == Brightness.dark
                                ? Colors.grey.shade900
                                : Colors.white,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 32,
                              vertical: 18,
                            ),
                            elevation: 4,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(8),
                            ),
                          ),
                        ),
                      ),
                    // Right side buttons
                    Expanded(
                      child: Align(
                        alignment: Alignment.centerRight,
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            // Save button
                            Tooltip(
                              message: !state.canModify
                                  ? 'Cannot modify a deployed twin'
                                  : '',
                              child: OutlinedButton.icon(
                                onPressed: (isSaving || !state.canModify)
                                    ? null
                                    : () => _handleSaveDraft(context, state),
                                icon: Stack(
                                  clipBehavior: Clip.none,
                                  children: [
                                    isSaving
                                        ? const SizedBox(
                                            width: 18,
                                            height: 18,
                                            child: CircularProgressIndicator(
                                              strokeWidth: 2,
                                            ),
                                          )
                                        : const Icon(Icons.save),
                                    if (state.hasUnsavedChanges && !isSaving)
                                      Positioned(
                                        right: -4,
                                        top: -4,
                                        child: Container(
                                          width: 10,
                                          height: 10,
                                          decoration: const BoxDecoration(
                                            color: Colors.orange,
                                            shape: BoxShape.circle,
                                          ),
                                        ),
                                      ),
                                  ],
                                ),
                                label: const Text('Save'),
                              ),
                            ),
                            const SizedBox(width: 16),
                            if (journey.currentTaskId !=
                                ConfigurationTaskId.validationAndPreflight)
                              FilledButton.icon(
                                onPressed: journey.nextNavigableTaskId == null
                                    ? null
                                    : () => _selectTask(
                                        context,
                                        journey.nextNavigableTaskId!,
                                      ),
                                icon: const Icon(Icons.arrow_forward),
                                label: const Text('Continue'),
                              )
                            else
                              Tooltip(
                                message: !state.canModify
                                    ? 'Cannot modify a deployed twin'
                                    : !(state.isSection2Valid &&
                                          state.isSection3Valid)
                                    ? 'Complete and validate all required fields before finishing'
                                    : '',
                                child: ElevatedButton.icon(
                                  onPressed:
                                      (state.canModify &&
                                          state.isSection2Valid &&
                                          state.isSection3Valid)
                                      ? () => _handleFinishConfiguration(
                                          context,
                                          bloc,
                                          state,
                                        )
                                      : null,
                                  icon: const Icon(Icons.check_circle),
                                  label: const Text('Finish Configuration'),
                                  style: ElevatedButton.styleFrom(
                                    backgroundColor: Colors.green,
                                    foregroundColor: Colors.white,
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  String _calculationDisabledReason(WizardState state) {
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
      // Show warning dialog and stay on screen
      showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: const Icon(Icons.warning_amber, color: Colors.orange, size: 48),
          title: const Text('Unconfigured Providers'),
          content: Text(
            'The following providers are required by your selected architecture but do not have deployment access:\n\n'
            '${unconfigured.map((p) => '• $p').join('\n')}\n\n'
            'Open Cloud access and bind a valid deployment connection for each provider.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('OK'),
            ),
          ],
        ),
      );
    } else {
      // All providers configured, proceed to finish
      bloc.add(const WizardFinish());
    }
  }

  Widget _buildTaskContent(ConfigurationTaskId taskId) => switch (taskId) {
    ConfigurationTaskId.cloudAccess => const CloudAccessTask(),
    ConfigurationTaskId.scenarioAndCurrency ||
    ConfigurationTaskId.deviceTraffic ||
    ConfigurationTaskId.processing ||
    ConfigurationTaskId.retention ||
    ConfigurationTaskId.twinCapabilities => Step2Optimizer(taskId: taskId),
    _ => switch (ConfigurationJourney.legacyStepFor(taskId)) {
      0 => const Step1Configuration(),
      1 => const Step2Optimizer(),
      2 => const Step3Deployer(),
      _ => const SizedBox.shrink(),
    },
  };

  Future<void> _showExitConfirmation(
    BuildContext context,
    WizardState state,
  ) async {
    // If no unsaved changes and no invalidation, just exit
    if (!state.hasUnsavedChanges && !state.step3Invalidated) {
      ref.invalidate(twinsProvider);
      context.go('/dashboard');
      return;
    }

    // Different dialog for invalidation case
    if (state.step3Invalidated) {
      final result = await showDialog<String>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Row(
            children: [
              Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 28),
              SizedBox(width: 12),
              Text('Configuration Changed'),
            ],
          ),
          content: const Text(
            'Your new calculation affects Step 3.\n\n'
            'If you save now, Step 3 configuration will be reset to match the new calculation.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, 'cancel'),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(ctx, 'discard'),
              child: const Text('Leave Without Saving'),
            ),
            ElevatedButton(
              onPressed: () => Navigator.pop(ctx, 'save'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.orange,
                foregroundColor: Colors.white,
              ),
              child: const Text('Save & Leave'),
            ),
          ],
        ),
      );

      if (!context.mounted) return;

      switch (result) {
        case 'discard':
          ref.invalidate(twinsProvider);
          context.go('/dashboard');
          break;
        case 'save':
          // Clear invalidation, save, then navigate
          context.read<WizardBloc>().add(const WizardProceedAndSave());
          // Wait for save then navigate
          Future.delayed(const Duration(milliseconds: 500), () {
            if (context.mounted) {
              ref.invalidate(twinsProvider);
              context.go('/dashboard');
            }
          });
          break;
        case 'cancel':
        default:
          break;
      }
      return;
    }

    // Normal unsaved changes dialog
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Leave Wizard?'),
        content: const Text(
          'You have unsaved changes. What would you like to do?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, 'cancel'),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, 'discard'),
            child: const Text('Discard Changes'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, 'save'),
            child: const Text('Save'),
          ),
        ],
      ),
    );

    if (!context.mounted) return;

    switch (result) {
      case 'discard':
        ref.invalidate(twinsProvider);
        context.go('/dashboard');
        break;
      case 'save':
        context.read<WizardBloc>().add(const WizardSaveDraft());
        break;
      case 'cancel':
      default:
        break;
    }
  }

  /// Show confirmation dialog when Step 3 will be invalidated
  /// Returns: 'proceed' (keep new results), 'restore' (keep old data), or null (cancel)
  Future<String?> _showInvalidationConfirmation(
    BuildContext context,
    WizardState state,
  ) async {
    final canDiscard = state.savedCalcResult != null;

    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 28),
            SizedBox(width: 12),
            Text('Configuration Changed'),
          ],
        ),
        content: Text(
          'Your new calculation has different parameters that may affect Step 3 configuration.\n\n'
          'What would you like to do?'
          '${!canDiscard ? '\n\n(Discard not available - no saved version exists)' : ''}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, null), // Cancel
            child: const Text('Cancel'),
          ),
          OutlinedButton(
            onPressed: canDiscard ? () => Navigator.pop(ctx, 'restore') : null,
            child: const Text('Discard Changes'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, 'proceed'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange,
              foregroundColor: Colors.white,
            ),
            child: const Text('Keep New Results'),
          ),
        ],
      ),
    );
  }

  /// Handle Save Draft with potential invalidation confirmation
  Future<void> _handleSaveDraft(BuildContext context, WizardState state) async {
    if (state.step3Invalidated) {
      final result = await _showInvalidationConfirmation(context, state);
      if (!context.mounted) return;

      switch (result) {
        case 'proceed':
          context.read<WizardBloc>().add(const WizardProceedAndSave());
          break;
        case 'restore':
          context.read<WizardBloc>().add(const WizardRestoreOldResults());
          break;
        default:
          // Cancel - do nothing
          break;
      }
    } else {
      context.read<WizardBloc>().add(const WizardSaveDraft());
    }
  }

  Future<void> _handleTaskBack(
    BuildContext context,
    WizardState state,
    ConfigurationJourney journey,
  ) async {
    final previous = journey.previousNavigableTaskId;
    if (previous == null) {
      await _showExitConfirmation(context, state);
      return;
    }

    await _selectTask(context, previous);
  }

  Future<void> _selectTask(
    BuildContext context,
    ConfigurationTaskId taskId,
  ) async {
    if (_currentTaskId == taskId) return;

    final state = context.read<WizardBloc>().state;
    final targetStep = ConfigurationJourney.legacyStepFor(taskId);
    final isInitialSelection = _currentTaskId == null;

    if (!isInitialSelection &&
        state.step3Invalidated &&
        targetStep != state.currentStep) {
      final result = await _showInvalidationConfirmation(context, state);
      if (!context.mounted) return;

      switch (result) {
        case 'proceed':
          context.read<WizardBloc>().add(const WizardClearInvalidation());
          break;
        case 'restore':
          context.read<WizardBloc>().add(const WizardRestoreOldResults());
          break;
        default:
          return;
      }
    }

    if (mounted) setState(() => _currentTaskId = taskId);
    context.read<WizardBloc>().add(WizardGoToStep(targetStep));
  }
}
