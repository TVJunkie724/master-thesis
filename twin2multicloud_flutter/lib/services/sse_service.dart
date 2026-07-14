import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../core/result.dart';
import 'log_stream_client.dart';

export 'log_stream_client.dart' show SseLogEvent;

/// Cancellable SSE transport. Reconnect policy belongs to the owning BLoC.
class SseService implements LogStreamClient {
  final Uri _baseUri;
  final Future<String?> Function() _authTokenProvider;
  final http.Client _client;

  StreamSubscription<String>? _lineSubscription;
  StreamController<SseLogEvent>? _controller;
  bool _cancelled = false;

  SseService({
    required String baseUrl,
    String? authToken,
    Future<String?> Function()? authTokenProvider,
    http.Client? client,
  }) : _baseUri = _parseBaseUri(baseUrl),
       assert(
         authToken == null || authTokenProvider == null,
         'Provide authToken or authTokenProvider, not both.',
       ),
       _authTokenProvider = authTokenProvider ?? (() async => authToken),
       _client = client ?? http.Client();

  @override
  Stream<SseLogEvent> streamDeploymentLogs(String sseUrl, {int? lastEventId}) {
    if (_controller != null) {
      throw StateError('An SSE client instance supports only one stream.');
    }
    final uri = _buildUri(sseUrl, lastEventId: lastEventId);
    late final StreamController<SseLogEvent> controller;
    controller = StreamController<SseLogEvent>(
      onListen: () => _connect(uri, controller),
      onCancel: cancel,
    );
    _controller = controller;
    return controller.stream;
  }

  Future<void> _connect(
    Uri uri,
    StreamController<SseLogEvent> controller,
  ) async {
    try {
      final authToken = (await _authTokenProvider())?.trim();
      final request = http.Request('GET', uri)
        ..headers.addAll({
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
          if (authToken != null && authToken.isNotEmpty)
            'Authorization': 'Bearer $authToken',
        });
      final response = await _client.send(request);
      if (_cancelled) return;
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw AppException(
          'Deployment log stream returned HTTP ${response.statusCode}.',
          code: 'DEPLOYMENT_STREAM_HTTP_ERROR',
        );
      }

      final parser = _SseEventParser(controller.add);
      _lineSubscription = response.stream
          .transform(utf8.decoder)
          .transform(const LineSplitter())
          .listen(
            (line) {
              try {
                parser.addLine(line);
              } catch (error, stackTrace) {
                _addError(controller, error, stackTrace);
                unawaited(_lineSubscription?.cancel());
              }
            },
            onError: (Object error, StackTrace stackTrace) {
              _addError(controller, error, stackTrace);
            },
            onDone: () {
              try {
                parser.finish();
                _closeController(controller);
              } catch (error, stackTrace) {
                _addError(controller, error, stackTrace);
              }
            },
            cancelOnError: true,
          );
    } catch (error, stackTrace) {
      _addError(controller, error, stackTrace);
    }
  }

  Uri _buildUri(String sseUrl, {int? lastEventId}) {
    final relative = Uri.tryParse(sseUrl);
    if (relative == null ||
        relative.hasScheme ||
        relative.hasAuthority ||
        !relative.path.startsWith('/')) {
      throw const AppException(
        'Deployment stream URL must be a relative Management API path.',
        code: 'DEPLOYMENT_STREAM_URL_INVALID',
      );
    }
    if (lastEventId != null && lastEventId < 0) {
      throw const AppException(
        'Deployment stream cursor cannot be negative.',
        code: 'DEPLOYMENT_STREAM_CURSOR_INVALID',
      );
    }
    final resolved = _baseUri.resolveUri(relative);
    if (lastEventId == null || lastEventId == 0) return resolved;
    return resolved.replace(
      queryParameters: {
        ...resolved.queryParameters,
        'last_event_id': '$lastEventId',
      },
    );
  }

  void _addError(
    StreamController<SseLogEvent> controller,
    Object error,
    StackTrace stackTrace,
  ) {
    if (_cancelled || controller.isClosed) return;
    controller.addError(error, stackTrace);
    _closeController(controller);
  }

  void _closeController(StreamController<SseLogEvent> controller) {
    if (!_cancelled && !controller.isClosed) {
      unawaited(controller.close());
    }
  }

  @override
  void cancel() {
    if (_cancelled) return;
    _cancelled = true;
    unawaited(_lineSubscription?.cancel());
    _lineSubscription = null;
    _client.close();
    final controller = _controller;
    if (controller != null && !controller.isClosed) {
      unawaited(controller.close());
    }
  }

  static Uri _parseBaseUri(String baseUrl) {
    final uri = Uri.tryParse(baseUrl);
    if (uri == null || !uri.hasScheme || !uri.hasAuthority) {
      throw ArgumentError.value(baseUrl, 'baseUrl', 'Must be an absolute URL.');
    }
    return uri;
  }
}

