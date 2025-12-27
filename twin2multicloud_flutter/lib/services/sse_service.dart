import 'dart:async';
import 'dart:convert';
import 'package:flutter_client_sse/flutter_client_sse.dart';
import 'package:flutter_client_sse/constants/sse_request_type_enum.dart';

/// Service for handling Server-Sent Events (SSE) streams
/// Reusable for pricing refresh, deployment logs, etc.
class SseService {
  final String baseUrl;
  final String? authToken;

  SseService({required this.baseUrl, this.authToken});

  /// Stream pricing refresh logs for a provider
  /// Returns a stream of SseLogEvent objects
  Stream<SseLogEvent> streamRefreshPricing(String provider, String twinId) {
    final url = '$baseUrl/optimizer/stream/refresh-pricing/$provider?twin_id=$twinId';
    return _createEventStream(url);
  }

  /// Generic SSE stream creator - can be reused for deployment logs later
  Stream<SseLogEvent> _createEventStream(String url) {
    final controller = StreamController<SseLogEvent>();

    final stream = SSEClient.subscribeToSSE(
      method: SSERequestType.GET,
      url: url,
      header: authToken != null 
        ? {'Authorization': 'Bearer $authToken', 'Accept': 'text/event-stream'} 
        : {'Accept': 'text/event-stream'},
    );

    stream.listen(
      (event) {
        try {
          final data = json.decode(event.data ?? '{}');
          final eventType = event.event ?? 'log';
          
          controller.add(SseLogEvent(
            message: data['message']?.toString() ?? '',
            type: eventType,
          ));

          // Close stream on terminal events
          if (eventType == 'complete' || eventType == 'error') {
            controller.close();
          }
        } catch (e) {
          controller.addError('Failed to parse event: $e');
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
}

/// Represents a single SSE log event
class SseLogEvent {
  final String message;
  final String type; // 'log', 'complete', 'error'

  SseLogEvent({required this.message, required this.type});

  bool get isComplete => type == 'complete';
  bool get isError => type == 'error';
  bool get isLog => type == 'log';
}
