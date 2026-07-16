import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/demo/demo_management_api.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/models/wizard_config_requests.dart';

import '../fixtures/typed_api_fixtures.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final now = DateTime.parse('2026-07-13T10:00:00Z');
  late DemoFixtureStore store;
  late DemoManagementApi api;

  setUp(() async {
    store = await DemoFixtureStore.load(
      DemoScenario.showcase,
      clock: () => now,
    );
    api = DemoManagementApi(store: store, latency: Duration.zero);
  });

  group('session and cloud access', () {
    test('exposes the production capability contract in demo mode', () async {
      final capabilities = await api.getProviderCapabilities();

      expect(capabilities.providers, hasLength(3));
      expect(capabilities.capability('aws', 'l5').selectable, isTrue);
      expect(capabilities.capability('gcp', 'l4').selectable, isFalse);
      expect(capabilities.capability('gcp', 'l5').selectable, isFalse);
    });

    test('updates session state and user preferences in memory', () async {
      api.setToken('session-token');
      final user = await api.updateUserPreferences(themePreference: 'light');

      expect(await api.getAuthToken(), 'session-token');
      expect(user['theme_preference'], 'light');
      expect(store.user['theme_preference'], 'light');
      await expectLater(
        api.updateUserPreferences(themePreference: 'sepia'),
        throwsDemoCode('DEMO_THEME_INVALID'),
      );
    });

    test('supports credential-safe cloud connection lifecycle', () async {
      const secret = 'must-never-be-stored';
      final created = await api.createCloudConnection(
        const CloudConnectionCreateRequest(
          provider: CloudProvider.aws,
          purpose: CloudConnectionPurpose.pricing,
          displayName: 'Secondary AWS reader',
          cloudScope: {'account_id': '999999999999'},
          credentials: {
            'access_key_id': 'AKIADEMO',
            'secret_access_key': secret,
          },
          isDefaultForPricing: true,
        ),
      );

      expect(created.isDefaultForPricing, isTrue);
      expect(
        (await api.listCloudConnections(
          provider: CloudProvider.aws,
        )).where((item) => item.isDefaultForPricing),
        hasLength(1),
      );
      expect(
        store.cloudConnection(created.id).toString(),
        isNot(contains(secret)),
      );

      final validated = await api.validateCloudConnection(created.id);
      expect(validated.valid, isTrue);
      expect(
        (await api.updateCloudConnection(
          created.id,
          displayName: 'Renamed AWS reader',
        )).displayName,
        'Renamed AWS reader',
      );

      await api.deleteCloudConnection(created.id);
      expect(
        await api.listCloudConnections(provider: CloudProvider.aws),
        hasLength(2),
      );
      await expectLater(
        api.deleteCloudConnection('demo-aws-deployment'),
        throwsDemoCode('DEMO_CONNECTION_IN_USE'),
      );
      await expectLater(
        api.createCloudConnection(
          const CloudConnectionCreateRequest(
            provider: CloudProvider.aws,
            displayName: 'Missing credentials',
            credentials: {},
          ),
        ),
        throwsDemoCode('DEMO_CONNECTION_CREDENTIALS_REQUIRED'),
      );
    });

    test('derives purpose-separated access inventory', () async {
      final inventory = await api.getCloudAccessInventory();

      expect(inventory.schemaVersion, 'cloud-access-inventory.v1');
      expect(inventory.pricingFor('aws')?.connectionId, 'demo-aws-pricing');
      expect(inventory.pricingFor('azure')?.scope, 'public');
      expect(inventory.providers['gcp']?.deployment, hasLength(1));
    });
  });

  group('twin lifecycle and configuration', () {
    test('supports create, update, configure, and delete', () async {
      final created = await api.createTwin('Session Twin');
      final id = created.id;

      expect((await api.getDashboardStats()).totalTwins, 4);
      expect(
        (await api.updateTwin(id, name: 'Renamed Twin')).name,
        'Renamed Twin',
      );
      final config = await api.updateTwinConfig(id, {
        'debug_mode': false,
        'cloud_connections': {'aws': 'demo-aws-deployment'},
      });
      expect(
        config.provider(CloudProvider.aws).cloudConnectionId,
        'demo-aws-deployment',
      );
      expect(
        (await api.updateTwinConfigRequest(
          id,
          const TwinConfigUpdateRequest(highestStepReached: 1),
        )).highestStepReached,
        1,
      );
      expect((await api.getTwinConfigResult(id)).isSuccess, isTrue);

      await api.deleteTwin(id);
      await expectLater(api.getTwin(id), throwsDemoCode('DEMO_TWIN_NOT_FOUND'));
    });

    test('enforces lifecycle and binding conflicts', () async {
      await expectLater(
        api.createTwin('Factory Draft'),
        throwsDemoCode('DEMO_TWIN_NAME_CONFLICT'),
      );
      await expectLater(
        api.updateTwin('demo-draft', name: '  '),
        throwsDemoCode('DEMO_TWIN_NAME_REQUIRED'),
      );
      await expectLater(
        api.deleteTwin('demo-deployed'),
        throwsDemoCode('DEMO_TWIN_DELETE_CONFLICT'),
      );
      await expectLater(
        api.updateTwinConfig('demo-draft', {
          'cloud_connections': {'aws': 'demo-aws-pricing'},
        }),
        throwsDemoCode('DEMO_CONNECTION_BINDING_INVALID'),
      );
    });
  });

  group('pricing and optimization', () {
    test('refreshes each provider and exposes review evidence', () async {
      final aws = await api.startPricingRefresh('aws');
      final azure = await api.startPricingRefresh('azure');
      final gcp = await api.startPricingRefresh('gcp');

      expect(aws.credentialSummary.connectionId, 'demo-aws-pricing');
      expect(azure.credentialSummary.scope, 'public');
      expect(gcp.credentialSummary.connectionId, 'demo-gcp-pricing');
      final reports = await api.listPricingCandidateReports(
        'gcp',
        gcp.refreshRunId,
      );
      expect(reports.reports, hasLength(1));
      expect(reports.reports.single.refreshRunId, gcp.refreshRunId);
      final report = reports.reports.single;
      final trace = await api.getPricingCandidateTrace(report.reportId);
      expect(trace.sanitization.secretFree, isTrue);

      final decision = await api.createPricingReviewDecision(
        report.reportId,
        'select_alternative',
        candidateId: report.candidates.last.candidateId,
        rationale: 'Selected during the demo.',
      );
      expect(decision.decision, 'select_alternative');
      await expectLater(
        api.createPricingReviewDecision(report.reportId, 'approve'),
        throwsDemoCode('DEMO_PRICING_CANDIDATE_REQUIRED'),
      );
    });

    test('supports health, exports, calculation, and persistence', () async {
      expect((await api.getPricingHealth()).providers, hasLength(3));
      expect((await api.getPricingStatusResult()).isSuccess, isTrue);
      expect((await api.getRegionsStatus())['providers'], hasLength(3));
      expect((await api.exportPricing('aws')).payload, isNotEmpty);

      final calculationParams = CalcParams.fromJson({
        ...CalcParams.defaultParams().toJson(),
        'needs3DModel': true,
        'useEventChecking': true,
      });
      final calculation = await api.calculateCosts(calculationParams);
      expect(calculation.result.totalCost, 84.42);
      expect(
        (await api.calculateCostsResult(calculationParams)).isSuccess,
        isTrue,
      );

      final savedParams = CalcParams.fromJson({
        ...CalcParams.defaultParams().toJson(),
        'numberOfDevices': 12,
      });
      await api.saveOptimizerParams('demo-draft', savedParams);
      await api.saveOptimizerResult(
        'demo-draft',
        params: savedParams,
        optimization: calculation,
        cheapestPath: CheapestPath.fromSegments(
          calculation.result.cheapestPath,
        ),
        pricingSnapshots: {
          for (final provider in CloudProvider.values)
            provider: TypedApiFixtures.pricingExport(provider),
        },
      );
      expect(
        (await api.getOptimizerConfig('demo-draft'))?.optimization?.payload,
        isNotEmpty,
      );
    });
  });

  group('deployer configuration and lifecycle', () {
    test('validates and mutates deployment artifacts', () async {
      expect(
        (await api.validateDeployerConfig(
          'demo-draft',
          'config',
          '{}',
        ))['valid'],
        isTrue,
      );
      expect(
        (await api.validateDeployerConfig(
          'demo-draft',
          'events',
          '{',
        ))['valid'],
        isFalse,
      );
      expect(
        (await api.validateL2Content(
          'demo-draft',
          'function-code',
          'def handler(): pass',
          'aws',
        ))['valid'],
        isTrue,
      );
      expect(
        (await api.validateL4Content(
          'demo-draft',
          'hierarchy',
          '{}',
          'azure',
        ))['valid'],
        isTrue,
      );

      await api.updateDeployerConfig('demo-draft', {'payloads_json': '{}'});
      await api.updateDeployerConfigRequest(
        'demo-draft',
        const DeployerConfigUpdateRequest(
          deployerDigitalTwinName: 'demo-draft',
        ),
      );
      expect(
        (await api.getDeployerConfig('demo-draft'))?.deployerDigitalTwinName,
        'demo-draft',
      );
      await api.uploadSceneGlb(
        'demo-draft',
        Uint8List.fromList([1, 2, 3]),
        'scene.glb',
      );
      expect(
        (await api.getDeployerConfig('demo-draft'))?.sceneGlbUploaded,
        isTrue,
      );
      await api.deleteSceneGlb('demo-draft');
      expect(
        (await api.getDeployerConfig('demo-draft'))?.sceneGlbUploaded,
        isFalse,
      );
      expect(
        (await api.uploadProjectZip(
          'demo-draft',
          Uint8List.fromList([1]),
          'project.zip',
        ))['success'],
        isTrue,
      );
    });

    test('deploys, exposes evidence, verifies, and destroys', () async {
      final cached = await api.getDeploymentReadiness('demo-configured');
      expect(cached.ready, isFalse);
      expect(cached.providers.first.status.name, 'notChecked');
      await expectLater(
        api.deployTwin('demo-configured'),
        throwsDemoCode('DEMO_DEPLOYMENT_PREFLIGHT_REQUIRED'),
      );

      final preflight = await api.runDeploymentPreflight('demo-configured');
      expect(preflight.ready, isTrue);
      expect(preflight.providers, hasLength(3));
      final deployment = await api.deployTwin('demo-configured');
      expect(deployment.sseUrl, startsWith('/demo/deployment/'));
      expect(
        (await api.getDeploymentStatus('demo-configured')).state.apiValue,
        'deployed',
      );
      expect(
        (await api.getDeploymentOutputs('demo-configured')).outputs,
        isNotEmpty,
      );
      expect(
        (await api.getDeploymentLogs('demo-configured')).logs,
        hasLength(1),
      );
      expect(
        (await api.getDeploymentHistory('demo-configured')).deployments,
        hasLength(1),
      );
      expect(
        (await api.startLogTrace('demo-configured')).sseUrl,
        startsWith('/demo/trace/'),
      );
      final simulator = await api.downloadSimulator('demo-configured');
      expect(simulator.bytes, isNotEmpty);
      expect(simulator.filename, endsWith('.zip'));

      expect(
        (await api.verifyInfrastructure('demo-configured'))['summary'],
        isNotEmpty,
      );
      expect(
        (await api.verifyDataFlow('demo-configured', {
          'iotDeviceId': 'meter-001',
        }))['sse_url'],
        startsWith('/demo/verification/'),
      );
      expect(
        api.getSseUrl('/demo/path', lastEventId: 4),
        contains('last_event_id=4'),
      );

      final destroy = await api.destroyTwin('demo-configured');
      expect(destroy.sseUrl, startsWith('/demo/destroy/'));
      expect(
        (await api.getDeploymentStatus('demo-configured')).state.apiValue,
        'destroyed',
      );
    });

    test(
      'pages deployment logs in event order and within one session',
      () async {
        store.addDeploymentLog('demo-deployed', {
          'event_id': 4,
          'session_id': 'other-session',
          'level': 'info',
          'message': 'Other operation',
          'timestamp': '2026-07-12T10:02:00Z',
        });
        store.addDeploymentLog('demo-deployed', {
          'event_id': 3,
          'session_id': 'demo-session-deployed',
          'level': 'info',
          'message': 'Final deployment event',
          'timestamp': '2026-07-12T10:01:00Z',
        });

        final page = await api.getDeploymentLogs(
          'demo-deployed',
          sessionId: 'demo-session-deployed',
          afterEventId: 1,
          limit: 1,
        );

        expect(page.logs.single.eventId, 2);
        expect(page.hasMore, isTrue);
        expect(page.nextAfterEventId, 2);
        expect(page.latestEventId, 3);
      },
    );

    test('rejects invalid lifecycle operations and payloads', () async {
      await expectLater(
        api.deployTwin('demo-draft'),
        throwsDemoCode('DEMO_DEPLOY_STATE_CONFLICT'),
      );
      await expectLater(
        api.destroyTwin('demo-draft'),
        throwsDemoCode('DEMO_DESTROY_STATE_CONFLICT'),
      );
      await expectLater(
        api.verifyDataFlow('demo-deployed', const {}),
        throwsDemoCode('DEMO_DATAFLOW_PAYLOAD_INVALID'),
      );
      await expectLater(
        api.uploadSceneGlb('demo-draft', Uint8List(0), 'scene.glb'),
        throwsDemoCode('DEMO_GLB_INVALID'),
      );
    });
  });
}

Matcher throwsDemoCode(String code) {
  return throwsA(
    isA<DemoApiException>().having((error) => error.code, 'code', code),
  );
}