class _SseEventParser {
  static const maxEventBytes = 1024 * 1024;

  final void Function(SseLogEvent event) _onEvent;
  final List<String> _dataLines = [];
  String? _eventType;
  String? _eventId;
  int _eventBytes = 0;

  _SseEventParser(this._onEvent);

  void addLine(String line) {
    if (line.isEmpty) {
      _dispatch();
      return;
    }
    if (line.startsWith(':')) return;

    final separator = line.indexOf(':');
    final field = separator == -1 ? line : line.substring(0, separator);
    var value = separator == -1 ? '' : line.substring(separator + 1);
    if (value.startsWith(' ')) value = value.substring(1);
    switch (field) {
      case 'data':
        _eventBytes += utf8.encode(value).length + 1;
        if (_eventBytes > maxEventBytes) {
          throw const AppException(
            'Deployment stream event exceeds the supported size.',
            code: 'DEPLOYMENT_STREAM_EVENT_TOO_LARGE',
          );
        }
        _dataLines.add(value);
      case 'event':
        _eventType = value;
      case 'id':
        if (!value.contains('\u0000')) _eventId = value;
      case 'retry':
        break;
    }
  }

  void finish() => _dispatch();

  void _dispatch() {
    if (_dataLines.isEmpty) {
      _reset();
      return;
    }
    final raw = _dataLines.join('\n');
    final eventType = _eventType;
    final eventId = _eventId;
    _reset();
    final decoded = jsonDecode(raw);
    if (decoded is! Map) {
      throw const AppException(
        'Deployment stream event must be a JSON object.',
        code: 'DEPLOYMENT_STREAM_EVENT_INVALID',
      );
    }
    final payload = Map<String, dynamic>.from(decoded);
    final id = _parseEventId(payload['id'] ?? eventId);
    final type =
        _nonEmptyString(payload['type']) ?? _nonEmptyString(eventType) ?? 'log';
    final timestamp = _parseTimestamp(payload['timestamp']);
    final outputs = _optionalMap(payload['outputs'], 'outputs');
    final dataValue = payload['data'];
    final message =
        _nonEmptyString(payload['message']) ??
        (dataValue is String ? dataValue : jsonEncode(dataValue ?? ''));

    _onEvent(
      SseLogEvent(
        id: id,
        message: message,
        type: type,
        level: _nonEmptyString(payload['level']),
        outputs: outputs,
        data: payload,
        timestamp: timestamp,
        operationId: _nonEmptyString(payload['operation_id']),
        errorCode: _nonEmptyString(payload['error_code']),
      ),
    );
  }

  void _reset() {
    _dataLines.clear();
    _eventType = null;
    _eventId = null;
    _eventBytes = 0;
  }

  static int _parseEventId(Object? value) {
    final parsed = value is int ? value : int.tryParse(value?.toString() ?? '');
    if (parsed == null || parsed < 0) {
      throw const AppException(
        'Deployment stream event ID must be a non-negative integer.',
        code: 'DEPLOYMENT_STREAM_EVENT_INVALID',
      );
    }
    return parsed;
  }

  static DateTime? _parseTimestamp(Object? value) {
    if (value == null) return null;
    final parsed = value is String ? DateTime.tryParse(value) : null;
    if (parsed == null) {
      throw const AppException(
        'Deployment stream timestamp must be ISO-8601.',
        code: 'DEPLOYMENT_STREAM_EVENT_INVALID',
      );
    }
    return parsed;
  }

  static Map<String, dynamic>? _optionalMap(Object? value, String field) {
    if (value == null) return null;
    if (value is! Map) {
      throw AppException(
        'Deployment stream $field must be an object.',
        code: 'DEPLOYMENT_STREAM_EVENT_INVALID',
      );
    }
    return Map.unmodifiable(Map<String, dynamic>.from(value));
  }

  static String? _nonEmptyString(Object? value) {
    if (value is! String || value.trim().isEmpty) return null;
    return value.trim();
  }
}
