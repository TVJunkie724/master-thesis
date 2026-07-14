import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/services/sse_service.dart';

void main() {
  test(
    'streams typed SSE events with auth and merged reconnect cursor',
    () async {
      late http.Request capturedRequest;
      var token = 'stale-token';
      final client = MockClient((request) async {
        capturedRequest = request;
        return http.Response(
          'id: 1\n'
          'data: {"id":1,"type":"log","data":"Validated manifest.",'
          '"level":"info","timestamp":"2026-07-14T12:00:00Z"}\n\n'
          'id: 2\n'
          'data: {"id":2,"type":"complete","data":"Deployment complete",'
          '"outputs":{"endpoint":"https://example.test"},'
          '"timestamp":"2026-07-14T12:00:01Z"}\n\n',
          200,
          headers: {'content-type': 'text/event-stream'},
        );
      });
      final service = SseService(
        baseUrl: 'http://localhost:5005',
        authTokenProvider: () async => token,
        client: client,
      );

      final stream = service.streamDeploymentLogs(
        '/sse/deploy/session-1?source=overview',
        lastEventId: 7,
      );
      token = 'test-token';
      final events = await stream.toList();

      expect(capturedRequest.url.path, '/sse/deploy/session-1');
      expect(capturedRequest.url.queryParameters, {
        'source': 'overview',
        'last_event_id': '7',
      });
      expect(capturedRequest.headers['Authorization'], 'Bearer test-token');
      expect(capturedRequest.headers['Accept'], 'text/event-stream');
      expect(events, hasLength(2));
      expect(events.first.id, 1);
      expect(events.first.message, 'Validated manifest.');
      expect(events.first.timestamp, DateTime.utc(2026, 7, 14, 12));
      expect(events.last.isComplete, isTrue);
      expect(events.last.outputs, {'endpoint': 'https://example.test'});
      service.cancel();
    },
  );

  test('rejects non-success HTTP responses', () async {
    final service = SseService(
      baseUrl: 'http://localhost:5005',
      client: MockClient((_) async => http.Response('unauthorized', 401)),
    );

    await expectLater(
      service.streamDeploymentLogs('/sse/deploy/session-1'),
      emitsError(
        isA<AppException>().having(
          (error) => error.code,
          'code',
          'DEPLOYMENT_STREAM_HTTP_ERROR',
        ),
      ),
    );
    service.cancel();
  });

  test('rejects malformed event timestamps as contract errors', () async {
    final service = SseService(
      baseUrl: 'http://localhost:5005',
      client: MockClient(
        (_) async => http.Response(
          'data: {"id":1,"type":"log","data":"message",'
          '"timestamp":"not-a-date"}\n\n',
          200,
        ),
      ),
    );

    await expectLater(
      service.streamDeploymentLogs('/sse/deploy/session-1'),
      emitsError(
        isA<AppException>().having(
          (error) => error.code,
          'code',
          'DEPLOYMENT_STREAM_EVENT_INVALID',
        ),
      ),
    );
    service.cancel();
  });

  test(
    'rejects oversized events without buffering them into UI state',
    () async {
      final oversized = 'x' * (1024 * 1024 + 1);
      final service = SseService(
        baseUrl: 'http://localhost:5005',
        client: MockClient(
          (_) async => http.Response('data: $oversized\n\n', 200),
        ),
      );

      await expectLater(
        service.streamDeploymentLogs('/sse/deploy/session-1'),
        emitsError(
          isA<AppException>().having(
            (error) => error.code,
            'code',
            'DEPLOYMENT_STREAM_EVENT_TOO_LARGE',
          ),
        ),
      );
      service.cancel();
    },
  );

  test('rejects external stream URLs and negative cursors before I/O', () {
    final service = SseService(
      baseUrl: 'http://localhost:5005',
      client: MockClient((_) async => http.Response('', 200)),
    );

    expect(
      () => service.streamDeploymentLogs('https://attacker.test/stream'),
      throwsA(isA<AppException>()),
    );
    expect(
      () => service.streamDeploymentLogs(
        '/sse/deploy/session-1',
        lastEventId: -1,
      ),
      throwsA(isA<AppException>()),
    );
    service.cancel();
  });
}
