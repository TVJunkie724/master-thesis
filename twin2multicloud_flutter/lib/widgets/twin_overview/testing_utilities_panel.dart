import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../theme/spacing.dart';

const _compactBreakpoint = 720.0;
const _actionHeight = 44.0;

class TestingUtilitiesPanel extends StatelessWidget {
  final String provider;
  final TraceViewState trace;
  final SimulatorDownloadViewState simulator;
  final VoidCallback onStartTrace;
  final VoidCallback onCancelTrace;
  final VoidCallback onDownloadSimulator;

  const TestingUtilitiesPanel({
    super.key,
    required this.provider,
    required this.trace,
    required this.simulator,
    required this.onStartTrace,
    required this.onCancelTrace,
    required this.onDownloadSimulator,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.science_outlined, color: theme.colorScheme.primary),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(
                    'Testing utilities',
                    style: theme.textTheme.titleMedium,
                  ),
                ),
                _ProviderLabel(provider: provider),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              'Validate telemetry flow or run the standalone device simulator.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.md),
            LayoutBuilder(
              builder: (context, constraints) {
                final traceAction = _TraceAction(
                  trace: trace,
                  onStart: onStartTrace,
                  onCancel: onCancelTrace,
                );
                final simulatorAction = _SimulatorAction(
                  provider: provider,
                  simulator: simulator,
                  onDownload: onDownloadSimulator,
                );
                if (constraints.maxWidth < _compactBreakpoint) {
                  return Column(
                    children: [
                      traceAction,
                      const SizedBox(height: AppSpacing.md),
                      simulatorAction,
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: traceAction),
                    const SizedBox(width: AppSpacing.lg),
                    Expanded(child: simulatorAction),
                  ],
                );
              },
            ),
            if (trace.hasDiagnostics) ...[
              const SizedBox(height: AppSpacing.sm),
              ExpansionTile(
                key: const Key('trace-diagnostics'),
                tilePadding: EdgeInsets.zero,
                childrenPadding: const EdgeInsets.only(bottom: AppSpacing.sm),
                title: const Text('Trace details'),
                subtitle: Text(
                  '${trace.diagnostics.length} diagnostic entries',
                ),
                children: [
                  Container(
                    width: double.infinity,
                    constraints: const BoxConstraints(maxHeight: 260),
                    padding: const EdgeInsets.all(AppSpacing.md),
                    color: theme.colorScheme.surfaceContainerHighest,
                    child: SingleChildScrollView(
                      child: SelectableText(
                        trace.diagnostics.join('\n'),
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontFamily: 'monospace',
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _TraceAction extends StatelessWidget {
  final TraceViewState trace;
  final VoidCallback onStart;
  final VoidCallback onCancel;

  const _TraceAction({
    required this.trace,
    required this.onStart,
    required this.onCancel,
  });

  @override
  Widget build(BuildContext context) {
    final active = trace.isActive;
    return _UtilityAction(
      title: 'Telemetry trace',
      status: _traceStatus(trace),
      icon: Icons.sensors_outlined,
      action: SizedBox(
        height: _actionHeight,
        width: double.infinity,
        child: active
            ? OutlinedButton.icon(
                key: const Key('cancel-trace'),
                onPressed: onCancel,
                icon: const Icon(Icons.stop_circle_outlined),
                label: const Text('Cancel trace'),
              )
            : OutlinedButton.icon(
                key: const Key('start-trace'),
                onPressed: onStart,
                icon: const Icon(Icons.play_arrow),
                label: const Text('Send test message'),
              ),
      ),
      busy: active,
    );
  }
}

class _SimulatorAction extends StatelessWidget {
  final String provider;
  final SimulatorDownloadViewState simulator;
  final VoidCallback onDownload;

  const _SimulatorAction({
    required this.provider,
    required this.simulator,
    required this.onDownload,
  });

  @override
  Widget build(BuildContext context) {
    return _UtilityAction(
      title: 'Standalone simulator',
      status: simulator.message ?? 'Package for ${provider.toUpperCase()}.',
      icon: Icons.developer_board_outlined,
      action: SizedBox(
        height: _actionHeight,
        width: double.infinity,
        child: OutlinedButton.icon(
          key: const Key('download-simulator'),
          onPressed: simulator.isBusy ? null : onDownload,
          icon: const Icon(Icons.download_outlined),
          label: Text(
            simulator.isBusy ? 'Preparing package' : 'Download simulator',
          ),
        ),
      ),
      busy: simulator.isBusy,
    );
  }
}

class _UtilityAction extends StatelessWidget {
  final String title;
  final String status;
  final IconData icon;
  final Widget action;
  final bool busy;

  const _UtilityAction({
    required this.title,
    required this.status,
    required this.icon,
    required this.action,
    required this.busy,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      label: '$title. $status',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 20, color: theme.colorScheme.primary),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: Text(title, style: theme.textTheme.labelLarge)),
              if (busy)
                const SizedBox.square(
                  dimension: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xs),
          SizedBox(
            height: 40,
            child: Text(
              status,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          action,
        ],
      ),
    );
  }
}

class _ProviderLabel extends StatelessWidget {
  final String provider;

  const _ProviderLabel({required this.provider});

  @override
  Widget build(BuildContext context) {
    return Text(
      provider.toUpperCase(),
      style: Theme.of(context).textTheme.labelSmall?.copyWith(
        color: Theme.of(context).colorScheme.onSurfaceVariant,
        fontWeight: FontWeight.w600,
      ),
    );
  }
}

String _traceStatus(TraceViewState trace) => switch (trace.phase) {
  TraceViewPhase.idle => 'No trace has been run in this session.',
  TraceViewPhase.starting => 'Starting the provider trace.',
  TraceViewPhase.streaming => 'Collecting provider logs.',
  TraceViewPhase.completed => 'Trace completed (${trace.totalLogs ?? 0} logs).',
  TraceViewPhase.failed => trace.message ?? 'Trace failed.',
  TraceViewPhase.cancelled => 'Trace cancelled.',
};
