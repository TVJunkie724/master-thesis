import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../models/deployment_access.dart';
import '../../theme/spacing.dart';
import '../terraform_outputs_card.dart';
import 'cleanup_evidence_panel.dart';
import 'deployment_operations_panel.dart';
import 'deployment_readiness_panel.dart';
import 'layer_access_panel.dart';
import 'testing_utilities_panel.dart';
import 'twin_lifecycle_summary.dart';
import 'twin_overview_code_artifact.dart';
import 'twin_overview_configuration_review.dart';
import 'twin_overview_strings.dart';

class TwinOverviewContent extends StatelessWidget {
  final TwinOverviewLoaded state;
  final Widget? deploymentVerification;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onRunPreflight;
  final VoidCallback onReviewPreparation;
  final VoidCallback onOpenCloudAccounts;
  final VoidCallback onDeploy;
  final VoidCallback onDestroy;
  final VoidCallback onViewLogs;
  final VoidCallback onCloseTerminal;
  final VoidCallback onStartTrace;
  final VoidCallback onCancelTrace;
  final VoidCallback onDownloadSimulator;
  final VoidCallback onRetryLayerAccess;
  final ValueChanged<DeploymentAccessSurface> onOpenLayerAccess;
  final VoidCallback onRotateLayerAccessCredential;
  final ValueChanged<String> onOutputCopyFeedback;
  final ValueChanged<TwinOverviewCodeArtifact> onViewArtifact;
  final ValueChanged<TwinOverviewCodeArtifact> onDownloadArtifact;

