import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/cloud_accounts_panel.dart';

void main() {
  Widget buildWidget({
    required AsyncValue<List<CloudConnection>> connections,
    Future<void> Function(CloudConnectionCreateRequest request)? onCreate,
    Future<void> Function(CloudConnection connection)? onValidate,
    Future<void> Function(CloudConnection connection)? onDelete,
    VoidCallback? onRetry,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: CloudAccountsPanel(
            connections: connections,
            onCreate: onCreate ?? (_) async {},
            onValidate: onValidate ?? (_) async {},
            onDelete: onDelete ?? (_) async {},
            onRetry: onRetry ?? () {},
          ),
        ),
      ),
    );
  }

  group('CloudAccountsPanel', () {
    testWidgets('renders provider empty states', (tester) async {
      await tester.pumpWidget(
        buildWidget(connections: const AsyncValue.data([])),
      );

      expect(find.text('Cloud Accounts'), findsOneWidget);
      expect(find.text('No AWS Cloud Connection stored.'), findsOneWidget);
      expect(find.text('No Azure Cloud Connection stored.'), findsOneWidget);
      expect(find.text('No GCP Cloud Connection stored.'), findsOneWidget);
      expect(find.text('New AWS connection'), findsOneWidget);
    });

    testWidgets('renders stored connection metadata without secrets', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(connections: AsyncValue.data([_connection()])),
      );

      expect(find.text('AWS thesis dev'), findsOneWidget);
      expect(find.text('Valid'), findsOneWidget);
      expect(find.text('Fingerprint: sha256:abc123'), findsOneWidget);
      expect(find.text('account_id: 123456789012'), findsOneWidget);
      expect(find.text('region: eu-central-1'), findsOneWidget);
      expect(find.textContaining('SECRET'), findsNothing);
    });

    testWidgets('runs validate callback from connection action', (
      tester,
    ) async {
      CloudConnection? validated;
      final connection = _connection();
      await tester.pumpWidget(
        buildWidget(
          connections: AsyncValue.data([connection]),
          onValidate: (value) async => validated = value,
        ),
      );

      await tester.ensureVisible(find.text('Validate'));
      await tester.tap(find.text('Validate'));
      await tester.pump();

      expect(validated, connection);
    });

    testWidgets('requires confirmation before delete callback', (tester) async {
      CloudConnection? deleted;
      final connection = _connection();
      await tester.pumpWidget(
        buildWidget(
          connections: AsyncValue.data([connection]),
          onDelete: (value) async => deleted = value,
        ),
      );

      await tester.ensureVisible(find.text('Delete'));
      await tester.tap(find.text('Delete'));
      await tester.pumpAndSettle();

      expect(deleted, isNull);

      await tester.tap(find.widgetWithText(FilledButton, 'Delete'));
      await tester.pumpAndSettle();

      expect(deleted, connection);
    });

    testWidgets('renders retry action for load errors', (tester) async {
      var retried = false;
      await tester.pumpWidget(
        buildWidget(
          connections: AsyncValue.error(Exception('boom'), StackTrace.current),
          onRetry: () => retried = true,
        ),
      );

      expect(
        find.textContaining('Cloud Accounts could not be loaded'),
        findsOneWidget,
      );

      await tester.tap(find.text('Retry'));
      await tester.pump();

      expect(retried, isTrue);
    });
  });
}

CloudConnection _connection() {
  return CloudConnection(
    id: 'connection-aws',
    provider: CloudProvider.aws,
    displayName: 'AWS thesis dev',
    authType: 'access_key',
    cloudScope: const {'region': 'eu-central-1'},
    payloadFingerprint: 'sha256:abc123',
    payloadSummary: const {'account_id': '123456789012'},
    validationStatus: 'valid',
    validationMessage: 'Permissions verified',
    lastValidatedAt: DateTime.utc(2026, 7, 8, 10),
    createdAt: DateTime.utc(2026, 7, 8, 9),
    updatedAt: DateTime.utc(2026, 7, 8, 10),
  );
}
