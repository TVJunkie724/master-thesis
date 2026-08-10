import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../models/deployment_access.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

class LayerAccessPanel extends StatelessWidget {
  final LayerAccessViewState state;
  final VoidCallback onRetry;
  final ValueChanged<DeploymentAccessSurface> onOpenSurface;
  final VoidCallback onRotateViewerCredential;

  const LayerAccessPanel({
    super.key,
    required this.state,
    required this.onRetry,
    required this.onOpenSurface,
    required this.onRotateViewerCredential,
  });

  @override
  Widget build(BuildContext context) {
    final aggregate = _panelStatus(state);
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact =
            constraints.maxWidth < AppSpacing.twinOverviewCompactBreakpoint;
        return Semantics(
          container: true,
          label: 'Layer access. ${aggregate.label}',
          child: Card(
            elevation: AppSpacing.cardElevationLow,
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _PanelHeader(status: aggregate),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Inspect semantic state in L4 and raw history and rollups in L5.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  _phaseContent(context, compact: compact),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _phaseContent(BuildContext context, {required bool compact}) {
    return switch (state.phase) {
      LayerAccessViewPhase.idle => const _Message(
        icon: Icons.schedule,
        text: 'Layer access becomes available after deployment.',
      ),
      LayerAccessViewPhase.loading => const Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          LinearProgressIndicator(),
          SizedBox(height: AppSpacing.sm),
          Text('Loading L4 and L5 access evidence...'),
        ],
      ),
      LayerAccessViewPhase.failed => _Failure(
        message: state.errorMessage ?? 'Layer access could not be loaded.',
        onRetry: onRetry,
      ),
      LayerAccessViewPhase.unsupported => const _Message(
        icon: Icons.info_outline,
        text:
            'Layer links are unavailable for this historical five-layer profile. No access links were inferred.',
      ),
      LayerAccessViewPhase.ready => _surfaceCards(context, compact: compact),
    };
  }

  Widget _surfaceCards(BuildContext context, {required bool compact}) {
    final surfaces = [...?state.snapshot?.surfaces]
      ..sort((left, right) => left.layer.index.compareTo(right.layer.index));
    if (surfaces.length != 2) {
      return _Failure(
        message: 'Layer access evidence is incomplete.',
        onRetry: onRetry,
      );
    }
    final cards = surfaces
        .map(
          (surface) => LayerAccessCard(
            surface: surface,
            compactActions: compact,
            rotatingViewerCredential:
                state.rotatingViewerCredential &&
                surface.layer == DeploymentLayer.l5,
            rotationError: surface.layer == DeploymentLayer.l5
                ? state.rotationError
                : null,
            onOpen: () => onOpenSurface(surface),
            onRotateViewerCredential: onRotateViewerCredential,
          ),
        )
        .toList(growable: false);
    if (compact) {
      return FocusTraversalGroup(
        policy: OrderedTraversalPolicy(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            cards.first,
            const SizedBox(height: AppSpacing.lg),
            cards.last,
          ],
        ),
      );
    }
    return FocusTraversalGroup(
      policy: OrderedTraversalPolicy(),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: cards.first),
          const SizedBox(width: AppSpacing.lg),
          Expanded(child: cards.last),
        ],
      ),
    );
  }
}

class LayerAccessCard extends StatelessWidget {
  final DeploymentAccessSurface surface;
  final bool compactActions;
  final bool rotatingViewerCredential;
  final String? rotationError;
  final VoidCallback onOpen;
  final VoidCallback onRotateViewerCredential;

  const LayerAccessCard({
    super.key,
    required this.surface,
    required this.compactActions,
    required this.rotatingViewerCredential,
    required this.rotationError,
    required this.onOpen,
    required this.onRotateViewerCredential,
  });

