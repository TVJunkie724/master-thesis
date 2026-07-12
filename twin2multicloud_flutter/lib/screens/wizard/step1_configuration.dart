import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../bloc/wizard/wizard.dart';
import '../../theme/spacing.dart';

class Step1Configuration extends StatefulWidget {
  const Step1Configuration({super.key});

  @override
  State<Step1Configuration> createState() => _Step1ConfigurationState();
}

class _Step1ConfigurationState extends State<Step1Configuration> {
  final _nameController = TextEditingController();
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      final state = context.read<WizardBloc>().state;
      _nameController.text = state.twinName ?? '';
      _initialized = true;
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<WizardBloc, WizardState>(
      listenWhen: (prev, curr) => prev.twinName != curr.twinName,
      listener: (context, state) {
        if (_nameController.text != (state.twinName ?? '')) {
          _nameController.text = state.twinName ?? '';
        }
      },
      child: BlocBuilder<WizardBloc, WizardState>(
        builder: (context, state) {
          final bloc = context.read<WizardBloc>();

          return SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(
                  maxWidth: AppSpacing.maxContentWidthMedium,
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Digital Twin Name',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    TextField(
                      controller: _nameController,
                      decoration: const InputDecoration(
                        hintText: 'e.g., Smart Home IoT',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (value) {
                        bloc.add(WizardTwinNameChanged(value));
                      },
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Wrap(
                      spacing: AppSpacing.md,
                      runSpacing: AppSpacing.sm,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                          'Mode:',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        ChoiceChip(
                          label: const Text('Production'),
                          selected: !state.debugMode,
                          onSelected: (_) {
                            bloc.add(const WizardDebugModeChanged(false));
                          },
                        ),
                        ChoiceChip(
                          label: const Text('Debug'),
                          selected: state.debugMode,
                          onSelected: (_) {
                            bloc.add(const WizardDebugModeChanged(true));
                          },
                        ),
                      ],
                    ),
                    if (state.twinName?.trim().isEmpty ?? true) ...[
                      const SizedBox(height: AppSpacing.md),
                      Text(
                        'Give the twin a name to continue.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.outline,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
