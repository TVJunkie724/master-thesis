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
    VoidCallback? onReviewPreparation,
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
              onReviewPreparation: onReviewPreparation ?? () {},
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

  testWidgets('shows graph requirements and opens bounded preparation review', (
    tester,
  ) async {
    var reviews = 0;
    await tester.pumpWidget(
      buildWidget(
        DeploymentReadinessViewState.fromSnapshot(_preparableSnapshot()),
        onReviewPreparation: () => reviews += 1,
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Review preparation'), findsOneWidget);
    expect(find.textContaining('project API can be enabled'), findsOneWidget);
    await tester.tap(find.text('Review preparation'));
    expect(reviews, 1);
  });
}

DeploymentReadinessSnapshot _preparableSnapshot() {
  const graphDigest =
      'sha256:1111111111111111111111111111111111111111111111111111111111111111';
  const requirementsDigest =
      'sha256:2222222222222222222222222222222222222222222222222222222222222222';
  const planDigest =
      'sha256:3333333333333333333333333333333333333333333333333333333333333333';
  const requirement = DeploymentRequirementReadiness(
    requirementId: 'gcp:serviceusage.googleapis.com',
    requirementType: 'provider_api',
    provider: CloudProvider.gcp,
    capabilityId: 'serviceusage.googleapis.com',
    preparationMode: DeploymentPreparationMode.confirmedAccount,
    mandatory: true,
    status: DeploymentRequirementReadinessStatus.preparable,
    message: 'The project API can be enabled automatically.',
    action: 'Confirm the provider preparation.',
    sourceNodeIds: ['l1'],
    sourceEdgeIds: [],
  );
  const check = DeploymentReadinessCheck(
    component: 'deployer',
    status: DeploymentReadinessCheckStatus.passed,
    code: 'OK',
    message: 'Connection access passed.',
    action: 'No action required.',
    permissions: [],
  );
  const action = AccountPreparationAction(
    actionId: 'gcp:enable:serviceusage.googleapis.com',
    provider: CloudProvider.gcp,
    actionType: 'enable_project_api',
    capabilityId: 'serviceusage.googleapis.com',
    scope: 'project',
    requirementIds: ['gcp:serviceusage.googleapis.com'],
    reason: 'Required by the resolved graph.',
  );
  return const DeploymentReadinessSnapshot(
    schemaVersion: DeploymentReadinessSnapshot.preflightSchemaVersion,
    source: DeploymentReadinessSource.preflight,
    twinId: 'twin-1',
    ready: false,
    summary: 'Provider preparation is required.',
    requiredProviders: [CloudProvider.gcp],
    providers: [
      ProviderDeploymentReadiness(
        provider: CloudProvider.gcp,
        connectionId: 'connection-1',
        connectionDisplayName: 'GCP deployment',
        ready: false,
        status: ProviderDeploymentReadinessStatus.reviewRequired,
        summary: 'One project API must be enabled.',
        graphDigest: graphDigest,
        requirementsDigest: requirementsDigest,
        checks: [check],
        requirements: [requirement],
      ),
    ],
    graphDigest: graphDigest,
    requirementsDigest: requirementsDigest,
    preparationPlan: DeploymentPreparationPlan(
      graphDigest: graphDigest,
      requirementsDigest: requirementsDigest,
      planDigest: planDigest,
      actions: [action],
      manualRequirements: [],
    ),
    issues: [],
  );
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
        checkedAt: ready ? DateTime.utc(2026, 7, 14, 9) : null,
        checks: [check],
      ),
    ],
    checkedAt: ready ? DateTime.utc(2026, 7, 14, 9) : null,
    issues: const [],
  );
}
