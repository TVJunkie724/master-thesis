import 'package:flutter/material.dart';

/// Centralized color definitions for the Twin2MultiCloud application.
/// 
/// Use these instead of hardcoded colors throughout the codebase to ensure
/// consistent branding and easier theme maintenance.
abstract class AppColors {
  // ============================================================
  // Provider Brand Colors
  // ============================================================
  
  /// AWS Orange (official brand color)
  static const Color aws = Color(0xFFFF9900);
  
  /// Azure Blue (official brand color)
  static const Color azure = Color(0xFF0078D4);
  
  /// GCP Green (official brand color)
  static const Color gcp = Color(0xFF34A853);
  
  // ============================================================
  // Semantic Colors
  // ============================================================
  
  /// Success state (validation passed, deployment complete)
  static const Color success = Color(0xFF4CAF50);
  
  /// Warning state (missing config, unconfigured provider in path)
  static const Color warning = Color(0xFFFFA726);
  
  /// Error state (validation failed, deployment error)
  static const Color error = Color(0xFFEF5350);
  
  /// Glue code indicator (cyan for multi-cloud connectors)
  static const Color glueCode = Color(0xFF00BCD4);
  
  // ============================================================
  // Utility Methods
  // ============================================================
  
  /// Get the brand color for a cloud provider by name.
  /// 
  /// Accepts case-insensitive provider names: 'aws', 'azure', 'gcp'.
  /// Returns grey for unknown providers.
  static Color getProviderColor(String provider) {
    return switch (provider.toUpperCase()) {
      'AWS' => aws,
      'AZURE' => azure,
      'GCP' => gcp,
      _ => Colors.grey,
    };
  }
  
  /// Get a semi-transparent version of the provider color for backgrounds.
  static Color getProviderBackgroundColor(String provider, {int alpha = 25}) {
    return getProviderColor(provider).withAlpha(alpha);
  }
}
