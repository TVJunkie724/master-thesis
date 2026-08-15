import 'dart:async';

import 'package:bloc_test/bloc_test.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_bloc.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_event.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_access.dart';
import 'package:twin2multicloud_flutter/models/deployment_operations.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/screens/twin_overview/twin_overview_screen.dart';
import 'package:twin2multicloud_flutter/services/external_auth_launcher.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';
import 'package:twin2multicloud_flutter/widgets/terraform_outputs_card.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/deployment_operations_panel.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/layer_access_panel.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/testing_utilities_panel.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_configuration_review.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_operation_dialogs.dart';

class _MockTwinOverviewBloc
    extends MockBloc<TwinOverviewEvent, TwinOverviewState>
    implements TwinOverviewBloc {}

class _MockManagementApi extends Mock implements ManagementApi {}

class _MockExternalAuthLauncher extends Mock implements ExternalAuthLauncher {}

class _MockExternalAuthLaunchHandle extends Mock
    implements ExternalAuthLaunchHandle {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Open reserves a browser handle and navigates to the exact URL', (
    tester,
  ) async {
    final bloc = _MockTwinOverviewBloc();
    final launcher = _MockExternalAuthLauncher();
    final handle = _MockExternalAuthLaunchHandle();
    final state = _loadedState();
    final l4 = state.layerAccess.snapshot!.surfaceFor(DeploymentLayer.l4)!;
    when(() => launcher.reserve()).thenReturn(handle);
    when(() => handle.navigate(l4.url)).thenAnswer((_) async => true);

    await _pumpView(tester, bloc: bloc, state: state, launcher: launcher);
    await tester.ensureVisible(find.byKey(const Key('open-layer-l4')));
    await tester.tap(find.byKey(const Key('open-layer-l4')));
    await tester.pump();

    verify(() => launcher.reserve()).called(1);
    verify(() => handle.navigate(l4.url)).called(1);
    verifyNever(() => handle.close());
  });

  testWidgets('failed browser launch closes the handle and emits a safe error', (
    tester,
  ) async {
    final bloc = _MockTwinOverviewBloc();
    final launcher = _MockExternalAuthLauncher();
    final handle = _MockExternalAuthLaunchHandle();
    final state = _loadedState();
    final l4 = state.layerAccess.snapshot!.surfaceFor(DeploymentLayer.l4)!;
    when(() => launcher.reserve()).thenReturn(handle);
    when(() => handle.navigate(l4.url)).thenAnswer((_) async => false);
    when(() => handle.close()).thenAnswer((_) async {});

    await _pumpView(tester, bloc: bloc, state: state, launcher: launcher);
    await tester.ensureVisible(find.byKey(const Key('open-layer-l4')));
    await tester.tap(find.byKey(const Key('open-layer-l4')));
    await tester.pumpAndSettle();

    verify(() => handle.close()).called(1);
    verify(
      () => bloc.add(
        const TwinOverviewShowMessage(
          'Could not open L4 Azure Digital Twins Explorer in the external browser.',
          MessageType.error,
        ),
      ),
    ).called(1);
  });

  testWidgets('rapid Open clicks create one isolated launch per click', (
    tester,
  ) async {
    final bloc = _MockTwinOverviewBloc();
    final launcher = _MockExternalAuthLauncher();
    final firstHandle = _MockExternalAuthLaunchHandle();
    final secondHandle = _MockExternalAuthLaunchHandle();
    final state = _loadedState();
    final l4 = state.layerAccess.snapshot!.surfaceFor(DeploymentLayer.l4)!;
    var reservation = 0;
    when(
      () => launcher.reserve(),
    ).thenAnswer((_) => reservation++ == 0 ? firstHandle : secondHandle);
    when(() => firstHandle.navigate(l4.url)).thenAnswer((_) async => true);
    when(() => secondHandle.navigate(l4.url)).thenAnswer((_) async => true);

    await _pumpView(tester, bloc: bloc, state: state, launcher: launcher);
    await tester.ensureVisible(find.byKey(const Key('open-layer-l4')));
    await tester.tap(find.byKey(const Key('open-layer-l4')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('open-layer-l4')));
    await tester.pump();

    verify(() => launcher.reserve()).called(2);
    verify(() => firstHandle.navigate(l4.url)).called(1);
    verify(() => secondHandle.navigate(l4.url)).called(1);
  });

  testWidgets('GCP Viewer rotation requires confirmation before one event', (
    tester,
  ) async {
    final bloc = _MockTwinOverviewBloc();
    final launcher = _MockExternalAuthLauncher();
    final state = _loadedState(l5: CloudProvider.gcp);

    await _pumpView(tester, bloc: bloc, state: state, launcher: launcher);
    await tester.ensureVisible(find.byKey(const Key('rotate-gcp-viewer')));
    await tester.tap(find.byKey(const Key('rotate-gcp-viewer')));
    await tester.pumpAndSettle();

    verifyNever(
      () => bloc.add(const TwinOverviewRotateGcpGrafanaViewerCredential()),
    );
    await tester.tap(find.byKey(const Key('confirm-gcp-viewer-rotation')));
    await tester.pumpAndSettle();
    verify(
      () => bloc.add(const TwinOverviewRotateGcpGrafanaViewerCredential()),
    ).called(1);
  });

  testWidgets('one-time Viewer credential is consumed before one reveal', (
    tester,
  ) async {
    final bloc = _MockTwinOverviewBloc();
    final launcher = _MockExternalAuthLauncher();
    final states = StreamController<TwinOverviewState>.broadcast(sync: true);
    addTearDown(states.close);
    final initial = _loadedState(l5: CloudProvider.gcp);
    whenListen(bloc, states.stream, initialState: initial);

    await _pumpView(
      tester,
      bloc: bloc,
      state: initial,
      launcher: launcher,
      stubStream: false,
    );
    final pending = initial.copyWith(
      layerAccess: initial.layerAccess.copyWith(
        credentialRequestToken: 7,
        pendingCredential: _credential(),
      ),
    );
    states.add(pending);
    await tester.pumpAndSettle();

    expect(find.text('viewer@example.invalid'), findsOneWidget);
    expect(
      tester
          .widget<TextField>(find.byKey(const Key('gcp-viewer-password')))
          .obscureText,
      isTrue,
    );
    verify(
      () => bloc.add(const TwinOverviewAccessCredentialConsumed(7)),
    ).called(1);

    await tester.tap(find.byKey(const Key('close-gcp-viewer-credential')));
    await tester.pumpAndSettle();
    states.add(pending.copyWith(infoMessage: 'Unrelated update'));
    await tester.pumpAndSettle();

    expect(find.byType(GcpGrafanaCredentialRevealDialog), findsNothing);
    verifyNever(() => bloc.add(const TwinOverviewAccessCredentialConsumed(7)));
  });

  testWidgets('rotation failure stays inline and never opens a reveal dialog', (
    tester,
  ) async {
    final bloc = _MockTwinOverviewBloc();
    final launcher = _MockExternalAuthLauncher();
    final states = StreamController<TwinOverviewState>.broadcast(sync: true);
    addTearDown(states.close);
    final initial = _loadedState(l5: CloudProvider.gcp);
    whenListen(bloc, states.stream, initialState: initial);

    await _pumpView(
      tester,
      bloc: bloc,
      state: initial,
      launcher: launcher,
      stubStream: false,
    );
    states.add(
      initial.copyWith(
        layerAccess: initial.layerAccess.copyWith(
          rotationError:
              'Viewer credential rotation failed: '
              'GCP_GRAFANA_VIEWER_ROTATION_IN_PROGRESS',
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.textContaining('GCP_GRAFANA_VIEWER_ROTATION_IN_PROGRESS'),
      findsOneWidget,
    );
    expect(find.byType(GcpGrafanaCredentialRevealDialog), findsNothing);
    verifyNever(() => bloc.add(const TwinOverviewAccessCredentialConsumed(1)));
  });

  testWidgets('layer access does not replace downstream deployment panels', (
    tester,
  ) async {
    final bloc = _MockTwinOverviewBloc();
    final launcher = _MockExternalAuthLauncher();
    final state = _loadedState(
      deploymentOutputs: DeploymentOutputsSnapshot(
        schemaVersion: DeploymentOutputsSnapshot.supportedSchemaVersion,
        outputs: const {'azure_endpoint': 'https://example.invalid'},
        deployedAt: DateTime.utc(2026, 7, 31, 12),
        redacted: true,
      ),
    );

    await _pumpView(tester, bloc: bloc, state: state, launcher: launcher);

    expect(find.byType(LayerAccessPanel), findsOneWidget);
    expect(find.byType(DeploymentOperationsPanel), findsOneWidget);
    expect(find.byType(TestingUtilitiesPanel), findsOneWidget);
    expect(find.byType(TerraformOutputsCard), findsOneWidget);
    expect(find.byType(TwinOverviewConfigurationReview), findsOneWidget);
  });
}

Future<void> _pumpView(
  WidgetTester tester, {
  required _MockTwinOverviewBloc bloc,
  required TwinOverviewLoaded state,
  required _MockExternalAuthLauncher launcher,
  bool stubStream = true,
}) async {
  await tester.binding.setSurfaceSize(const Size(1200, 1600));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  if (stubStream) {
    whenListen(
      bloc,
      const Stream<TwinOverviewState>.empty(),
      initialState: state,
    );
  }
  final api = _MockManagementApi();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        appRuntimeProvider.overrideWithValue(const AppRuntimeConfig.demo()),
        apiServiceProvider.overrideWithValue(api),
        logStreamClientFactoryProvider.overrideWithValue(
          () => throw StateError('Log stream not expected in this test.'),
        ),
        externalAuthLauncherProvider.overrideWithValue(launcher),
      ],
      child: MaterialApp(
        home: BlocProvider<TwinOverviewBloc>.value(
          value: bloc,
          child: const TwinOverviewView(twinId: 'twin-1'),
        ),
      ),
    ),
  );
  await tester.pump();
}

