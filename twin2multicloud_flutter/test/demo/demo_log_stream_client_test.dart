import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/demo/demo_log_stream_client.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late DemoFixtureStore showcase;

  setUp(() async {
    showcase = await DemoFixtureStore.load(DemoScenario.showcase);
  });

  test('streams deterministic deployment logs and outputs', () async {
    final client = DemoLogStreamClient(
      store: showcase,
      interval: Duration.zero,
    );

    final events = await client
        .streamDeploymentLogs('/demo/deployment/demo-deployed/session-1')
        .toList();

    expect(events.map((event) => event.id), [1, 2, 3]);
    expect(events.last.isComplete, isTrue);
    expect(events.last.outputs, isNotEmpty);
  });

  test('resumes strictly after the supplied event cursor', () async {
    final client = DemoLogStreamClient(
      store: showcase,
      interval: Duration.zero,
    );

    final events = await client
        .streamDeploymentLogs(
          '/demo/deployment/demo-deployed/session-1',
          lastEventId: 2,
        )
        .toList();

    expect(events, hasLength(1));
    expect(events.single.id, 3);
  });

  test('supports pricing, trace, and verification stream contracts', () async {
    final client = DemoLogStreamClient(
      store: showcase,
      interval: Duration.zero,
    );

    final pricing = await client
        .streamDeploymentLogs('/demo/pricing/aws/run-1')
        .toList();
    final trace = await client
        .streamDeploymentLogs('/demo/trace/demo-deployed/trace-1')
        .toList();
    final verification = await client
        .streamDeploymentLogs('/demo/verification/demo-deployed/check-1')
        .toList();

    expect(pricing.last.isComplete, isTrue);
    expect(trace.last.type, 'done');
    expect(trace.where((event) => event.isLog), hasLength(3));
    expect(verification.last.isComplete, isTrue);
  });

  test('cancels an active stream before subsequent events', () async {
    final client = DemoLogStreamClient(
      store: showcase,
      interval: const Duration(milliseconds: 1),
    );
    final events = <int>[];

    await for (final event in client.streamDeploymentLogs(
      '/demo/deployment/demo-deployed/session-1',
    )) {
      events.add(event.id);
      client.cancel();
    }

    expect(events, [1]);
  });

  test('rejects unknown stream URLs with a structured error', () async {
    final client = DemoLogStreamClient(
      store: showcase,
      interval: Duration.zero,
    );

    await expectLater(
      client.streamDeploymentLogs('/unknown').toList(),
      throwsA(
        isA<DemoApiException>().having(
          (error) => error.code,
          'code',
          'DEMO_STREAM_NOT_FOUND',
        ),
      ),
    );
  });
}
