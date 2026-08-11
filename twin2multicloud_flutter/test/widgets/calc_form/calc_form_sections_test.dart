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

  testWidgets('Five-layer v2 initializes Small and emits only canonical fields', (
    tester,
  ) async {
    CalcParams? changed;
    await tester.binding.setSurfaceSize(const Size(1000, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              profileId: 'five-layer-baseline',
              profileVersion: '2',
              section: CalcFormSection.scenarioAndCurrency,
              onChanged: (params) => changed = params,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(changed?.scenario, FiveLayerWorkloadScenario.small);
    expect(changed?.toJson()['eventingScenarioId'], 'eventing-small-v1');
    expect(changed?.toJson(), isNot(contains('useEventChecking')));
    expect(
      find.text(
        'Events are embedded and always active in Five-layer v2. '
        'They are part of the frozen comparison workload and cannot be disabled.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('Five-layer v2 scenario and currency selection stays frozen', (
    tester,
  ) async {
    CalcParams? changed;
    await tester.binding.setSurfaceSize(const Size(1000, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              profileId: 'five-layer-baseline',
              profileVersion: '2',
              section: CalcFormSection.scenarioAndCurrency,
              initialParams: CalcParams.fiveLayerV2(
                scenario: FiveLayerWorkloadScenario.small,
              ),
              onChanged: (params) => changed = params,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(
      find.byKey(const ValueKey('five-layer-v2-scenario-large')),
    );
    await tester.pump();
    await tester.tap(find.text('EUR (€)'));
    await tester.pump();

    expect(changed?.scenario, FiveLayerWorkloadScenario.large);
    expect(changed?.currency, 'EUR');
    expect(changed?.eventingScenarioId, 'eventing-large-v1');
    expect(changed?.numberOfDevices, 30000);
    expect(changed?.hotStorageDurationInMonths, 1);
  });

  testWidgets('Five-layer v2 processing is read-only embedded event evidence', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              profileId: 'five-layer-baseline',
              profileVersion: '2',
              section: CalcFormSection.processing,
              initialParams: CalcParams.fiveLayerV2(
                scenario: FiveLayerWorkloadScenario.medium,
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('eventing-medium-v1'), findsOneWidget);
    expect(find.text('Mandatory'), findsNWidgets(2));
    expect(find.byType(Switch), findsNothing);
    expect(find.byType(TextFormField), findsNothing);
  });

  testWidgets(
    'Five-layer v2 scenario cards follow all supported responsive boundaries',
    (tester) async {
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPhysicalSize);
      for (final width in [640.0, 719.0, 720.0, 959.0, 960.0, 1199.0, 1200.0]) {
        tester.view.physicalSize = Size(width, 1800);
        await tester.pumpWidget(
          MaterialApp(
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(
                context,
              ).copyWith(textScaler: const TextScaler.linear(2)),
              child: child!,
            ),
            home: Scaffold(
              body: SingleChildScrollView(
                child: CalcForm(
                  profileId: 'five-layer-baseline',
                  profileVersion: '2',
                  section: CalcFormSection.scenarioAndCurrency,
                  initialParams: CalcParams.fiveLayerV2(
                    scenario: FiveLayerWorkloadScenario.small,
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pump();

        final columns = width >= 1200
            ? 3
            : width >= 960
            ? 2
            : 1;
        final expectedWidth = (width - (columns - 1) * 16) / columns;
        for (final scenario in FiveLayerWorkloadScenario.values) {
          final size = tester.getSize(
            find.byKey(
              ValueKey('five-layer-v2-scenario-card-${scenario.name}'),
            ),
          );
          expect(size.width, closeTo(expectedWidth, 0.01), reason: '$width');
        }
        expect(tester.takeException(), isNull, reason: '$width');
      }
    },
  );
}
