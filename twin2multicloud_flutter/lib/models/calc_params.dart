import 'package:collection/collection.dart';

enum SixLayerWorkloadScenario {
  small,
  medium,
  large;

  String get label => switch (this) {
    SixLayerWorkloadScenario.small => 'Small',
    SixLayerWorkloadScenario.medium => 'Medium',
    SixLayerWorkloadScenario.large => 'Large',
  };

  String get eventingScenarioId => 'eventing-$name-v1';
}

/// Calculation parameters for cost optimization.
///
/// Contains the user-configurable input fields required by the Optimizer API.
/// Used in Wizard Step 2 to configure digital twin cost calculation.
class CalcParams {
  static const _mapEquality = MapEquality<String, dynamic>();
  static const sixLayerSchemaVersion = 'six-layer-workload.v1';

  /// Wire discriminator. Null denotes the historical v1 calculation shape.
  final String? schemaVersion;

  /// Frozen thesis scenario for the strict Phase 8 workload-v2 wire variant.
  final SixLayerWorkloadScenario? scenario;

  /// Embedded event workload paired with the selected v2 scenario.
  final String? eventingScenarioId;

  /// V2 Twin-state projection rate used by the complete-service formulas.
  final double? twinStateMaterializationsPerSecond;

  /// V2 Twin-graph mutation rate used by the complete-service formulas.
  final double? twinGraphUpdatesPerSecond;

  // ============================================================
  // LAYER 1 & 2 - WORKLOAD PARAMETERS
  // ============================================================

  /// Number of IoT devices (required, must be > 0)
  final int numberOfDevices;

  /// Sending interval in minutes (required, must be > 0)
  final double deviceSendingIntervalInMinutes;

  /// Average message size in KB (required, must be > 0)
  final double averageSizeOfMessageInKb;

  /// Number of distinct device types (default: 1, min: 1)
  final int numberOfDeviceTypes;

  // ============================================================
  // LAYER 2 - PROCESSING & ORCHESTRATION
  // ============================================================

  /// Enable event checking (default: false)
  final bool useEventChecking;

  /// Events per message (default: 1, min: 1)
  /// Only used when useEventChecking is true
  final int eventsPerMessage;

  /// Trigger notification workflow (default: false)
  final bool triggerNotificationWorkflow;

  /// Orchestration actions per message (default: 3, min: 1)
  /// Only used when triggerNotificationWorkflow is true
  final int orchestrationActionsPerMessage;

  /// Return feedback to device (default: false)
  final bool returnFeedbackToDevice;

  /// Number of event actions (default: 0, min: 0)
  /// Only used when returnFeedbackToDevice is true
  final int numberOfEventActions;

  /// Event trigger rate 0.0-1.0 (default: 0.1)
  /// Not exposed in UI, hardcoded
  final double eventTriggerRate;

  /// Legacy compatibility field; true is not executable in the baseline.
  final bool integrateErrorHandling;

  // ============================================================
  // LAYER 3 - STORAGE TIERS
  // ============================================================

  /// Hot storage duration in months (required, min: 1, slider 1-12)
  final int hotStorageDurationInMonths;

  /// Cool storage duration in months (required, min: 1, slider 1-24)
  final int coolStorageDurationInMonths;

  /// Archive storage duration in months (required, min: 6, slider 6-36)
  final int archiveStorageDurationInMonths;

  // ============================================================
  // LAYER 4 - TWIN MANAGEMENT
  // ============================================================

  /// Is 3D model necessary (radio: yes/no)
  final bool needs3DModel;

  /// Number of 3D entities (default: 0, min: 0)
  /// Only shown when needs3DModel is true
  final int entityCount;

  /// Average 3D model size in MB (default: 100.0, min: 0.1)
  /// Only shown when needs3DModel is true
  final double average3DModelSizeInMB;

  /// Estimated Azure Digital Twins query units per logical query.
  final double averageDigitalTwinQueryUnitsPerQuery;

