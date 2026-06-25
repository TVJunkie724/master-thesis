import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_command_center.dart';

void main() {
  Widget buildWidget({
    required TwinOverviewLoaded state,
    VoidCallback? onEdit,
    VoidCallback? onDelete,
    VoidCallback? onDeploy,
    VoidCallback? onDestroy,
    VoidCallback? onStartLogTrace,
    VoidCallback? onDownloadSimulator,
    VoidCallback? onViewLogs,
    VoidCallback? onCloseTerminal,
    ValueChanged<String>? onOutputCopyFeedback,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: TwinOverviewCommandCenter(
            state: state,
            onEdit: onEdit ?? () {},
            onDelete: onDelete ?? () {},
            onDeploy: onDeploy ?? () {},
            onDestroy: onDestroy ?? () {},
            onStartLogTrace: onStartLogTrace ?? () {},
            onDownloadSimulator: onDownloadSimulator ?? () {},
            onViewLogs: onViewLogs ?? () {},
            onCloseTerminal: onCloseTerminal ?? () {},
            onOutputCopyFeedback: onOutputCopyFeedback ?? (_) {},
          ),
        ),
      ),
    );
  }

  group('TwinOverviewCommandCenter', () {
    testWidgets('renders deploy actions and invokes callbacks', (tester) async {
      var deployed = false;
      var edited = false;

      await tester.pumpWidget(
        buildWidget(
          state: _state(twinState: 'configured', canDeploy: true),
          onDeploy: () => deployed = true,
          onEdit: () => edited = true,
        ),
      );

      await tester.tap(find.text('DEPLOY'));
      await tester.tap(find.text('Edit'));
      await tester.pump();

      expect(deployed, isTrue);
      expect(edited, isTrue);
      expect(find.text('DESTROY'), findsOneWidget);
    });

    testWidgets('shows deployed testing utilities', (tester) async {
      var traced = false;
      var downloaded = false;

      await tester.pumpWidget(
        buildWidget(
          state: _state(
            twinState: 'deployed',
            canDestroy: true,
            canEdit: false,
            canDelete: false,
            cheapestPath: const {'l1': 'aws'},
          ),
          onStartLogTrace: () => traced = true,
          onDownloadSimulator: () => downloaded = true,
        ),
      );

      await tester.tap(find.text('Send Test Message'));
      await tester.tap(find.text('Download AWS Simulator'));
      await tester.pump();

      expect(find.text('TESTING UTILITIES'), findsOneWidget);
      expect(traced, isTrue);
      expect(downloaded, isTrue);
    });

    testWidgets('shows error logs action for failed deployments', (
      tester,
    ) async {
      var viewedLogs = false;

      await tester.pumpWidget(
        buildWidget(
          state: _state(
            twinState: 'error',
            canDeploy: true,
            canDestroy: true,
            lastError: 'Terraform failed',
          ),
          onViewLogs: () => viewedLogs = true,
        ),
      );

      expect(find.text('Deployment Failed'), findsOneWidget);

      await tester.tap(find.text('View Logs'));
      await tester.pump();

      expect(viewedLogs, isTrue);
    });

    testWidgets('shows terminal and close action', (tester) async {
      var closed = false;

      await tester.pumpWidget(
        buildWidget(
          state: _state(
            twinState: 'deploying',
            showTerminal: true,
            terminalLogs: const ['Starting deployment'],
          ),
          onCloseTerminal: () => closed = true,
        ),
      );

      expect(find.text('Deployment Output'), findsOneWidget);
      expect(find.textContaining('Starting deployment'), findsOneWidget);

      await tester.tap(find.byTooltip('Close terminal'));
      await tester.pump();

      expect(closed, isTrue);
    });
  });
}

TwinOverviewLoaded _state({
  String twinState = 'draft',
  bool canDeploy = false,
  bool canDestroy = false,
  bool canEdit = true,
  bool canDelete = true,
  Map<String, dynamic>? cheapestPath,
  String? lastError,
  bool showTerminal = false,
  List<String> terminalLogs = const [],
}) {
  return TwinOverviewLoaded(
    twinId: 'twin-1',
    projectName: 'Demo Twin',
    cloudResourceName: 'cloud-demo',
    twinState: twinState,
    canDeploy: canDeploy,
    canDestroy: canDestroy,
    canEdit: canEdit,
    canDelete: canDelete,
    cheapestPath: cheapestPath,
    lastError: lastError,
    showTerminal: showTerminal,
    terminalLogs: terminalLogs,
  );
}
