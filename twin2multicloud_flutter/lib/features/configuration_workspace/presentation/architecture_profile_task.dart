import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../bloc/wizard/wizard.dart';
import '../../../models/architecture_profile.dart';
import '../../../theme/spacing.dart';
import '../domain/configuration_journey.dart';
import 'architecture_profile_change_dialog.dart';
import 'architecture_profile_choice.dart';
import 'logical_profile_flow.dart';

class ArchitectureProfileTask extends StatelessWidget {
  final ConfigurationTaskId taskId;
  final ValueChanged<ConfigurationTaskId> onOpenTask;

  const ArchitectureProfileTask({
    super.key,
    required this.taskId,
    required this.onOpenTask,
  });

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<WizardBloc, WizardState>(
      listenWhen: (previous, current) =>
          previous.architectureChangePhase != current.architectureChangePhase,
      listener: (context, state) {
        if (state.architectureChangePhase ==
            ArchitectureChangePhase.awaitingConfirmation) {
          unawaited(
            showDialog<void>(
              context: context,
              barrierDismissible: false,
              builder: (_) => BlocProvider.value(
                value: context.read<WizardBloc>(),
                child: const ArchitectureProfileChangeDialog(),
              ),
            ),
          );
        }
      },
      builder: (context, state) {
        _acknowledgeUnderstandingIfReady(context, state);
        return SingleChildScrollView(
          key: ValueKey(taskId),
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: AppSpacing.maxContentWidthLarge,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    taskId == ConfigurationTaskId.selectProfile
                        ? 'Architecture profile'
                        : 'Understand architecture',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Choose one reviewed functional architecture. Provider placement is optimized later within that profile.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  if (state.hasHistoricalArchitectureSelection)
                    _HistoricalSelectionBanner(
                      selection: state.architectureSelection!,
                    ),
                  _CatalogBody(
                    state: state,
                    showSelection: taskId == ConfigurationTaskId.selectProfile,
                    onOpenDetails: () =>
                        onOpenTask(ConfigurationTaskId.understandArchitecture),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  void _acknowledgeUnderstandingIfReady(
    BuildContext context,
    WizardState state,
  ) {
    if (taskId != ConfigurationTaskId.understandArchitecture ||
        state.architectureDetailPhase != ArchitectureDetailPhase.ready ||
        state.architectureDetailAcknowledged) {
      return;
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!context.mounted) return;
      final bloc = context.read<WizardBloc>();
      if (bloc.state.architectureDetailPhase == ArchitectureDetailPhase.ready &&
          !bloc.state.architectureDetailAcknowledged) {
        bloc.add(const WizardArchitectureUnderstandingAcknowledged());
      }
    });
  }
}

class _CatalogBody extends StatelessWidget {
  final WizardState state;
  final bool showSelection;
  final VoidCallback onOpenDetails;

  const _CatalogBody({
    required this.state,
    required this.showSelection,
    required this.onOpenDetails,
  });

  @override
  Widget build(BuildContext context) {
    final bloc = context.read<WizardBloc>();
    switch (state.architectureCatalogPhase) {
      case ArchitectureCatalogPhase.initial:
      case ArchitectureCatalogPhase.loading:
        if (state.architectureProfiles.isEmpty) {
          return const _InlineState(
            icon: Icons.hourglass_top,
            title: 'Loading architecture profiles',
            message: 'Reading the active reviewed catalog from Management.',
            progress: true,
          );
        }
        break;
      case ArchitectureCatalogPhase.empty:
        return _InlineState(
          icon: Icons.inventory_2_outlined,
          title: 'No active architecture profile is available',
          message:
              'This implementation phase keeps the historical baseline read-only. Five-layer v2 becomes selectable only after its complete runtime profile is published.',
          actionLabel: 'Retry',
          onAction: () =>
              bloc.add(const WizardArchitectureProfilesLoadRequested()),
        );
      case ArchitectureCatalogPhase.error:
        return _InlineState(
          icon: Icons.error_outline,
          title: 'Architecture profiles could not be loaded',
          message:
              state.architectureCatalogError ?? 'Retry the catalog request.',
          actionLabel: 'Retry',
          onAction: () =>
              bloc.add(const WizardArchitectureProfilesLoadRequested()),
        );
      case ArchitectureCatalogPhase.ready:
        break;
    }

    final selected = state.architectureSelection?.profileRef;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (state.architectureCatalogPhase == ArchitectureCatalogPhase.loading)
          const LinearProgressIndicator(),
        if (showSelection)
          for (final profile in state.architectureProfiles)
            ArchitectureProfileChoice(
              profile: profile,
              selected: selected != null && _sameRef(profile.ref, selected),
              disabled:
                  state.architectureChangePhase ==
                      ArchitectureChangePhase.previewing ||
                  state.architectureChangePhase ==
                      ArchitectureChangePhase.submitting,
              onSelect: () =>
                  bloc.add(WizardArchitectureProfileSelected(profile.ref)),
              onExpand: selected != null && _sameRef(profile.ref, selected)
                  ? onOpenDetails
                  : null,
            ),
        if (state.architectureChangePhase == ArchitectureChangePhase.previewing)
          const LinearProgressIndicator(),
        if (state.architectureChangePhase == ArchitectureChangePhase.conflict ||
            state.architectureChangePhase == ArchitectureChangePhase.error)
          _InlineState(
            icon: Icons.sync_problem_outlined,
            title:
                state.architectureChangePhase ==
                    ArchitectureChangePhase.conflict
                ? 'Architecture selection changed'
                : 'Profile change failed',
            message:
                state.architectureChangeError ?? 'Review the selection again.',
          ),
        const SizedBox(height: AppSpacing.lg),
        _ProfileDetailBody(state: state),
      ],
    );
  }
}

