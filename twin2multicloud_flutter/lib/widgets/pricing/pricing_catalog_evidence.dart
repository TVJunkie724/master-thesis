import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../models/pricing_catalog.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

abstract final class PricingCatalogEvidenceStrings {
  static const title = 'Pricing catalog evidence';
  static const technicalDetails = 'Technical details';
  static const unavailable = 'Pricing catalog evidence is unavailable.';
  static const fetched = 'Fetched';
  static const digest = 'Digest';
  static const snapshotId = 'Snapshot ID';
  static const providerSchema = 'Provider schema';
  static const contractVersion = 'Contract version';
  static const registryVersion = 'Registry version';
  static const mappingVersions = 'Mapping versions';
  static const provenance = 'Provenance';
}

class PricingCatalogEvidence extends StatelessWidget {
  final Iterable<PricingCatalogReference> references;
  final String emptyLabel;
  final bool showMissingProviders;

  const PricingCatalogEvidence({
    super.key,
    required this.references,
    this.emptyLabel = PricingCatalogEvidenceStrings.unavailable,
    this.showMissingProviders = false,
  });

  @override
  Widget build(BuildContext context) {
    final ordered = references.toList(growable: false)
      ..sort(
        (left, right) => left.provider.index.compareTo(right.provider.index),
      );
    if (ordered.isEmpty && showMissingProviders) {
      return Column(
        children: [
          for (var index = 0; index < CloudProvider.values.length; index++) ...[
            _UnavailableCatalogReferenceRow(
              provider: CloudProvider.values[index],
              emptyLabel: emptyLabel,
            ),
            if (index < CloudProvider.values.length - 1)
              const SizedBox(height: AppSpacing.sm),
          ],
        ],
      );
    }
    if (ordered.isEmpty) {
      return Align(
        alignment: Alignment.centerLeft,
        child: Text(
          emptyLabel,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      );
    }

    return Column(
      children: [
        for (var index = 0; index < ordered.length; index++) ...[
          _PricingCatalogReferenceRow(reference: ordered[index]),
          if (index < ordered.length - 1) const SizedBox(height: AppSpacing.sm),
        ],
      ],
    );
  }
}

class _UnavailableCatalogReferenceRow extends StatelessWidget {
  final CloudProvider provider;
  final String emptyLabel;

  const _UnavailableCatalogReferenceRow({
    required this.provider,
    required this.emptyLabel,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final providerColor = AppColors.getProviderColor(provider.label);
    return Semantics(
      container: true,
      label: '${provider.label} pricing catalog unavailable',
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(
          border: Border.all(color: theme.dividerColor),
          borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        ),
        child: Row(
          children: [
            Icon(
              Icons.cloud_off_outlined,
              color: providerColor,
              size: AppSpacing.iconMd,
            ),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    provider.label,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    emptyLabel,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PricingCatalogReferenceRow extends StatelessWidget {
  final PricingCatalogReference reference;

  const _PricingCatalogReferenceRow({required this.reference});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final providerColor = AppColors.getProviderColor(reference.provider.label);
    final semanticLabel =
        '${reference.provider.label} pricing catalog, '
        'region ${reference.pricingRegion}, '
        '${reference.sourceSummary}, '
        'fetched ${_timestamp(reference.fetchedAt)}, '
        'digest ${reference.shortenedDigest}';

    return Semantics(
      container: true,
      label: semanticLabel,
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(color: theme.dividerColor),
          borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        ),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final identity = _CatalogIdentity(
                    reference: reference,
                    providerColor: providerColor,
                  );
                  final evidence = _CatalogEvidence(reference: reference);
                  if (constraints.maxWidth <
                      AppSpacing.pricingReviewCardBreakpoint) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        identity,
                        const SizedBox(height: AppSpacing.sm),
                        evidence,
                      ],
                    );
                  }
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: identity),
                      const SizedBox(width: AppSpacing.lg),
                      Expanded(child: evidence),
                    ],
                  );
                },
              ),
            ),
            const Divider(height: AppSpacing.xxs),
            ExpansionTile(
              tilePadding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
              ),
              childrenPadding: const EdgeInsets.only(
                left: AppSpacing.md,
                right: AppSpacing.md,
                bottom: AppSpacing.md,
              ),
              title: const Text(PricingCatalogEvidenceStrings.technicalDetails),
              children: [
                Align(
                  alignment: Alignment.centerLeft,
                  child: SelectableText(_technicalDetails(reference)),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _CatalogIdentity extends StatelessWidget {
  final PricingCatalogReference reference;
  final Color providerColor;

  const _CatalogIdentity({
    required this.reference,
    required this.providerColor,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(
          Icons.cloud_outlined,
          color: providerColor,
          size: AppSpacing.iconMd,
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                reference.provider.label,
                style: Theme.of(
                  context,
                ).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600),
              ),
              Text(
                reference.pricingRegion,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _CatalogEvidence extends StatelessWidget {
  final PricingCatalogReference reference;

  const _CatalogEvidence({required this.reference});

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodySmall;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(reference.sourceSummary, style: style),
        const SizedBox(height: AppSpacing.xxs),
        Text(
          '${PricingCatalogEvidenceStrings.fetched}: '
          '${_timestamp(reference.fetchedAt)}',
          style: style,
        ),
        const SizedBox(height: AppSpacing.xxs),
        Text(
          '${PricingCatalogEvidenceStrings.digest}: '
          '${reference.shortenedDigest}',
          style: style,
        ),
      ],
    );
  }
}

String _technicalDetails(PricingCatalogReference reference) {
  return [
    '${PricingCatalogEvidenceStrings.snapshotId}: ${reference.snapshotId}',
    '${PricingCatalogEvidenceStrings.providerSchema}: '
        '${reference.providerSchemaVersion}',
    '${PricingCatalogEvidenceStrings.contractVersion}: '
        '${reference.contractVersion}',
    '${PricingCatalogEvidenceStrings.registryVersion}: '
        '${reference.registryVersion}',
    '${PricingCatalogEvidenceStrings.mappingVersions}: '
        '${reference.mappingVersions.join(', ')}',
    '${PricingCatalogEvidenceStrings.provenance}: ${reference.source.apiValue}',
    '${PricingCatalogEvidenceStrings.digest}: ${reference.contentDigest}',
  ].join('\n');
}

String _timestamp(DateTime value) => value.toUtc().toIso8601String();
