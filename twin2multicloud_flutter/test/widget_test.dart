// Basic smoke test for Twin2MultiCloud Flutter app.
//
// Verifies the main app widget can be created and rendered.

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:twin2multicloud_flutter/app.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/user.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  testWidgets('Twin2MultiCloudApp smoke test', (WidgetTester tester) async {
    final api = _MockManagementApi();
    when(() => api.setUnauthorizedHandler(any())).thenReturn(null);
    when(() => api.getCurrentUser()).thenAnswer(
      (_) async => User(id: 'profile-user', email: 'profile@example.test'),
    );

    // Build our app wrapped in ProviderScope and trigger a frame.
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          appRuntimeProvider.overrideWithValue(
            AppRuntimeConfig.production(
              managementApiBaseUri: Uri.parse('https://management.test'),
              pocAuthToken: 'local-token',
            ),
          ),
          apiServiceProvider.overrideWithValue(api),
        ],
        child: const Twin2MultiCloudApp(),
      ),
    );

    await tester.pump();

    // Verify that the app renders without crashing after profile bootstrap.
    expect(find.byType(Twin2MultiCloudApp), findsOneWidget);
  });
}
