// lib/widgets/wizard/step_indicator.dart
// Extracted step indicator widget from wizard_screen.dart

import 'package:flutter/material.dart';

/// A horizontal step indicator showing wizard progress.
/// 
/// Features:
/// - Visual step circles with numbers
/// - Active/completed/upcoming states
/// - Clickable navigation to reached steps
/// - Animated transitions
class StepIndicator extends StatelessWidget {
  final int currentStep;
  final int highestStepReached;
  final int totalSteps;
  final List<String> stepLabels;
  final ValueChanged<int>? onStepTapped;
  
  const StepIndicator({
    super.key,
    required this.currentStep,
    required this.highestStepReached,
    this.totalSteps = 3,
    this.stepLabels = const ['Configuration', 'Optimizer', 'Deployer'],
    this.onStepTapped,
  });
  
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (int i = 0; i < totalSteps; i++) ...[
          if (i > 0) _buildConnector(theme, i),
          _buildStep(theme, i),
        ],
      ],
    );
  }
  
  Widget _buildStep(ThemeData theme, int index) {
    final isActive = index == currentStep;
    final isCompleted = index < currentStep;
    final isReachable = index <= highestStepReached;
    
    return InkWell(
      onTap: isReachable && onStepTapped != null
          ? () => onStepTapped!(index)
          : null,
      borderRadius: BorderRadius.circular(24),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Circle
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 36,
              height: 36,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isActive
                    ? theme.colorScheme.primary
                    : isCompleted
                        ? theme.colorScheme.primary.withOpacity(0.2)
                        : theme.colorScheme.surfaceContainerHighest,
                border: Border.all(
                  color: isActive || isCompleted
                      ? theme.colorScheme.primary
                      : theme.colorScheme.outline,
                  width: isActive ? 2 : 1,
                ),
              ),
              child: Center(
                child: isCompleted
                    ? Icon(
                        Icons.check,
                        size: 20,
                        color: theme.colorScheme.primary,
                      )
                    : Text(
                        '${index + 1}',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: isActive
                              ? theme.colorScheme.onPrimary
                              : isReachable
                                  ? theme.colorScheme.onSurface
                                  : theme.colorScheme.outline,
                        ),
                      ),
              ),
            ),
            const SizedBox(height: 4),
            // Label
            Text(
              stepLabels[index],
              style: TextStyle(
                fontSize: 12,
                fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
                color: isActive
                    ? theme.colorScheme.primary
                    : isReachable
                        ? theme.colorScheme.onSurface
                        : theme.colorScheme.outline,
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildConnector(ThemeData theme, int toIndex) {
    final isCompleted = toIndex <= currentStep;
    
    return Container(
      width: 40,
      height: 2,
      color: isCompleted
          ? theme.colorScheme.primary
          : theme.colorScheme.outlineVariant,
    );
  }
}
