/// Calculation parameters for cost optimization.
/// 
/// Contains all 26 input fields required by the Optimizer API.
/// Used in Wizard Step 2 to configure digital twin cost calculation.
class CalcParams {
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

  /// Integrate error handling (default: false)
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

  /// Allow GCP self-hosted L4 (ALWAYS FALSE - not implemented)
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

  /// Allow GCP self-hosted L5 (ALWAYS FALSE - not implemented)
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
    this.allowGcpSelfHostedL4 = false,
    this.apiCallsPerDashboardRefresh = 1,
    this.dashboardActiveHoursPerDay = 0,
    this.allowGcpSelfHostedL5 = false,
    this.currency = 'USD',
  });

  /// Validation: Hot ≤ Cool ≤ Archive
  bool get isStorageDurationValid =>
      hotStorageDurationInMonths <= coolStorageDurationInMonths &&
      coolStorageDurationInMonths <= archiveStorageDurationInMonths;

  /// Convert to JSON for API request
  Map<String, dynamic> toJson() => {
        'numberOfDevices': numberOfDevices,
        'deviceSendingIntervalInMinutes': deviceSendingIntervalInMinutes,
        'averageSizeOfMessageInKb': averageSizeOfMessageInKb,
        'hotStorageDurationInMonths': hotStorageDurationInMonths,
        'coolStorageDurationInMonths': coolStorageDurationInMonths,
        'archiveStorageDurationInMonths': archiveStorageDurationInMonths,
        'needs3DModel': needs3DModel,
        'entityCount': entityCount,
        'average3DModelSizeInMB': average3DModelSizeInMB,
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

  /// Create from JSON (for loading saved params)
  factory CalcParams.fromJson(Map<String, dynamic> json) => CalcParams(
        numberOfDevices: json['numberOfDevices'] ?? 100,
        deviceSendingIntervalInMinutes: (json['deviceSendingIntervalInMinutes'] ?? 2.0).toDouble(),
        averageSizeOfMessageInKb: (json['averageSizeOfMessageInKb'] ?? 0.25).toDouble(),
        numberOfDeviceTypes: json['numberOfDeviceTypes'] ?? 1,
        useEventChecking: json['useEventChecking'] ?? false,
        eventsPerMessage: json['eventsPerMessage'] ?? 1,
        triggerNotificationWorkflow: json['triggerNotificationWorkflow'] ?? false,
        orchestrationActionsPerMessage: json['orchestrationActionsPerMessage'] ?? 3,
        returnFeedbackToDevice: json['returnFeedbackToDevice'] ?? false,
        numberOfEventActions: json['numberOfEventActions'] ?? 0,
        integrateErrorHandling: json['integrateErrorHandling'] ?? false,
        hotStorageDurationInMonths: json['hotStorageDurationInMonths'] ?? 1,
        coolStorageDurationInMonths: json['coolStorageDurationInMonths'] ?? 3,
        archiveStorageDurationInMonths: json['archiveStorageDurationInMonths'] ?? 12,
        needs3DModel: json['needs3DModel'] ?? false,
        entityCount: json['entityCount'] ?? 0,
        average3DModelSizeInMB: (json['average3DModelSizeInMB'] ?? 100.0).toDouble(),
        dashboardRefreshesPerHour: json['dashboardRefreshesPerHour'] ?? 2,
        apiCallsPerDashboardRefresh: json['apiCallsPerDashboardRefresh'] ?? 1,
        dashboardActiveHoursPerDay: json['dashboardActiveHoursPerDay'] ?? 8,
        amountOfActiveEditors: json['amountOfActiveEditors'] ?? 0,
        amountOfActiveViewers: json['amountOfActiveViewers'] ?? 5,
        currency: json['currency'] ?? 'USD',
      );
}
