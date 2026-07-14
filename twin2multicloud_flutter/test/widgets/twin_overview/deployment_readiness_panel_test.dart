import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_readiness.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/deployment_readiness_panel.dart';

void main() {
  Widget buildWidget(
    DeploymentReadinessViewState state, {
    VoidCallback? onRunPreflight,
    VoidCallback? onOpenCloudAccounts,
    double width = 1000,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: SizedBox(
          width: width,
          child: SingleChildScrollView(
            child: DeploymentReadinessPanel(
              state: state,
              onRunPreflight: onRunPreflight ?? () {},
              onOpenCloudAccounts: onOpenCloudAccounts ?? () {},
            ),
          ),
        ),
      ),
    );
  }

  testWidgets('renders concise ready state with collapsed provider evidence', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildWidget(
        DeploymentReadinessViewState.fromSnapshot(_snapshot(ready: true)),
      ),
    );

    expect(find.text('Deployment readiness'), findsOneWidget);
    expect(find.text('Ready'), findsOneWidget);
    expect(find.text('AWS'), findsOneWidget);
    expect(find.text('Access passed.'), findsNothing);

    await tester.tap(find.text('Provider details'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Access passed.'), findsOneWidget);
  });

  testWidgets('expands blocking evidence and invokes remediation actions', (
    tester,
  ) async {
    var preflightRuns = 0;
    var accountOpens = 0;
    await tester.pumpWidget(
      buildWidget(
        DeploymentReadinessViewState.fromSnapshot(_snapshot(ready: false)),
        onRunPreflight: () => preflightRuns += 1,
        onOpenCloudAccounts: () => accountOpens += 1,
        width: 640,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Run preflight'), findsOneWidget);
    expect(find.text('Cloud accounts'), findsOneWidget);
    expect(find.textContaining('Preflight has not been run.'), findsOneWidget);
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('Run preflight'));
    await tester.tap(find.text('Cloud accounts'));
    expect(preflightRuns, 1);
    expect(accountOpens, 1);
  });

  testWidgets('shows stable loading and failed states', (tester) async {
    final previous = _snapshot(ready: false);
    await tester.pumpWidget(
      buildWidget(DeploymentReadinessViewState.loading(previous: previous)),
    );

    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    final loadingButton = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, 'Run preflight'),
    );
    expect(loadingButton.onPressed, isNull);

    await tester.pumpWidget(
      buildWidget(
        DeploymentReadinessViewState.failed(
          'Readiness service unavailable.',
          previous: previous,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Readiness service unavailable.'), findsOneWidget);
    expect(find.text('Unavailable'), findsOneWidget);
  });
}

DeploymentReadinessSnapshot _snapshot({required bool ready}) {
  final check = DeploymentReadinessCheck(
    component: ready ? 'deployer' : 'configuration',
    status: ready
        ? DeploymentReadinessCheckStatus.passed
        : DeploymentReadinessCheckStatus.failed,
    code: ready ? 'OK' : 'PREFLIGHT_NOT_RUN',
    message: ready ? 'Access passed.' : 'Preflight has not been run.',
    action: ready ? 'No action required.' : 'Run deployment preflight.',
    permissions: const [],
  );
  return DeploymentReadinessSnapshot(
    schemaVersion: DeploymentReadinessSnapshot.cachedSchemaVersion,
    source: DeploymentReadinessSource.cached,
    twinId: 'twin-1',
    ready: ready,
    summary: ready
        ? 'All required providers are ready for deployment.'
        : '1 of 1 required providers need review.',
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
        summary: check.message,
        expectedPermissionSetVersion: 'thesis-demo-v1',
        suppliedPermissionSetVersion: 'thesis-demo-v1',
        permissionSetStatus: PermissionSetReadinessStatus.matched,
        checkedAt: ready ? DateTime.utc(2026, 7, 14, 9) : null,
        checks: [check],
      ),
    ],
    checkedAt: ready ? DateTime.utc(2026, 7, 14, 9) : null,
    issues: const [],
  );
}
