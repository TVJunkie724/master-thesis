/// Standardized spacing tokens for consistent UI layout.
/// 
/// Use these constants instead of magic numbers throughout the codebase.
/// Based on an 8px grid system with half-step support.
abstract class AppSpacing {
  // ============================================================
  // Standard Spacing Scale
  // ============================================================
  
  /// 2px - Minimal spacing (icon gaps, tight elements)
  static const double xxs = 2;
  
  /// 4px - Extra small spacing (between text lines)
  static const double xs = 4;
  
  /// 8px - Small spacing (standard element gap)
  static const double sm = 8;
  
  /// 16px - Medium spacing (card padding, section gaps)
  static const double md = 16;
  
  /// 24px - Large spacing (section separators)
  static const double lg = 24;
  
  /// 32px - Extra large spacing (major section breaks)
  static const double xl = 32;
  
  /// 48px - Double extra large (page-level margins)
  static const double xxl = 48;
  
  // ============================================================
  // Layout Constants
  // ============================================================
  
  /// Maximum content width for dashboard screens
  static const double maxContentWidthLarge = 1200;
  
  /// Maximum content width for form screens (wizard steps)
  static const double maxContentWidthMedium = 800;
  
  /// Standard border radius for cards
  static const double borderRadiusSm = 8;
  
  /// Large border radius for prominent cards
  static const double borderRadiusLg = 12;
  
  /// Standard card elevation
  static const double cardElevation = 4;
}
