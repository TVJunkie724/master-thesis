abstract interface class LogStreamClient {
  Stream<SseLogEvent> streamDeploymentLogs(String sseUrl, {int? lastEventId});

  void cancel();
}

typedef LogStreamClientFactory = LogStreamClient Function();

class SseLogEvent {
  final int id;
  final String message;
  final String type;
  final String? level;
  final Map<String, dynamic>? outputs;
  final Map<String, dynamic>? data;
  final DateTime? timestamp;
  final String? operationId;
  final String? errorCode;

  const SseLogEvent({
    this.id = 0,
    required this.message,
    required this.type,
    this.level,
    this.outputs,
    this.data,
    this.timestamp,
    this.operationId,
    this.errorCode,
  });

  bool get isComplete => type == 'complete' || type == 'done';
  bool get isError => type == 'error';
  bool get isLog => type == 'log';
  bool get isHeartbeat => type == 'heartbeat';
}
