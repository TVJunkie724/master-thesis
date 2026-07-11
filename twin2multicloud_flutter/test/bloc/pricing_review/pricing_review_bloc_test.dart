import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/pricing_review/pricing_review.dart';
import 'package:twin2multicloud_flutter/models/cloud_access_inventory.dart';
import 'package:twin2multicloud_flutter/models/pricing_candidate_review.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';
import 'package:twin2multicloud_flutter/models/pricing_refresh_run.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;

  setUp(() => api = MockApiService());

  test('loads account-scoped health and access without twins', () async {
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    final bloc = PricingReviewBloc(api: api);

    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    expect(bloc.state.pricingHealth?.provider('aws')?.state, 'fresh');
    expect(bloc.state.accessFor('aws')?.connectionId, 'aws-1');
    verifyNever(api.getTwins);
    await bloc.close();
  });

  test('isolates health failure from usable cloud access', () async {
    when(api.getPricingHealth).thenThrow(Exception('health unavailable'));
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    final bloc = PricingReviewBloc(api: api);

    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    expect(bloc.state.pricingHealthError, contains('health unavailable'));
    expect(bloc.state.accessFor('aws')?.canRefreshPricing, isTrue);
    await bloc.close();
  });

  test('refreshes AWS with its account connection and loads reports', () async {
    when(
      () => api.startPricingRefresh('aws', connectionId: 'aws-1'),
    ).thenAnswer((_) async => _run('aws'));
    when(
      () => api.listPricingCandidateReports('aws', 'run-1'),
    ).thenAnswer((_) async => _reports());
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    final bloc = PricingReviewBloc(api: api);
    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    bloc.add(
      const PricingReviewProviderRefreshRequested('AWS', connectionId: 'aws-1'),
    );
    await bloc.stream.firstWhere(
      (state) =>
          state.latestRuns['aws']?.refreshRunId == 'run-1' &&
          state.reportsByProvider['aws']?.isNotEmpty == true,
    );

    expect(bloc.state.reportsByProvider['aws'], hasLength(1));
    verify(
      () => api.startPricingRefresh('aws', connectionId: 'aws-1'),
    ).called(1);
    await bloc.close();
  });

  test('refreshes public Azure pricing without a connection id', () async {
    when(
      () => api.startPricingRefresh('azure'),
    ).thenAnswer((_) async => _run('azure'));
    when(
      () => api.listPricingCandidateReports('azure', 'run-1'),
    ).thenAnswer((_) async => _reports(provider: 'azure'));
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    final bloc = PricingReviewBloc(api: api);
    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    bloc.add(const PricingReviewProviderRefreshRequested('azure'));
    await bloc.stream.firstWhere(
      (state) =>
          state.latestRuns.containsKey('azure') &&
          state.refreshingProvider == null,
    );

    verify(() => api.startPricingRefresh('azure')).called(1);
    await bloc.close();
  });

  test('keeps a successful run when evidence loading fails', () async {
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    when(
      () => api.startPricingRefresh('aws', connectionId: 'aws-1'),
    ).thenAnswer((_) async => _run('aws'));
    when(
      () => api.listPricingCandidateReports('aws', 'run-1'),
    ).thenThrow(Exception('reports unavailable'));
    final bloc = PricingReviewBloc(api: api);
    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    bloc.add(
      const PricingReviewProviderRefreshRequested('aws', connectionId: 'aws-1'),
    );
    await bloc.stream.firstWhere(
      (state) => state.reportErrorsByProvider.containsKey('aws'),
    );

    expect(bloc.state.latestRuns['aws']?.succeeded, isTrue);
    expect(bloc.state.feedback?.message, contains('was refreshed'));

    reset(api);
    when(
      () => api.listPricingCandidateReports('aws', 'run-1'),
    ).thenAnswer((_) async => _reports());
    bloc.add(const PricingReviewReportsReloadRequested('aws'));
    await bloc.stream.firstWhere(
      (state) =>
          state.reportsByProvider['aws']?.isNotEmpty == true &&
          !state.reportErrorsByProvider.containsKey('aws'),
    );

    verify(() => api.listPricingCandidateReports('aws', 'run-1')).called(1);
    await bloc.close();
  });

  test('failed refresh does not request candidate reports', () async {
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    when(
      () => api.startPricingRefresh('aws', connectionId: 'aws-1'),
    ).thenAnswer((_) async => _failedRun());
    final bloc = PricingReviewBloc(api: api);
    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    bloc.add(
      const PricingReviewProviderRefreshRequested('aws', connectionId: 'aws-1'),
    );
    await bloc.stream.firstWhere(
      (state) => state.latestRuns['aws']?.status == 'failed',
    );

    expect(bloc.state.feedback?.message, 'Provider rejected the request.');
    verifyNever(() => api.listPricingCandidateReports(any(), any()));
    await bloc.close();
  });

  test('uses a valid AI suggestion as the review default', () async {
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    when(
      () => api.startPricingRefresh('aws', connectionId: 'aws-1'),
    ).thenAnswer((_) async => _run('aws'));
    when(
      () => api.listPricingCandidateReports('aws', 'run-1'),
    ).thenAnswer((_) async => _reports(aiCandidateId: 'candidate-2'));
    final bloc = PricingReviewBloc(api: api);
    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    bloc.add(
      const PricingReviewProviderRefreshRequested('aws', connectionId: 'aws-1'),
    );
    await bloc.stream.firstWhere(
      (state) => state.reportsByProvider['aws']?.isNotEmpty == true,
    );

    expect(bloc.state.selectedCandidateIds['report-1'], 'candidate-2');
    await bloc.close();
  });

  test('does not refresh when provider access is missing', () async {
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(
      api.getCloudAccessInventory,
    ).thenAnswer((_) async => _access(gcpMissing: true));
    final bloc = PricingReviewBloc(api: api);
    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    bloc.add(const PricingReviewProviderRefreshRequested('gcp'));
    await Future<void>.delayed(Duration.zero);

    verifyNever(
      () => api.startPricingRefresh(
        any(),
        connectionId: any(named: 'connectionId'),
      ),
    );
    await bloc.close();
  });

  test('rejects a connection id that differs from confirmed access', () async {
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    final bloc = PricingReviewBloc(api: api);
    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );

    bloc.add(
      const PricingReviewProviderRefreshRequested(
        'aws',
        connectionId: 'different-account',
      ),
    );
    await Future<void>.delayed(Duration.zero);

    verifyNever(
      () => api.startPricingRefresh(
        any(),
        connectionId: any(named: 'connectionId'),
      ),
    );
    await bloc.close();
  });

  test('loads a secret-free trace lazily only once', () async {
    when(
      () => api.getPricingCandidateTrace('report-1'),
    ).thenAnswer((_) async => _trace());
    final bloc = PricingReviewBloc(api: api);

    bloc.add(const PricingReviewReportExpanded('report-1'));
    await bloc.stream.firstWhere(
      (state) => state.tracesByReportId.containsKey('report-1'),
    );
    bloc.add(const PricingReviewReportExpanded('report-1'));
    await Future<void>.delayed(Duration.zero);

    verify(() => api.getPricingCandidateTrace('report-1')).called(1);
    await bloc.close();
  });

  test('persists the explicitly selected alternative', () async {
    when(api.getPricingHealth).thenAnswer((_) async => _health());
    when(api.getCloudAccessInventory).thenAnswer((_) async => _access());
    when(
      () => api.startPricingRefresh('aws', connectionId: 'aws-1'),
    ).thenAnswer((_) async => _run('aws'));
    when(
      () => api.listPricingCandidateReports('aws', 'run-1'),
    ).thenAnswer((_) async => _reports());
    when(
      () => api.createPricingReviewDecision(
        'report-1',
        'select_alternative',
        candidateId: 'candidate-2',
      ),
    ).thenAnswer((_) async => _decision());
    final bloc = PricingReviewBloc(api: api);
    bloc.add(const PricingReviewStarted());
    await bloc.stream.firstWhere(
      (state) => !state.isLoadingPricingHealth && !state.isLoadingCloudAccess,
    );
    bloc.add(
      const PricingReviewProviderRefreshRequested('aws', connectionId: 'aws-1'),
    );
    await bloc.stream.firstWhere(
      (state) => state.reportsByProvider['aws']?.isNotEmpty == true,
    );
    bloc.add(const PricingReviewCandidateSelected('report-1', 'candidate-2'));
    await bloc.stream.firstWhere(
      (state) => state.selectedCandidateIds['report-1'] == 'candidate-2',
    );

    bloc.add(
      const PricingReviewDecisionRequested(
        reportId: 'report-1',
        decision: 'select_alternative',
      ),
    );
    await bloc.stream.firstWhere(
      (state) => state.decisionsByReportId.containsKey('report-1'),
    );

    expect(bloc.state.decisionsByReportId['report-1']?.decision, 'approve');
    await bloc.close();
  });
}

