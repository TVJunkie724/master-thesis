import 'package:flutter/material.dart';

import '../../models/pricing_health.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';
import 'pricing_review_strings.dart';

class PricingProviderSelector extends StatelessWidget {
  final String selectedProvider;
  final PricingHealthResponse? pricingHealth;
  final bool enabled;
  final ValueChanged<String> onSelected;

  const PricingProviderSelector({
    super.key,
    required this.selectedProvider,
    required this.pricingHealth,
    this.enabled = true,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth >= AppSpacing.pricingReviewCardBreakpoint) {
          return Row(
            children: [
              for (
                var index = 0;
                index < PricingReviewStrings.providers.length;
                index++
              )
                Expanded(
                  child: Padding(
                    padding: EdgeInsets.only(
                      right: index == PricingReviewStrings.providers.length - 1
                          ? 0
                          : AppSpacing.sm,
                    ),
                    child: _ProviderChoice(
                      provider: PricingReviewStrings.providers[index],
                      state: pricingHealth
                          ?.provider(PricingReviewStrings.providers[index])
                          ?.state,
                      selected:
                          selectedProvider ==
                          PricingReviewStrings.providers[index],
                      enabled: enabled,
                      onTap: onSelected,
                    ),
                  ),
                ),
            ],
          );
        }
        return SegmentedButton<String>(
          segments: PricingReviewStrings.providers
              .map(
                (provider) => ButtonSegment(
                  value: provider,
                  label: Text(
                    PricingReviewStrings.providerName(provider),
                    semanticsLabel:
                        '${PricingReviewStrings.providerName(provider)}, '
                        '${PricingReviewStrings.healthLabel(pricingHealth?.provider(provider)?.state)}',
                    overflow: TextOverflow.ellipsis,
                  ),
                  icon: Icon(
                    Icons.cloud,
                    color: AppColors.getProviderColor(provider),
                  ),
                ),
              )
              .toList(),
          selected: {selectedProvider},
          showSelectedIcon: false,
          onSelectionChanged: enabled
              ? (selection) => onSelected(selection.single)
              : null,
        );
      },
    );
  }
}

class _ProviderChoice extends StatelessWidget {
  final String provider;
  final String? state;
  final bool selected;
  final bool enabled;
  final ValueChanged<String> onTap;

  const _ProviderChoice({
    required this.provider,
    required this.state,
    required this.selected,
    required this.enabled,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = AppColors.getProviderColor(provider);
    final label =
        '${PricingReviewStrings.providerName(provider)}, '
        '${PricingReviewStrings.healthLabel(state)}';
    return Semantics(
      button: true,
      selected: selected,
      enabled: enabled,
      label: label,
      child: InkWell(
        onTap: enabled ? () => onTap(provider) : null,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: selected ? color.withAlpha(24) : null,
            border: Border.all(
              color: selected ? color : Theme.of(context).colorScheme.outline,
            ),
            borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
          ),
          child: Row(
            children: [
              Icon(Icons.cloud, color: color),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: Text(label, overflow: TextOverflow.ellipsis)),
            ],
          ),
        ),
      ),
    );
  }
}
