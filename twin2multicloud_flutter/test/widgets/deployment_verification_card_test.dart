import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/deployment_verification/deployment_verification.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/services/sse_service.dart';
import 'package:twin2multicloud_flutter/models/deployment_verification.dart';
import 'package:twin2multicloud_flutter/widgets/deployment_verification_card.dart';
import 'package:twin2multicloud_flutter/widgets/twin_overview/twin_overview_strings.dart';

class MockApiService extends Mock implements ApiService {}

class MockSseService extends Mock implements SseService {}

void main() {
  setUpAll(() {
    registerFallbackValue(<String, dynamic>{});
  });

  for (final outcome in ['pass', 'fail', 'empty', 'unavailable']) {
    testWidgets('history-only mode preserves $outcome without live controls', (
      tester,
    ) async {
      final api = MockApiService();
      final records = <TelemetryVerificationRecord>[
        if (outcome == 'pass' || outcome == 'fail')
          TelemetryVerificationRecord(
            id: 'record-1',
            twinId: 'twin-1',
            sessionId: 'session-1',
            deviceId: 'sensor',
            requestedAt: DateTime.utc(2026, 10, 19),
            status: outcome == 'pass'
                ? TelemetryVerificationStatus.pass
                : TelemetryVerificationStatus.fail,
            result: outcome == 'pass'
                ? const TelemetryVerificationEvidence(
                    schemaVersion:
                        TelemetryVerificationEvidence.supportedSchemaVersion,
                    traceId: 'VERIFY-ABCDEF12',
                    status: TelemetryVerificationStatus.pass,
                    passCount: 3,
                    failCount: 0,
                    skipCount: 0,
                    totalTime: 3.4,
                    evidence: [],
                  )
                : null,
            errorMessage: outcome == 'fail' ? 'Projection failed' : null,
          ),
      ];
      when(() => api.listDataFlowVerifications('twin-1')).thenAnswer((_) async {
        if (outcome == 'unavailable') throw Exception('History unavailable');
        return TelemetryVerificationHistory(
          schemaVersion: TelemetryVerificationHistory.supportedSchemaVersion,
          verifications: records,
        );
      });
      await tester.binding.setSurfaceSize(const Size(640, 900));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: TextScaler.linear(2)),
            child: child!,
          ),
          home: Scaffold(
            body: SingleChildScrollView(
              child: BlocProvider(
                create: (_) => DeploymentVerificationBloc(
                  twinId: 'twin-1',
                  api: api,
                  logStreamClientFactory: () =>
                      throw StateError('No live stream allowed'),
                ),
                child: const DeploymentVerificationCard(historyOnly: true),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.text(TwinOverviewStrings.recordedVerification),
        findsOneWidget,
      );
      expect(find.text('CHECK INFRASTRUCTURE'), findsNothing);
      expect(find.text('VERIFY DATA FLOW'), findsNothing);
      expect(find.byType(TextField), findsNothing);
      if (outcome == 'pass' || outcome == 'fail') {
        expect(find.text(outcome.toUpperCase()), findsOneWidget);
        if (outcome == 'pass') {
          expect(find.text('VERIFY-ABCDEF12'), findsOneWidget);
          expect(find.text('3 pass · 0 fail · 0 skip'), findsOneWidget);
        }
      } else if (outcome == 'empty') {
        expect(find.text('NO EVIDENCE'), findsOneWidget);
      } else {
        expect(find.textContaining('History unavailable:'), findsOneWidget);
      }
      verify(() => api.listDataFlowVerifications('twin-1')).called(1);
      verifyNever(() => api.verifyInfrastructure(any()));
      verifyNever(() => api.verifyDataFlow(any(), any()));
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('renders verification actions and dispatches infrastructure', (
    tester,
  ) async {
    final api = MockApiService();
    final sse = MockSseService();
    when(() => api.verifyInfrastructure('twin-1')).thenAnswer(
      (_) async => {
        'checks': const [],
        'summary': {
          'pass_count': 0,
          'fail_count': 0,
          'skip_count': 0,
          'total': 0,
          'healthy': true,
        },
      },
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: BlocProvider(
              create: (_) => DeploymentVerificationBloc(
                twinId: 'twin-1',
                api: api,
                logStreamClientFactory: () => sse,
                loadHistory: false,
              ),
              child: const DeploymentVerificationCard(),
            ),
          ),
        ),
      ),
    );

    expect(find.text('DEPLOYMENT VERIFICATION'), findsOneWidget);
    expect(find.text('CHECK INFRASTRUCTURE'), findsOneWidget);
    expect(find.text('VERIFY DATA FLOW'), findsOneWidget);
    expect(find.text(TwinOverviewStrings.infrastructureScope), findsOneWidget);
    expect(
      find.text('Payload values must satisfy any configured event conditions.'),
      findsOneWidget,
    );
    expect(find.textContaining('L0-L5'), findsNothing);
    expect(find.text(TwinOverviewStrings.telemetryScope), findsOneWidget);
    expect(find.textContaining('Cost: none'), findsNothing);
    expect(find.textContaining('event checking is enabled'), findsNothing);

    await tester.tap(find.text('CHECK INFRASTRUCTURE'));
    await tester.pumpAndSettle();

    verify(() => api.verifyInfrastructure('twin-1')).called(1);
  });
}
