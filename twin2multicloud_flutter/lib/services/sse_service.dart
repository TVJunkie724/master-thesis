import 'dart:async';
import 'dart:convert';
import 'package:flutter_client_sse/flutter_client_sse.dart';
import 'package:flutter_client_sse/constants/sse_request_type_enum.dart';
import '../utils/api_error_handler.dart';

/// Service for handling Server-Sent Events (SSE) streams
/// Reusable for pricing refresh, deployment logs, etc.
class SseService {
  final String baseUrl;
  final String? authToken;
  StreamSubscription? _currentSubscription;

  SseService({required this.baseUrl, this.authToken});

  /// Stream pricing refresh logs for a provider
  /// Returns a stream of SseLogEvent objects
  Stream<SseLogEvent> streamRefreshPricing(String provider, String twinId) {
    final url =
        '$baseUrl/optimizer/stream/refresh-pricing/$provider?twin_id=$twinId';
    return _createEventStream(url);
  }

  /// Stream deployment logs for a session
  /// Supports reconnection with lastEventId
  Stream<SseLogEvent> streamDeploymentLogs(String sseUrl, {int? lastEventId}) {
    var url = '$baseUrl$sseUrl';
    if (lastEventId != null && lastEventId > 0) {
      url = '$url?last_event_id=$lastEventId';
    }
    return _createEventStream(url);
  }

  /// Generic SSE stream creator - can be reused for deployment logs later
  Stream<SseLogEvent> _createEventStream(String url) {
    final controller = StreamController<SseLogEvent>();

    final stream = SSEClient.subscribeToSSE(
      method: SSERequestType.GET,
      url: url,
      header: authToken != null
          ? {
              'Authorization': 'Bearer $authToken',
              'Accept': 'text/event-stream',
            }
          : {'Accept': 'text/event-stream'},
    );

    _currentSubscription = stream.listen(
      (event) {
        try {
          final data = json.decode(event.data ?? '{}');
          final eventType = data['type']?.toString() ?? event.event ?? 'log';
          final eventId = data['id'] as int? ?? 0;

          controller.add(
            SseLogEvent(
              id: eventId,
              message:
                  data['data']?.toString() ?? data['message']?.toString() ?? '',
              type: eventType,
              level: data['level']?.toString(),
              outputs: data['outputs'] as Map<String, dynamic>?,
            ),
          );

          // Close stream on terminal events
          if (eventType == 'complete' || eventType == 'error') {
            controller.close();
          }
        } catch (e) {
          controller.addError(
            'Failed to parse event: ${ApiErrorHandler.extractMessage(e)}',
          );
        }
      },
      onError: (e) {
        controller.addError(e);
        controller.close();
      },
      onDone: () => controller.close(),
    );

    return controller.stream;
  }

  /// Cancel current SSE subscription
  void cancel() {
    _currentSubscription?.cancel();
    _currentSubscription = null;
  }
}

/// Represents a single SSE log event
class SseLogEvent {
  final int id; // Event ID for reconnection support
  final String message;
  final String type; // 'log', 'complete', 'error', 'heartbeat'
  final String? level; // 'info', 'error', 'warning'
  final Map<String, dynamic>? outputs;

  SseLogEvent({
    this.id = 0,
    required this.message,
    required this.type,
    this.level,
    this.outputs,
  });

  bool get isComplete => type == 'complete';
  bool get isError => type == 'error';
  bool get isLog => type == 'log';
  bool get isHeartbeat => type == 'heartbeat';
}