  @override
  Widget build(BuildContext context) {
    final status = _surfaceStatus(surface);
    final providerColor = AppColors.getProviderColor(surface.provider.label);
    final blockingReason = _openBlockingReason(surface.readiness);
    final canOpen = blockingReason == null;
    final canRotate =
        surface.layer == DeploymentLayer.l5 &&
        surface.auth.credentialAction ==
            DeploymentAccessCredentialAction.rotate;
    final purpose = surface.layer == DeploymentLayer.l4
        ? 'L4 Semantic Twin'
        : 'L5 Raw & Rollups';

    return Semantics(
      key: Key('layer-access-card-${surface.layer.name}'),
      container: true,
      label:
          '$purpose. ${surface.provider.label}. ${surface.displayName}. ${status.label}.',
      child: Card(
        margin: EdgeInsets.zero,
        color: Theme.of(context).colorScheme.surfaceContainerLow,
        child: Container(
          decoration: BoxDecoration(
            border: Border(
              left: BorderSide(
                color: providerColor,
                width: AppSpacing.providerAccentWidth,
              ),
            ),
          ),
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    surface.layer == DeploymentLayer.l4
                        ? Icons.hub_outlined
                        : Icons.monitor_heart_outlined,
                    color: providerColor,
                    size: AppSpacing.iconMd,
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          purpose,
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        Text(
                          surface.displayName,
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  _StatusChip(status: status),
                ],
              ),
              const SizedBox(height: AppSpacing.sm),
              Chip(
                avatar: Icon(
                  Icons.cloud_outlined,
                  size: AppSpacing.iconSm,
                  color: providerColor,
                ),
                label: Text(surface.provider.label),
                visualDensity: VisualDensity.compact,
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                surface.capabilities.join(' '),
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                '${_principalLabel(surface.auth.mode)}: ${surface.auth.principalLabel}',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              if (blockingReason != null) ...[
                const SizedBox(height: AppSpacing.sm),
                _InlineNotice(
                  icon: Icons.block,
                  message: blockingReason,
                  isError: true,
                ),
              ],
              if (rotationError != null) ...[
                const SizedBox(height: AppSpacing.sm),
                _InlineNotice(
                  icon: Icons.error_outline,
                  message: rotationError!,
                  isError: true,
                ),
              ],
              const SizedBox(height: AppSpacing.md),
              _Actions(
                surface: surface,
                compact: compactActions,
                canOpen: canOpen,
                canRotate: canRotate,
                rotating: rotatingViewerCredential,
                onOpen: onOpen,
                onRotate: onRotateViewerCredential,
              ),
              const SizedBox(height: AppSpacing.sm),
              _AccessDetails(
                surface: surface,
                initiallyExpanded: !status.ready,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PanelHeader extends StatelessWidget {
  final _AccessVisual status;

  const _PanelHeader({required this.status});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(Icons.link, color: status.color, size: AppSpacing.iconMd),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            'Layer access',
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        _StatusChip(status: status),
      ],
    );
  }
}

class _StatusChip extends StatelessWidget {
  final _AccessVisual status;

  const _StatusChip({required this.status});

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: Icon(status.icon, color: status.color, size: AppSpacing.iconSm),
      label: Text(status.label),
      visualDensity: VisualDensity.compact,
    );
  }
}

class _Actions extends StatelessWidget {
  final DeploymentAccessSurface surface;
  final bool compact;
  final bool canOpen;
  final bool canRotate;
  final bool rotating;
  final VoidCallback onOpen;
  final VoidCallback onRotate;

  const _Actions({
    required this.surface,
    required this.compact,
    required this.canOpen,
    required this.canRotate,
    required this.rotating,
    required this.onOpen,
    required this.onRotate,
  });

  @override
  Widget build(BuildContext context) {
    final open = FocusTraversalOrder(
      order: NumericFocusOrder(surface.layer == DeploymentLayer.l4 ? 1 : 3),
      child: FilledButton.icon(
        key: Key('open-layer-${surface.layer.name}'),
        onPressed: canOpen ? onOpen : null,
        icon: const Icon(Icons.open_in_new),
        label: Text(
          surface.layer == DeploymentLayer.l4 ? 'Open Twin UI' : 'Open Grafana',
        ),
      ),
    );
    final rotate = canRotate
        ? FocusTraversalOrder(
            order: const NumericFocusOrder(4),
            child: OutlinedButton.icon(
              key: const Key('rotate-gcp-viewer'),
              onPressed: rotating ? null : onRotate,
              icon: rotating
                  ? const SizedBox.square(
                      dimension: AppSpacing.iconMd,
                      child: CircularProgressIndicator(
                        strokeWidth:
                            AppSpacing.compactProgressIndicatorStrokeWidth,
                      ),
                    )
                  : const Icon(Icons.key_outlined),
              label: Text(rotating ? 'Creating...' : 'New password'),
            ),
          )
        : null;
    if (compact) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          open,
          if (rotate != null) ...[
            const SizedBox(height: AppSpacing.sm),
            rotate,
          ],
        ],
      );
    }
    return Wrap(
      spacing: AppSpacing.sm,
      runSpacing: AppSpacing.sm,
      children: [open, if (rotate != null) rotate],
    );
  }
}

class _AccessDetails extends StatelessWidget {
  final DeploymentAccessSurface surface;
  final bool initiallyExpanded;

  const _AccessDetails({
    required this.surface,
    required this.initiallyExpanded,
  });

  @override
  Widget build(BuildContext context) {
    return FocusTraversalOrder(
      order: NumericFocusOrder(surface.layer == DeploymentLayer.l4 ? 2 : 5),
      child: ExpansionTile(
        key: Key('layer-access-details-${surface.layer.name}'),
        tilePadding: EdgeInsets.zero,
        childrenPadding: EdgeInsets.zero,
        initiallyExpanded: initiallyExpanded,
        title: Text(
          surface.layer == DeploymentLayer.l4
              ? 'Authentication details'
              : 'Access details',
        ),
        children: [
          _DetailRow(
            label: 'Authentication',
            value: _authLabel(surface.auth.mode),
          ),
          _DetailRow(label: 'Resource', value: surface.readiness.resource.name),
          _DetailRow(
            label: 'Access binding',
            value: surface.readiness.accessBinding.name,
          ),
          _DetailRow(label: 'Content', value: surface.readiness.content.name),
          _DetailRow(
            label: 'Data probe',
            value: surface.readiness.dataProbe.name,
          ),
          _DetailRow(
            label: 'Browser sign-in',
            value: surface.readiness.browserSignIn.name,
          ),
          if (surface.limitations.isNotEmpty) ...[
            const Divider(),
            for (final limitation in surface.limitations)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.info_outline, size: AppSpacing.iconSm),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(child: Text(limitation)),
                  ],
                ),
              ),
          ],
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  final String label;
  final String value;

