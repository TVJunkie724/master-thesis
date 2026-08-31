import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/cloud_access/cloud_access.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/providers/theme_provider.dart';
import 'package:twin2multicloud_flutter/screens/settings_screen.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/cloud_accounts_panel.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  setUpAll(() => registerFallbackValue(_importRequest()));

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

    expect(find.text('Cloud access'), findsOneWidget);
    expect(find.text('Provider connections'), findsOneWidget);
    expect(find.text('AWS'), findsOneWidget);
    expect(find.text('Azure'), findsOneWidget);
    expect(find.text('GCP'), findsOneWidget);
    expect(find.text('aws-deploy'), findsOneWidget);
    expect(find.text('aws-pricing'), findsNothing);
    expect(find.textContaining('Fingerprint'), findsNothing);
    expect(find.textContaining('payload_'), findsNothing);
    verify(() => api.listCloudConnections()).called(1);
  });

  testWidgets('omits non-actionable profile and identity-provider claims', (
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

    expect(find.text('Provider connections'), findsOneWidget);
    expect(find.byType(CircleAvatar), findsNothing);
    expect(find.textContaining('Demo Operator'), findsNothing);
    expect(find.textContaining('@example'), findsNothing);
    expect(find.textContaining('UIBK Account'), findsNothing);
    expect(find.textContaining('Google Account'), findsNothing);
  });

  testWidgets('shows an initial Management load error with Retry', (
    tester,
  ) async {
    final api = MockApiService();
    when(
      () => api.listCloudConnections(),
    ).thenThrow(const AppException('Management unavailable.'));
    final container = _container(api);
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Management unavailable.'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Retry'), findsOneWidget);
  });

  testWidgets('shows one safe snackbar when an import command fails', (
    tester,
  ) async {
    final api = MockApiService();
    when(() => api.listCloudConnections()).thenAnswer((_) async => const []);
    when(
      () => api.importCloudConnection(any()),
    ).thenThrow(const AppException('Synthetic import rejected.'));
    final container = _container(api);
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pumpAndSettle();
    final panelContext = tester.element(find.byType(CloudAccountsPanel));

    BlocProvider.of<CloudAccessBloc>(
      panelContext,
    ).add(CloudAccessImportRequested(_importRequest()));
    await tester.pumpAndSettle();

    expect(find.text('Synthetic import rejected.'), findsOneWidget);
    verify(() => api.importCloudConnection(any())).called(1);
  });

  testWidgets('opens the canonical guide without changing cloud state', (
    tester,
  ) async {
    final api = MockApiService();
    when(() => api.listCloudConnections()).thenAnswer((_) async => const []);
    Uri? opened;
    final container = _container(api);
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: SettingsScreen(
            setupGuideLauncher: (uri) async {
              opened = uri;
              return true;
            },
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Setup guide').first);
    await tester.pump();

    expect(opened, Uri.parse('http://localhost:5010/cloud-setup/aws/'));
    verify(() => api.listCloudConnections()).called(1);
    verifyNoMoreInteractions(api);
  });

  testWidgets('shows one sanitized message when a guide cannot open', (
    tester,
  ) async {
    final api = MockApiService();
    when(() => api.listCloudConnections()).thenAnswer((_) async => const []);
    final container = _container(api);
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: SettingsScreen(setupGuideLauncher: (_) async => false),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(TextButton, 'Setup guide').first);
    await tester.pump();

    expect(find.text('Could not open the setup guide.'), findsOneWidget);
    expect(find.textContaining('http://'), findsNothing);
  });

  testWidgets('keeps Cloud access visible after theme toggle', (tester) async {
    final api = MockApiService();
    when(() => api.listCloudConnections()).thenAnswer((_) async => const []);
    final container = _container(api);
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pumpAndSettle();
    final initialTheme = container.read(themeProvider);
    await tester.tap(find.byTooltip('Toggle theme'));
    await tester.pumpAndSettle();

    expect(container.read(themeProvider), isNot(initialTheme));
    expect(find.text('Cloud access'), findsOneWidget);
    expect(find.text('Provider connections'), findsOneWidget);

    await tester.tap(find.byTooltip('Toggle theme'));
    await tester.pumpAndSettle();
    expect(container.read(themeProvider), initialTheme);
    expect(find.text('Cloud access'), findsOneWidget);
  });
}

ProviderContainer _container(ApiService api) => ProviderContainer(
  overrides: [
    appRuntimeProvider.overrideWithValue(
      AppRuntimeConfig.production(
        managementApiBaseUri: Uri.parse('https://management.test'),
        pocAuthToken: 'local-token',
      ),
    ),
    apiServiceProvider.overrideWithValue(api),
  ],
);

CloudConnectionImportRequest _importRequest() => CloudConnectionImportRequest(
  provider: CloudProvider.aws,
  displayName: 'Synthetic AWS import',
  region: 'eu-central-1',
  filename: 'credentials.csv',
  bytes: Uint8List.fromList([1, 2, 3]),
);

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
