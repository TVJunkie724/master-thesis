import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../bloc/pricing_review/pricing_review.dart';
import '../../models/pricing_review_state.dart';
import '../../models/twin.dart';
import '../../providers/twins_provider.dart';
import '../../theme/spacing.dart';
import '../../utils/api_error_handler.dart';
import '../../widgets/branded_app_bar.dart';
import '../../widgets/data_freshness_card.dart';
import '../../widgets/selectable_scaffold.dart';

class PricingReviewScreen extends ConsumerWidget {
  final String? initialTwinId;

  const PricingReviewScreen({super.key, this.initialTwinId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return BlocProvider(
      create: (_) => PricingReviewBloc(
        api: ref.read(apiServiceProvider),
        initialTwinId: initialTwinId,
      ),
      child: const _PricingReviewView(),
    );
  }
}

class _PricingReviewView extends ConsumerWidget {
  const _PricingReviewView();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final twinsAsync = ref.watch(twinsProvider);

    return BlocConsumer<PricingReviewBloc, PricingReviewState>(
      listenWhen: (previous, current) =>
          previous.refreshRevision != current.refreshRevision,
      listener: (context, state) {
        ref.invalidate(pricingReviewStateProvider(state.lastRefreshedTwinId));
        ref.invalidate(pricingReviewStateProvider(null));
      },
      builder: (context, commandState) {
        final reviewStateAsync = ref.watch(
          pricingReviewStateProvider(commandState.selectedTwinId),
        );

        return SelectableScaffold(
          appBar: BrandedAppBar(
            title: 'Pricing Review',
            leading: IconButton(
              icon: const Icon(Icons.arrow_back),
              tooltip: 'Back to dashboard',
              onPressed: () => context.go('/dashboard'),
            ),
            actions: [
              IconButton(
                icon: const Icon(Icons.refresh),
                tooltip: 'Reload pricing state',
                onPressed: () {
                  ref.invalidate(
                    pricingReviewStateProvider(commandState.selectedTwinId),
                  );
                  ref.invalidate(pricingReviewStateProvider(null));
                },
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
                      _buildHeader(context),
                      const SizedBox(height: AppSpacing.lg),
                      _buildTwinSelector(
                        context,
                        twinsAsync,
                        commandState.selectedTwinId,
                      ),
                      if (commandState.feedback != null) ...[
                        const SizedBox(height: AppSpacing.md),
                        _buildFeedback(context, commandState.feedback!),
                      ],
                      const SizedBox(height: AppSpacing.lg),
                      reviewStateAsync.when(
                        data: (reviewState) => _PricingReviewContent(
                          reviewState: reviewState,
                          selectedTwinId: commandState.selectedTwinId,
                          refreshingProvider: commandState.refreshingProvider,
                          onRefreshProvider: (provider) {
                            context.read<PricingReviewBloc>().add(
                              PricingReviewProviderRefreshRequested(provider),
                            );
                          },
                        ),
                        loading: () => const _PricingReviewLoading(),
                        error: (error, _) => _PricingReviewError(
                          message: ApiErrorHandler.extractMessage(error),
                          onRetry: () => ref.invalidate(
                            pricingReviewStateProvider(
                              commandState.selectedTwinId,
                            ),
                          ),
                        ),
                      ),
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

  Widget _buildHeader(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Cloud pricing readiness',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Review cached pricing state globally, then refresh individual '
          'providers with an explicit twin credential context.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }

  Widget _buildTwinSelector(
    BuildContext context,
    AsyncValue<List<Twin>> twinsAsync,
    String? selectedTwinId,
  ) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: twinsAsync.when(
          data: (twins) {
            final selectedExists = twins.any(
              (twin) => twin.id == selectedTwinId,
            );
            final effectiveSelectedTwinId = selectedExists
                ? selectedTwinId
                : null;

            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Credential context',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: AppSpacing.sm),
                DropdownButtonFormField<String>(
                  initialValue: effectiveSelectedTwinId,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    border: OutlineInputBorder(),
                    prefixIcon: Icon(Icons.cloud_sync),
                    labelText: 'Twin used for provider credentials',
                  ),
                  hint: const Text('Select a twin before refreshing pricing'),
                  items: twins
                      .map(
                        (twin) => DropdownMenuItem<String>(
                          value: twin.id,
                          child: Text('${twin.name} (${twin.state})'),
                        ),
                      )
                      .toList(),
                  onChanged: twins.isEmpty
                      ? null
                      : (value) {
                          context.read<PricingReviewBloc>().add(
                            PricingReviewTwinSelected(value),
                          );
                        },
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  twins.isEmpty
                      ? 'Create and configure a twin before provider pricing can be refreshed.'
                      : 'The selected twin determines which stored cloud account credentials are used for refresh operations.',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            );
          },
          loading: () => const LinearProgressIndicator(),
          error: (error, _) => Row(
            children: [
              const Icon(Icons.warning_amber),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  'Twin list could not be loaded: '
                  '${ApiErrorHandler.extractMessage(error)}',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildFeedback(BuildContext context, PricingReviewFeedback feedback) {
    final color = feedback.isError
        ? Theme.of(context).colorScheme.error
        : Theme.of(context).colorScheme.primary;
    final icon = feedback.isError ? Icons.error_outline : Icons.check_circle;

    return Card(
      color: color.withAlpha(24),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            Icon(icon, color: color),
            const SizedBox(width: AppSpacing.sm),
            Expanded(child: Text(feedback.message)),
          ],
        ),
      ),
    );
  }
}

class _PricingReviewContent extends StatelessWidget {
  static const _providers = ['aws', 'azure', 'gcp'];

  final PricingReviewStateResponse reviewState;
  final String? selectedTwinId;
  final String? refreshingProvider;
  final ValueChanged<String> onRefreshProvider;

  const _PricingReviewContent({
    required this.reviewState,
    required this.selectedTwinId,
    required this.refreshingProvider,
    required this.onRefreshProvider,
  });

  @override
  Widget build(BuildContext context) {
    final refreshEnabled = selectedTwinId != null && refreshingProvider == null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        LayoutBuilder(
          builder: (context, constraints) {
            final isNarrow = constraints.maxWidth < 900;
            final cards = _providers.map((provider) {
              final card = DataFreshnessCard(
                provider: provider,
                reviewState: reviewState.provider(provider),
                enabled: refreshEnabled,
                disabledReason: selectedTwinId == null
                    ? 'Select a twin credential context before refreshing pricing.'
                    : 'Another provider refresh is currently running.',
                onRefresh: () => onRefreshProvider(provider),
              );

              if (refreshingProvider == provider) {
                return Stack(
                  children: [
                    card,
                    const Positioned.fill(
                      child: ColoredBox(
                        color: Color(0x44FFFFFF),
                        child: Center(child: CircularProgressIndicator()),
                      ),
                    ),
                  ],
                );
              }
              return card;
            }).toList();

            if (isNarrow) {
              return Column(
                children: cards
                    .map(
                      (card) => Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.md),
                        child: card,
                      ),
                    )
                    .toList(),
              );
            }

            return Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: cards
                  .map(
                    (card) => Expanded(
                      child: Padding(
                        padding: const EdgeInsets.only(right: AppSpacing.md),
                        child: card,
                      ),
                    ),
                  )
                  .toList(),
            );
          },
        ),
        const SizedBox(height: AppSpacing.lg),
        _PricingReviewDetails(reviewState: reviewState),
      ],
    );
  }
}

class _PricingReviewDetails extends StatelessWidget {
  final PricingReviewStateResponse reviewState;

