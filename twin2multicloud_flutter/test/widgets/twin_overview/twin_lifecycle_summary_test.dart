import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_readiness.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_lifecycle_summary.dart';

void main() {
  Widget buildWidget({
    required TwinOverviewLoaded state,
    VoidCallback? onEdit,
    VoidCallback? onDelete,
    double textScale = 1,
  }) {
    return MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(
          context,
        ).copyWith(textScaler: TextScaler.linear(textScale)),
        child: child!,
      ),
      home: Scaffold(
        body: TwinLifecycleSummary(
          state: state,
          onEdit: onEdit ?? () {},
          onDelete: onDelete ?? () {},
        ),
      ),
    );
  }

  testWidgets('projects preflight and deploy as the next configured step', (
    tester,
  ) async {
    await tester.pumpWidget(buildWidget(state: _state()));

    expect(find.text('Demo Twin'), findsOneWidget);
    expect(find.text('Cloud resource: Not configured'), findsOneWidget);
    expect(find.text('CONFIGURED'), findsOneWidget);
    expect(find.textContaining('Next: Run provider preflight'), findsOneWidget);

    await tester.pumpWidget(
      buildWidget(state: _state(readiness: _readyReadiness())),
    );
    expect(find.text('Next: Deploy this bounded experiment.'), findsOneWidget);
  });

  testWidgets('projects verification before Destroy for a deployed Twin', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildWidget(
        state: _state(
          twinState: 'deployed',
          cloudResourceName: 'cloud-demo',
          canEdit: false,
          canDelete: false,
        ),
      ),
    );

    expect(
      find.textContaining('Verify L1-L3 and Event, then L4/L5'),
      findsOneWidget,
    );
    expect(find.textContaining('Destroy afterward'), findsOneWidget);
  });

  testWidgets('overflow invokes enabled actions and explains disabled ones', (
    tester,
  ) async {
    var edits = 0;
    var deletes = 0;
    await tester.pumpWidget(
      buildWidget(
        state: _state(),
        onEdit: () => edits += 1,
        onDelete: () => deletes += 1,
      ),
    );

    await tester.tap(find.byIcon(Icons.more_vert));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Edit configuration'));
    await tester.pumpAndSettle();
    expect(edits, 1);

    await tester.tap(find.byIcon(Icons.more_vert));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Delete Twin'));
    await tester.pumpAndSettle();
    expect(deletes, 1);

    await tester.pumpWidget(
      buildWidget(
        state: _state(twinState: 'deployed', canEdit: false, canDelete: false),
      ),
    );
    await tester.tap(find.byIcon(Icons.more_vert));
    await tester.pumpAndSettle();
    expect(find.text('Destroy cloud resources before editing'), findsOneWidget);
    expect(
      find.text('Destroy cloud resources before deleting'),
      findsOneWidget,
    );
  });

  testWidgets('remains usable at 640 pixels and 200 percent text', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(640, 900));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(buildWidget(state: _state(), textScale: 2));

    expect(find.byTooltip('More actions for Demo Twin'), findsOneWidget);
    expect(find.text('CONFIGURED'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

TwinOverviewLoaded _state({
  String twinState = 'configured',
  String? cloudResourceName,
  bool canEdit = true,
  bool canDelete = true,
  DeploymentReadinessViewState readiness =
      const DeploymentReadinessViewState.initial(),
}) {
  return TwinOverviewLoaded(
    twinId: 'twin-1',
    projectName: 'Demo Twin',
    cloudResourceName: cloudResourceName,
    twinState: twinState,
    canDeploy: twinState == 'configured',
    canDestroy: twinState == 'deployed',
    canEdit: canEdit,
    canDelete: canDelete,
    deploymentReadiness: readiness,
  );
}

DeploymentReadinessViewState _readyReadiness() {
  return DeploymentReadinessViewState.fromSnapshot(
    DeploymentReadinessSnapshot(
      schemaVersion: DeploymentReadinessSnapshot.cachedSchemaVersion,
      source: DeploymentReadinessSource.cached,
      twinId: 'twin-1',
      ready: true,
      summary: 'Ready.',
      requiredProviders: const [CloudProvider.aws],
      providers: const [],
      issues: const [],
    ),
  );
}
