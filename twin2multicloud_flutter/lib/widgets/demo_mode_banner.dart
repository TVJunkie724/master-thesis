import 'package:flutter/material.dart';

import '../config/app_runtime.dart';
import '../theme/spacing.dart';

class DemoModeBanner extends StatelessWidget {
  final DemoScenario scenario;

  const DemoModeBanner({super.key, required this.scenario});

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Material(
      color: colors.tertiaryContainer,
      child: SafeArea(
        bottom: false,
        child: Container(
          constraints: const BoxConstraints(minHeight: 36),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.sm,
          ),
          decoration: BoxDecoration(
            border: Border(bottom: BorderSide(color: colors.outlineVariant)),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.science_outlined,
                size: AppSpacing.iconSm,
                color: colors.onTertiaryContainer,
              ),
              const SizedBox(width: AppSpacing.sm),
              Flexible(
                child: Text(
                  'Offline demo | ${_scenarioLabel(scenario)}',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: colors.onTertiaryContainer,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _scenarioLabel(DemoScenario value) {
    return switch (value) {
      DemoScenario.showcase => 'Showcase data',
      DemoScenario.empty => 'Empty state',
      DemoScenario.degraded => 'Degraded state',
    };
  }
}
