import 'package:flutter/material.dart';

import '../../models/optimizer_transfer_pricing.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

class TransferRouteEvidencePanel extends StatelessWidget {
  final TransferPricingContext context;
  final CompletePathOptimizationDiagnostics diagnostics;

  const TransferRouteEvidencePanel({
    super.key,
    required this.context,
    required this.diagnostics,
  });

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      key: const Key('transfer-route-evidence'),
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      title: const Text('Transfer route evidence'),
      subtitle: Text('${this.context.routes.length} exact architecture edges'),
      children: [
        _SolverSummary(
          diagnostics: diagnostics,
          currency: this.context.currency,
        ),
        const SizedBox(height: AppSpacing.sm),
        for (var index = 0; index < this.context.routes.length; index++) ...[
          _TransferRouteRow(
            route: this.context.routes[index],
            currency: this.context.currency,
          ),
          if (index < this.context.routes.length - 1)
            const Divider(height: AppSpacing.xs),
        ],
        if (this.context.pools.isNotEmpty) ...[
          const Divider(height: AppSpacing.md),
          _BillingPoolDetails(
            pools: this.context.pools,
            currency: this.context.currency,
          ),
        ],
        if (this.context.assumptions.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.sm),
          _AssumptionList(
            title: 'Calculation assumptions',
            values: this.context.assumptions,
          ),
        ],
      ],
    );
  }
}

class _SolverSummary extends StatelessWidget {
  final CompletePathOptimizationDiagnostics diagnostics;
  final String currency;

  const _SolverSummary({required this.diagnostics, required this.currency});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Semantics(
      container: true,
      label:
          '${diagnostics.evaluatedPathCount} paths evaluated. '
          'Winning transfer cost ${_money(currency, diagnostics.winningTransferCost)}.',
      child: Wrap(
        spacing: AppSpacing.lg,
        runSpacing: AppSpacing.xs,
        children: [
          _Metric(
            label: 'Evaluated paths',
            value: diagnostics.evaluatedPathCount.toString(),
          ),
          _Metric(
            label: 'Rejected paths',
            value: diagnostics.rejectedPathCount.toString(),
          ),
          _Metric(
            label: 'Layer cost',
            value: _money(currency, diagnostics.winningLayerCost),
          ),
          _Metric(
            label: 'Transfer cost',
            value: _money(currency, diagnostics.winningTransferCost),
          ),
          _Metric(label: 'Tie break', value: 'Canonical provider order'),
          SelectableText(
            'Winner: ${diagnostics.winningCandidateId}',
            style: textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _Metric extends StatelessWidget {
  final String label;
  final String value;

  const _Metric({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 120),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelSmall),
          Text(value, style: Theme.of(context).textTheme.bodyMedium),
        ],
      ),
    );
  }
}

class _TransferRouteRow extends StatelessWidget {
  final TransferRouteEvidence route;
  final String currency;

  const _TransferRouteRow({required this.route, required this.currency});

  @override
  Widget build(BuildContext context) {
    final routeLabel =
        '${_segmentLabel(route.segmentId)}: '
        '${route.source.provider.label} ${route.source.region} to '
        '${route.destination.provider.label} ${route.destination.region}';
    return Semantics(
      container: true,
      label: '$routeLabel. Total ${_money(currency, route.totalCost)}.',
      child: ExpansionTile(
        key: Key('transfer-route-${route.segmentId}'),
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.only(
          left: AppSpacing.md,
          right: AppSpacing.md,
          bottom: AppSpacing.sm,
        ),
        leading: Icon(
          route.isCrossProvider ? Icons.route_outlined : Icons.link_outlined,
          color: AppColors.getProviderColor(route.source.provider.apiValue),
        ),
        title: LayoutBuilder(
          builder: (context, constraints) {
            final endpoint = _EndpointSummary(route: route);
            final cost = Text(
              _money(currency, route.totalCost),
              style: Theme.of(
                context,
              ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w600),
            );
            if (constraints.maxWidth < AppSpacing.pricingReviewCardBreakpoint) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  endpoint,
                  const SizedBox(height: AppSpacing.xs),
                  cost,
                ],
              );
            }
            return Row(
              children: [
                Expanded(child: endpoint),
                const SizedBox(width: AppSpacing.md),
                cost,
              ],
            );
          },
        ),
        subtitle: Text(
          route.isCrossProvider
              ? '${_humanize(route.routeClass)} · ${_humanize(route.networkTier)}'
              : 'Same provider and region · no cross-cloud egress charge',
        ),
        children: [_RouteTechnicalDetails(route: route, currency: currency)],
      ),
    );
  }
}

class _EndpointSummary extends StatelessWidget {
  final TransferRouteEvidence route;

  const _EndpointSummary({required this.route});

  @override
  Widget build(BuildContext context) {
    return Text(
      '${_segmentLabel(route.segmentId)} · '
      '${route.source.provider.label} ${route.source.region} '
      '→ ${route.destination.provider.label} ${route.destination.region}',
      style: Theme.of(
        context,
      ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
    );
  }
}

class _RouteTechnicalDetails extends StatelessWidget {
  final TransferRouteEvidence route;
  final String currency;

