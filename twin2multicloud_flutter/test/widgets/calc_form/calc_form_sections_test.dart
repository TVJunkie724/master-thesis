import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/widgets/calc_form/calc_form.dart';

void main() {
  for (final profile in [null, 'five-layer', 'unknown']) {
    testWidgets('missing or retired profile $profile cannot emit a workload', (
      tester,
    ) async {
      CalcParams? changed;
      bool? valid;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: CalcForm(
              profileId: profile,
              profileVersion: '1',
              initialParams: CalcParams.defaultParams(),
              onChanged: (value) => changed = value,
              onValidChanged: (value) => valid = value,
            ),
          ),
        ),
      );
      await tester.pump();
      expect(changed, isNull);
      expect(valid, isFalse);
      expect(
        find.textContaining('verified Six-layer architecture'),
        findsOneWidget,
      );
      expect(find.byType(TextFormField), findsNothing);
      expect(find.byType(Switch), findsNothing);
    });
  }

  testWidgets(
    'profile arrival restores saved scenario and removal blocks output',
    (tester) async {
      final saved = CalcParams.sixLayer(
        scenario: SixLayerWorkloadScenario.medium,
        currency: 'EUR',
      );
      final changes = <CalcParams>[];
      bool? valid;
      Widget form(String? profile, String? version) => MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              profileId: profile,
              profileVersion: version,
              initialParams: saved,
              section: CalcFormSection.processing,
              onChanged: changes.add,
              onValidChanged: (value) => valid = value,
            ),
          ),
        ),
      );
      await tester.pumpWidget(form(null, null));
      await tester.pump();
      expect(changes, isEmpty);
      await tester.pumpWidget(form('six-layer-eventing', '1'));
      await tester.pump();
      expect(changes.last.scenario, SixLayerWorkloadScenario.medium);
      expect(changes.last.currency, 'EUR');
      expect(valid, isTrue);
      final count = changes.length;
      await tester.pumpWidget(form('six-layer-eventing', '2'));
      await tester.pump();
      expect(changes.length, count);
      expect(valid, isFalse);
    },
  );

  testWidgets(
    'historical input stays readable but cannot restore legacy controls',
    (tester) async {
      final historical = CalcParams.defaultParams();
      final original = historical.toJson();
      CalcParams? changed;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: CalcForm(
                profileId: 'six-layer-eventing',
                profileVersion: '1',
                initialParams: historical,
                section: CalcFormSection.deviceTraffic,
                onChanged: (value) => changed = value,
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(historical.toJson(), original);
      expect(changed?.scenario, SixLayerWorkloadScenario.small);
      expect(changed?.numberOfDevices, 100);
      expect(find.text('Devices'), findsOneWidget);
      expect(find.byType(TextFormField), findsNothing);
      expect(find.text('Currency:'), findsNothing);
    },
  );

  testWidgets('Six-layer initializes Small and emits only canonical fields', (
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
              profileId: 'six-layer-eventing',
              profileVersion: '1',
              section: CalcFormSection.scenarioAndCurrency,
              onChanged: (params) => changed = params,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(changed?.scenario, SixLayerWorkloadScenario.small);
    expect(changed?.toJson()['eventingScenarioId'], 'eventing-small-v1');
    expect(changed?.toJson(), isNot(contains('useEventChecking')));
    expect(
      find.text(
        'Events use the independent Event Layer and are always active in the standalone Six-layer profile. '
        'They are part of the canonical PoC workload and cannot be disabled.',
      ),
      findsOneWidget,
    );
  });

  testWidgets('Six-layer scenario and currency selection stays frozen', (
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
              profileId: 'six-layer-eventing',
              profileVersion: '1',
              section: CalcFormSection.scenarioAndCurrency,
              initialParams: CalcParams.sixLayer(
                scenario: SixLayerWorkloadScenario.small,
              ),
              onChanged: (params) => changed = params,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    await tester.tap(find.byKey(const ValueKey('six-layer-scenario-large')));
    await tester.pump();
    await tester.tap(find.text('EUR (€)'));
    await tester.pump();

    expect(changed?.scenario, SixLayerWorkloadScenario.large);
    expect(changed?.currency, 'EUR');
    expect(changed?.eventingScenarioId, 'eventing-large-v1');
    expect(changed?.numberOfDevices, 30000);
    expect(changed?.hotStorageDurationInMonths, 1);
  });

  testWidgets('Six-layer processing is read-only embedded event evidence', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              profileId: 'six-layer-eventing',
              profileVersion: '1',
              section: CalcFormSection.processing,
              initialParams: CalcParams.sixLayer(
                scenario: SixLayerWorkloadScenario.medium,
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

  testWidgets('Six-layer v1 reuses the frozen workload without an event flag', (
    tester,
  ) async {
    CalcParams? changed;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              profileId: 'six-layer-eventing',
              profileVersion: '1',
              section: CalcFormSection.processing,
              onChanged: (params) => changed = params,
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(changed?.eventingScenarioId, 'eventing-small-v1');
    expect(changed?.toJson(), isNot(contains('useEventChecking')));
    expect(find.text('Independent Event Layer workload'), findsOneWidget);
    expect(find.byType(Switch), findsNothing);
  });

  testWidgets('Phase 8 twin capabilities omit historical 3D language', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: CalcForm(
              profileId: 'six-layer-eventing',
              profileVersion: '1',
              section: CalcFormSection.twinCapabilities,
              initialParams: CalcParams.sixLayer(
                scenario: SixLayerWorkloadScenario.small,
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pump();

    expect(find.text('Twin and dashboard activity'), findsOneWidget);
    expect(find.text('Twin entities'), findsOneWidget);
    expect(find.textContaining('3D representation'), findsNothing);
    expect(find.text('Is a 3D Model Necessary?'), findsNothing);
  });

  testWidgets(
    'Six-layer scenario cards follow all supported responsive boundaries',
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
                  profileId: 'six-layer-eventing',
                  profileVersion: '1',
                  section: CalcFormSection.scenarioAndCurrency,
                  initialParams: CalcParams.sixLayer(
                    scenario: SixLayerWorkloadScenario.small,
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
        for (final scenario in SixLayerWorkloadScenario.values) {
          final size = tester.getSize(
            find.byKey(ValueKey('six-layer-scenario-card-${scenario.name}')),
          );
          expect(size.width, closeTo(expectedWidth, 0.01), reason: '$width');
        }
        expect(tester.takeException(), isNull, reason: '$width');
      }
    },
  );
}
