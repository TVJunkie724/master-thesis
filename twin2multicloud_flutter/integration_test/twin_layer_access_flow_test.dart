import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/bloc/twin_overview/twin_overview_state.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_access.dart';
import 'package:twin2multicloud_flutter/models/deployment_operations.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/widgets/terraform_outputs_card.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_code_artifact.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_content.dart';

final _runtime = AppRuntimeConfig.fromEnvironment();
final _apiUri =
    _runtime.managementApiBaseUri ??
    (throw StateError('Integration runtime requires a Management API origin.'));
final _authToken =
    _runtime.initialAuthToken ??
    (throw StateError('Integration tests require the development profile.'));
final _api = ApiService(baseUri: _apiUri, initialAuthToken: _authToken);
final _raw = Dio(
  BaseOptions(
    baseUrl: _apiUri.toString(),
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer $_authToken',
    },
  ),
);
late final Map<String, dynamic> _fixtures;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  setUpAll(() async {
    final response = await _raw.post('/twins/test-fixtures/layer-access');
    _fixtures = _map(response.data, 'fixture response');
    expect(_fixtures['schema_version'], 'layer-access-test-fixtures.v1');
  });

  testWidgets('AWS/AWS returns and renders exact services and URLs', (
    tester,
  ) async {
    final snapshot = await _placement('aws-aws');
    final opened = <Uri>[];

    await _pumpOverview(tester, snapshot: snapshot, opened: opened);

    expect(snapshot.surfaces, hasLength(2));
    expect(find.text('AWS IoT TwinMaker'), findsOneWidget);
    expect(find.text('Amazon Managed Grafana'), findsOneWidget);
    await _tapOpen(tester, DeploymentLayer.l4);
    await _tapOpen(tester, DeploymentLayer.l5);
    expect(opened, snapshot.surfaces.map((surface) => surface.url).toList());
  });

  testWidgets('mixed GCP L4 and Azure L5 keeps auth and opening independent', (
    tester,
  ) async {
    final snapshot = await _placement('gcp-azure');
    final opened = <Uri>[];

    await _pumpOverview(tester, snapshot: snapshot, opened: opened);
    await _expandDetails(tester, DeploymentLayer.l4);
    await _expandDetails(tester, DeploymentLayer.l5);

    expect(find.text('Google Cloud IAP'), findsOneWidget);
    expect(find.text('Microsoft Entra ID'), findsOneWidget);
    await _tapOpen(tester, DeploymentLayer.l4);
    await _tapOpen(tester, DeploymentLayer.l5);
    expect(opened, snapshot.surfaces.map((surface) => surface.url).toList());
  });

  testWidgets('owner boundary returns 404 and renders no links', (
    tester,
  ) async {
    final response = await _captureResponse(
      () => _raw.get(
        '/twins/${_fixtures['foreign_owner_twin_id']}/deployment-access',
      ),
    );

    expect(response.statusCode, 404);
    expect(_map(response.data, 'owner error')['detail'], 'Twin not found');
    await _pumpOverview(
      tester,
      layerAccess: const LayerAccessViewState(
        phase: LayerAccessViewPhase.failed,
        errorMessage: 'Layer access unavailable: Resource not found.',
      ),
    );
    expect(find.byKey(const Key('open-layer-l4')), findsNothing);
    expect(find.byKey(const Key('open-layer-l5')), findsNothing);
  });

  testWidgets(
    'blocked L4 shows exact code and remediation while L5 stays open',
    (tester) async {
      final snapshot = await _api.getDeploymentAccess(
        _fixtures['blocked_twin_id'] as String,
      );

      await _pumpOverview(tester, snapshot: snapshot);

      expect(find.text('ACCESS_BINDING_BLOCKED'), findsOneWidget);
      expect(
        find.text(
          'Grant the thesis researcher access, then retry Layer Access.',
        ),
        findsOneWidget,
      );
      expect(_openButton(tester, DeploymentLayer.l4).onPressed, isNull);
      expect(_openButton(tester, DeploymentLayer.l5).onPressed, isNotNull);
    },
  );

  testWidgets('all nine placements expose exact ordered L4 and L5 pairs', (
    tester,
  ) async {
    final placements = _map(_fixtures['placements'], 'placements');
    expect(placements, hasLength(9));

    for (final l4 in CloudProvider.values) {
      for (final l5 in CloudProvider.values) {
        final snapshot = await _placement('${l4.apiValue}-${l5.apiValue}');
        expect(snapshot.surfaces, hasLength(2));
        expect(
          snapshot.surfaces
              .map((surface) => (surface.layer, surface.provider))
              .toList(),
          [(DeploymentLayer.l4, l4), (DeploymentLayer.l5, l5)],
        );
      }
    }
  });

  testWidgets('historical v1 is unsupported and fabricates zero links', (
    tester,
  ) async {
    final snapshot = await _api.getDeploymentAccess(
      _fixtures['historical_twin_id'] as String,
    );

    await _pumpOverview(tester, snapshot: snapshot);

    expect(snapshot.availability, DeploymentAccessAvailability.unsupported);
    expect(snapshot.surfaces, isEmpty);
    expect(find.textContaining('historical six-layer profile'), findsOneWidget);
    expect(find.byKey(const Key('open-layer-l4')), findsNothing);
  });

  testWidgets('destroyed fixture returns 409 and clears the visible cards', (
    tester,
  ) async {
    final response = await _captureResponse(
      () => _raw.get(
        '/twins/${_fixtures['destroyed_twin_id']}/deployment-access',
      ),
    );

    expect(response.statusCode, 409);
    expect(
      _map(response.data, 'destroyed error')['detail'],
      'DEPLOYMENT_ACCESS_REQUIRES_DEPLOYED_TWIN',
    );
    await _pumpOverview(tester, twinState: 'destroyed');
    expect(find.byKey(const Key('layer-access-card-l4')), findsNothing);
    expect(find.byKey(const Key('layer-access-card-l5')), findsNothing);
  });

  testWidgets('GCP Viewer rotations replace only fingerprinted fixture state', (
    tester,
  ) async {
    final twinId = _fixtures['rotation_twin_id'] as String;
    final accessBefore = await _api.getDeploymentAccess(twinId);
    final rawAccessBefore = await _raw.get('/twins/$twinId/deployment-access');
    final first = await _api.rotateGcpGrafanaViewerCredential(twinId);
    final firstState = await _rotationState(twinId);
    final second = await _api.rotateGcpGrafanaViewerCredential(twinId);
    final secondState = await _rotationState(twinId);

    expect(first.username, 'viewer@example.invalid');
    expect(second.username, 'viewer@example.invalid');
    expect(second.password, isNot(first.password));
    expect(firstState['provider_mutation_count'], 1);
    expect(secondState['provider_mutation_count'], 2);
    expect(
      secondState['credential_fingerprint'],
      isNot(firstState['credential_fingerprint']),
    );
    expect(accessBefore.surfaces, hasLength(2));
    final readModel = jsonEncode(rawAccessBefore.data);
    expect(readModel, isNot(contains(first.password)));
    expect(readModel, isNot(contains(second.password)));
    expect(readModel, isNot(contains('admin_password')));
    expect(readModel, isNot(contains('reader_token')));
  });

  testWidgets('generic outputs remain separate, rendered, and redacted', (
    tester,
  ) async {
    final twinId = _fixtures['outputs_twin_id'] as String;
    final snapshot = await _api.getDeploymentAccess(twinId);
    final outputs = await _api.getDeploymentOutputs(twinId);

    expect(outputs.redacted, isTrue);
    expect(outputs.outputs?['admin_password'], '[REDACTED]');
    expect(outputs.outputs?['reader_token'], '[REDACTED]');
    expect(jsonEncode(outputs.outputs), isNot(contains('must-not-cross-api')));
    await _pumpOverview(tester, snapshot: snapshot, deploymentOutputs: outputs);
    expect(find.byType(TerraformOutputsCard), findsOneWidget);
    expect(find.text('[REDACTED]'), findsNWidgets(2));
    expect(find.byKey(const Key('layer-access-card-l4')), findsOneWidget);
  });

  testWidgets(
    'concurrent rotation returns 409 and one mutation with retry UI',
    (tester) async {
      final twinId = _fixtures['rotation_twin_id'] as String;
      final before = await _rotationState(twinId);
      final first = _captureResponse(
        () =>
            _raw.post('/twins/$twinId/deployment-access/l5/credentials:rotate'),
      );
      final second = Future<void>.delayed(const Duration(milliseconds: 40))
          .then(
            (_) => _captureResponse(
              () => _raw.post(
                '/twins/$twinId/deployment-access/l5/credentials:rotate',
              ),
            ),
          );
      final responses = await Future.wait([first, second]);
      final after = await _rotationState(twinId);

      expect(responses.map((response) => response.statusCode).toSet(), {
        200,
        409,
      });
      final conflict = responses.singleWhere(
        (response) => response.statusCode == 409,
      );
      expect(
        _map(conflict.data, 'rotation conflict')['detail'],
        'GCP_GRAFANA_VIEWER_ROTATION_IN_PROGRESS',
      );
      expect(
        after['provider_mutation_count'],
        (before['provider_mutation_count'] as int) + 1,
      );

      final snapshot = await _api.getDeploymentAccess(twinId);
      await _pumpOverview(
        tester,
        layerAccess: LayerAccessViewState.fromSnapshot(snapshot).copyWith(
          rotationError:
              'Viewer credential rotation failed: '
              'GCP_GRAFANA_VIEWER_ROTATION_IN_PROGRESS',
        ),
      );
      expect(
        find.textContaining('GCP_GRAFANA_VIEWER_ROTATION_IN_PROGRESS'),
        findsOneWidget,
      );
      expect(
        tester
            .widget<OutlinedButton>(find.byKey(const Key('rotate-gcp-viewer')))
            .onPressed,
        isNotNull,
      );
    },
  );
}

