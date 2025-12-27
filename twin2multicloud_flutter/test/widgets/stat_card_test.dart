import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/stat_card.dart';

void main() {
  // Helper to build widget with required parent (StatCard uses Expanded)
  Widget buildTestWidget({
    required String title,
    required String value,
    required IconData icon,
    Color? color,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: Row(
          children: [
            StatCard(
              title: title,
              value: value,
              icon: icon,
              color: color,
            ),
          ],
        ),
      ),
    );
  }

  group('StatCard', () {
    // ============================================================
    // Happy Path Tests
    // ============================================================

    testWidgets('renders title and value', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        title: 'Total Cost',
        value: '\$1,234.56',
        icon: Icons.attach_money,
      ));

      expect(find.text('Total Cost'), findsOneWidget);
      expect(find.text('\$1,234.56'), findsOneWidget);
    });

    testWidgets('displays icon correctly', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        title: 'Devices',
        value: '100',
        icon: Icons.devices,
      ));

      expect(find.byIcon(Icons.devices), findsOneWidget);
    });

    testWidgets('renders with custom color', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        title: 'Status',
        value: 'Active',
        icon: Icons.check_circle,
        color: Colors.green,
      ));

      // Find icon and verify it exists
      expect(find.byIcon(Icons.check_circle), findsOneWidget);
    });

    // ============================================================
    // Edge Case Tests
    // ============================================================

    testWidgets('handles empty value', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        title: 'Empty',
        value: '',
        icon: Icons.warning,
      ));

      expect(find.text('Empty'), findsOneWidget);
    });

    testWidgets('renders in Card container', (tester) async {
      await tester.pumpWidget(buildTestWidget(
        title: 'Test',
        value: '42',
        icon: Icons.info,
      ));

      expect(find.byType(Card), findsOneWidget);
    });
  });
}
