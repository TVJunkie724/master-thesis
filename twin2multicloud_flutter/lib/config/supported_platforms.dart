import 'package:flutter/foundation.dart';

/// Product-level targets supported by the Twin2MultiCloud application.
enum SupportedAppPlatform { web, macOS, windows, linux }

/// Resolves Flutter's runtime target to the explicit application contract.
///
/// Web is identified before the native target because browser builds can
/// report a host-oriented [TargetPlatform]. A `null` result means the target
/// is intentionally unsupported and application composition must not start.
SupportedAppPlatform? resolveSupportedAppPlatform({
  required bool isWeb,
  required TargetPlatform nativePlatform,
}) {
  if (isWeb) {
    return SupportedAppPlatform.web;
  }

  return switch (nativePlatform) {
    TargetPlatform.macOS => SupportedAppPlatform.macOS,
    TargetPlatform.windows => SupportedAppPlatform.windows,
    TargetPlatform.linux => SupportedAppPlatform.linux,
    TargetPlatform.android ||
    TargetPlatform.iOS ||
    TargetPlatform.fuchsia => null,
  };
}
