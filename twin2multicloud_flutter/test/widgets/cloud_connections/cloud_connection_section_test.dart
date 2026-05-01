import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/widgets/cloud_connections/cloud_connection_section.dart';

void main() {
  testWidgets('renders empty provider state and create action', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CloudConnectionSection(
            provider: CloudProvider.aws,
            icon: Icons.cloud,
            connections: const [],
            selectedConnectionId: null,
            isLoading: false,
            errorMessage: null,
            validation: null,
            onCreate: () {},
            onValidate: null,
            onUnbind: null,
            onSelected: (_) {},
            onDelete: (_) {},
          ),
        ),
      ),
    );

    expect(find.text('AWS'), findsOneWidget);
    expect(find.text('No AWS Cloud Connections yet.'), findsOneWidget);
    expect(find.text('New connection'), findsOneWidget);
  });

  testWidgets('renders selected connection summary', (tester) async {
    final connection = CloudConnection(
      id: 'connection-aws',
      provider: CloudProvider.aws,
      displayName: 'AWS dev',
      authType: 'access_key',
      cloudScope: const {},
      payloadFingerprint: 'fingerprint',
      payloadSummary: const {'region': 'eu-central-1'},
      validationStatus: 'valid',
      validationMessage: 'Validation complete',
      lastValidatedAt: DateTime.utc(2026, 5, 1),
      createdAt: DateTime.utc(2026, 5, 1),
      updatedAt: DateTime.utc(2026, 5, 1),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: CloudConnectionSection(
            provider: CloudProvider.aws,
            icon: Icons.cloud,
            connections: [connection],
            selectedConnectionId: connection.id,
            isLoading: false,
            errorMessage: null,
            validation: null,
            onCreate: () {},
            onValidate: () {},
            onUnbind: () {},
            onSelected: (_) {},
            onDelete: (_) {},
          ),
        ),
      ),
    );

    expect(find.text('AWS dev'), findsOneWidget);
    expect(find.text('region: eu-central-1'), findsOneWidget);
    expect(find.text('Valid'), findsOneWidget);
  });
}
