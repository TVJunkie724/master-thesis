// lib/utils/twin_state_utils.dart
// Unified twin state colors, labels, and icons - single source of truth

import 'package:flutter/material.dart';

/// Configuration for a twin state's visual representation.
class TwinStateConfig {
  final Color color;
  final IconData icon;
  final String label;
  final String description;
  final bool isAnimated;

  const TwinStateConfig({
    required this.color,
    required this.icon,
    required this.label,
    required this.description,
    this.isAnimated = false,
  });
}

/// Centralized twin state utilities - single source of truth for state visualization.
class TwinStateUtils {
  TwinStateUtils._(); // Private constructor

  /// State color definitions
  static const Color draftColor = Colors.grey;
  static const Color configuredColor = Colors.blue;
  static const Color deployingColor = Colors.amber;
  static const Color deployedColor = Colors.green;
  static const Color destroyingColor = Colors.orange;
  static const Color destroyedColor = Colors.grey;
  static const Color errorColor = Colors.red;

  /// Get the full configuration for a state.
  static TwinStateConfig getConfig(String? state) {
    switch (state?.toLowerCase()) {
      case 'draft':
        return const TwinStateConfig(
          color: draftColor,
          icon: Icons.edit_note,
          label: 'DRAFT',
          description: 'Configuration incomplete',
        );
      case 'configured':
        return const TwinStateConfig(
          color: configuredColor,
          icon: Icons.check_circle_outline,
          label: 'CONFIGURED',
          description: 'Ready to deploy',
        );
      case 'deploying':
        return const TwinStateConfig(
          color: deployingColor,
          icon: Icons.sync,
          label: 'DEPLOYING...',
          description: 'Provisioning cloud resources',
          isAnimated: true,
        );
      case 'deployed':
        return const TwinStateConfig(
          color: deployedColor,
          icon: Icons.cloud_done,
          label: 'DEPLOYED',
          description: 'Live in cloud',
        );
      case 'destroying':
        return const TwinStateConfig(
          color: destroyingColor,
          icon: Icons.sync,
          label: 'DESTROYING...',
          description: 'Removing cloud resources',
          isAnimated: true,
        );
      case 'destroyed':
        return const TwinStateConfig(
          color: destroyedColor,
          icon: Icons.cloud_off,
          label: 'DESTROYED',
          description: 'Resources removed, ready to redeploy',
        );
      case 'error':
        return const TwinStateConfig(
          color: errorColor,
          icon: Icons.error,
          label: 'ERROR',
          description: 'Deployment failed',
        );
      default:
        return TwinStateConfig(
          color: draftColor,
          icon: Icons.help_outline,
          label: (state ?? 'UNKNOWN').toUpperCase(),
          description: 'Unknown state',
        );
    }
  }

  /// Get just the color for a state (convenience method).
  static Color getColor(String? state) => getConfig(state).color;

  /// Get just the icon for a state (convenience method).
  static IconData getIcon(String? state) => getConfig(state).icon;

  /// Get just the label for a state (convenience method).
  static String getLabel(String? state) => getConfig(state).label;

  /// Get just the description for a state (convenience method).
  static String getDescription(String? state) => getConfig(state).description;

  /// Check if a state is transient (deploying/destroying).
  static bool isTransient(String? state) {
    return state == 'deploying' || state == 'destroying';
  }

  /// Check if deploy button should be enabled.
  static bool canDeploy(String? state) {
    return state == 'configured' || state == 'destroyed' || state == 'error';
  }

  /// Check if destroy button should be enabled.
  static bool canDestroy(String? state) {
    return state == 'deployed' || state == 'error';
  }

  /// Check if edit button should be enabled.
  static bool canEdit(String? state) {
    return state != 'deploying' && state != 'destroying' && state != 'deployed';
  }

  /// Build a consistent state badge widget.
  static Widget buildBadge(
    BuildContext context,
    String? state, {
    bool showIcon = true,
    double? fontSize,
  }) {
    final config = getConfig(state);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: config.color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: config.color.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (showIcon) ...[
            config.isAnimated
                ? SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      valueColor: AlwaysStoppedAnimation<Color>(config.color),
                    ),
                  )
                : Icon(config.icon, color: config.color, size: 16),
            const SizedBox(width: 8),
          ],
          Text(
            config.label,
            style: TextStyle(
              color: config.color,
              fontWeight: FontWeight.bold,
              fontSize: fontSize ?? 12,
            ),
          ),
        ],
      ),
    );
  }
}
