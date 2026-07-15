import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_operations.dart';
import 'package:twin2multicloud_flutter/models/deployment_readiness.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/deployment_operations_panel.dart';

void main() {
  Widget buildWidget({
    required TwinOverviewLoaded state,
    ThemeData? theme,
    VoidCallback? onDeploy,
    VoidCallback? onDestroy,
    VoidCallback? onViewLogs,
    VoidCallback? onCloseTerminal,
  }) {
    return MaterialApp(
      theme: theme,
      home: Scaffold(
        body: SingleChildScrollView(
          child: DeploymentOperationsPanel(
            twinState: state.twinState,
            canDeploy: state.canDeploy,
            canDestroy: state.canDestroy,
            readiness: state.deploymentReadiness,
            operation: state.deploymentOperation,
            lastError: state.lastError,
            onDeploy: onDeploy ?? () {},
            onDestroy: onDestroy ?? () {},
            onViewLogs: onViewLogs ?? () {},
            onCloseTerminal: onCloseTerminal ?? () {},
          ),
        ),
      ),
    );
  }

  group('DeploymentOperationsPanel', () {
    testWidgets('renders deploy actions and invokes callbacks', (tester) async {
      var deployed = false;

      await tester.pumpWidget(
        buildWidget(
          state: _state(twinState: 'configured', canDeploy: true),
          onDeploy: () => deployed = true,
        ),
      );

      await tester.tap(find.text('DEPLOY'));
      await tester.pump();

      expect(deployed, isTrue);
      expect(find.text('DESTROY'), findsOneWidget);
    });

    testWidgets('blocks deploy with an adjacent readiness explanation', (
      tester,
    ) async {
      var deployed = false;
      await tester.pumpWidget(
        buildWidget(
          state: _state(
            twinState: 'configured',
            canDeploy: true,
            readinessReady: false,
          ),
          onDeploy: () => deployed = true,
        ),
      );

      expect(
        find.text(
          'Deployment is blocked until the current provider preflight passes.',
        ),
        findsOneWidget,
      );
      await tester.tap(find.text('DEPLOY'));
      await tester.pump();
      expect(deployed, isFalse);
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

    testWidgets('shows reconnect state and actionable operation detail', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildWidget(
          state: _state(
            twinState: 'deploying',
            showTerminal: true,
            operationPhase: DeploymentOperationViewPhase.reconnecting,
            operationMessage: 'Connection lost. Reconnecting (1/3).',
          ),
        ),
      );

      expect(find.text('Reconnecting...'), findsOneWidget);
      expect(find.text('Connection lost. Reconnecting (1/3).'), findsOneWidget);
      expect(
        find.text('Connection lost. Attempting to reconnect...'),
        findsOneWidget,
      );
    });

    testWidgets('stacks commands at 640 pixels without overflowing', (
      tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(640, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        buildWidget(
          theme: ThemeData.dark(),
          state: _state(
            twinState: 'error',
            canDeploy: true,
            canDestroy: true,
            lastError:
                'Terraform failed while reconciling the selected provider resources.',
          ),
        ),
      );

      final deployTop = tester.getTopLeft(find.text('RETRY DEPLOY'));
      final destroyTop = tester.getTopLeft(find.text('CLEANUP'));
      expect(destroyTop.dy, greaterThan(deployTop.dy));
      expect(find.text('View Logs'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  });
}

TwinOverviewLoaded _state({
  String twinState = 'draft',
  bool canDeploy = false,
  bool canDestroy = false,
  bool canEdit = true,
  bool canDelete = true,
  String? lastError,
  bool showTerminal = false,
  List<String> terminalLogs = const [],
  bool readinessReady = true,
  DeploymentOperationViewPhase operationPhase =
      DeploymentOperationViewPhase.streaming,
  String? operationMessage,
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
    deploymentReadiness: DeploymentReadinessViewState.fromSnapshot(
      _readinessSnapshot(readinessReady),
    ),
    lastError: lastError,
    deploymentOperation: DeploymentOperationViewState(
      phase: showTerminal ? operationPhase : DeploymentOperationViewPhase.idle,
      operationType: showTerminal ? DeploymentOperationType.deploy : null,
      session: showTerminal
          ? const OperationSession(
              sessionId: 'session-1',
              sseUrl: '/sse/deploy/session-1',
            )
          : null,
      logs: [
        for (var index = 0; index < terminalLogs.length; index += 1)
          DeploymentLogEntry(
            eventId: index + 1,
            sessionId: 'session-1',
            timestamp: DateTime.utc(2026, 7, 14, 12, 0, index),
            level: 'info',
            message: terminalLogs[index],
            operationType: 'deploy',
          ),
      ],
      lastEventId: terminalLogs.length,
      showLogs: showTerminal,
      message: operationMessage,
    ),
  );
}

DeploymentReadinessSnapshot _readinessSnapshot(bool ready) {
  const failedCheck = DeploymentReadinessCheck(
    component: 'configuration',
    status: DeploymentReadinessCheckStatus.failed,
    code: 'PREFLIGHT_NOT_RUN',
    message: 'Preflight has not been run.',
    action: 'Run preflight.',
    permissions: [],
  );
  const passedCheck = DeploymentReadinessCheck(
    component: 'deployer',
    status: DeploymentReadinessCheckStatus.passed,
    code: 'OK',
    message: 'Access passed.',
    action: 'No action required.',
    permissions: [],
  );
  return DeploymentReadinessSnapshot(
    schemaVersion: DeploymentReadinessSnapshot.cachedSchemaVersion,
    source: DeploymentReadinessSource.cached,
    twinId: 'twin-1',
    ready: ready,
    summary: ready ? 'Ready.' : 'Review required.',
    requiredProviders: const [CloudProvider.aws],
    providers: [
      ProviderDeploymentReadiness(
        provider: CloudProvider.aws,
        connectionId: 'connection-1',
        connectionDisplayName: 'AWS deployment',
        ready: ready,
        status: ready
            ? ProviderDeploymentReadinessStatus.ready
            : ProviderDeploymentReadinessStatus.notChecked,
        summary: ready ? 'Ready.' : 'Not checked.',
        expectedPermissionSetVersion: 'thesis-demo-v1',
        suppliedPermissionSetVersion: 'thesis-demo-v1',
        permissionSetStatus: PermissionSetReadinessStatus.matched,
        checks: [ready ? passedCheck : failedCheck],
      ),
    ],
    issues: const [],
  );
}