  /// Estimated Azure Digital Twins response size per logical query.
  final double averageDigitalTwinQueryResponseSizeInKb;

  /// Legacy wire field; provider availability comes from the capability contract.
  final bool allowGcpSelfHostedL4;

  // ============================================================
  // LAYER 5 - VISUALIZATION
  // ============================================================

  /// Dashboard refreshes per hour (required, min: 0)
  final int dashboardRefreshesPerHour;

  /// API calls per dashboard refresh (default: 1, min: 1)
  final int apiCallsPerDashboardRefresh;

  /// Dashboard active hours per day (default: 0, slider 0-24)
  final int dashboardActiveHoursPerDay;

  /// Number of monthly editors (required, min: 0)
  final int amountOfActiveEditors;

  /// Number of monthly viewers (required, min: 0)
  final int amountOfActiveViewers;

  /// Legacy wire field; provider availability comes from the capability contract.
  final bool allowGcpSelfHostedL5;

  // ============================================================
  // GLOBAL SETTINGS
  // ============================================================

  /// Currency code (default: 'USD', dropdown: USD/EUR)
  final String currency;

  CalcParams({
    required this.numberOfDevices,
    required this.deviceSendingIntervalInMinutes,
    required this.averageSizeOfMessageInKb,
    required this.hotStorageDurationInMonths,
    required this.coolStorageDurationInMonths,
    required this.archiveStorageDurationInMonths,
    required this.needs3DModel,
    required this.dashboardRefreshesPerHour,
    required this.amountOfActiveEditors,
    required this.amountOfActiveViewers,
    this.numberOfDeviceTypes = 1,
    this.useEventChecking = false,
    this.eventsPerMessage = 1,
    this.triggerNotificationWorkflow = false,
    this.orchestrationActionsPerMessage = 3,
    this.returnFeedbackToDevice = false,
    this.numberOfEventActions = 0,
    this.eventTriggerRate = 0.1,
    this.integrateErrorHandling = false,
    this.entityCount = 0,
    this.average3DModelSizeInMB = 100.0,
    this.averageDigitalTwinQueryUnitsPerQuery = 1.0,
    this.averageDigitalTwinQueryResponseSizeInKb = 1.0,
    this.allowGcpSelfHostedL4 = false,
    this.apiCallsPerDashboardRefresh = 1,
    this.dashboardActiveHoursPerDay = 0,
    this.allowGcpSelfHostedL5 = false,
    this.currency = 'USD',
    this.schemaVersion,
    this.scenario,
    this.eventingScenarioId,
    this.twinStateMaterializationsPerSecond,
    this.twinGraphUpdatesPerSecond,
  });

  bool get isSixLayer =>
      schemaVersion == sixLayerSchemaVersion &&
      scenario != null &&
      eventingScenarioId == scenario!.eventingScenarioId &&
      twinStateMaterializationsPerSecond != null &&
      twinGraphUpdatesPerSecond != null &&
      (currency == 'USD' || currency == 'EUR');

  /// Validation: Hot ≤ Cool ≤ Archive
  bool get isStorageDurationValid =>
      hotStorageDurationInMonths <= coolStorageDurationInMonths &&
      coolStorageDurationInMonths <= archiveStorageDurationInMonths;

  /// Whether the current values can be submitted to the executable baseline.
  bool get isExecutableTopology => !integrateErrorHandling;

  /// Convert to the exact wire variant expected by Management.
  Map<String, dynamic> toJson() {
    final hasVariantMetadata =
        schemaVersion != null ||
        scenario != null ||
        eventingScenarioId != null ||
        twinStateMaterializationsPerSecond != null ||
        twinGraphUpdatesPerSecond != null;
    if (hasVariantMetadata && !isSixLayer) {
      throw StateError('Phase 8 workload-v2 metadata is inconsistent.');
    }
    return isSixLayer ? _sixLayerJson() : _legacyJson();
  }

