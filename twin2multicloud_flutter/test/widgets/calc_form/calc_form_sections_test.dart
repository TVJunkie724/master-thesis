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
}