PricingHealthResponse _health() => PricingHealthResponse.fromJson({
  'schema_version': 'pricing-health.v1',
  'providers': {
    'aws': {
      'provider': 'aws',
      'state': 'fresh',
      'severity': 'success',
      'can_calculate': true,
      'pricing_freshness': 'fresh',
      'credential_summary': {},
    },
  },
});

CloudAccessInventory _access({bool gcpMissing = false}) =>
    CloudAccessInventory.fromJson({
      'schema_version': 'cloud-access-inventory.v1',
      'providers': {
        'aws': {
          'provider': 'aws',
          'pricing': {
            'connection_id': 'aws-1',
            'provider': 'aws',
            'purpose': 'pricing',
            'scope': 'user',
            'identity_label': 'AWS Pricing',
            'status': 'active',
          },
        },
        'azure': {
          'provider': 'azure',
          'pricing': {
            'provider': 'azure',
            'purpose': 'pricing',
            'scope': 'public',
            'identity_label': 'Azure Retail Prices API',
            'status': 'active',
          },
        },
        'gcp': {
          'provider': 'gcp',
          'pricing': {
            'connection_id': gcpMissing ? null : 'gcp-1',
            'provider': 'gcp',
            'purpose': 'pricing',
            'scope': 'user',
            'identity_label': 'GCP Pricing',
            'status': gcpMissing ? 'missing' : 'active',
          },
        },
      },
    });