  Map<String, dynamic> _legacyJson() => {
    'numberOfDevices': numberOfDevices,
    'deviceSendingIntervalInMinutes': deviceSendingIntervalInMinutes,
    'averageSizeOfMessageInKb': averageSizeOfMessageInKb,
    'hotStorageDurationInMonths': hotStorageDurationInMonths,
    'coolStorageDurationInMonths': coolStorageDurationInMonths,
    'archiveStorageDurationInMonths': archiveStorageDurationInMonths,
    'needs3DModel': needs3DModel,
    'entityCount': entityCount,
    'average3DModelSizeInMB': average3DModelSizeInMB,
    'averageDigitalTwinQueryUnitsPerQuery':
        averageDigitalTwinQueryUnitsPerQuery,
    'averageDigitalTwinQueryResponseSizeInKb':
        averageDigitalTwinQueryResponseSizeInKb,
    'amountOfActiveEditors': amountOfActiveEditors,
    'amountOfActiveViewers': amountOfActiveViewers,
    'dashboardRefreshesPerHour': dashboardRefreshesPerHour,
    'dashboardActiveHoursPerDay': dashboardActiveHoursPerDay,
    'useEventChecking': useEventChecking,
    'eventsPerMessage': eventsPerMessage,
    'triggerNotificationWorkflow': triggerNotificationWorkflow,
    'orchestrationActionsPerMessage': orchestrationActionsPerMessage,
    'returnFeedbackToDevice': returnFeedbackToDevice,
    'integrateErrorHandling': integrateErrorHandling,
    'apiCallsPerDashboardRefresh': apiCallsPerDashboardRefresh,
    'numberOfDeviceTypes': numberOfDeviceTypes,
    'numberOfEventActions': numberOfEventActions,
    'eventTriggerRate': eventTriggerRate,
    'allowGcpSelfHostedL4': allowGcpSelfHostedL4,
    'allowGcpSelfHostedL5': allowGcpSelfHostedL5,
    'currency': currency,
  };

  Map<String, dynamic> _sixLayerJson() => {
    'schemaVersion': sixLayerSchemaVersion,
    'numberOfDevices': numberOfDevices,
    'deviceSendingIntervalInMinutes': deviceSendingIntervalInMinutes,
    'averageSizeOfMessageInKb': averageSizeOfMessageInKb,
    'numberOfDeviceTypes': numberOfDeviceTypes,
    'hotStorageDurationInMonths': hotStorageDurationInMonths,
    'coolStorageDurationInMonths': coolStorageDurationInMonths,
    'archiveStorageDurationInMonths': archiveStorageDurationInMonths,
    'twinEntityCount': entityCount,
    'aggregateDashboardRefreshesPerHour': dashboardRefreshesPerHour,
    'apiCallsPerAggregateDashboardRefresh': apiCallsPerDashboardRefresh,
    'dashboardActiveHoursPerDay': dashboardActiveHoursPerDay,
    'monthlyEditorSeats': amountOfActiveEditors,
    'monthlyViewerSeats': amountOfActiveViewers,
    'twinStateMaterializationsPerSecond': twinStateMaterializationsPerSecond,
    'twinGraphUpdatesPerSecond': twinGraphUpdatesPerSecond,
    'eventingScenarioId': eventingScenarioId,
    'currency': currency,
  };

  bool hasSameCalculationInputs(CalcParams other) =>
      _mapEquality.equals(toJson(), other.toJson());

  /// Create default params for testing
  factory CalcParams.defaultParams() => CalcParams(
    numberOfDevices: 100,
    deviceSendingIntervalInMinutes: 2.0,
    averageSizeOfMessageInKb: 0.25,
    hotStorageDurationInMonths: 1,
    coolStorageDurationInMonths: 3,
    archiveStorageDurationInMonths: 12,
    needs3DModel: false,
    dashboardRefreshesPerHour: 2,
    amountOfActiveEditors: 0,
    amountOfActiveViewers: 0,
  );

