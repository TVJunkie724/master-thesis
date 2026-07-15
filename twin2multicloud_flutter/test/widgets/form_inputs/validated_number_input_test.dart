// test/widgets/form_inputs/validated_number_input_test.dart
// Tests for ValidatedNumberInput widget

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/form_inputs/validated_number_input.dart';

void main() {
  group('ValidatedNumberInput', () {
    group('basic functionality', () {
      testWidgets('displays label', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Test Label',
                value: 42,
                onChanged: (_) {},
              ),
            ),
          ),
        );

        expect(find.text('Test Label'), findsOneWidget);
      });

      testWidgets('displays initial value', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Count',
                value: 100,
                onChanged: (_) {},
              ),
            ),
          ),
        );

        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, '100');
      });

      testWidgets('calls onChanged with parsed value', (tester) async {
        int? changedValue;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Number',
                value: null,
                onChanged: (v) => changedValue = v,
              ),
            ),
          ),
        );

        await tester.enterText(find.byType(TextField), '42');
        await tester.pump();

        expect(changedValue, 42);
      });
    });

    group('validation', () {
      testWidgets('input formatter blocks non-numeric chars', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Number',
                value: null,
                onChanged: (_) {},
              ),
            ),
          ),
        );

        // Try to enter non-numeric - formatter blocks it
        await tester.enterText(find.byType(TextField), 'abc');
        await tester.pump();

        // Field should be empty since formatter rejected it
        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, '');
      });

      testWidgets('shows error for value below minimum', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Number',
                value: null,
                minValue: 10,
                onChanged: (_) {},
              ),
            ),
          ),
        );

        await tester.enterText(find.byType(TextField), '5');
        await tester.pump();

        expect(find.textContaining('Minimum'), findsOneWidget);
      });

      testWidgets('shows error for value above maximum', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Number',
                value: null,
                maxValue: 100,
                onChanged: (_) {},
              ),
            ),
          ),
        );

        await tester.enterText(find.byType(TextField), '200');
        await tester.pump();

        expect(find.textContaining('Maximum'), findsOneWidget);
      });
    });

    group('disabled state', () {
      testWidgets('disables input when enabled is false', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Disabled',
                value: 42,
                enabled: false,
                onChanged: (_) {},
              ),
            ),
          ),
        );

        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.enabled, false);
      });
    });

    group('edge cases', () {
      testWidgets('handles null initial value', (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Optional',
                value: null,
                onChanged: (_) {},
              ),
            ),
          ),
        );

        final textField = tester.widget<TextField>(find.byType(TextField));
        expect(textField.controller?.text, '');
      });

      testWidgets('handles negative numbers', (tester) async {
        int? changedValue;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Number',
                value: null,
                onChanged: (v) => changedValue = v,
              ),
            ),
          ),
        );

        await tester.enterText(find.byType(TextField), '-10');
        await tester.pump();

        expect(changedValue, -10);
      });

      testWidgets('clears value on empty input', (tester) async {
        int? changedValue = 99;

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ValidatedNumberInput(
                label: 'Number',
                value: 42,
                onChanged: (v) => changedValue = v,
              ),
            ),
          ),
        );

        await tester.enterText(find.byType(TextField), '');
        await tester.pump();

        expect(changedValue, null);
      });
    });
  });
}
