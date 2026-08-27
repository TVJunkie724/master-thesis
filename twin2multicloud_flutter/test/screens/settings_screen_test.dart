import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/user.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/screens/settings_screen.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  testWidgets('loads deployment administrators through the Management API', (
    tester,
  ) async {
    final api = MockApiService();
    when(
      () => api.listCloudConnections(),
    ).thenAnswer((_) async => [_connection('aws-deploy')]);
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(
          AppRuntimeConfig.production(
            managementApiBaseUri: Uri.parse('https://management.test'),
            pocAuthToken: 'local-token',
          ),
        ),
        apiServiceProvider.overrideWithValue(api),
        initialUserProvider.overrideWithValue(
          User(id: 'user-1', email: 'developer@example.com', name: 'Developer'),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Deployment administrators'), findsOneWidget);
    expect(find.text('AWS'), findsOneWidget);
    expect(find.text('Azure'), findsOneWidget);
    expect(find.text('GCP'), findsOneWidget);
    expect(find.text('aws-deploy'), findsOneWidget);
    expect(find.text('aws-pricing'), findsNothing);
    expect(find.textContaining('Fingerprint'), findsNothing);
    expect(find.textContaining('payload_'), findsNothing);
    verify(() => api.listCloudConnections()).called(1);
  });

  testWidgets('shows the profile without identity-provider claims', (
    tester,
  ) async {
    final api = MockApiService();
    when(() => api.listCloudConnections()).thenAnswer((_) async => const []);
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(
          AppRuntimeConfig.production(
            managementApiBaseUri: Uri.parse('https://management.test'),
            pocAuthToken: 'local-token',
          ),
        ),
        apiServiceProvider.overrideWithValue(api),
        initialUserProvider.overrideWithValue(
          User(
            id: 'demo-user',
            email: 'demo@example.test',
            name: 'Demo Operator',
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Demo Operator'), findsOneWidget);
    expect(find.textContaining('UIBK Account'), findsNothing);
    expect(find.textContaining('Google Account'), findsNothing);
  });
}

CloudConnection _connection(String id) => CloudConnection(
  id: id,
  provider: CloudProvider.aws,
  displayName: id,
  authType: 'administrator',
  cloudScope: const {},
  payloadFingerprint: 'opaque',
  payloadSummary: const {},
  validationStatus: 'valid',
  createdAt: DateTime.utc(2026, 8, 27),
  updatedAt: DateTime.utc(2026, 8, 27),
);