class _ProfileDetailBody extends StatelessWidget {
  final WizardState state;

  const _ProfileDetailBody({required this.state});

  @override
  Widget build(BuildContext context) {
    switch (state.architectureDetailPhase) {
      case ArchitectureDetailPhase.idle:
        return const _InlineState(
          icon: Icons.account_tree_outlined,
          title: 'Select a profile to inspect its architecture',
          message:
              'The logical flow is profile-owned and does not expose infrastructure editing controls.',
        );
      case ArchitectureDetailPhase.loading:
        final detail = state.architectureProfileDetail;
        if (detail != null) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const LinearProgressIndicator(),
              const SizedBox(height: AppSpacing.sm),
              _ProfileDetail(detail: detail),
            ],
          );
        }
        return const _InlineState(
          icon: Icons.hourglass_top,
          title: 'Loading architecture details',
          message: 'Validating the versioned logical graph.',
          progress: true,
        );
      case ArchitectureDetailPhase.error:
        final selected = state.selectedArchitectureSummary;
        return _InlineState(
          icon: Icons.error_outline,
          title: 'Architecture detail could not be loaded',
          message: state.architectureDetailError ?? 'Retry the detail request.',
          actionLabel: selected == null ? null : 'Retry',
          onAction: selected == null
              ? null
              : () => context.read<WizardBloc>().add(
                  WizardArchitectureProfileDetailLoadRequested(selected.ref),
                ),
        );
      case ArchitectureDetailPhase.ready:
        return _ProfileDetail(detail: state.architectureProfileDetail!);
    }
  }
}

class _ProfileDetail extends StatelessWidget {
  final ArchitectureProfileDetail detail;

  const _ProfileDetail({required this.detail});

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Wrap(
        spacing: AppSpacing.sm,
        runSpacing: AppSpacing.sm,
        children: [
          Chip(
            avatar: const Icon(Icons.check_circle_outline),
            label: Text(
              '${detail.summary.capabilityIds.length} required capabilities complete',
            ),
          ),
          Chip(
            label: Text(
              '${detail.logicalComponents.length} logical components',
            ),
          ),
          Chip(label: Text('${detail.logicalEdges.length} connections')),
        ],
      ),
      const SizedBox(height: AppSpacing.lg),
      Text('Logical flow', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: AppSpacing.sm),
      LogicalProfileFlow(detail: detail),
      const SizedBox(height: AppSpacing.lg),
      Text('Responsibilities', style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: AppSpacing.sm),
      for (final responsibility in detail.summary.responsibilities)
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(
            responsibility.required
                ? Icons.check_circle_outline
                : Icons.add_circle_outline,
          ),
          title: Text(responsibility.displayName),
          subtitle: Text(
            '${responsibility.capabilityIds.length} capabilities · '
            '${responsibility.workloadFieldIds.length} workload fields',
          ),
        ),
      ExpansionTile(
        tilePadding: EdgeInsets.zero,
        title: const Text('Technical details'),
        children: [
          SelectableText(
            '${detail.summary.profileId}@${detail.summary.profileVersion}\n'
            '${detail.summary.profileDigest}',
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final provider in [
            ...detail.summary.availableProviders,
            ...detail.summary.unsupportedProviders,
          ])
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              leading: Icon(
                provider.supported ? Icons.cloud_done : Icons.cloud_off,
              ),
              title: Text(provider.provider.label),
              subtitle: Text(
                provider.supported
                    ? 'Reviewed provider profile available'
                    : provider.reasonCodes.join(', '),
              ),
            ),
        ],
      ),
    ],
  );
}

class _HistoricalSelectionBanner extends StatelessWidget {
  final TwinArchitectureSelection selection;

  const _HistoricalSelectionBanner({required this.selection});

  @override
  Widget build(BuildContext context) => Card(
    color: Theme.of(context).colorScheme.surfaceContainerHighest,
    child: ListTile(
      leading: const Icon(Icons.history),
      title: const Text('Historical architecture (read-only)'),
      subtitle: Text(
        '${selection.profileRef.id}@${selection.profileRef.version} remains available for audit, verification, and destroy only.',
      ),
    ),
  );
}

class _InlineState extends StatelessWidget {
  final IconData icon;
  final String title;
  final String message;
  final bool progress;
  final String? actionLabel;
  final VoidCallback? onAction;

  const _InlineState({
    required this.icon,
    required this.title,
    required this.message,
    this.progress = false,
    this.actionLabel,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        children: [
          Icon(icon, size: AppSpacing.xl),
          const SizedBox(height: AppSpacing.sm),
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: AppSpacing.xs),
          Text(message, textAlign: TextAlign.center),
          if (progress) ...[
            const SizedBox(height: AppSpacing.md),
            const LinearProgressIndicator(),
          ],
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: AppSpacing.md),
            OutlinedButton(onPressed: onAction, child: Text(actionLabel!)),
          ],
        ],
      ),
    ),
  );
}

bool _sameRef(
  PinnedArchitectureReference left,
  PinnedArchitectureReference right,
) =>
    left.id == right.id &&
    left.version == right.version &&
    left.digest == right.digest;
