import 'package:flutter/material.dart';

import '../../../models/architecture_profile.dart';
import '../../../theme/spacing.dart';

const _profileDescriptionMaxLines = 2;

class ArchitectureProfileChoice extends StatelessWidget {
  final ArchitectureProfileSummary profile;
  final bool selected;
  final bool disabled;
  final VoidCallback? onSelect;
  final VoidCallback? onExpand;

  const ArchitectureProfileChoice({
    super.key,
    required this.profile,
    required this.selected,
    required this.disabled,
    required this.onSelect,
    required this.onExpand,
  });

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    final providers = profile.availableProviders
        .map((item) => item.provider.label)
        .join(', ');
    final limitation = profile.unsupportedProviders.isEmpty
        ? 'All reviewed providers available'
        : '${profile.unsupportedProviders.length} provider limitation(s)';
    final semantics =
        '${profile.displayName}, version ${profile.profileVersion}, '
        '${selected ? 'selected' : 'not selected'}, '
        '${profile.responsibilities.length} responsibilities, $limitation';

    return Semantics(
      button: !disabled,
      selected: selected,
      enabled: !disabled,
      inMutuallyExclusiveGroup: true,
      label: semantics,
      child: Card(
        clipBehavior: Clip.antiAlias,
        color: selected ? colors.primaryContainer : null,
        child: InkWell(
          onTap: disabled ? null : onSelect,
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  selected
                      ? Icons.radio_button_checked
                      : Icons.radio_button_unchecked,
                  color: disabled ? colors.outline : colors.primary,
                ),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Wrap(
                        spacing: AppSpacing.sm,
                        runSpacing: AppSpacing.xs,
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          Text(
                            profile.displayName,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          Chip(
                            label: Text('Active v${profile.profileVersion}'),
                          ),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        profile.description,
                        maxLines: _profileDescriptionMaxLines,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        '${profile.responsibilities.length} responsibilities · '
                        '${profile.capabilityIds.length} capabilities · '
                        '${providers.isEmpty ? 'No providers' : providers}',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: colors.onSurfaceVariant,
                        ),
                      ),
                      if (onExpand != null) ...[
                        const SizedBox(height: AppSpacing.sm),
                        TextButton.icon(
                          onPressed: onExpand,
                          icon: const Icon(Icons.account_tree_outlined),
                          label: const Text('Understand architecture'),
                        ),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
