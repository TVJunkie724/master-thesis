// test/widgets/dashboard/twins_table_test.dart
// Tests for TwinsTable widget

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/twin.dart';
import 'package:twin2multicloud_flutter/widgets/dashboard/twins_table.dart';

void main() {
  // Factory for test twins
  Twin createTestTwin({
    required String id,
    required String name,
    String state = 'draft',
    List<String> providers = const ['AWS'],
  }) {
    return Twin(
      id: id,
      name: name,
      state: state,
      providers: providers,
      createdAt: DateTime.utc(2026),
      updatedAt: DateTime.utc(2026),
    );
  }

  group('TwinsTable', () {
    testWidgets('shows empty state when no twins', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: TwinsTable(
              twins: const [],
              onRefresh: () {},
              onEdit: (_) {},
              onDelete: (_) {},
            ),
          ),
        ),
      );

      expect(find.text('No Digital Twins Yet'), findsOneWidget);
      expect(
        find.text('Create your first twin to get started'),
        findsOneWidget,
      );
    });

    testWidgets('displays twin names', (tester) async {
      final twins = [
        createTestTwin(id: '1', name: 'Test Twin 1'),
        createTestTwin(id: '2', name: 'Test Twin 2'),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: TwinsTable(
                twins: twins,
                onRefresh: () {},
                onEdit: (_) {},
                onDelete: (_) {},
              ),
            ),
          ),
        ),
      );

      expect(find.text('Test Twin 1'), findsOneWidget);
      expect(find.text('Test Twin 2'), findsOneWidget);
    });

    testWidgets('shows provider chips', (tester) async {
      final twins = [
        createTestTwin(
          id: '1',
          name: 'Multi-Cloud Twin',
          providers: ['AWS', 'AZURE'],
        ),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: TwinsTable(
                twins: twins,
                onRefresh: () {},
                onEdit: (_) {},
                onDelete: (_) {},
              ),
            ),
          ),
        ),
      );

      expect(find.text('AWS'), findsOneWidget);
      expect(find.text('AZURE'), findsOneWidget);
    });

    testWidgets('shows state badges', (tester) async {
      final twins = [
        createTestTwin(id: '1', name: 'Draft Twin', state: 'draft'),
        createTestTwin(id: '2', name: 'Deployed Twin', state: 'deployed'),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: TwinsTable(
                twins: twins,
                onRefresh: () {},
                onEdit: (_) {},
                onDelete: (_) {},
              ),
            ),
          ),
        ),
      );

      expect(find.text('DRAFT'), findsOneWidget);
      expect(find.text('DEPLOYED'), findsOneWidget);
    });

    testWidgets('shows edit and delete icons for each twin', (tester) async {
      final twins = [createTestTwin(id: '1', name: 'Test Twin')];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: TwinsTable(
                twins: twins,
                onRefresh: () {},
                onEdit: (_) {},
                onDelete: (_) {},
              ),
            ),
          ),
        ),
      );

      // Verify icons exist
      expect(find.byIcon(Icons.edit), findsWidgets);
      expect(find.byIcon(Icons.delete), findsWidgets);
    });

    testWidgets('displays the required update timestamp', (tester) async {
      final twins = [createTestTwin(id: '1', name: 'Test Twin')];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: TwinsTable(
                twins: twins,
                onRefresh: () {},
                onEdit: (_) {},
                onDelete: (_) {},
              ),
            ),
          ),
        ),
      );

      expect(find.text('1/1/2026'), findsOneWidget);
    });
  });
}
