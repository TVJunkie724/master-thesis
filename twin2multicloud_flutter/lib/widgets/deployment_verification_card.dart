import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../bloc/deployment_verification/deployment_verification.dart';
import '../models/deployment_verification.dart';
import '../theme/colors.dart';
import '../theme/spacing.dart';

class DeploymentVerificationCard extends StatefulWidget {
  final String? payloadsJson;
  final String? configEventsJson;

  const DeploymentVerificationCard({
    super.key,
    this.payloadsJson,
    this.configEventsJson,
  });

  @override
  State<DeploymentVerificationCard> createState() =>
      _DeploymentVerificationCardState();
}

class _DeploymentVerificationCardState
    extends State<DeploymentVerificationCard> {
  late final TextEditingController _payloadController;
  late final String _defaultPayload;
  final ScrollController _terminalScroll = ScrollController();
  int _lastLogCount = 0;

  @override
  void initState() {
    super.initState();
    _defaultPayload = DeploymentVerificationPayload.initialPayload(
      widget.payloadsJson,
    );
    _payloadController = TextEditingController(text: _defaultPayload);
  }

  @override
  void dispose() {
    _payloadController.dispose();
    _terminalScroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return BlocConsumer<
      DeploymentVerificationBloc,
      DeploymentVerificationState
    >(
      listener: (context, state) {
        if (state.dataFlowLogs.length > _lastLogCount) {
          _lastLogCount = state.dataFlowLogs.length;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (_terminalScroll.hasClients) {
              _terminalScroll.animateTo(
                _terminalScroll.position.maxScrollExtent,
                duration: const Duration(milliseconds: 150),
                curve: Curves.easeOut,
              );
            }
          });
        }
      },
      builder: (context, state) {
        return Card(
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _VerificationHeader(theme: theme),
                const SizedBox(height: AppSpacing.lg),
                _InfrastructureSection(state: state),
                const SizedBox(height: AppSpacing.lg),
                Divider(color: theme.dividerColor.withValues(alpha: 0.5)),
                const SizedBox(height: AppSpacing.md),
                _DataFlowSection(
                  state: state,
                  payloadController: _payloadController,
                  terminalScroll: _terminalScroll,
                  defaultPayload: _defaultPayload,
                  configEventsJson: widget.configEventsJson,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _VerificationHeader extends StatelessWidget {
  final ThemeData theme;

  const _VerificationHeader({required this.theme});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.verified_outlined, color: theme.colorScheme.primary),
        const SizedBox(width: AppSpacing.sm),
        Text(
          'DEPLOYMENT VERIFICATION',
          style: theme.textTheme.labelLarge?.copyWith(
            color: theme.colorScheme.primary,
            letterSpacing: 1.2,
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

class _InfrastructureSection extends StatelessWidget {
  final DeploymentVerificationState state;

  const _InfrastructureSection({required this.state});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: double.infinity,
          height: 48,
          child: FilledButton.icon(
            onPressed: state.isCheckingInfrastructure
                ? null
                : () => context.read<DeploymentVerificationBloc>().add(
                    const DeploymentVerificationInfrastructureRequested(),
                  ),
            icon: state.isCheckingInfrastructure
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.play_arrow),
            label: Text(
              state.isCheckingInfrastructure
                  ? 'Checking...'
                  : 'CHECK INFRASTRUCTURE',
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Verify deployed cloud resources across L0-L5. Duration: 5-30s. Cost: none.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        if (state.infrastructureError != null) ...[
          const SizedBox(height: AppSpacing.md),
          _ErrorBox(message: state.infrastructureError!),
        ],
        if (state.infrastructureResult != null) ...[
          const SizedBox(height: AppSpacing.md),
          _InfrastructureResultCard(result: state.infrastructureResult!),
        ],
      ],
    );
  }
}

class _DataFlowSection extends StatelessWidget {
  final DeploymentVerificationState state;
  final TextEditingController payloadController;
  final ScrollController terminalScroll;
  final String defaultPayload;
  final String? configEventsJson;

  const _DataFlowSection({
    required this.state,
    required this.payloadController,
    required this.terminalScroll,
    required this.defaultPayload,
    required this.configEventsJson,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: double.infinity,
          height: 48,
          child: FilledButton.icon(
            onPressed: state.isRunningDataFlow
                ? null
                : () => context.read<DeploymentVerificationBloc>().add(
                    DeploymentVerificationDataFlowRequested(
                      payloadController.text,
                    ),
                  ),
            icon: state.isRunningDataFlow
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.send),
            label: Text(
              state.isRunningDataFlow ? 'Verifying...' : 'VERIFY DATA FLOW',
            ),
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.success,
              foregroundColor: Colors.white,
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Send one test IoT message end-to-end. Duration: 1-15 min. Cost: one IoT message.',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        _EventConditionHint(),
        const SizedBox(height: AppSpacing.md),
        _PayloadEditor(
          controller: payloadController,
          defaultPayload: defaultPayload,
          enabled: !state.isRunningDataFlow,
          configEventsJson: configEventsJson,
        ),
        if (state.dataFlowError != null) ...[
          const SizedBox(height: AppSpacing.md),
          _ErrorBox(message: state.dataFlowError!),
        ],
        if (state.dataFlowLogs.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          _TerminalOutput(logs: state.dataFlowLogs, controller: terminalScroll),
        ],
        if (state.dataFlowSummary != null) ...[
          const SizedBox(height: AppSpacing.md),
          _DataFlowSummaryCard(summary: state.dataFlowSummary!),
        ],
      ],
    );
  }
}

class _EventConditionHint extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: BoxDecoration(
        color: AppColors.warning.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        border: Border.all(color: AppColors.warning.withValues(alpha: 0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(
            Icons.warning_amber_rounded,
            size: 16,
            color: AppColors.warning,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              'If event checking is enabled, payload values must match configured event conditions.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PayloadEditor extends StatelessWidget {
  final TextEditingController controller;
  final String defaultPayload;
  final bool enabled;
  final String? configEventsJson;

  const _PayloadEditor({
    required this.controller,
    required this.defaultPayload,
    required this.enabled,
    required this.configEventsJson,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        border: Border.all(color: theme.dividerColor),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              AppSpacing.sm,
              AppSpacing.md,
              0,
            ),
            child: Row(
              children: [
                Icon(
                  Icons.data_object,
                  size: 16,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  'TEST PAYLOAD',
                  style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const Spacer(),
                if (enabled)
                  TextButton.icon(
                    onPressed: () => controller.text = defaultPayload,
                    icon: const Icon(Icons.restore, size: 16),
                    label: const Text('Reset'),
                  ),
                if (configEventsJson != null && configEventsJson!.isNotEmpty)
                  TextButton.icon(
                    onPressed: () => _showEventsDialog(context),
                    icon: const Icon(Icons.event_note, size: 16),
                    label: const Text('Events'),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: TextField(
              controller: controller,
              enabled: enabled,
              maxLines: 6,
              style: theme.textTheme.bodySmall?.copyWith(
                fontFamily: 'monospace',
              ),
              decoration: const InputDecoration(
                border: OutlineInputBorder(),
                isDense: true,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showEventsDialog(BuildContext context) {
    String content = configEventsJson ?? '[]';
    try {
      final decoded = json.decode(content);
      content = const JsonEncoder.withIndent('  ').convert(decoded);
    } catch (_) {
      // Keep raw content if it is not valid JSON.
    }

    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Configured Events'),
        content: SizedBox(
          width: 600,
          child: SingleChildScrollView(child: SelectableText(content)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}

class _InfrastructureResultCard extends StatelessWidget {
  final InfrastructureVerificationResult result;

  const _InfrastructureResultCard({required this.result});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final summary = result.summary;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        border: Border.all(
          color: summary.healthy ? AppColors.success : AppColors.error,
        ),
      ),
      child: Column(
        children: [
          ListTile(
            leading: Icon(
              summary.healthy ? Icons.check_circle : Icons.cancel,
              color: summary.healthy ? AppColors.success : AppColors.error,
            ),
            title: Text(
              '${summary.passCount}/${summary.total} passed'
              '${summary.skipCount > 0 ? ' (${summary.skipCount} skipped)' : ''}',
            ),
            subtitle: Text(summary.healthy ? 'Healthy' : 'Issues found'),
          ),
          const Divider(height: 1),
          _InfrastructureCheckTable(result: result),
        ],
      ),
    );
  }
}

class _InfrastructureCheckTable extends StatelessWidget {
  final InfrastructureVerificationResult result;

  const _InfrastructureCheckTable({required this.result});

  @override
  Widget build(BuildContext context) {
    final grouped = result.groupedByLayer();
    const layerOrder = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5'];
    final orderedLayers = [
      ...layerOrder.where(grouped.containsKey),
      ...grouped.keys.where((layer) => !layerOrder.contains(layer)),
    ];

    return Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Column(
        children: [
          for (final layer in orderedLayers)
            _InfrastructureLayerChecks(layer: layer, checks: grouped[layer]!),
        ],
      ),
    );
  }
}

class _InfrastructureLayerChecks extends StatelessWidget {
  final String layer;
  final List<InfrastructureCheck> checks;

  const _InfrastructureLayerChecks({required this.layer, required this.checks});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            layer,
            style: theme.textTheme.labelMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          for (final check in checks) _InfrastructureCheckRow(check: check),
        ],
      ),
    );
  }
}

class _InfrastructureCheckRow extends StatelessWidget {
  final InfrastructureCheck check;

  const _InfrastructureCheckRow({required this.check});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = check.passed
        ? AppColors.success
        : check.skipped
        ? theme.colorScheme.onSurfaceVariant
        : AppColors.error;
    final icon = check.passed
        ? Icons.check_circle_outline
        : check.skipped
        ? Icons.remove_circle_outline
        : Icons.cancel_outlined;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
      child: Row(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: AppSpacing.sm),
          Expanded(child: Text(check.name)),
          if (check.provider.isNotEmpty)
            _ProviderBadge(provider: check.provider),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              check.detail,
              textAlign: TextAlign.end,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProviderBadge extends StatelessWidget {
  final String provider;

  const _ProviderBadge({required this.provider});

  @override
  Widget build(BuildContext context) {
    final color = provider.contains('/')
        ? Theme.of(context).colorScheme.secondary
        : AppColors.getProviderColor(provider);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppSpacing.xs),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.sm,
          vertical: AppSpacing.xs,
        ),
        child: Text(
          provider.toUpperCase(),
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: color,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}

class _TerminalOutput extends StatelessWidget {
  final List<DataFlowLogEntry> logs;
  final ScrollController controller;

  const _TerminalOutput({required this.logs, required this.controller});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: theme.colorScheme.inverseSurface,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: SizedBox(
        height: 220,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(AppSpacing.sm),
              child: Row(
                children: [
                  Icon(
                    Icons.terminal,
                    size: 16,
                    color: theme.colorScheme.onInverseSurface,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Text(
                    'DATA FLOW LOG',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onInverseSurface,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const Spacer(),
                  Text(
                    '${logs.length} events',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: theme.colorScheme.onInverseSurface,
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: ListView.builder(
                controller: controller,
                padding: const EdgeInsets.all(AppSpacing.sm),
                itemCount: logs.length,
                itemBuilder: (context, index) => _LogLine(log: logs[index]),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LogLine extends StatelessWidget {
  final DataFlowLogEntry log;

  const _LogLine({required this.log});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = switch (log.status) {
      'pass' => AppColors.success,
      'fail' => AppColors.error,
      'skip' => theme.colorScheme.onSurfaceVariant,
      _ => theme.colorScheme.onInverseSurface,
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxs),
      child: Text.rich(
        TextSpan(
          children: [
            if (log.timestamp.isNotEmpty) TextSpan(text: '[${log.timestamp}] '),
            TextSpan(
              text: log.message,
              style: TextStyle(color: color),
            ),
            if (log.detail != null && log.detail!.isNotEmpty)
              TextSpan(text: ' ${log.detail}'),
          ],
        ),
        style: theme.textTheme.bodySmall?.copyWith(
          fontFamily: 'monospace',
          color: theme.colorScheme.onInverseSurface,
        ),
      ),
    );
  }
}

class _DataFlowSummaryCard extends StatelessWidget {
  final DataFlowVerificationSummary summary;

  const _DataFlowSummaryCard({required this.summary});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = summary.allPass ? AppColors.success : AppColors.error;

    return DecoratedBox(
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        border: Border.all(color: color),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  summary.allPass ? Icons.check_circle : Icons.cancel,
                  color: color,
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    '${summary.passCount} passed, ${summary.failCount} failed'
                    '${summary.skipCount > 0 ? ', ${summary.skipCount} skipped' : ''}'
                    ' - ${summary.totalTime}s',
                    style: theme.textTheme.titleSmall?.copyWith(
                      color: color,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            if (summary.failedPhase != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Text('First failure: ${summary.failedPhase}'),
            ],
            for (final hint in summary.hints) ...[
              const SizedBox(height: AppSpacing.sm),
              Row(
                children: [
                  const Icon(
                    Icons.lightbulb_outline,
                    size: 16,
                    color: AppColors.warning,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(child: Text(hint)),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ErrorBox extends StatelessWidget {
  final String message;

  const _ErrorBox({required this.message});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.error.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        border: Border.all(color: AppColors.error),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            const Icon(Icons.error, color: AppColors.error),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                message,
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurface,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
