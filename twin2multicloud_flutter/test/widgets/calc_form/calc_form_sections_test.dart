import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/widgets/calc_form/calc_form.dart';

void main() {
  testWidgets('device traffic shows only its focused field group', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              section: CalcFormSection.deviceTraffic,
              initialParams: CalcParams.defaultParams(),
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Number of IoT Devices'), findsOneWidget);
    expect(find.text('Hot Storage Duration'), findsNothing);
    expect(find.text('Enable Event Checking'), findsNothing);
    expect(find.text('Currency:'), findsNothing);
  });

  testWidgets('twin capabilities combines 3D and dashboard intent', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              section: CalcFormSection.twinCapabilities,
              initialParams: CalcParams.defaultParams(),
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Is a 3D Model Necessary?'), findsOneWidget);
    expect(find.text('Dashboard Refreshes per Hour'), findsOneWidget);
    expect(find.text('Number of IoT Devices'), findsNothing);
  });

  testWidgets('ADT billing assumptions stay collapsed and emit valid values', (
    tester,
  ) async {
    CalcParams? changed;
    await tester.binding.setSurfaceSize(const Size(1000, 1000));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              section: CalcFormSection.twinCapabilities,
              initialParams: CalcParams.defaultParams(),
              onChanged: (params) => changed = params,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Azure Digital Twins assumptions'), findsOneWidget);
    expect(find.text('Query Units per Query'), findsNothing);

    await tester.tap(find.text('Azure Digital Twins assumptions'));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('adt-query-units-input')),
      '2.5',
    );
    await tester.enterText(
      find.byKey(const ValueKey('adt-query-response-size-input')),
      '1.25',
    );
    await tester.pump();

    expect(changed?.averageDigitalTwinQueryUnitsPerQuery, 2.5);
    expect(changed?.averageDigitalTwinQueryResponseSizeInKb, 1.25);

    await tester.enterText(
      find.byKey(const ValueKey('adt-query-units-input')),
      '0',
    );
    await tester.pump();

    expect(find.text('Must be greater than 0.0'), findsOneWidget);
    expect(changed?.averageDigitalTwinQueryUnitsPerQuery, 2.5);
  });

  testWidgets(
    'processing exposes legacy unsupported topology without coercion',
    (tester) async {
      bool? isValid;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: CalcForm(
                section: CalcFormSection.processing,
                initialParams: CalcParams.fromJson({
                  ...CalcParams.defaultParams().toJson(),
                  'integrateErrorHandling': true,
                }),
                onValidChanged: (value) => isValid = value,
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump();

      expect(find.text('Legacy, not deployable'), findsOneWidget);
      expect(tester.widget<Switch>(find.byType(Switch).last).value, isTrue);
      expect(isValid, isFalse);
    },
  );
}
