import 'package:flutter/material.dart';

import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../theme/spacing.dart';
import '../terraform_outputs_card.dart';
import 'deployment_operations_panel.dart';
import 'deployment_readiness_panel.dart';
import 'testing_utilities_panel.dart';
import 'twin_overview_code_artifact.dart';
import 'twin_overview_configuration_review.dart';
import 'twin_overview_name_header.dart';
import 'twin_overview_navigation_header.dart';

class TwinOverviewContent extends StatelessWidget {
  final TwinOverviewLoaded state;
  final Widget? deploymentVerification;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onRunPreflight;
  final VoidCallback onOpenCloudAccounts;
  final VoidCallback onDeploy;
  final VoidCallback onDestroy;
  final VoidCallback onViewLogs;
  final VoidCallback onCloseTerminal;
  final VoidCallback onStartTrace;
  final VoidCallback onCancelTrace;
  final VoidCallback onDownloadSimulator;
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
    required this.onOpenCloudAccounts,
    required this.onDeploy,
    required this.onDestroy,
    required this.onViewLogs,
    required this.onCloseTerminal,
    required this.onStartTrace,
    required this.onCancelTrace,
    required this.onDownloadSimulator,
    required this.onOutputCopyFeedback,
    required this.onViewArtifact,
    required this.onDownloadArtifact,
  });

  @override
  Widget build(BuildContext context) {
    final isDeployed = state.twinState == 'deployed';
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
                TwinOverviewNavigationHeader(
                  twinState: state.twinState,
                  canEdit: state.canEdit,
                  canDelete: state.canDelete,
                  onEdit: onEdit,
                  onDelete: onDelete,
                ),
                const SizedBox(height: AppSpacing.md),
                TwinOverviewNameHeader(
                  projectName: state.projectName,
                  cloudResourceName: state.cloudResourceName,
                ),
                const SizedBox(height: AppSpacing.lg),
                DeploymentReadinessPanel(
                  state: state.deploymentReadiness,
                  onRunPreflight: onRunPreflight,
                  onOpenCloudAccounts: onOpenCloudAccounts,
                ),
                const SizedBox(height: AppSpacing.lg),
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
                const SizedBox(height: AppSpacing.lg),
                if (isDeployed) ...[
                  TestingUtilitiesPanel(
                    provider:
                        (state.cheapestPath?['l1'] as String?)?.toLowerCase() ??
                        'l1',
                    trace: state.trace,
                    simulator: state.simulatorDownload,
                    onStartTrace: onStartTrace,
                    onCancelTrace: onCancelTrace,
                    onDownloadSimulator: onDownloadSimulator,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                ],
                if (isDeployed &&
                    state.deploymentOutputs?.outputs != null &&
                    state.deploymentOutputs!.outputs!.isNotEmpty) ...[
                  TerraformOutputsCard(
                    outputs: state.deploymentOutputs!.outputs!,
                    deployedAt: state.deploymentOutputs!.deployedAt,
                    onCopyFeedback: onOutputCopyFeedback,
                  ),
                  const SizedBox(height: AppSpacing.lg),
                ],
                if (state.outputsError != null) ...[
                  DeploymentOutputsError(message: state.outputsError!),
                  const SizedBox(height: AppSpacing.lg),
                ],
                if (deploymentVerification != null) ...[
                  deploymentVerification!,
                  const SizedBox(height: AppSpacing.lg),
                ],
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
}