Future<DeploymentAccessSnapshot> _placement(String key) async {
  final placements = _map(_fixtures['placements'], 'placements');
  return _api.getDeploymentAccess(placements[key] as String);
}

Future<Map<String, dynamic>> _rotationState(String twinId) async {
  final response = await _raw.get(
    '/twins/$twinId/test-fixtures/layer-access-rotation',
  );
  return _map(response.data, 'rotation state');
}

Future<Response<dynamic>> _captureResponse(
  Future<Response<dynamic>> Function() request,
) async {
  try {
    return await request();
  } on DioException catch (error) {
    return error.response ??
        (throw StateError('HTTP request had no response.'));
  }
}

Map<String, dynamic> _map(Object? value, String label) {
  if (value is! Map) throw StateError('$label must be an object.');
  return value.map((key, value) => MapEntry(key.toString(), value));
}

Future<void> _pumpOverview(
  WidgetTester tester, {
  DeploymentAccessSnapshot? snapshot,
  LayerAccessViewState? layerAccess,
  DeploymentOutputsSnapshot? deploymentOutputs,
  String twinState = 'deployed',
  List<Uri>? opened,
}) async {
  await tester.binding.setSurfaceSize(const Size(1200, 1800));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  final state = TwinOverviewLoaded(
    twinId: snapshot?.twinId ?? 'fixture-twin',
    projectName: 'Layer Access Integration Twin',
    cloudResourceName: 'layer-access-integration',
    twinState: twinState,
    canDeploy: false,
    canDestroy: twinState == 'deployed',
    canEdit: false,
    canDelete: false,
    layerAccess:
        layerAccess ??
        (snapshot == null
            ? const LayerAccessViewState()
            : LayerAccessViewState.fromSnapshot(snapshot)),
    deploymentOutputs: deploymentOutputs,
  );
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: TwinOverviewContent(
          state: state,
          deploymentVerification: null,
          onEdit: () {},
          onDelete: () {},
          onRunPreflight: () {},
          onOpenCloudAccounts: () {},
          onDeploy: () {},
          onDestroy: () {},
          onViewLogs: () {},
          onCloseTerminal: () {},
          onStartTrace: () {},
          onCancelTrace: () {},
          onDownloadSimulator: () {},
          onRetryLayerAccess: () {},
          onOpenLayerAccess: (surface) => opened?.add(surface.url),
          onRotateLayerAccessCredential: () {},
          onOutputCopyFeedback: (_) {},
          onViewArtifact: _ignoreArtifact,
          onDownloadArtifact: _ignoreArtifact,
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void _ignoreArtifact(TwinOverviewCodeArtifact _) {}

FilledButton _openButton(WidgetTester tester, DeploymentLayer layer) {
  return tester.widget<FilledButton>(
    find.byKey(Key('open-layer-${layer.name}')),
  );
}

Future<void> _tapOpen(WidgetTester tester, DeploymentLayer layer) async {
  final finder = find.byKey(Key('open-layer-${layer.name}'));
  await tester.ensureVisible(finder);
  await tester.tap(finder);
  await tester.pump();
}

Future<void> _expandDetails(WidgetTester tester, DeploymentLayer layer) async {
  final finder = find.byKey(Key('layer-access-details-${layer.name}'));
  await tester.ensureVisible(finder);
  await tester.tap(finder);
  await tester.pumpAndSettle();
}
