import 'dart:convert';

import '../services/log_stream_client.dart';
import 'demo_fixture_store.dart';

class DemoLogStreamClient implements LogStreamClient {
  final DemoFixtureStore store;
  final Duration interval;
  bool _cancelled = false;

  DemoLogStreamClient({
    required this.store,
    this.interval = const Duration(milliseconds: 90),
  });

  @override
  Stream<SseLogEvent> streamDeploymentLogs(
    String sseUrl, {
    int? lastEventId,
  }) async* {
    _cancelled = false;
    final path = Uri.parse(sseUrl).path;
    final events = switch (path) {
      final value when value.startsWith('/demo/deployment/') =>
        _deploymentEvents(path, isDestroy: false),
      final value when value.startsWith('/demo/destroy/') => _deploymentEvents(
        path,
        isDestroy: true,
      ),
      final value when value.startsWith('/demo/trace/') => _traceEvents(path),
      final value when value.startsWith('/demo/verification/') =>
        _verificationEvents(path),
      final value when value.startsWith('/demo/pricing/') => _pricingEvents(
        path,
      ),
      _ => throw DemoApiException(
        'DEMO_STREAM_NOT_FOUND',
        'Demo stream "$path" does not exist.',
      ),
    };

    for (final event in events) {
      if (_cancelled) return;
      if (event.id <= (lastEventId ?? 0)) continue;
      if (interval > Duration.zero) await Future<void>.delayed(interval);
      if (_cancelled) return;
      yield event;
    }
  }

  @override
  void cancel() => _cancelled = true;

  List<SseLogEvent> _deploymentEvents(String path, {required bool isDestroy}) {
    final segments = Uri.parse(path).pathSegments;
    final twinId = segments.length > 2 ? segments[2] : '';
    final outputs = store.deploymentOutput(twinId)?['outputs'];
    return [
      const SseLogEvent(
        id: 1,
        message: 'Validated deployment manifest.',
        type: 'log',
        level: 'info',
      ),
      SseLogEvent(
        id: 2,
        message: isDestroy
            ? 'Removed provider resources in dependency order.'
            : 'Provisioned provider resources in dependency order.',
        type: 'log',
        level: 'info',
      ),
      SseLogEvent(
        id: 3,
        message: isDestroy
            ? 'Demo infrastructure destroyed successfully.'
            : 'Demo infrastructure deployed successfully.',
        type: 'complete',
        level: 'info',
        outputs: isDestroy || outputs is! Map
            ? null
            : Map<String, dynamic>.from(outputs),
      ),
    ];
  }

  List<SseLogEvent> _traceEvents(String path) {
    final now = store.clock();
    final records = [
      {
        'timestamp': now.toIso8601String(),
        'layer': 'L1',
        'provider': 'aws',
        'function': 'iot-ingest',
        'message': 'Test telemetry accepted.',
      },
      {
        'timestamp': now.add(const Duration(seconds: 1)).toIso8601String(),
        'layer': 'L2',
        'provider': 'azure',
        'function': 'normalize',
        'message': 'Telemetry normalized.',
      },
      {
        'timestamp': now.add(const Duration(seconds: 2)).toIso8601String(),
        'layer': 'L3',
        'provider': 'gcp',
        'function': 'storage-write',
        'message': 'Telemetry persisted.',
      },
    ];
    return [
      for (var index = 0; index < records.length; index += 1)
        SseLogEvent(
          id: index + 1,
          message: records[index]['message']!,
          type: 'log',
          level: 'info',
          data: {'data': records[index]},
        ),
      SseLogEvent(
        id: 4,
        message: 'Demo trace completed.',
        type: 'done',
        data: {
          'data': {'log_count': records.length},
        },
      ),
    ];
  }

  List<SseLogEvent> _verificationEvents(String path) {
    final segments = Uri.parse(path).pathSegments;
    final twinId = segments.length > 2 ? segments[2] : '';
    final dataFlow = store.verification(twinId)?['dataflow'];
    final summary = dataFlow is Map
        ? Map<String, dynamic>.from(dataFlow)
        : <String, dynamic>{
            'pass_count': 0,
            'fail_count': 1,
            'skip_count': 0,
            'total': 1,
            'healthy': false,
          };
    return [
      SseLogEvent(
        id: 1,
        message: jsonEncode({
          'timestamp': store.clock().toIso8601String(),
          'phase': 1,
          'name': 'Send telemetry',
          'status': 'running',
          'timeout': 10,
        }),
        type: 'log',
      ),
      SseLogEvent(
        id: 2,
        message: jsonEncode({
          'timestamp': store.clock().toIso8601String(),
          'phase': 1,
          'name': 'Send telemetry',
          'status': summary['healthy'] == true ? 'pass' : 'fail',
          'elapsed': 0.4,
          if (summary['healthy'] != true)
            'reason': 'Demo degraded scenario failure.',
        }),
        type: 'log',
      ),
      SseLogEvent(
        id: 3,
        message: jsonEncode(summary),
        type: summary['healthy'] == true ? 'complete' : 'error',
      ),
    ];
  }

  List<SseLogEvent> _pricingEvents(String path) {
    return const [
      SseLogEvent(id: 1, message: 'Queried provider catalog.', type: 'log'),
      SseLogEvent(
        id: 2,
        message: 'Pricing evidence prepared.',
        type: 'complete',
      ),
    ];
  }
}
