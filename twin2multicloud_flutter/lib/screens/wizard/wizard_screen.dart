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
  // Note: Name error handling will be via BLoC state in future
  
  @override
  Widget build(BuildContext context) {
    return BlocConsumer<WizardBloc, WizardState>(
      listenWhen: (prev, curr) => 
        prev.status != curr.status ||
        prev.successMessage != curr.successMessage,
      listener: (context, state) {
        // Handle navigation on finish
        if (state.successMessage == 'Configuration complete!') {
          ref.invalidate(twinsProvider);
          context.go('/dashboard');
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
          return Scaffold(
            appBar: _buildAppBar(context),
            body: const Center(child: CircularProgressIndicator()),
          );
        }
        
        return Scaffold(
          appBar: _buildAppBar(context),
          body: Column(
            children: [
              // Screen header with title
              _buildHeader(context, state),
              // Step indicator
              _buildStepIndicator(context, state),
              // Navigation bar
              _buildNavigationBar(context, state),
              const Divider(height: 1),
              // Alert banners
              _buildAlertBanners(context, state),
              // Step content
              Expanded(child: _buildStepContent(context, state)),
            ],
          ),
        );
      },
    );
  }
  
  PreferredSizeWidget _buildAppBar(BuildContext context) {
    return AppBar(
      title: const Text('Twin2MultiCloud'),
      automaticallyImplyLeading: false,
      backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
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
        const CircleAvatar(child: Icon(Icons.person)),
        const SizedBox(width: 16),
      ],
    );
  }
  
  Widget _buildHeader(BuildContext context, WizardState state) {
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
          Text(
            state.mode == WizardMode.create 
                ? 'Create Digital Twin' 
                : 'Edit Digital Twin',
            style: Theme.of(context).textTheme.headlineSmall,
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
        onDismiss: () => context.read<WizardBloc>().add(const WizardDismissError()),
      );
    } else if (state.successMessage != null) {
      return _buildBanner(
        context,
        message: state.successMessage!,
        color: Colors.green,
        icon: Icons.check_circle,
        onDismiss: () => context.read<WizardBloc>().add(const WizardClearNotifications()),
      );
    } else if (state.warningMessage != null) {
      return _buildBanner(
        context,
        message: state.warningMessage!,
        color: Colors.orange,
        icon: Icons.warning_amber_rounded,
        onDismiss: () => context.read<WizardBloc>().add(const WizardClearNotifications()),
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
      color: color.shade50,
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
  
  Widget _buildNavigationBar(BuildContext context, WizardState state) {
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
                          onPressed: state.currentStep == 0 
                              ? () => _showExitConfirmation(context, state)
                              : () => bloc.add(const WizardPreviousStep()),
                          icon: const Icon(Icons.arrow_back),
                          label: Text(state.currentStep == 0 ? 'Exit' : 'Back'),
                        ),
                      ),
                    ),
                    // Center: Calculate button (only on Step 2)
                    if (state.currentStep == 1)
                      ElevatedButton.icon(
                        onPressed: (state.calcParams != null && !state.isCalculating)
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
                          state.isCalculating ? 'CALCULATING...' : 'CALCULATE',
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.0,
                          ),
                        ),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Theme.of(context).brightness == Brightness.dark 
                              ? Colors.white 
                              : Colors.grey.shade900,
                          foregroundColor: Theme.of(context).brightness == Brightness.dark 
                              ? Colors.grey.shade900 
                              : Colors.white,
                          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 18),
                          elevation: 4,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8),
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
                            // Save Draft button
                            OutlinedButton.icon(
                              onPressed: isSaving 
                                  ? null 
                                  : () => bloc.add(const WizardSaveDraft()),
                              icon: Stack(
                                clipBehavior: Clip.none,
                                children: [
                                  isSaving 
                                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
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
                              label: const Text('Save Draft'),
                            ),
                            const SizedBox(width: 16),
                            // Next/Finish button
                            if (state.currentStep < 2)
                              FilledButton.icon(
                                onPressed: _canProceedToNextStep(state) 
                                    ? () => bloc.add(const WizardNextStep())
                                    : null,
                                icon: const Icon(Icons.arrow_forward),
                                label: const Text('Next Step'),
                              )
                            else
                              ElevatedButton.icon(
                                onPressed: () => bloc.add(const WizardFinish()),
                                icon: const Icon(Icons.check_circle),
                                label: const Text('Finish Configuration'),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.green,
                                  foregroundColor: Colors.white,
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
  
  bool _canProceedToNextStep(WizardState state) {
    switch (state.currentStep) {
      case 0:
        return state.canProceedToStep2;
      case 1:
        return state.canProceedToStep3;
      default:
        return true;
    }
  }
  
  Widget _buildStepIndicator(BuildContext context, WizardState state) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _buildStep(context, state, 0, '1. Configuration', Icons.settings),
              _buildConnector(state, 0),
              _buildStep(context, state, 1, '2. Optimizer', Icons.analytics),
              _buildConnector(state, 1),
              _buildStep(context, state, 2, '3. Deployer', Icons.cloud_upload),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primaryContainer.withAlpha(100),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            'Step ${state.currentStep + 1} / 3',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: Theme.of(context).colorScheme.primary,
            ),
          ),
        ),
        const SizedBox(height: 8),
      ],
    );
  }
  
  Widget _buildStep(BuildContext context, WizardState state, int index, String label, IconData icon) {
    final isActive = state.currentStep == index;
    final isCompleted = state.highestStepReached > index;
    final bloc = context.read<WizardBloc>();
    
    return InkWell(
      onTap: () {
        if (index <= state.highestStepReached) {
          bloc.add(WizardGoToStep(index));
        }
      },
      borderRadius: BorderRadius.circular(20),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Column(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isCompleted 
                  ? Colors.green 
                  : isActive 
                    ? Theme.of(context).colorScheme.primary 
                    : (index <= state.highestStepReached)
                      ? Theme.of(context).colorScheme.primary.withAlpha(150)
                      : Colors.grey.shade300,
              ),
              child: Icon(
                isCompleted ? Icons.check : icon,
                color: Colors.white,
                size: 20,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
                color: index <= state.highestStepReached 
                  ? null 
                  : Colors.grey.shade500,
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildConnector(WizardState state, int afterIndex) {
    final isActive = state.highestStepReached > afterIndex;
    return Container(
      width: 60,
      height: 2,
      margin: const EdgeInsets.only(bottom: 20),
      color: isActive ? Colors.green : Colors.grey.shade300,
    );
  }
  
  Widget _buildStepContent(BuildContext context, WizardState state) {
    switch (state.currentStep) {
      case 0:
        return const Step1Configuration();
      case 1:
        return const Step2Optimizer();
      case 2:
        return const Step3Deployer();
      default:
        return const SizedBox();
    }
  }
  
  Future<void> _showExitConfirmation(BuildContext context, WizardState state) async {
    // If no unsaved changes, just exit
    if (!state.hasUnsavedChanges) {
      ref.invalidate(twinsProvider);
      context.go('/dashboard');
      return;
    }
    
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Leave Wizard?'),
        content: const Text(
          'You have unsaved changes. What would you like to do?'
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
            child: const Text('Save Draft'),
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
        // The BLoC will handle the save and show success message
        // We could listen for success and then navigate, but for now keep it simple
        break;
      case 'cancel':
      default:
        break;
    }
  }
}