  const _DetailRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: AppSpacing.sm),
          Flexible(
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

class _Failure extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _Failure({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _InlineNotice(
          icon: Icons.error_outline,
          message: message,
          isError: true,
        ),
        const SizedBox(height: AppSpacing.md),
        OutlinedButton.icon(
          onPressed: onRetry,
          icon: const Icon(Icons.refresh),
          label: const Text('Retry layer access'),
        ),
      ],
    );
  }
}

class _Message extends StatelessWidget {
  final IconData icon;
  final String text;

  const _Message({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return _InlineNotice(icon: icon, message: text);
  }
}

class _InlineNotice extends StatelessWidget {
  final IconData icon;
  final String message;
  final bool isError;

  const _InlineNotice({
    required this.icon,
    required this.message,
    this.isError = false,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final color = isError ? colors.error : colors.onSurfaceVariant;
    return Semantics(
      label: message,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: AppSpacing.iconMd),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: color),
            ),
          ),
        ],
      ),
    );
  }
}

_AccessVisual _panelStatus(LayerAccessViewState state) {
  return switch (state.phase) {
    LayerAccessViewPhase.ready when state.snapshot != null =>
      state.snapshot!.surfaces.every((surface) => _surfaceStatus(surface).ready)
          ? _readyVisual
          : _reviewVisual,
    LayerAccessViewPhase.failed => _failedVisual,
    LayerAccessViewPhase.unsupported => _unsupportedVisual,
    _ => _pendingVisual,
  };
}

_AccessVisual _surfaceStatus(DeploymentAccessSurface surface) {
  final readiness = surface.readiness;
  final ready =
      readiness.resource == DeploymentAccessResourceStatus.ready &&
      readiness.accessBinding == DeploymentAccessBindingStatus.ready &&
      readiness.content == DeploymentAccessContentStatus.ready &&
      readiness.dataProbe == DeploymentAccessDataProbeStatus.ready;
  if (ready) return _readyVisual;
  if (readiness.resource == DeploymentAccessResourceStatus.failed ||
      readiness.accessBinding == DeploymentAccessBindingStatus.blocked ||
      readiness.content == DeploymentAccessContentStatus.failed ||
      readiness.dataProbe == DeploymentAccessDataProbeStatus.failed) {
    return _reviewVisual;
  }
  return _pendingVisual;
}

String? _openBlockingReason(LayerAccessReadiness readiness) {
  if (readiness.resource == DeploymentAccessResourceStatus.failed) {
    return 'Open is blocked because the cloud resource failed readiness.';
  }
  if (readiness.resource == DeploymentAccessResourceStatus.pending) {
    return 'Open is blocked while the cloud resource is pending.';
  }
  if (readiness.accessBinding == DeploymentAccessBindingStatus.blocked) {
    return 'Open is blocked because the user access binding is blocked.';
  }
  if (readiness.accessBinding == DeploymentAccessBindingStatus.pending) {
    return 'Open is blocked while the user access binding is pending.';
  }
  return null;
}

String _principalLabel(DeploymentAccessAuthMode mode) => switch (mode) {
  DeploymentAccessAuthMode.generatedViewer => 'Viewer',
  _ => 'Principal',
};

String _authLabel(DeploymentAccessAuthMode mode) => switch (mode) {
  DeploymentAccessAuthMode.awsIdentityCenter => 'AWS Identity Center',
  DeploymentAccessAuthMode.azureEntra => 'Microsoft Entra ID',
  DeploymentAccessAuthMode.gcpIap => 'Google Cloud IAP',
  DeploymentAccessAuthMode.generatedViewer => 'Generated Grafana Viewer',
};

class _AccessVisual {
  final String label;
  final IconData icon;
  final Color color;
  final bool ready;

  const _AccessVisual({
    required this.label,
    required this.icon,
    required this.color,
    required this.ready,
  });
}

const _readyVisual = _AccessVisual(
  label: 'Ready',
  icon: Icons.check_circle_outline,
  color: AppColors.success,
  ready: true,
);
const _reviewVisual = _AccessVisual(
  label: 'Needs review',
  icon: Icons.warning_amber_outlined,
  color: AppColors.warning,
  ready: false,
);
const _failedVisual = _AccessVisual(
  label: 'Unavailable',
  icon: Icons.error_outline,
  color: AppColors.error,
  ready: false,
);
const _pendingVisual = _AccessVisual(
  label: 'Pending',
  icon: Icons.schedule,
  color: AppColors.warning,
  ready: false,
);
const _unsupportedVisual = _AccessVisual(
  label: 'Unsupported',
  icon: Icons.info_outline,
  color: AppColors.warning,
  ready: false,
);
