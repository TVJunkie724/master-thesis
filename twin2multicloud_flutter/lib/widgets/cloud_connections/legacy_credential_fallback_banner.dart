import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../theme/spacing.dart';
import 'cloud_connection_strings.dart';

class LegacyCredentialFallbackBanner extends StatelessWidget {
  final Set<CloudProvider> providers;

  const LegacyCredentialFallbackBanner({super.key, required this.providers});

  @override
  Widget build(BuildContext context) {
    if (providers.isEmpty) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);
    final labels = providers.map((provider) => provider.label).join(', ');

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: theme.colorScheme.secondaryContainer,
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
      ),
      child: Row(
        children: [
          Icon(Icons.history, color: theme.colorScheme.onSecondaryContainer),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Text(
              '${CloudConnectionStrings.legacyConfigured}: $labels',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSecondaryContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
