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

  /// Maximum content width for the compact authentication surface.
  static const double authCardMaxWidth = 400;

  /// Stable authentication brand-mark size.
  static const double authLogoSize = 96;

  /// Standard border radius for cards
  static const double borderRadiusSm = 8;

  /// Large border radius for prominent cards
  static const double borderRadiusLg = 12;

  /// Standard card elevation
  static const double cardElevation = 4;

  /// Lower card elevation for embedded operational panels
  static const double cardElevationLow = 2;

  /// Full-width command button height
  static const double actionButtonHeight = 48;

  /// Small icon size for inline hints
  static const double iconSm = 16;

  /// Extra-small icon size for compact table affordances.
  static const double iconXs = 12;

  /// Medium icon size for inline buttons and indicators
  static const double iconMd = 20;

  /// Fixed label/key column width in Terraform output tables.
  static const double outputTableColumnWidth = 160;

  /// Compact output-table row padding.
  static const double compactRowPadding = 6;

  /// Hairline divider width for dense data rows.
  static const double hairlineWidth = 0.5;

  /// Provider accent strip width
  static const double providerAccentWidth = 4;

  /// Provider pricing row accent strip height
  static const double providerAccentHeight = 40;

  /// Deployment verification terminal log viewport height
  static const double terminalLogHeight = 220;

  /// Compact global marker height for the isolated offline demo runtime
  static const double demoBannerMinHeight = 36;

  /// Profile avatar radius for account identity cards
  static const double profileAvatarRadius = 40;

  /// Deployment verification payload editor max lines
  static const int payloadEditorMaxLines = 6;

  /// Pricing review card layout breakpoint
  static const double pricingReviewCardBreakpoint = 900;

  /// Twin Overview sections stack below this width.
  static const double twinOverviewCompactBreakpoint = 900;

  /// Wizard navigation uses its three-region desktop layout from this width.
  static const double configurationNavigationWideBreakpoint = 1024;

  /// Workload scenario cards stack below the compact workspace breakpoint.
  static const double configurationWorkloadCompactBreakpoint = 960;

  /// Resolved deployment rows use fixed metadata columns from this width.
  static const double resolvedDeploymentWideBreakpoint = 720;

  /// User-function slot actions stack below this width.
  static const double userFunctionCompactBreakpoint = 620;

  /// Stable slot column width in resolved deployment rows.
  static const double resolvedDeploymentSlotColumnWidth = 112;

  /// Stable provider column width in resolved deployment rows.
  static const double resolvedDeploymentProviderColumnWidth = 96;

  /// Stable label column width in generic resolved-architecture evidence.
  static const double resolvedArchitectureEvidenceLabelWidth = 140;

  /// Stable label column width in the configuration summary.
  static const double configurationSummaryLabelWidth = 180;

  /// Logical architecture graph switches to its exact edge-list projection.
  static const double logicalProfileFlowCompactBreakpoint = 720;

  /// Stable logical architecture node width in the bounded graph viewport.
  static const double logicalProfileFlowNodeWidth = 190;

  /// Stable logical architecture graph viewport height.
  static const double logicalProfileFlowViewportHeight = 320;

  /// Minimum zoom for the bounded logical architecture graph.
  static const double logicalProfileFlowMinScale = 0.5;

  /// Default zoom for the bounded logical architecture graph.
  static const double logicalProfileFlowDefaultScale = 1;

  /// Maximum zoom for the bounded logical architecture graph.
  static const double logicalProfileFlowMaxScale = 2;

  /// Keyboard/button zoom increment for the logical architecture graph.
  static const double logicalProfileFlowScaleStep = 0.25;

  /// Graph edge stroke width.
  static const double logicalProfileFlowEdgeWidth = 1;

  /// Compact progress-indicator stroke width inside an action button.
  static const double compactProgressIndicatorStrokeWidth = 2;

  /// Maximum text scaling that still uses fixed resolved-review columns.
  static const double resolvedArchitectureWideTextScaleLimit = 1.3;

  /// Maximum width for confirmation-dialog content.
  static const double dialogContentMaxWidth = 480;

  /// Preferred read-only code viewer width before dialog constraints apply.
  static const double codeViewerWidth = 700;

  /// Preferred read-only code viewer height before dialog constraints apply.
  static const double codeViewerHeight = 500;

  /// Readable monospace size for code and deployment-log artifacts.
  static const double codeViewerFontSize = 13;

  /// Stable two-line status area in compact operational actions.
  static const double utilityStatusHeight = 40;

  /// Maximum height for collapsed operational diagnostic details.
  static const double diagnosticViewportHeight = 260;

  /// Uppercase label letter spacing
  static const double labelLetterSpacing = 1.2;

  /// Short UI animation duration in milliseconds
  static const int animationFastMs = 150;
}
