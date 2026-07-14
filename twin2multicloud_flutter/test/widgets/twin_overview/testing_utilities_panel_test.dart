import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/testing_utilities_panel.dart';

void main() {
  Widget buildPanel({
    TraceViewState trace = const TraceViewState(),
    SimulatorDownloadViewState simulator = const SimulatorDownloadViewState(),
    VoidCallback? onStart,
    VoidCallback? onCancel,
    VoidCallback? onDownload,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: TestingUtilitiesPanel(
            provider: 'aws',
            trace: trace,
            simulator: simulator,
            onStartTrace: onStart ?? () {},
            onCancelTrace: onCancel ?? () {},
            onDownloadSimulator: onDownload ?? () {},
          ),
        ),
      ),
    );
  }

  testWidgets('renders compact actions and invokes idle callbacks', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(500, 800));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    var started = false;
    var downloaded = false;

    await tester.pumpWidget(
      buildPanel(
        onStart: () => started = true,
        onDownload: () => downloaded = true,
      ),
    );

    await tester.tap(find.byKey(const Key('start-trace')));
    await tester.tap(find.byKey(const Key('download-simulator')));
    await tester.pump();

    expect(started, isTrue);
    expect(downloaded, isTrue);
    expect(find.text('AWS'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'shows active trace cancellation and keeps diagnostics collapsed',
    (tester) async {
      var cancelled = false;
      await tester.pumpWidget(
        buildPanel(
          trace: const TraceViewState(
            phase: TraceViewPhase.streaming,
            diagnostics: ['Provider accepted telemetry.'],
          ),
          onCancel: () => cancelled = true,
        ),
      );

      expect(find.text('Provider accepted telemetry.'), findsNothing);
      await tester.tap(find.byKey(const Key('cancel-trace')));
      await tester.tap(find.byKey(const Key('trace-diagnostics')));
      await tester.pump(const Duration(milliseconds: 300));

      expect(cancelled, isTrue);
      expect(find.text('Provider accepted telemetry.'), findsOneWidget);
    },
  );

  testWidgets(
    'disables duplicate simulator requests while package is prepared',
    (tester) async {
      var downloads = 0;
      await tester.pumpWidget(
        buildPanel(
          simulator: const SimulatorDownloadViewState(
            phase: SimulatorDownloadViewPhase.requesting,
            provider: 'aws',
            message: 'Preparing the aws simulator package.',
          ),
          onDownload: () => downloads += 1,
        ),
      );

      await tester.tap(find.byKey(const Key('download-simulator')));
      await tester.pump();

      expect(downloads, 0);
      expect(find.text('Preparing package'), findsOneWidget);
    },
  );

  testWidgets('renders wide layout without overflow for terminal states', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1100, 700));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      buildPanel(
        trace: const TraceViewState(
          phase: TraceViewPhase.failed,
          message: 'Trace connection failed.',
        ),
        simulator: const SimulatorDownloadViewState(
          phase: SimulatorDownloadViewPhase.saved,
          filename: 'simulator.zip',
          message: 'Simulator package saved.',
        ),
      ),
    );

    expect(find.text('Trace connection failed.'), findsOneWidget);
    expect(find.text('Simulator package saved.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