TwinOverviewLoaded _loadedState({
  CloudProvider l5 = CloudProvider.aws,
  DeploymentOutputsSnapshot? deploymentOutputs,
}) {
  return TwinOverviewLoaded(
    twinId: 'twin-1',
    projectName: 'Demo Twin',
    cloudResourceName: 'demo-twin',
    twinState: 'deployed',
    canDeploy: false,
    canDestroy: true,
    canEdit: false,
    canDelete: false,
    layerAccess: LayerAccessViewState.fromSnapshot(_snapshot(l5: l5)),
    deploymentOutputs: deploymentOutputs,
  );
}

DeploymentAccessSnapshot _snapshot({required CloudProvider l5}) {
  return DeploymentAccessSnapshot.fromJson({
    'schema_version': 'deployment-access.v1',
    'twin_id': 'twin-1',
    'deployment_id': 'deployment-1',
    'generated_at': '2026-07-31T12:00:00Z',
    'availability': 'available',
    'reason_code': null,
    'surfaces': [
      _surface(DeploymentLayer.l4, CloudProvider.azure),
      _surface(DeploymentLayer.l5, l5),
    ],
  });
}

Map<String, dynamic> _surface(DeploymentLayer layer, CloudProvider provider) {
  final config = switch ((layer, provider)) {
    (DeploymentLayer.l4, CloudProvider.azure) => (
      'azure_digital_twins',
      'Azure Digital Twins Explorer',
      'azure_entra',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.aws) => (
      'aws_managed_grafana',
      'Amazon Managed Grafana',
      'aws_identity_center',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.gcp) => (
      'gcp_grafana_oss',
      'Grafana OSS on GKE',
      'generated_viewer',
      'rotate',
    ),
    _ => throw StateError('Unsupported test surface.'),
  };
  return {
    'layer': layer.name,
    'provider': provider.name,
    'service_id': config.$1,
    'display_name': config.$2,
    'url': 'https://${layer.name}-${provider.name}.example.invalid/',
    'auth': {
      'mode': config.$3,
      'principal_label': 'researcher@example.invalid',
      'credential_action': config.$4,
    },
    'readiness': {
      'resource': 'ready',
      'access_binding': 'ready',
      'content': 'ready',
      'data_probe': 'ready',
      'browser_sign_in': 'unverified',
    },
    'capabilities': ['Inspect the deployed layer.'],
    'limitations': ['Browser sign-in remains user verified.'],
  };
}

DeploymentAccessCredential _credential() {
  return DeploymentAccessCredential.fromJson({
    'schema_version': 'deployment-access-credential.v1',
    'layer': 'l5',
    'provider': 'gcp',
    'username': 'viewer@example.invalid',
    'password': 'one-time-secret',
    'issued_at': '2026-07-31T12:00:00Z',
  });
}
