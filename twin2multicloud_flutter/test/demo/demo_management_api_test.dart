import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/demo/demo_management_api.dart';
import 'package:twin2multicloud_flutter/models/cloud_bootstrap.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_access.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/pricing_refresh_run.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/models/wizard_config_requests.dart';

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

    test('guided bootstrap demo matches deterministic fake disposal', () async {
      final target = CloudBootstrapTarget.aws(
        accountId: '123456789012',
        region: 'eu-central-1',
      );
      final guide = await api.getCloudBootstrapGuide(CloudProvider.aws, target);
      expect(guide.bootstrapAuthorityPack.id, 'bootstrap.aws.admin-v2');
      expect(guide.bootstrapAuthorityPack.version, '2');
      expect(
        guide.generatedDeploymentPack.id,
        'aws.thesis-demo-v2.iam-user-v1',
      );
      final gcpGuide = await api.getCloudBootstrapGuide(
        CloudProvider.gcp,
        CloudBootstrapTarget.gcpExistingProject(
          projectId: 'twin2mc-demo-project',
          region: 'europe-west1',
        ),
      );
      expect(gcpGuide.bootstrapAuthorityPack.id, 'bootstrap.gcp.admin-v3');
      expect(gcpGuide.bootstrapAuthorityPack.version, '3');
      expect(gcpGuide.apiBaseline?.services, hasLength(19));
      expect(gcpGuide.apiBaseline?.retainEnabled, isTrue);
      final azureGuide = await api.getCloudBootstrapGuide(
        CloudProvider.azure,
        CloudBootstrapTarget.azure(
          tenantId: '11111111-1111-4111-8111-111111111111',
          subscriptionId: '22222222-2222-4222-8222-222222222222',
          region: 'westeurope',
        ),
      );
      expect(
        azureGuide.generatedDeploymentPack.id,
        'azure.thesis-demo-v2.service-principal-v1',
      );
      final draft = await api.createCloudBootstrapSession(
        guide: guide,
        entryPoint: CloudBootstrapEntryPoint.settings,
        displayName: 'Demo AWS deployment access',
        idempotencyKey: 'demo-create-bootstrap-0001',
      );
      final resumed = await api.createCloudBootstrapSession(
        guide: guide,
        entryPoint: CloudBootstrapEntryPoint.settings,
        displayName: 'Ignored duplicate display name',
        idempotencyKey: 'demo-create-bootstrap-0002',
      );
      expect(resumed.id, draft.id);
      const submittedSecret = 'submitted-demo-bootstrap-secret';
      final connectionCount = store.cloudConnections.length;
      final ready = await api.executeCloudBootstrapSession(
        draft.id,
        CloudBootstrapExecuteRequest(
          expectedRevision: draft.revision,
          idempotencyKey: 'demo-execute-bootstrap-0001',
          credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
          credential: const {
            'provider': 'aws',
            'access_key_id': 'AKIAEXAMPLE00000001',
            'secret_access_key': submittedSecret,
          },
        ),
      );
      final replay = await api.executeCloudBootstrapSession(
        draft.id,
        CloudBootstrapExecuteRequest(
          expectedRevision: draft.revision,
          idempotencyKey: 'demo-execute-bootstrap-0001',
          credentialOrigin: CloudBootstrapCredentialOrigin.dedicatedDisposable,
          credential: const {
            'provider': 'aws',
            'access_key_id': 'AKIAREPLAY0000000000',
            'secret_access_key': 'different-replay-secret',
          },
        ),
      );

      expect(ready.state, CloudBootstrapSessionState.ready);
      expect(ready.disposalStatus, 'revoked');
      expect(ready.connection?.permissionSetVersion, 'thesis-demo-v2');
      expect(replay.connection?.id, ready.connection?.id);
      expect(store.cloudConnections, hasLength(connectionCount + 1));
      expect(
        store.cloudConnections.toString(),
        isNot(contains(submittedSecret)),
      );
    });

    test(
      'guided bootstrap demo enforces re-entry and manual cleanup',
      () async {
        final awsTarget = CloudBootstrapTarget.aws(
          accountId: '123456789012',
          region: 'eu-central-1',
        );
        final awsGuide = await api.getCloudBootstrapGuide(
          CloudProvider.aws,
          awsTarget,
        );
        final awsDraft = await api.createCloudBootstrapSession(
          guide: awsGuide,
          entryPoint: CloudBootstrapEntryPoint.settings,
          displayName: 'AWS re-entry',
          idempotencyKey: 'demo-create-reentry-0001',
        );
        final rejected = await api.executeCloudBootstrapSession(
          awsDraft.id,
          CloudBootstrapExecuteRequest(
            expectedRevision: awsDraft.revision,
            idempotencyKey: 'demo-execute-rejected-0001',
            credentialOrigin:
                CloudBootstrapCredentialOrigin.dedicatedDisposable,
            credential: const {
              'provider': 'aws',
              'access_key_id': 'ZZZZEXAMPLE00000001',
              'secret_access_key': 'submitted-invalid-secret',
            },
          ),
        );
        expect(
          rejected.state,
          CloudBootstrapSessionState.credentialReentryRequired,
        );
        expect(rejected.finding?.code, 'BOOTSTRAP_CREDENTIAL_INVALID');

        final azureTarget = CloudBootstrapTarget.azure(
          tenantId: 'tenant-demo',
          subscriptionId: 'subscription-demo',
          region: 'westeurope',
          bootstrapCredentialKeyId: 'manual-key-demo',
        );
        final azureGuide = await api.getCloudBootstrapGuide(
          CloudProvider.azure,
          azureTarget,
        );
        expect(
          azureGuide.bootstrapAuthorityPack.id,
          'bootstrap.azure.admin-v2',
        );
        expect(azureGuide.bootstrapAuthorityPack.version, '2');
        final azureDraft = await api.createCloudBootstrapSession(
          guide: azureGuide,
          entryPoint: CloudBootstrapEntryPoint.settings,
          displayName: 'Azure manual cleanup',
          idempotencyKey: 'demo-create-manual-0001',
        );
        final pending = await api.executeCloudBootstrapSession(
          azureDraft.id,
          CloudBootstrapExecuteRequest(
            expectedRevision: azureDraft.revision,
            idempotencyKey: 'demo-execute-manual-0001',
            credentialOrigin:
                CloudBootstrapCredentialOrigin.dedicatedDisposable,
            credential: const {
              'provider': 'azure',
              'tenant_id': 'tenant-demo',
              'subscription_id': 'subscription-demo',
              'client_id': 'client-demo',
              'client_secret': 'submitted-azure-secret',
            },
          ),
        );
        expect(
          pending.state,
          CloudBootstrapSessionState.manualRevocationRequired,
        );
        expect(pending.safeCredentialIdentifier, 'manual-key-demo');
        expect(pending.finding?.code, 'BOOTSTRAP_MANUAL_REVOCATION_REQUIRED');
        expect(pending.finding?.remediationUrl?.scheme, 'https');
        final ready = await api.acknowledgeCloudBootstrapRevocation(
          pending.id,
          pending.revision,
        );
        expect(ready.state, CloudBootstrapSessionState.ready);
        expect(ready.disposalStatus, 'revoked');
      },
    );

    test('filters active and terminal bootstrap sessions exactly', () async {
      final guide = await api.getCloudBootstrapGuide(
        CloudProvider.aws,
        CloudBootstrapTarget.aws(
          accountId: '123456789012',
          region: 'eu-central-1',
        ),
      );
      final draft = await api.createCloudBootstrapSession(
        guide: guide,
        entryPoint: CloudBootstrapEntryPoint.settings,
        displayName: 'Filtered bootstrap',
        idempotencyKey: 'create-filter-session-0001',
      );

      expect(await api.listCloudBootstrapSessions(active: true), [draft]);
      expect(await api.listCloudBootstrapSessions(active: false), isEmpty);

      await api.cancelCloudBootstrapSession(draft.id, draft.revision);
      expect(await api.listCloudBootstrapSessions(active: true), isEmpty);
      expect(
        (await api.listCloudBootstrapSessions(active: false)).single.state,
        CloudBootstrapSessionState.cancelled,
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
      expect(aws.awsTwinMakerContext, isNotNull);
      expect(
        aws.awsTwinMakerContext!.currentPlan.mode,
        AwsTwinMakerPricingPlanMode.standard,
      );
      expect(aws.awsTwinMakerContext!.verifiedAccountId, '123456789012');
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

    test('supports health, catalog-bound calculation, and persistence', () async {
      expect((await api.getPricingHealth()).providers, hasLength(3));
      expect((await api.getPricingStatusResult()).isSuccess, isTrue);
      expect((await api.getRegionsStatus())['providers'], hasLength(3));
      final seeded = await api.getOptimizerConfig('demo-configured');
      expect(
        seeded?.pricingCatalogContext
            ?.reference(CloudProvider.aws)
            .pricingRegion,
        'eu-central-1',
      );

      final calculationParams = CalcParams.fiveLayerV2(
        scenario: FiveLayerWorkloadScenario.small,
      );
      final run = await api.createOptimizerRun('demo-draft', calculationParams);
      final calculation = run.optimization;
      expect(run.twinId, 'demo-draft');
      expect(
        run.id,
        matches(
          RegExp(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-a[0-9a-f]{3}-[0-9a-f]{12}$',
          ),
        ),
      );
      expect(calculation.result.totalCost, greaterThan(0));
      expect(calculation.result.pricingCatalogContext, isNotNull);
      expect(calculation.result.pricingCatalogContext!.catalogs, hasLength(3));
      expect(calculation.isNativeFiveLayerV2, isTrue);
      expect(
        calculation.result.optimizationProfile?.profileId,
        'cost-minimization-v2',
      );
      expect(
        calculation.result.optimizationProfile?.resultSchemaVersion,
        'cost-result.v2',
      );
      expect(calculation.result.cheapestPath, hasLength(7));
      expect(calculation.result.transferPricingContext, isNull);
      expect(calculation.result.optimizationDiagnostics, isNull);
      expect(calculation.result.transferCosts, hasLength(8));
      expect(calculation.result.transferCosts!.values, everyElement(0));
      final persisted = await api.getOptimizerConfig('demo-draft');
      expect(persisted?.optimization?.payload, isNotEmpty);
      expect(persisted?.params?.toJson(), calculationParams.toJson());
      expect(
        persisted?.pricingCatalogContext,
        calculation.result.pricingCatalogContext,
      );
      final latest = await api.getLatestOptimizerRun('demo-draft');
      expect(latest?.id, run.id);
      expect(latest?.selectedForDeploymentAt, isNull);
      final specification =
          latest?.specification as ResolvedDeploymentSpecificationV2;
      expect(specification.architectureProfileRef.version, '2');
      expect(specification.logicalComponentCount, 7);
      expect(specification.providers, {CloudProvider.aws});
      expect(specification.readiness.evaluationOnly, isTrue);
      expect(
        specification.readiness.blockingGateIds,
        unorderedEquals(const [
          'gate.live-capacity.aws.dynamodb-partition-distribution',
          'gate.live-capacity.aws.reader-latency-and-quota',
          'gate.live-capacity.aws.twinmaker-query-behavior',
          'gate.live-pricing.aws.twinmaker-account-plan',
        ]),
      );
      expect(
        ResolvedDeploymentReview.fromRun(latest).state,
        ResolvedDeploymentReviewState.evaluationOnly,
      );
      final architecture = await api.getRunResolvedArchitecture(run.id);
      expect(
        architecture.architecture.schemaVersion,
        'resolved-twin-architecture.v2',
      );
      expect(
        architecture.architecture.resolutionStatus,
        'offline_contract_fixture',
      );
      expect(
        architecture.architecture.deploymentSpecificationDigest,
        specification.digest,
      );
      expect(
        architecture.architecture.costSummary.monthlyTotal,
        run.optimization.payload['totalCostExact'],
      );
      expect(
        double.parse(architecture.architecture.costSummary.monthlyTotal),
        run.totalMonthlyCost,
      );

      await expectLater(
        api.selectOptimizerRunForDeployment('demo-draft', run.id),
        throwsDemoCode('DEPLOYMENT_CAPACITY_EVIDENCE_PENDING'),
      );
      expect(
        (await api.getLatestOptimizerRun(
          'demo-draft',
        ))?.selectedForDeploymentAt,
        isNull,
      );
    });

    test('rejects a legacy workload after Five-layer v2 activation', () async {
      final params = CalcParams.fromJson({
        ...CalcParams.defaultParams().toJson(),
        'integrateErrorHandling': true,
      });

      await expectLater(
        api.createOptimizerRun('demo-draft', params),
        throwsDemoCode('ARCH_WORKLOAD_INCOMPATIBLE'),
      );
      expect(await api.getOptimizerConfig('demo-draft'), isNull);
    });

    test('keeps all v2 scenario evidence internally paired', () async {
      const cases = <(FiveLayerWorkloadScenario, String, Set<CloudProvider>)>[
        (FiveLayerWorkloadScenario.small, 'USD', {CloudProvider.aws}),
        (
          FiveLayerWorkloadScenario.medium,
          'EUR',
          {CloudProvider.azure, CloudProvider.gcp},
        ),
        (
          FiveLayerWorkloadScenario.large,
          'USD',
          {CloudProvider.aws, CloudProvider.azure, CloudProvider.gcp},
        ),
      ];

      for (final testCase in cases) {
        final run = await api.createOptimizerRun(
          'demo-draft',
          CalcParams.fiveLayerV2(scenario: testCase.$1, currency: testCase.$2),
        );
        final specification =
            run.deploymentRun.specification
                as ResolvedDeploymentSpecificationV2;
        final architecture = await api.getRunResolvedArchitecture(run.id);

        expect(specification.currency, testCase.$2);
        expect(specification.providers, testCase.$3);
        expect(specification.readiness.evaluationOnly, isTrue);
        expect(specification.readiness.blockingGateIds, isNotEmpty);
        expect(architecture.architecture.costSummary.currency, testCase.$2);
        expect(run.optimization.isNativeFiveLayerV2, isTrue);
        expect(run.optimization.payload, isNot(contains('inputParamsUsed')));
        expect(run.optimization.result.cheapestPath, hasLength(7));
        expect(
          architecture.architecture.costSummary.monthlyTotal,
          run.optimization.payload['totalCostExact'],
        );
        expect(
          architecture.architecture.deploymentSpecificationDigest,
          specification.digest,
        );
        await expectLater(
          api.selectOptimizerRunForDeployment('demo-draft', run.id),
          throwsDemoCode('DEPLOYMENT_CAPACITY_EVIDENCE_PENDING'),
        );
      }
    });

    test(
      'uses the pinned Five-layer v2 EUR conversion in demo results',
      () async {
        final usd = await api.createOptimizerRun(
          'demo-draft',
          CalcParams.fiveLayerV2(scenario: FiveLayerWorkloadScenario.small),
        );
        final eur = await api.createOptimizerRun(
          'demo-draft',
          CalcParams.fiveLayerV2(
            scenario: FiveLayerWorkloadScenario.small,
            currency: 'EUR',
          ),
        );

        expect(eur.currency, 'EUR');
        expect(
          eur.totalMonthlyCost,
          closeTo(usd.totalMonthlyCost * 0.865948, 0.00001),
        );
      },
    );

    test(
      'does not invent catalog evidence for a legacy saved result',
      () async {
        final legacy = store.optimizerConfig('demo-configured')!;
        legacy.remove('pricing_catalog_context');
        (legacy['result'] as Map).remove('pricingCatalogs');
        store.setOptimizerConfig('demo-configured', legacy);

        final loaded = await api.getOptimizerConfig('demo-configured');

        expect(loaded?.pricingCatalogContext, isNull);
        expect(loaded?.optimization?.result.pricingCatalogContext, isNull);
        final run = await api.getLatestOptimizerRun('demo-configured');
        expect(run?.compatibility, DeploymentCompatibility.legacyNotDeployable);
        expect(run?.specification, isNull);
      },
    );
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
      final access = await api.getDeploymentAccess('demo-configured');
      expect(access.surfaceFor(DeploymentLayer.l4)?.provider.name, 'azure');
      expect(access.surfaceFor(DeploymentLayer.l5)?.provider.name, 'aws');
      await expectLater(
        api.rotateGcpGrafanaViewerCredential('demo-configured'),
        throwsDemoCode('DEMO_GCP_GRAFANA_ROTATION_UNAVAILABLE'),
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
      'demo GCP viewer rotation is typed, deterministic, and one-time',
      () async {
        final optimizer = store.optimizerConfig('demo-deployed')!;
        (optimizer['cheapest_path'] as Map)['l5'] = 'GCP';
        store.setOptimizerConfig('demo-deployed', optimizer);

        final access = await api.getDeploymentAccess('demo-deployed');
        expect(access.surfaceFor(DeploymentLayer.l5)?.provider.name, 'gcp');
        final first = await api.rotateGcpGrafanaViewerCredential(
          'demo-deployed',
        );
        final second = await api.rotateGcpGrafanaViewerCredential(
          'demo-deployed',
        );

        expect(
          first.password,
          matches(RegExp(r'^demo-viewer-demo-grafana-viewer-rotation-\d{4}$')),
        );
        expect(
          second.password,
          matches(RegExp(r'^demo-viewer-demo-grafana-viewer-rotation-\d{4}$')),
        );
        expect(second.password, isNot(first.password));
        expect(first.toString(), isNot(contains(first.password)));
      },
    );

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
