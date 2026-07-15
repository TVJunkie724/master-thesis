// lib/widgets/architecture/architecture_components.dart
// Shared component building utilities for architecture visualization

import 'package:flutter/material.dart';
import 'architecture_service_map.dart';

/// Shared component-building utilities for architecture visualization.
///
/// Provides consistent styling for:
/// - Layer cards
/// - Component boxes (system, editable, storage)
/// - Provider chips
/// - Arrows
/// - Legend
class ArchitectureComponents {
  // ================================================================
  // Layer Cards
  // ================================================================

  /// Build a layer card container
  static Widget buildLayerCard(
    BuildContext context, {
    required String layer,
    required String title,
    required String? provider,
    required List<Widget> components,
    bool isEditable = false,
    bool isStorage = false,
  }) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final providerColor = ArchitectureServiceMap.getProviderColor(
      provider,
      isDark: isDark,
    );

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: ArchitectureServiceMap.getProviderBackgroundColor(
          provider,
          isDark: isDark,
        ),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: providerColor.withValues(alpha: 0.5),
          width: isEditable ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: providerColor.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  layer,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: providerColor,
                    fontSize: 12,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: isDark ? Colors.white : Colors.black87,
                  ),
                ),
              ),
              if (isEditable)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.pink.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Text(
                    'EDIT',
                    style: TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      color: Colors.pink,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          // Components
          ...components,
        ],
      ),
    );
  }

  // ================================================================
  // Component Boxes
  // ================================================================

  /// System component box - grey style for non-editable components
  static Widget buildSystemComponentBox(
    BuildContext context, {
    required String name,
    required IconData icon,
    String? provider,
    bool showProvider = true,
  }) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey.shade800 : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: isDark ? Colors.grey.shade600 : Colors.grey.shade300,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.grey.shade500),
          const SizedBox(width: 8),
          Text(
            name,
            style: TextStyle(
              fontSize: 13,
              color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
            ),
          ),
          if (showProvider && provider != null) ...[
            const SizedBox(width: 8),
            buildProviderChipSmall(provider, isDark: isDark),
          ],
        ],
      ),
    );
  }

  /// Editable component box with pink EDIT badge
  static Widget buildEditableComponentBox(
    BuildContext context, {
    required String name,
    required IconData icon,
  }) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.pink.withValues(alpha: isDark ? 0.15 : 0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: Colors.pink.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: Colors.pink),
          const SizedBox(width: 8),
          Text(
            name,
            style: const TextStyle(
              fontSize: 13,
              color: Colors.pink,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
            decoration: BoxDecoration(
              color: Colors.pink.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(4),
            ),
            child: const Text(
              'EDIT',
              style: TextStyle(
                fontSize: 8,
                fontWeight: FontWeight.bold,
                color: Colors.pink,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Storage tier box
  static Widget buildStorageBox(
    BuildContext context, {
    required String tier,
    required String service,
    required String? provider,
  }) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final providerColor = ArchitectureServiceMap.getProviderColor(
      provider,
      isDark: isDark,
    );
    final icon = ArchitectureServiceMap.getL3Icon(tier);

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: providerColor.withValues(alpha: isDark ? 0.15 : 0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: providerColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Icon(icon, size: 20, color: providerColor),
          const SizedBox(height: 4),
          Text(
            tier,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: providerColor,
            ),
          ),
          Text(
            service,
            style: TextStyle(
              fontSize: 10,
              color: isDark ? Colors.grey.shade300 : Colors.grey.shade600,
            ),
          ),
        ],
      ),
    );
  }

  // ================================================================
  // Provider Chips
  // ================================================================

  static Widget buildProviderChip(String? provider, {bool isDark = false}) {
    final color = ArchitectureServiceMap.getProviderColor(
      provider,
      isDark: isDark,
    );

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Text(
        provider ?? 'N/A',
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.bold,
          color: color,
        ),
      ),
    );
  }

  static Widget buildProviderChipSmall(
    String? provider, {
    bool isDark = false,
  }) {
    final color = ArchitectureServiceMap.getProviderColor(
      provider,
      isDark: isDark,
    );

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        provider ?? '',
        style: TextStyle(
          fontSize: 9,
          fontWeight: FontWeight.bold,
          color: color,
        ),
      ),
    );
  }

  // ================================================================
  // Arrows
  // ================================================================

  static Widget buildArrow({bool small = false, bool vertical = true}) {
    return Icon(
      vertical ? Icons.arrow_downward : Icons.arrow_forward,
      size: small ? 16 : 24,
      color: Colors.grey.shade400,
    );
  }

  // ================================================================
  // Legend
  // ================================================================

  static Widget buildLegend(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: isDark
            ? Colors.grey.shade800.withValues(alpha: 0.5)
            : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Wrap(
        spacing: 16,
        runSpacing: 8,
        children: [
          _legendItem(
            'AWS',
            ArchitectureServiceMap.getProviderColor('AWS', isDark: isDark),
          ),
          _legendItem(
            'Azure',
            ArchitectureServiceMap.getProviderColor('Azure', isDark: isDark),
          ),
          _legendItem(
            'GCP',
            ArchitectureServiceMap.getProviderColor('GCP', isDark: isDark),
          ),
          _legendItem('Editable', Colors.pink),
        ],
      ),
    );
  }

  static Widget _legendItem(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
        ),
      ],
    );
  }
}