  factory CalcParams.sixLayer({
    required SixLayerWorkloadScenario scenario,
    String currency = 'USD',
  }) {
    if (currency != 'USD' && currency != 'EUR') {
      throw const FormatException(
        'Phase 8 workload-v2 currency must be USD or EUR.',
      );
    }
    final values = switch (scenario) {
      SixLayerWorkloadScenario.small => const (
        devices: 100,
        interval: 2.0,
        messageSize: 0.25,
        twinEntities: 100,
        refreshes: 12,
        callsPerRefresh: 1,
        activeHours: 1,
        editors: 2,
        viewers: 1,
        materializations: 0.1,
        graphUpdates: 0.01,
      ),
      SixLayerWorkloadScenario.medium => const (
        devices: 4000,
        interval: 0.5,
        messageSize: 0.5,
        twinEntities: 4000,
        refreshes: 60,
        callsPerRefresh: 10,
        activeHours: 4,
        editors: 25,
        viewers: 10,
        materializations: 2.5,
        graphUpdates: 0.1,
      ),
      SixLayerWorkloadScenario.large => const (
        devices: 30000,
        interval: 0.1,
        messageSize: 0.8,
        twinEntities: 30000,
        refreshes: 120,
        callsPerRefresh: 100,
        activeHours: 8,
        editors: 100,
        viewers: 300,
        materializations: 50.0,
        graphUpdates: 1.0,
      ),
    };
    return CalcParams(
      numberOfDevices: values.devices,
      deviceSendingIntervalInMinutes: values.interval,
      averageSizeOfMessageInKb: values.messageSize,
      numberOfDeviceTypes: 1,
      hotStorageDurationInMonths: 1,
      coolStorageDurationInMonths: 3,
      archiveStorageDurationInMonths: 12,
      needs3DModel: false,
      entityCount: values.twinEntities,
      dashboardRefreshesPerHour: values.refreshes,
      apiCallsPerDashboardRefresh: values.callsPerRefresh,
      dashboardActiveHoursPerDay: values.activeHours,
      amountOfActiveEditors: values.editors,
      amountOfActiveViewers: values.viewers,
      useEventChecking: true,
      triggerNotificationWorkflow: true,
      returnFeedbackToDevice: true,
      currency: currency,
      schemaVersion: sixLayerSchemaVersion,
      scenario: scenario,
      eventingScenarioId: scenario.eventingScenarioId,
      twinStateMaterializationsPerSecond: values.materializations,
      twinGraphUpdatesPerSecond: values.graphUpdates,
    );
  }