  const TwinOverviewContent({
    super.key,
    required this.state,
    required this.deploymentVerification,
    required this.onEdit,
    required this.onDelete,
    required this.onRunPreflight,
    required this.onReviewPreparation,
    required this.onOpenCloudAccounts,
    required this.onDeploy,
    required this.onDestroy,
    required this.onViewLogs,
    required this.onCloseTerminal,
    required this.onStartTrace,
    required this.onCancelTrace,
    required this.onDownloadSimulator,
    required this.onRetryLayerAccess,
    required this.onOpenLayerAccess,
    required this.onRotateLayerAccessCredential,
    required this.onOutputCopyFeedback,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    final isDeployed = state.twinState == 'deployed';
    final isError = state.twinState == 'error';
    final isDestroyed = state.twinState == 'destroyed';
    final isDestroying = state.twinState == 'destroying';
    return SingleChildScrollView(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppSpacing.maxContentWidthLarge,
          ),
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TwinLifecycleSummary(
                  state: state,
                  onEdit: onEdit,
                  onDelete: onDelete,
                ),
                if (isDeployed) ...[
                  const SizedBox(height: AppSpacing.lg),
                  const _LifecycleSectionHeader(
                    title: TwinOverviewStrings.verifyAndAccess,
                    description: TwinOverviewStrings.verificationDescription,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  LayerAccessPanel(
                    state: state.layerAccess,
                    onRetry: onRetryLayerAccess,
                    onOpenSurface: onOpenLayerAccess,
                    onRotateViewerCredential: onRotateLayerAccessCredential,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  TestingUtilitiesPanel(
                    provider: state.l1ProviderLabel,
                    trace: state.trace,
                    simulator: state.simulatorDownload,
                    onStartTrace: onStartTrace,
                    onCancelTrace: onCancelTrace,
                    onDownloadSimulator: onDownloadSimulator,
                  ),
                  if (state.deploymentOutputs?.outputs != null &&
                      state.deploymentOutputs!.outputs!.isNotEmpty) ...[
                    const SizedBox(height: AppSpacing.lg),
                    TerraformOutputsCard(
                      outputs: state.deploymentOutputs!.outputs!,
                      deployedAt: state.deploymentOutputs!.deployedAt,
                      onCopyFeedback: onOutputCopyFeedback,
                    ),
                  ],
                  if (state.outputsError != null) ...[
                    const SizedBox(height: AppSpacing.lg),
                    DeploymentOutputsError(message: state.outputsError!),
                  ],
                  if (deploymentVerification != null) ...[
                    const SizedBox(height: AppSpacing.lg),
                    deploymentVerification!,
                  ],
                ],
                if (!isDeployed && !isError && !isDestroyed && !isDestroying)
                  ..._prepareSection(),
                if (isError) ..._errorSection(),
                if (isDestroyed) ..._destroyedSection(),
                if (isDestroying) ..._cleanupSection(includeEvidence: true),
                if (isDeployed) ..._cleanupSection(includeEvidence: true),
                const SizedBox(height: AppSpacing.lg),
                const _LifecycleSectionHeader(
                  title: TwinOverviewStrings.configurationEvidence,
                  description: TwinOverviewStrings.evidenceDescription,
                ),
                const SizedBox(height: AppSpacing.sm),
                TwinOverviewConfigurationReview(
                  state: state,
                  onViewArtifact: onViewArtifact,
                  onDownloadArtifact: onDownloadArtifact,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _prepareSection({
    bool nextRun = false,
    bool includeOperation = true,
  }) => [
    const SizedBox(height: AppSpacing.lg),
    _LifecycleSectionHeader(
      title: nextRun
          ? TwinOverviewStrings.prepareNextRun
          : TwinOverviewStrings.prepareAndDeploy,
      description: nextRun
          ? TwinOverviewStrings.nextRunDescription
          : TwinOverviewStrings.preparingDescription,
    ),
    const SizedBox(height: AppSpacing.sm),
    DeploymentReadinessPanel(
      state: state.deploymentReadiness,
      onRunPreflight: onRunPreflight,
      onReviewPreparation: onReviewPreparation,
      onOpenCloudAccounts: onOpenCloudAccounts,
    ),
    const SizedBox(height: AppSpacing.lg),
    if (includeOperation)
      DeploymentOperationsPanel(
        twinState: state.twinState,
        canDeploy: state.canDeploy,
        canDestroy: state.canDestroy,
        readiness: state.deploymentReadiness,
        operation: state.deploymentOperation,
        lastError: state.lastError,
        onDeploy: onDeploy,
        onDestroy: onDestroy,
        onViewLogs: onViewLogs,
        onCloseTerminal: onCloseTerminal,
      ),
    if (state.outputsError != null) ...[
      const SizedBox(height: AppSpacing.lg),
      DeploymentOutputsError(message: state.outputsError!),
    ],
  ];

  List<Widget> _errorSection() => [
    ..._cleanupSection(includeEvidence: true),
    ..._prepareSection(nextRun: true, includeOperation: false),
  ];

  List<Widget> _destroyedSection() => [
    ..._cleanupSection(includeEvidence: true, includeOperation: false),
    ..._prepareSection(nextRun: true),
  ];

  List<Widget> _cleanupSection({
    required bool includeEvidence,
    bool includeOperation = true,
  }) => [
    const SizedBox(height: AppSpacing.lg),
    const _LifecycleSectionHeader(
      title: TwinOverviewStrings.destroyAndCleanup,
      description: TwinOverviewStrings.cleanupDescription,
    ),
    const SizedBox(height: AppSpacing.sm),
    if (includeOperation)
      DeploymentOperationsPanel(
        twinState: state.twinState,
        canDeploy: state.canDeploy,
        canDestroy: state.canDestroy,
        readiness: state.deploymentReadiness,
        operation: state.deploymentOperation,
        lastError: state.lastError,
        onDeploy: onDeploy,
        onDestroy: onDestroy,
        onViewLogs: onViewLogs,
        onCloseTerminal: onCloseTerminal,
      ),
    if (includeEvidence &&
        (state.cleanupEvidence != null ||
            state.cleanupEvidenceError != null ||
            state.twinState == 'destroyed')) ...[
      if (includeOperation) const SizedBox(height: AppSpacing.lg),
      CleanupEvidencePanel(
        evidence: state.cleanupEvidence,
        errorMessage: state.cleanupEvidenceError,
      ),
    ],
  ];
}

class _LifecycleSectionHeader extends StatelessWidget {
  final String title;
  final String description;

  const _LifecycleSectionHeader({
    required this.title,
    required this.description,
  });

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(title, style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: AppSpacing.xs),
      Text(
        description,
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    ],
  );
}