  const _PricingReviewDetails({required this.reviewState});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.fact_check_outlined),
        title: const Text('Review details'),
        subtitle: const Text('Provider reasons, missing keys and actions'),
        childrenPadding: const EdgeInsets.all(AppSpacing.md),
        children: [
          if (reviewState.optimizer.isNotEmpty)
            _DetailsSection(
              title: 'Optimizer',
              values: reviewState.optimizer.entries
                  .map((entry) => '${entry.key}: ${entry.value}')
                  .toList(),
            ),
          ...reviewState.providers.entries.map(
            (entry) =>
                _ProviderDetails(provider: entry.key, state: entry.value),
          ),
        ],
      ),
    );
  }
}

class _ProviderDetails extends StatelessWidget {
  final String provider;
  final ProviderPricingReviewState state;

  const _ProviderDetails({required this.provider, required this.state});

  @override
  Widget build(BuildContext context) {
    final values = <String>[
      'State: ${state.state}',
      'Calculation source: ${state.calculationSource}',
      'Can calculate: ${state.canCalculate}',
      if (state.status != null) 'Schema status: ${state.status}',
      if (state.lastKnownGoodUpdatedAt != null)
        'Last-known-good: ${state.lastKnownGoodUpdatedAt}',
    ];

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _DetailsSection(title: provider.toUpperCase(), values: values),
          if (state.missingKeys.isNotEmpty)
            _DetailsSection(title: 'Missing keys', values: state.missingKeys),
          if (state.actions.isNotEmpty)
            _DetailsSection(
              title: 'Recommended actions',
              values: state.actions,
            ),
          if (state.reviewReasons.isNotEmpty)
            _DetailsSection(
              title: 'Review reasons',
              values: state.reviewReasons.map((reason) {
                final intent = reason.intentId == null
                    ? ''
                    : ' (${reason.intentId})';
                return '${reason.status}$intent: ${reason.reason}';
              }).toList(),
            ),
        ],
      ),
    );
  }
}

class _DetailsSection extends StatelessWidget {
  final String title;
  final List<String> values;

  const _DetailsSection({required this.title, required this.values});

  @override
  Widget build(BuildContext context) {
    if (values.isEmpty) return const SizedBox.shrink();

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.labelLarge),
          const SizedBox(height: AppSpacing.xs),
          ...values.map(
            (value) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: Text(
                value,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PricingReviewLoading extends StatelessWidget {
  const _PricingReviewLoading();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(AppSpacing.lg),
        child: Center(child: CircularProgressIndicator()),
      ),
    );
  }
}

class _PricingReviewError extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _PricingReviewError({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Row(
          children: [
            Icon(
              Icons.error_outline,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(child: Text(message)),
            OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
