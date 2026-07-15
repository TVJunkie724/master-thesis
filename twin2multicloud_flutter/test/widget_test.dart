// Basic smoke test for Twin2MultiCloud Flutter app.
//
// Verifies the main app widget can be created and rendered.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:twin2multicloud_flutter/app.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';

void main() {
  testWidgets('Twin2MultiCloudApp smoke test', (WidgetTester tester) async {
    // Build our app wrapped in ProviderScope and trigger a frame.
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appRuntimeProvider.overrideWithValue(
            AppRuntimeConfig.production(
              managementApiBaseUri: Uri.parse('https://management.test'),
            ),
          ),
        ],
        child: const Twin2MultiCloudApp(),
      ),
    );

    // Verify that the app renders without crashing.
    // The dashboard or login screen should be visible.
    expect(find.byType(Twin2MultiCloudApp), findsOneWidget);
  });
}
