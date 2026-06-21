import 'package:flutter/material.dart';

import '../../theme/spacing.dart';

class TwinOverviewNameHeader extends StatelessWidget {
  final String projectName;
  final String? cloudResourceName;

  const TwinOverviewNameHeader({
    super.key,
    required this.projectName,
    required this.cloudResourceName,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final cards = [
          _NameCard(
            label: 'PROJECT NAME',
            value: projectName,
            description: 'UI identifier',
          ),
          _NameCard(
            label: 'CLOUD RESOURCE NAME',
            value: cloudResourceName ?? 'Not configured',
            description: 'Used for cloud resources (from config.json)',
            monospace: true,
          ),
        ];

        if (constraints.maxWidth < 720) {
          return Column(
            children: [
              for (final card in cards)
                Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.md),
                  child: card,
                ),
            ],
          );
        }

        return Row(
          children: [
            Expanded(child: cards[0]),
            const SizedBox(width: AppSpacing.md),
            Expanded(child: cards[1]),
          ],
        );
      },
    );
  }
}

class _NameCard extends StatelessWidget {
  final String label;
  final String value;
  final String description;
  final bool monospace;

  const _NameCard({
    required this.label,
    required this.value,
    required this.description,
    this.monospace = false,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: theme.textTheme.labelSmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              value,
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
                fontFamily: monospace ? 'monospace' : null,
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              description,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
