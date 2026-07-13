import 'dart:async';
import 'dart:convert';
import 'package:flutter_client_sse/flutter_client_sse.dart';
import 'package:flutter_client_sse/constants/sse_request_type_enum.dart';
import '../utils/api_error_handler.dart';
import 'log_stream_client.dart';

export 'log_stream_client.dart' show SseLogEvent;

/// Service for handling Server-Sent Events (SSE) streams
/// Reusable for pricing refresh, deployment logs, etc.
class SseService implements LogStreamClient {
  final String baseUrl;
  final String? authToken;
  StreamSubscription? _currentSubscription;

  SseService({required this.baseUrl, this.authToken});

  /// Stream deployment logs for a session
  /// Supports reconnection with lastEventId
  @override
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
          final rawData = event.data;
          if (rawData == null || rawData.trim().isEmpty) {
            return; // Skip heartbeat/empty events
          }
          final data = json.decode(rawData);
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
              data: data as Map<String, dynamic>?,
            ),
          );

          // Close stream on terminal events
          if (eventType == 'complete' ||
              eventType == 'error' ||
              eventType == 'done') {
            controller.close();
          }
        } catch (e) {
          controller.addError(
            'Failed to parse event: ${ApiErrorHandler.extractMessage(e)}',
          );
        }
      },
      onError: (e) {
        if (!controller.isClosed) {
          controller.addError(e);
          controller.close();
        }
      },
      onDone: () {
        // Normal stream end — only close if not already closed by a terminal event
        if (!controller.isClosed) {
          controller.close();
        }
      },
    );

    return controller.stream;
  }

  /// Cancel current SSE subscription
  @override
  void cancel() {
    _currentSubscription?.cancel();
    _currentSubscription = null;
  }
}
