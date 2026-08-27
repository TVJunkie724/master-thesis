import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/deployment_verification.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/telemetry_evidence_panel.dart';

void main() {
  testWidgets(
    'shows latest persisted trace, counts, phases, and earlier runs',
    (tester) async {
      final latest = _record(
        id: 'verification-latest',
        result: _passEvidence(),
      );
      final earlier = _notRunRecord();

      await _pump(tester, latestRecord: latest, history: [latest, earlier]);

      expect(find.text('PASS'), findsOneWidget);
      expect(find.text('VERIFY-ABCDEF12'), findsOneWidget);
      expect(find.text('3 pass · 0 fail · 0 skip'), findsOneWidget);
      expect(find.text('Phase evidence'), findsOneWidget);
      expect(find.text('Earlier persisted runs'), findsOneWidget);

      await tester.tap(find.text('Phase evidence'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Phase 1 · message accepted'), findsOneWidget);
      expect(
        find.textContaining('Phase 3 · gcp twin projection'),
        findsOneWidget,
      );

      await tester.tap(find.text('Earlier persisted runs'));
      await tester.pumpAndSettle();
      expect(find.text('verification-earlier'), findsOneWidget);
      expect(find.textContaining('NOT RUN'), findsOneWidget);
    },
  );

  testWidgets('expands failed phase evidence and shows failure context', (
    tester,
  ) async {
    final record = _record(
      id: 'verification-failed',
      status: 'fail',
      result: _failEvidence(),
      errorCode: 'PROJECTION_TIMEOUT',
      errorMessage: 'Projection was not observed.',
    );

    await _pump(tester, latestRecord: record, history: [record]);

    expect(find.text('FAIL'), findsOneWidget);
    expect(
      find.text('Failed phase: Phase 3 - Twin Projection'),
      findsOneWidget,
    );
    expect(find.textContaining('Phase 2 · trace correlated'), findsOneWidget);
  });

  testWidgets('distinguishes loading, running, empty, and history failure', (
    tester,
  ) async {
    await _pump(tester, isLoading: true);
    expect(find.textContaining('Loading persisted'), findsOneWidget);

    await _pump(
      tester,
      isRunning: true,
      activeVerificationId: 'verification-active',
    );
    expect(find.text('RUNNING'), findsOneWidget);
    expect(
      find.textContaining('verification-active is running'),
      findsOneWidget,
    );

    await _pump(tester);
    expect(find.text('NO EVIDENCE'), findsOneWidget);
    expect(find.textContaining('No persisted telemetry'), findsOneWidget);

    await _pump(tester, historyError: 'database unavailable');
    expect(
      find.text('History unavailable: database unavailable'),
      findsOneWidget,
    );
  });
}

Future<void> _pump(
  WidgetTester tester, {
  bool isLoading = false,
  bool isRunning = false,
  String? historyError,
  String? activeVerificationId,
  TelemetryVerificationEvidence? terminalEvidence,
  TelemetryVerificationRecord? latestRecord,
  List<TelemetryVerificationRecord> history = const [],
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: TelemetryEvidencePanel(
            isLoading: isLoading,
            isRunning: isRunning,
            historyError: historyError,
            activeVerificationId: activeVerificationId,
            terminalEvidence: terminalEvidence,
            latestRecord: latestRecord,
            history: history,
          ),
        ),
      ),
    ),
  );
  if (isLoading) {
    await tester.pump();
  } else {
    await tester.pumpAndSettle();
  }
}

TelemetryVerificationRecord _record({
  required String id,
  String status = 'pass',
  required Map<String, dynamic> result,
  String? errorCode,
  String? errorMessage,
}) => TelemetryVerificationRecord.fromJson({
  'id': id,
  'twin_id': 'twin-1',
  'deployment_id': 'deployment-1',
  'session_id': 'session-1',
  'device_id': 'sensor-1',
  'status': status,
  'trace_id': result['trace_id'],
  'result': result,
  'error_code': errorCode,
  'error_message': errorMessage,
  'requested_at': '2026-08-27T12:00:00Z',
  'completed_at': '2026-08-27T12:00:03Z',
});

TelemetryVerificationRecord _notRunRecord() =>
    TelemetryVerificationRecord.fromJson({
      'id': 'verification-earlier',
      'twin_id': 'twin-1',
      'deployment_id': 'deployment-1',
      'session_id': 'session-0',
      'device_id': 'sensor-1',
      'status': 'not_run',
      'trace_id': null,
      'result': null,
      'error_code': 'DEMO_MODE',
      'error_message': 'Live telemetry is disabled.',
      'requested_at': '2026-08-26T12:00:00Z',
      'completed_at': '2026-08-26T12:00:00Z',
    });

Map<String, dynamic> _passEvidence() => {
  'schema_version': 'telemetry-verification.v1',
  'trace_id': 'VERIFY-ABCDEF12',
  'status': 'pass',
  'pass_count': 3,
  'fail_count': 0,
  'skip_count': 0,
  'total_time': 3.25,
  'failed_phase': null,
  'evidence': [
    {
      'phase': 1,
      'kind': 'message_accepted',
      'provider': 'aws',
      'record_count': null,
      'correlation': null,
    },
    {
      'phase': 2,
      'kind': 'trace_correlated_hot_record',
      'provider': 'azure',
      'record_count': 1,
      'correlation': null,
    },
    {
      'phase': 3,
      'kind': 'gcp_twin_projection',
      'provider': 'gcp',
      'record_count': null,
      'correlation': 'source_sequence',
    },
  ],
};

Map<String, dynamic> _failEvidence() => {
  'schema_version': 'telemetry-verification.v1',
  'trace_id': 'VERIFY-1234ABCD',
  'status': 'fail',
  'pass_count': 2,
  'fail_count': 1,
  'skip_count': 0,
  'total_time': 15,
  'failed_phase': 'Phase 3 - Twin Projection',
  'evidence': [
    {
      'phase': 1,
      'kind': 'message_accepted',
      'provider': 'aws',
      'record_count': null,
      'correlation': null,
    },
    {
      'phase': 2,
      'kind': 'trace_correlated_hot_record',
      'provider': 'azure',
      'record_count': 1,
      'correlation': null,
    },
  ],
};