PricingRefreshRun _run(String provider) => PricingRefreshRun.fromJson({
  'schema_version': 'pricing-refresh-run.v1',
  'refresh_run_id': 'run-1',
  'provider': provider,
  'status': 'succeeded',
  'credential_summary': {'scope': provider == 'azure' ? 'public' : 'user'},
  'force': true,
  'sse_url': '/stream',
  'created_at': '2026-07-11T10:00:00Z',
});

PricingRefreshRun _failedRun() => PricingRefreshRun.fromJson({
  'refresh_run_id': 'run-failed',
  'provider': 'aws',
  'status': 'failed',
  'credential_summary': {'scope': 'user'},
  'error_message': 'Provider rejected the request.',
  'created_at': '2026-07-11T10:00:00Z',
});

PricingCandidateReportList _reports({
  String provider = 'aws',
  String? aiCandidateId,
}) => PricingCandidateReportList.fromJson({
  'provider': provider,
  'refresh_run_id': 'run-1',
  'reports': [
    {
      'report_id': 'report-1',
      'provider': provider,
      'refresh_run_id': 'run-1',
      'intent_id': 'iot.message_ingest',
      'deterministic_selection': {
        'candidate_id': 'candidate-1',
        'selectable': true,
      },
      'ai_suggestion': {
        'enabled': aiCandidateId != null,
        'candidate_id': aiCandidateId,
      },
      'candidates': [
        {
          'candidate_id': 'candidate-1',
          'source_type': 'provider_api',
          'field_path': 'pricing.primary',
        },
        {
          'candidate_id': 'candidate-2',
          'source_type': 'provider_api',
          'field_path': 'pricing.alternative',
        },
      ],
      'created_at': '2026-07-11T10:00:00Z',
    },
  ],
});

PricingTrace _trace() => PricingTrace.fromJson({
  'report_id': 'report-1',
  'provider': 'aws',
  'sanitization': {'bounded': true, 'secret_free': true},
});

PricingReviewDecision _decision() => PricingReviewDecision.fromJson({
  'decision_id': 'decision-1',
  'report_id': 'report-1',
  'provider': 'aws',
  'intent_id': 'iot.message_ingest',
  'decision': 'approve',
  'selected_candidate_id': 'candidate-2',
});
