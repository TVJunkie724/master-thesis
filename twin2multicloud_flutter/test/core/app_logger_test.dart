import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/app_logger.dart';

final class _RecordingSink implements AppLogSink {
  final records = <AppLogRecord>[];

  @override
  void write(AppLogRecord record) => records.add(record);
}

void main() {
  test('logger emits only a closed event identifier and level', () {
    final sink = _RecordingSink();
    final logger = AppLogger(sink: sink);

    logger.warning(AppLogEvent.deploymentStartFailed);

    expect(sink.records, hasLength(1));
    expect(sink.records.single.toJson(), {
      'event': 'deploymentStartFailed',
      'level': 'warning',
    });
    expect(sink.records.single.toJson().keys, {'event', 'level'});
  });
}
