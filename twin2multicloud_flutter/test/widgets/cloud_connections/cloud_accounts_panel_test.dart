import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/cloud_accounts_panel.dart';

void main() {
  Widget buildWidget({
    List<CloudConnection> connections = const [],
    bool isLoading = false,
    String? loadError,
    Set<String> busyConnectionIds = const {},
    bool isCreating = false,
    bool isImporting = false,
    ValueChanged<CloudConnectionCreateRequest>? onCreate,
    ValueChanged<CloudConnectionImportRequest>? onImport,
    ValueChanged<CloudConnection>? onValidate,
    ValueChanged<CloudConnection>? onDelete,
    VoidCallback? onRetry,
    double textScale = 1,
  }) {
    return MaterialApp(
      home: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(textScale)),
        child: Scaffold(
          body: SingleChildScrollView(
            child: CloudAccountsPanel(
              connections: connections,
              isLoading: isLoading,
              loadError: loadError,
              busyConnectionIds: busyConnectionIds,
              isCreating: isCreating,
              isImporting: isImporting,
              onCreate: onCreate ?? (_) {},
              onImport: onImport ?? (_) {},
              onValidate: onValidate ?? (_) {},
              onDelete: onDelete ?? (_) {},
              onRetry: onRetry ?? () {},
            ),
          ),
        ),
      ),
    );
  }

  testWidgets('renders provider-grouped deployment connections only', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1400, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      buildWidget(
        connections: [
          _connection('AWS Administrator'),
          _connection('Azure Administrator', provider: CloudProvider.azure),
        ],
      ),
    );

    expect(find.text('Deployment administrators'), findsOneWidget);
    expect(find.text('AWS'), findsOneWidget);
    expect(find.text('Azure'), findsOneWidget);
    expect(find.text('GCP'), findsOneWidget);
    expect(find.text('AWS Administrator'), findsOneWidget);
    expect(find.text('Azure Administrator'), findsOneWidget);
    expect(find.textContaining('Pricing'), findsNothing);
    expect(find.textContaining('secret_access_key'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('validates a stored deployment administrator from its menu', (
    tester,
  ) async {
    CloudConnection? validated;
    final connection = _connection('AWS Administrator');
    await tester.pumpWidget(
      buildWidget(
        connections: [connection],
        onValidate: (value) => validated = value,
      ),
    );

    await tester.tap(find.byTooltip('Actions for AWS Administrator'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Validate').last);
    await tester.pumpAndSettle();

    expect(validated, connection);
  });

  testWidgets('requires confirmation before deletion', (tester) async {
    CloudConnection? deleted;
    final connection = _connection('AWS Administrator');
    await tester.pumpWidget(
      buildWidget(
        connections: [connection],
        onDelete: (value) => deleted = value,
      ),
    );

    await tester.tap(find.byTooltip('Actions for AWS Administrator'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete').last);
    await tester.pumpAndSettle();
    expect(deleted, isNull);
    expect(find.textContaining('bound to a Twin'), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
    await tester.pumpAndSettle();

    expect(deleted, connection);
  });

  testWidgets('opens manual and provider-file administrator dialogs', (
    tester,
  ) async {
    await tester.pumpWidget(buildWidget());

    await tester.tap(find.text('Enter manually').first);
    await tester.pumpAndSettle();
    expect(find.text('New AWS administrator access'), findsOneWidget);
    await tester.tap(find.text('Cancel').last);
    await tester.pumpAndSettle();

    await tester.tap(find.text('Import CSV'));
    await tester.pumpAndSettle();
    expect(find.text('Import AWS administrator'), findsOneWidget);
    expect(find.text('Select CSV credential file'), findsOneWidget);
    expect(find.textContaining('contents are never previewed'), findsOneWidget);
  });

  for (final textScale in [1.5, 2.0]) {
    testWidgets(
      'keeps controls reachable at 640 px and ${(textScale * 100).toInt()} percent text',
      (tester) async {
        await tester.binding.setSurfaceSize(const Size(640, 1200));
        addTearDown(() => tester.binding.setSurfaceSize(null));
        await tester.pumpWidget(
          buildWidget(
            connections: [_connection('AWS Administrator')],
            textScale: textScale,
          ),
        );

        expect(find.text('Import CSV'), findsOneWidget);
        expect(find.text('Enter manually'), findsWidgets);
        expect(tester.takeException(), isNull);
      },
    );
  }
}

CloudConnection _connection(
  String name, {
  CloudProvider provider = CloudProvider.aws,
}) => CloudConnection(
  id: name.toLowerCase().replaceAll(' ', '-'),
  provider: provider,
  displayName: name,
  authType: 'administrator',
  cloudScope: const {'account_id': '123456789012'},
  payloadFingerprint: 'opaque',
  payloadSummary: const {},
  validationStatus: 'valid',
  lastValidatedAt: DateTime.utc(2026, 8, 27),
  createdAt: DateTime.utc(2026, 8, 27),
  updatedAt: DateTime.utc(2026, 8, 27),
);