  /// Create from JSON (for loading saved params)
  factory CalcParams.fromJson(Map<String, dynamic> json) {
    if (json.containsKey('schemaVersion')) {
      return _sixLayerFromJson(json);
    }
    return CalcParams(
      numberOfDevices: json['numberOfDevices'] ?? 100,
      deviceSendingIntervalInMinutes:
          (json['deviceSendingIntervalInMinutes'] ?? 2.0).toDouble(),
      averageSizeOfMessageInKb: (json['averageSizeOfMessageInKb'] ?? 0.25)
          .toDouble(),
      numberOfDeviceTypes: json['numberOfDeviceTypes'] ?? 1,
      useEventChecking: json['useEventChecking'] ?? false,
      eventsPerMessage: json['eventsPerMessage'] ?? 1,
      triggerNotificationWorkflow: json['triggerNotificationWorkflow'] ?? false,
      orchestrationActionsPerMessage:
          json['orchestrationActionsPerMessage'] ?? 3,
      returnFeedbackToDevice: json['returnFeedbackToDevice'] ?? false,
      numberOfEventActions: json['numberOfEventActions'] ?? 0,
      integrateErrorHandling: json['integrateErrorHandling'] ?? false,
      hotStorageDurationInMonths: json['hotStorageDurationInMonths'] ?? 1,
      coolStorageDurationInMonths: json['coolStorageDurationInMonths'] ?? 3,
      archiveStorageDurationInMonths:
          json['archiveStorageDurationInMonths'] ?? 12,
      needs3DModel: json['needs3DModel'] ?? false,
      entityCount: json['entityCount'] ?? 0,
      average3DModelSizeInMB: (json['average3DModelSizeInMB'] ?? 100.0)
          .toDouble(),
      averageDigitalTwinQueryUnitsPerQuery: _positiveDoubleOrDefault(
        json,
        'averageDigitalTwinQueryUnitsPerQuery',
        1.0,
      ),
      averageDigitalTwinQueryResponseSizeInKb: _positiveDoubleOrDefault(
        json,
        'averageDigitalTwinQueryResponseSizeInKb',
        1.0,
      ),
      dashboardRefreshesPerHour: json['dashboardRefreshesPerHour'] ?? 2,
      apiCallsPerDashboardRefresh: json['apiCallsPerDashboardRefresh'] ?? 1,
      dashboardActiveHoursPerDay: json['dashboardActiveHoursPerDay'] ?? 8,
      amountOfActiveEditors: json['amountOfActiveEditors'] ?? 0,
      amountOfActiveViewers: json['amountOfActiveViewers'] ?? 5,
      allowGcpSelfHostedL4: json['allowGcpSelfHostedL4'] ?? false,
      allowGcpSelfHostedL5: json['allowGcpSelfHostedL5'] ?? false,
      currency: json['currency'] ?? 'USD',
    );
  }
}

CalcParams _sixLayerFromJson(Map<String, dynamic> json) {
  const keys = {
    'schemaVersion',
    'numberOfDevices',
    'deviceSendingIntervalInMinutes',
    'averageSizeOfMessageInKb',
    'numberOfDeviceTypes',
    'hotStorageDurationInMonths',
    'coolStorageDurationInMonths',
    'archiveStorageDurationInMonths',
    'twinEntityCount',
    'aggregateDashboardRefreshesPerHour',
    'apiCallsPerAggregateDashboardRefresh',
    'dashboardActiveHoursPerDay',
    'monthlyEditorSeats',
    'monthlyViewerSeats',
    'twinStateMaterializationsPerSecond',
    'twinGraphUpdatesPerSecond',
    'eventingScenarioId',
    'currency',
  };
  if (json.keys.toSet().difference(keys).isNotEmpty ||
      keys.difference(json.keys.toSet()).isNotEmpty ||
      json['schemaVersion'] != CalcParams.sixLayerSchemaVersion) {
    throw const FormatException(
      'Phase 8 workload-v2 fields are incomplete or unsupported.',
    );
  }
  final currency = json['currency'];
  if (currency != 'USD' && currency != 'EUR') {
    throw const FormatException(
      'Phase 8 workload-v2 currency must be USD or EUR.',
    );
  }
  for (final scenario in SixLayerWorkloadScenario.values) {
    final candidate = CalcParams.sixLayer(
      scenario: scenario,
      currency: currency as String,
    );
    if (CalcParams._mapEquality.equals(candidate.toJson(), json)) {
      return candidate;
    }
  }
  throw const FormatException(
    'Phase 8 workload v2 must match the frozen Small, Medium, or Large scenario.',
  );
}

double _positiveDoubleOrDefault(
  Map<String, dynamic> json,
  String key,
  double fallback,
) {
  if (!json.containsKey(key)) return fallback;
  final value = json[key];
  if (value is! num) {
    throw FormatException('$key must be a number');
  }
  final normalized = value.toDouble();
  if (!normalized.isFinite || normalized <= 0) {
    throw FormatException('$key must be finite and greater than zero');
  }
  return normalized;
}
