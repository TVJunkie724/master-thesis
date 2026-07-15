import 'dart:convert';
import 'dart:developer' as developer;

enum AppLogEvent {
  themePreferenceSyncFailed,
  twinOverviewLoadFailed,
  deploymentStartFailed,
  destructionStartFailed,
  twinDeleteFailed,
  logTraceStartFailed,
  simulatorDownloadFailed,
  wizardInitializationFailed,
  costCalculationFailed,
  pricingSnapshotPersistenceFailed,
  wizardSaveFailed,
  wizardFinishFailed,
  projectZipUploadFailed,
}

enum AppLogLevel { warning }

class AppLogRecord {
  final AppLogEvent event;
  final AppLogLevel level;

  const AppLogRecord({required this.event, required this.level});

  Map<String, String> toJson() => {'event': event.name, 'level': level.name};
}

abstract interface class AppLogSink {
  void write(AppLogRecord record);
}

final class DeveloperAppLogSink implements AppLogSink {
  const DeveloperAppLogSink();

  @override
  void write(AppLogRecord record) {
    developer.log(
      jsonEncode(record.toJson()),
      name: 'twin2multicloud',
      level: 900,
    );
  }
}

final class AppLogger {
  final AppLogSink _sink;

  const AppLogger({AppLogSink sink = const DeveloperAppLogSink()})
    : _sink = sink;

  void warning(AppLogEvent event) {
    _sink.write(AppLogRecord(event: event, level: AppLogLevel.warning));
  }
}
