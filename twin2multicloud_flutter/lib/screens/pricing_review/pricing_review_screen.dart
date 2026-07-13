import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../bloc/pricing_review/pricing_review.dart';
import '../../models/cloud_access_inventory.dart';
import '../../providers/twins_provider.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import '../../widgets/branded_app_bar.dart';
import '../../widgets/pricing/pricing_candidate_review_panel.dart';
import '../../widgets/pricing/pricing_provider_selector.dart';
import '../../widgets/pricing/pricing_provider_workspace.dart';
import '../../widgets/pricing/pricing_refresh_run_summary.dart';
import '../../widgets/pricing/pricing_review_strings.dart';
import '../../widgets/selectable_scaffold.dart';

class PricingReviewScreen extends ConsumerWidget {
  const PricingReviewScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return BlocProvider(
      create: (_) =>
          PricingReviewBloc(api: ref.read(apiServiceProvider))
            ..add(const PricingReviewStarted()),
      child: const _PricingReviewView(),
    );
  }
}

class _PricingReviewView extends StatelessWidget {
  const _PricingReviewView();

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<PricingReviewBloc, PricingReviewState>(
      builder: (context, state) {
        final provider = state.selectedProvider;
        final health = state.pricingHealth?.provider(provider);
        final access = state.accessFor(provider);
        final reports = state.reportsByProvider[provider];
        return SelectableScaffold(
          appBar: BrandedAppBar(
            title: PricingReviewStrings.pageTitle,
            leading: IconButton(
              icon: const Icon(Icons.arrow_back),
              tooltip: PricingReviewStrings.backToDashboard,
              onPressed: () => context.go('/dashboard'),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh),
                tooltip: PricingReviewStrings.reloadPricingState,
                onPressed: state.refreshingProvider == null
                    ? () => context.read<PricingReviewBloc>().add(
                        const PricingReviewReloadRequested(),
                      )
                    : null,
              ),
              const SizedBox(width: AppSpacing.sm),
            ],
          ),
          body: SingleChildScrollView(
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
                      Text(
                        PricingReviewStrings.screenTitle,
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        PricingReviewStrings.screenDescription,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      PricingProviderSelector(
                        selectedProvider: state.selectedProvider,
                        pricingHealth: state.pricingHealth,
                        enabled: state.refreshingProvider == null,
                        onSelected: (provider) => context
                            .read<PricingReviewBloc>()
                            .add(PricingReviewProviderSelected(provider)),
                      ),
                      if (state.feedback != null) ...[
                        const SizedBox(height: AppSpacing.sm),
                        _InlineFeedback(
                          feedback: state.feedback!,
                          onDismiss: () => context
                              .read<PricingReviewBloc>()
                              .add(const PricingReviewFeedbackCleared()),
                        ),
                      ],
                      const SizedBox(height: AppSpacing.md),
                      PricingProviderWorkspace(
                        provider: provider,
                        health: health,
                        access: access,
                        isLoading:
                            state.isLoadingPricingHealth ||
                            state.isLoadingCloudAccess,
                        isRefreshing: state.refreshingProvider == provider,
                        canRefresh: state.canRefresh(provider),
                        error:
                            state.pricingHealthError ?? state.cloudAccessError,
                        reportError: state.reportErrorsByProvider[provider],
                        onRefresh: () =>
                            _confirmRefresh(context, provider, access),
                        onRetry: () => context.read<PricingReviewBloc>().add(
                          state.reportErrorsByProvider[provider] != null &&
                                  state.latestRuns[provider]?.succeeded == true
                              ? PricingReviewReportsReloadRequested(provider)
                              : const PricingReviewReloadRequested(),
                        ),
                      ),
                      if (state.latestRuns[provider] case final run?) ...[
                        const SizedBox(height: AppSpacing.sm),
                        PricingRefreshRunSummary(run: run),
                      ],
                      if (reports != null) ...[
                        const SizedBox(height: AppSpacing.sm),
                        PricingCandidateReviewPanel(
                          reports: reports,
                          selectedCandidateIds: state.selectedCandidateIds,
                          tracesByReportId: state.tracesByReportId,
                          traceErrorsByReportId: state.traceErrorsByReportId,
                          loadingTraceReportIds: state.loadingTraceReportIds,
                          savingDecisionReportIds:
                              state.savingDecisionReportIds,
                          decisionsByReportId: state.decisionsByReportId,
                          onCandidateSelected: (reportId, candidateId) =>
                              context.read<PricingReviewBloc>().add(
                                PricingReviewCandidateSelected(
                                  reportId,
                                  candidateId,
                                ),
                              ),
                          onTraceRequested: (reportId) => context
                              .read<PricingReviewBloc>()
                              .add(PricingReviewReportExpanded(reportId)),
                          onDecisionRequested: (reportId, decision) =>
                              context.read<PricingReviewBloc>().add(
                                PricingReviewDecisionRequested(
                                  reportId: reportId,
                                  decision: decision,
                                ),
                              ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Future<void> _confirmRefresh(
    BuildContext context,
    String provider,
    CloudAccessEntry? access,
  ) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(PricingReviewStrings.refreshDialogTitle(provider)),
        content: Text(PricingReviewStrings.refreshDialogBody(access)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, false),
            child: const Text(PricingReviewStrings.cancel),
          ),
          FilledButton.icon(
            onPressed: () => Navigator.pop(dialogContext, true),
            icon: const Icon(Icons.refresh),
            label: const Text(PricingReviewStrings.refresh),
          ),
        ],
      ),
    );
    if (confirmed == true && context.mounted) {
      context.read<PricingReviewBloc>().add(
        PricingReviewProviderRefreshRequested(
          provider,
          connectionId: access?.scope == 'public' ? null : access?.connectionId,
        ),
      );
    }
  }
}

class _InlineFeedback extends StatelessWidget {
  final PricingReviewFeedback feedback;
  final VoidCallback onDismiss;

  const _InlineFeedback({required this.feedback, required this.onDismiss});

  @override
  Widget build(BuildContext context) {
    final color = feedback.isError
        ? Theme.of(context).colorScheme.error
        : AppColors.success;
    return Row(
      children: [
        Icon(
          feedback.isError ? Icons.error_outline : Icons.check_circle_outline,
          color: color,
          size: AppSpacing.iconMd,
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: Text(feedback.message)),
        IconButton(
          onPressed: onDismiss,
          icon: const Icon(Icons.close),
          tooltip: PricingReviewStrings.dismissMessage,
        ),
      ],
    );
  }
}