  const _RouteTechnicalDetails({required this.route, required this.currency});

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: AppSpacing.lg,
            runSpacing: AppSpacing.sm,
            children: [
              _Metric(label: 'Exact volume', value: _bytes(route.volumeBytes)),
              _Metric(
                label: 'Egress',
                value: _money(currency, route.egressCost),
              ),
              _Metric(
                label: 'Bridge / glue',
                value: _money(currency, route.glueCost),
              ),
              _Metric(label: 'Route class', value: _humanize(route.routeClass)),
              _Metric(
                label: 'Network tier',
                value: _humanize(route.networkTier),
              ),
            ],
          ),
          if (route.poolId != null) ...[
            const SizedBox(height: AppSpacing.sm),
            SelectableText(
              'Billing pool: ${route.poolId}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
          if (route.evidenceId != null)
            SelectableText(
              'Evidence: ${route.evidenceId}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          if (route.catalogSnapshotId != null)
            SelectableText(
              'Catalog snapshot: ${route.catalogSnapshotId}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          if (route.tierContributions.isNotEmpty)
            ExpansionTile(
              key: Key('transfer-tiers-${route.segmentId}'),
              tilePadding: EdgeInsets.zero,
              childrenPadding: EdgeInsets.zero,
              title: Text(
                'Tier contributions (${route.tierContributions.length})',
              ),
              children: [
                for (final contribution in route.tierContributions)
                  _TierContributionRow(
                    contribution: contribution,
                    currency: currency,
                  ),
              ],
            ),
          if (route.assumptions.isNotEmpty)
            _AssumptionList(
              title: 'Route assumptions',
              values: route.assumptions,
            ),
        ],
      ),
    );
  }
}

class _TierContributionRow extends StatelessWidget {
  final TransferTierContribution contribution;
  final String currency;

  const _TierContributionRow({
    required this.contribution,
    required this.currency,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Wrap(
        spacing: AppSpacing.lg,
        runSpacing: AppSpacing.xs,
        children: [
          _Metric(label: 'Tier', value: contribution.tierId),
          _Metric(
            label: 'Interval',
            value:
                '${_quantity(contribution.fromQuantity)}–'
                '${_quantity(contribution.toQuantity)}',
          ),
          _Metric(
            label: 'Billable',
            value: _quantity(contribution.billableQuantity),
          ),
          _Metric(
            label: 'Unit price',
            value: _money(currency, contribution.unitPrice),
          ),
          _Metric(
            label: 'Contribution',
            value: _money(currency, contribution.cost),
          ),
        ],
      ),
    );
  }
}

class _BillingPoolDetails extends StatelessWidget {
  final List<TransferBillingPoolEvidence> pools;
  final String currency;

  const _BillingPoolDetails({required this.pools, required this.currency});

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      key: const Key('transfer-billing-pools'),
      tilePadding: EdgeInsets.zero,
      childrenPadding: EdgeInsets.zero,
      title: Text('Shared billing pools (${pools.length})'),
      children: [
        for (var index = 0; index < pools.length; index++) ...[
          _BillingPoolRow(pool: pools[index], currency: currency),
          if (index < pools.length - 1) const Divider(height: AppSpacing.md),
        ],
      ],
    );
  }
}

class _BillingPoolRow extends StatelessWidget {
  final TransferBillingPoolEvidence pool;
  final String currency;

  const _BillingPoolRow({required this.pool, required this.currency});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${pool.provider.label} · ${_humanize(pool.networkTier)}',
            style: Theme.of(
              context,
            ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: AppSpacing.xs),
          Wrap(
            spacing: AppSpacing.lg,
            runSpacing: AppSpacing.xs,
            children: [
              _Metric(
                label: 'Aggregate volume',
                value: _bytes(pool.aggregateVolumeBytes),
              ),
              _Metric(
                label: 'Aggregate egress',
                value: _money(currency, pool.aggregateEgressCost),
              ),
              _Metric(
                label: 'Billing unit',
                value: pool.billingUnit.toUpperCase(),
              ),
              _Metric(
                label: 'Bytes per unit',
                value: pool.bytesPerBillingUnit.toString(),
              ),
              _Metric(label: 'Scope', value: _humanize(pool.billingScope)),
            ],
          ),
          SelectableText(
            'Evidence: ${pool.evidenceId}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _AssumptionList extends StatelessWidget {
  final String title;
  final List<String> values;

  const _AssumptionList({required this.title, required this.values});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: AppSpacing.xs),
          for (final value in values)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.xs),
              child: SelectableText(
                '• $value',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
        ],
      ),
    );
  }
}

String _segmentLabel(String value) => switch (value) {
  'L1_to_L2' => 'L1 → L2',
  'L2_to_L3_hot' => 'L2 → L3 Hot',
  'L3_hot_to_L3_cool' => 'L3 Hot → L3 Cool',
  'L3_cool_to_L3_archive' => 'L3 Cool → L3 Archive',
  'L3_hot_to_L4' => 'L3 Hot → L4',
  'L4_to_L5' => 'L4 → L5',
  _ => value,
};

String _humanize(String value) => value
    .split('_')
    .where((part) => part.isNotEmpty)
    .map((part) => '${part[0].toUpperCase()}${part.substring(1)}')
    .join(' ');

String _money(String currency, double value) {
  final parts = value.toStringAsFixed(6).split('.');
  final decimals = parts[1].replaceFirst(RegExp(r'0+$'), '').padRight(2, '0');
  return '$currency ${parts[0]}.$decimals';
}

String _bytes(double value) {
  if (value >= 1073741824) {
    return '${(value / 1073741824).toStringAsFixed(3)} GiB';
  }
  if (value >= 1000000) {
    return '${(value / 1000000).toStringAsFixed(3)} MB';
  }
  return '${value.toStringAsFixed(0)} bytes';
}

String _quantity(double value) => value == value.roundToDouble()
    ? value.toInt().toString()
    : value.toString();
