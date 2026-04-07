import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';

void main() {
  // Twin2MultiCloud is a desktop/web-only tool — the wizard, terminal output,
  // file uploads and Terraform dashboards are not laid out for phone screens.
  // The android/ios platform folders are intentionally absent from the repo,
  // but guard here too in case someone scaffolds them back via `flutter create`.
  if (!kIsWeb && (Platform.isAndroid || Platform.isIOS)) {
    throw UnsupportedError(
      'Twin2MultiCloud is not supported on mobile. '
      'Run with: flutter run -d chrome | -d macos | -d linux | -d windows',
    );
  }

  runApp(
    const ProviderScope(
      child: Twin2MultiCloudApp(),
    ),
  );
}
