// lib/widgets/step3/info_cards.dart
// Reusable info card widgets for Step 3 deployer

import 'package:flutter/material.dart';

/// Collection of info card widgets for Step 3 deployer.
///
/// All methods support dark mode through BuildContext parameter.
class Step3InfoCards {
  /// Build amber info box for unmet dependencies
  static Widget dependencyInfo(BuildContext context, String message) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.amber.shade900.withValues(alpha: 0.3)
            : Colors.amber.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.amber.shade700 : Colors.amber.shade200,
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.info_outline,
            color: isDark ? Colors.amber.shade300 : Colors.amber.shade700,
            size: 24,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: isDark ? Colors.amber.shade100 : Colors.amber.shade900,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Build grey info box for empty state
  static Widget emptyState(BuildContext context, String message) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.grey.shade700 : Colors.grey.shade300,
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.info_outline,
            color: isDark ? Colors.grey.shade400 : Colors.grey.shade500,
            size: 24,
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: isDark ? Colors.grey.shade300 : Colors.grey.shade600,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Auto-configured card for L3 storage
  static Widget autoConfigured(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.grey.shade700 : Colors.grey.shade300,
        ),
      ),
      child: Row(
        children: [
          Icon(Icons.check_circle, color: Colors.green.shade500, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Auto-configured',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: isDark ? Colors.white : Colors.black87,
                  ),
                ),
                Text(
                  'Storage tiers are automatically provisioned.',
                  style: TextStyle(
                    color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// L4 info card when needs3DModel is false or L4 provider is not AWS/Azure
  /// Takes only the parameters needed, not the full WizardState.
  static Widget l4Info(
    BuildContext context, {
    required bool needs3DModel,
    String? l4Provider,
  }) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final provider = l4Provider?.toUpperCase();

    String message;
    IconData icon;
    Color color;

    if (!needs3DModel) {
      message = 'L4 visualization is not required by the workload intent';
      icon = Icons.info_outline;
      color = Colors.blue;
    } else if (provider == null) {
      message = 'No L4 provider is present in the architecture decision';
      icon = Icons.warning_amber;
      color = Colors.amber;
    } else {
      message = 'L4 configuration not required';
      icon = Icons.check_circle_outline;
      color = Colors.green;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.grey.shade700 : Colors.grey.shade300,
        ),
      ),
      child: Row(
        children: [
          Icon(icon, color: color, size: 28),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: isDark ? Colors.grey.shade300 : Colors.grey.shade600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// L5 info card when L5 provider is not AWS/Azure
  /// Takes only the parameters needed, not the full WizardState.
  static Widget l5Info(BuildContext context, {String? l5Provider}) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final provider = l5Provider?.toUpperCase();

    String message;
    if (provider == null) {
      message = 'No L5 provider is present in the architecture decision';
    } else {
      message = 'L5 config not required for $provider';
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.grey.shade700 : Colors.grey.shade300,
        ),
      ),
      child: Row(
        children: [
          Icon(Icons.info_outline, color: Colors.blue, size: 28),
          const SizedBox(width: 16),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: isDark ? Colors.grey.shade300 : Colors.grey.shade600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
