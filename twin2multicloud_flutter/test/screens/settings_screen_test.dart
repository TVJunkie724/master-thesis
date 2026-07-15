import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/models/cloud_access_inventory.dart';
import 'package:twin2multicloud_flutter/models/user.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/screens/settings_screen.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  testWidgets('loads compact purpose-aware access through the Management API', (
    tester,
  ) async {
    final api = MockApiService();
    when(
      () => api.getCloudAccessInventory(),
    ).thenAnswer((_) async => _inventory());
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(
          AppRuntimeConfig.production(
            managementApiBaseUri: Uri.parse('https://management.test'),
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

    expect(find.text('Cloud accounts & access'), findsOneWidget);
    expect(find.text('AWS'), findsOneWidget);
    expect(find.text('Azure'), findsOneWidget);
    expect(find.text('GCP'), findsOneWidget);
    expect(find.textContaining('Fingerprint'), findsNothing);
    expect(find.textContaining('payload_'), findsNothing);
    verify(() => api.getCloudAccessInventory()).called(1);
  });
}

CloudAccessInventory _inventory() => CloudAccessInventory.fromJson({
  'schema_version': 'cloud-access-inventory.v1',
  'providers': {
    for (final provider in ['aws', 'azure', 'gcp'])
      provider: {
        'provider': provider,
        'pricing': {
          'provider': provider,
          'purpose': 'pricing',
          'scope': provider == 'azure' ? 'public' : 'user',
          'identity_label': provider == 'azure'
              ? 'Azure Retail Prices API'
              : '${provider.toUpperCase()} pricing not configured',
          'status': provider == 'azure' ? 'active' : 'missing',
          'actions': <String>[],
        },
        'pricing_options': <dynamic>[],
        'deployment': <dynamic>[],
      },
  },
});
