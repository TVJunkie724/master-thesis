import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../bloc/wizard/wizard.dart';
import '../../../models/deployer_config.dart';
import '../../../theme/spacing.dart';
import '../domain/configuration_journey.dart';

class ConfigurationReviewTask extends StatelessWidget {
  final ConfigurationTaskId taskId;
  final ValueChanged<ConfigurationTaskId> onOpenTask;

  const ConfigurationReviewTask({
    super.key,
    required this.taskId,
    required this.onOpenTask,
  });

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<WizardBloc, WizardState>(
      builder: (context, state) => SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppSpacing.maxContentWidthMedium,
            ),
            child: switch (taskId) {
              ConfigurationTaskId.summary => _Summary(state: state),
              ConfigurationTaskId.readinessFindings => _Findings(
                state: state,
                onOpenTask: onOpenTask,
              ),
              ConfigurationTaskId.validationAndPreflight => _Validation(
                state: state,
                onOpenFindings: () =>
                    onOpenTask(ConfigurationTaskId.readinessFindings),
              ),
              _ => const SizedBox.shrink(),
            },
          ),
        ),
      ),
    );
  }
}

class _Summary extends StatelessWidget {
  final WizardState state;

  const _Summary({required this.state});

  @override
  Widget build(BuildContext context) {
    final params = state.calcParams;
    final providers = state.layerProviders.entries
        .map((entry) => '${entry.key}: ${entry.value}')
        .join(' · ');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Configuration summary',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: AppSpacing.lg),
        _SummarySection(
          title: 'Twin',
          rows: {
            'Name': state.twinName ?? 'Not set',
            'Mode': state.debugMode ? 'Debug' : 'Production',
          },
        ),
        _SummarySection(
          title: 'Workload',
          rows: {
            'Devices': '${params?.numberOfDevices ?? 0}',
            'Message interval':
                '${params?.deviceSendingIntervalInMinutes ?? 0} minutes',
            'Storage retention': params == null
                ? 'Not set'
                : '${params.hotStorageDurationInMonths} / ${params.coolStorageDurationInMonths} / ${params.archiveStorageDurationInMonths} months',
            '3D representation': params?.needs3DModel == true
                ? 'Required'
                : 'Not required',
          },
        ),
        _SummarySection(
          title: 'Architecture',
          rows: {
            'Provider path': providers.isEmpty ? 'Not calculated' : providers,
            'Monthly estimate': state.calcResult == null
                ? 'Not calculated'
                : '${state.calcResult!.totalCost.toStringAsFixed(2)} ${params?.currency ?? 'USD'}',
          },
        ),
        _SummarySection(
          title: 'Deployment readiness',
          rows: {
            for (final section in state.deployerReadiness.sections)
              section.label: section.ready ? 'Ready' : 'Needs attention',
            'Cloud access': state.unconfiguredProviders.isEmpty
                ? 'Ready'
                : 'Missing ${state.unconfiguredProviders.join(', ')}',
          },
        ),
      ],
    );
  }
}

class _SummarySection extends StatelessWidget {
  final String title;
  final Map<String, String> rows;

  const _SummarySection({required this.title, required this.rows});

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: AppSpacing.xl),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleMedium),
        const Divider(),
        for (final row in rows.entries)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(width: 180, child: Text(row.key)),
                Expanded(
                  child: Text(
                    row.value,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                ),
              ],
            ),
          ),
      ],
    ),
  );
}

class _Findings extends StatelessWidget {
  final WizardState state;
  final ValueChanged<ConfigurationTaskId> onOpenTask;

  const _Findings({required this.state, required this.onOpenTask});

  @override
  Widget build(BuildContext context) {
    final findings = _buildFindings(state);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Readiness findings',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: AppSpacing.lg),
        if (findings.isEmpty)
          const ListTile(
            contentPadding: EdgeInsets.zero,
            leading: Icon(Icons.check_circle_outline),
            title: Text('Client readiness checks passed'),
          )
        else
          for (final finding in findings)
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.error_outline),
              title: Text(finding.title),
              subtitle: Text(finding.detail),
              trailing: const Icon(Icons.arrow_forward),
              onTap: () => onOpenTask(finding.taskId),
            ),
      ],
    );
  }
}

class _Validation extends StatelessWidget {
  final WizardState state;
  final VoidCallback onOpenFindings;

  const _Validation({required this.state, required this.onOpenFindings});

  @override
  Widget build(BuildContext context) {
    final ready = state.isConfigurationReadyForFinish;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Validation and preflight',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: AppSpacing.lg),
        ListTile(
          contentPadding: EdgeInsets.zero,
          leading: Icon(
            ready ? Icons.verified_outlined : Icons.pending_actions_outlined,
          ),
          title: Text(
            ready
                ? 'Ready for distributed validation'
                : 'Resolve readiness findings first',
          ),
          subtitle: const Text(
            'Finish validates the persisted configuration through the Management API, Optimizer, and Deployer before marking the twin configured.',
          ),
        ),
        if (!ready)
          TextButton.icon(
            onPressed: onOpenFindings,
            icon: const Icon(Icons.fact_check_outlined),
            label: const Text('Open readiness findings'),
          ),
      ],
    );
  }
}

class _Finding {
  final String title;
  final String detail;
  final ConfigurationTaskId taskId;

  const _Finding(this.title, this.detail, this.taskId);
}

List<_Finding> _buildFindings(WizardState state) {
  final findings = <_Finding>[];
  if (state.step3Invalidated) {
    findings.add(
      const _Finding(
        'Architecture changes require review',
        'Review the current recommendation before continuing.',
        ConfigurationTaskId.compareAndSelect,
      ),
    );
  }
  if (state.unconfiguredProviders.isNotEmpty) {
    findings.add(
      _Finding(
        'Deployment access is incomplete',
        'Missing: ${state.unconfiguredProviders.join(', ')}',
        ConfigurationTaskId.cloudAccess,
      ),
    );
  }
  for (final section in state.deployerReadiness.sections) {
    final taskId = switch (section.id) {
      DeployerSectionId.configuration ||
      DeployerSectionId.payloads => ConfigurationTaskId.dataContracts,
      DeployerSectionId.userLogic => ConfigurationTaskId.userLogic,
      DeployerSectionId.digitalTwinAssets => ConfigurationTaskId.twinAssets,
    };
    for (final artifact in section.artifacts.where(
      (artifact) => artifact.required && !artifact.ready,
    )) {
      findings.add(
        _Finding(
          '${artifact.label} needs attention',
          artifact.hasContent
              ? 'The artifact must pass validation.'
              : 'The required artifact is missing.',
          taskId,
        ),
      );
    }
  }
  return findings;
}
