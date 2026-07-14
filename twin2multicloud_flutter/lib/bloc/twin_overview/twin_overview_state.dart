// lib/bloc/twin_overview/twin_overview_state.dart
// State classes for the twin overview BLoC

import 'dart:typed_data';
import 'package:equatable/equatable.dart';
import '../../models/deployment_readiness.dart';
import '../../models/deployment_operations.dart';

enum DeploymentOperationViewPhase {
  idle,
  starting,
  connecting,
  streaming,
  reconnecting,
  completed,
  failed,
}

class DeploymentOperationViewState extends Equatable {
  static const maxLogEntries = 500;

  final DeploymentOperationViewPhase phase;
  final DeploymentOperationType? operationType;
  final OperationSession? session;
  final List<DeploymentLogEntry> logs;
  final int lastEventId;
  final int reconnectAttempt;
  final bool showLogs;
  final String? message;

  const DeploymentOperationViewState({
    this.phase = DeploymentOperationViewPhase.idle,
    this.operationType,
    this.session,
    this.logs = const [],
    this.lastEventId = 0,
    this.reconnectAttempt = 0,
    this.showLogs = false,
    this.message,
  });

  factory DeploymentOperationViewState.starting(
    DeploymentOperationType operationType,
  ) => DeploymentOperationViewState(
    phase: DeploymentOperationViewPhase.starting,
    operationType: operationType,
    showLogs: true,
    message: operationType == DeploymentOperationType.destroy
        ? 'Starting resource destruction.'
        : 'Starting deployment.',
  );

  bool get isActive => const {
    DeploymentOperationViewPhase.starting,
    DeploymentOperationViewPhase.connecting,
    DeploymentOperationViewPhase.streaming,
    DeploymentOperationViewPhase.reconnecting,
  }.contains(phase);

  bool get isReconnecting => phase == DeploymentOperationViewPhase.reconnecting;

  bool get isComplete => const {
    DeploymentOperationViewPhase.completed,
    DeploymentOperationViewPhase.failed,
  }.contains(phase);

  List<String> get formattedLogs => List.unmodifiable(
    logs.map((entry) {
      final time = entry.timestamp.toLocal();
      final timestamp =
          '${time.hour.toString().padLeft(2, '0')}:'
          '${time.minute.toString().padLeft(2, '0')}:'
          '${time.second.toString().padLeft(2, '0')}';
      return '[${entry.level.toUpperCase()}] [$timestamp] ${entry.message}';
    }),
  );

  DeploymentOperationViewState copyWith({
    DeploymentOperationViewPhase? phase,
    DeploymentOperationType? operationType,
    OperationSession? session,
    List<DeploymentLogEntry>? logs,
    int? lastEventId,
    int? reconnectAttempt,
    bool? showLogs,
    String? message,
    bool clearMessage = false,
  }) {
    final requestedLogs = logs ?? this.logs;
    final nextLogs = List<DeploymentLogEntry>.unmodifiable(
      requestedLogs.length <= maxLogEntries
          ? requestedLogs
          : requestedLogs.sublist(requestedLogs.length - maxLogEntries),
    );
    return DeploymentOperationViewState(
      phase: phase ?? this.phase,
      operationType: operationType ?? this.operationType,
      session: session ?? this.session,
      logs: nextLogs,
      lastEventId: lastEventId ?? this.lastEventId,
      reconnectAttempt: reconnectAttempt ?? this.reconnectAttempt,
      showLogs: showLogs ?? this.showLogs,
      message: clearMessage ? null : (message ?? this.message),
    );
  }

  DeploymentOperationViewState append(DeploymentLogEntry entry) {
    if (session == null || entry.sessionId != session!.sessionId) {
      throw StateError('Deployment log belongs to another operation session.');
    }
    if (entry.eventId <= lastEventId) return this;
    if (entry.eventId != lastEventId + 1) {
      throw StateError('Deployment log cursor contains a gap.');
    }
    return copyWith(
      logs: [...logs, entry],
      lastEventId: entry.eventId,
      showLogs: true,
    );
  }

  @override
  List<Object?> get props => [
    phase,
    operationType,
    session,
    logs,
    lastEventId,
    reconnectAttempt,
    showLogs,
    message,
  ];
}

enum DeploymentReadinessViewPhase {
  initial,
  loading,
  ready,
  reviewRequired,
  failed,
}

class DeploymentReadinessViewState extends Equatable {
  final DeploymentReadinessViewPhase phase;
  final DeploymentReadinessSnapshot? snapshot;
  final String? errorMessage;

  const DeploymentReadinessViewState._({
    required this.phase,
    this.snapshot,
    this.errorMessage,
  });

  const DeploymentReadinessViewState.initial()
    : this._(phase: DeploymentReadinessViewPhase.initial);

  const DeploymentReadinessViewState.loading({
    DeploymentReadinessSnapshot? previous,
  }) : this._(phase: DeploymentReadinessViewPhase.loading, snapshot: previous);

  factory DeploymentReadinessViewState.fromSnapshot(
    DeploymentReadinessSnapshot snapshot,
  ) {
    return DeploymentReadinessViewState._(
      phase: snapshot.ready
          ? DeploymentReadinessViewPhase.ready
          : DeploymentReadinessViewPhase.reviewRequired,
      snapshot: snapshot,
    );
  }

  const DeploymentReadinessViewState.failed(
    String message, {
    DeploymentReadinessSnapshot? previous,
  }) : this._(
         phase: DeploymentReadinessViewPhase.failed,
         snapshot: previous,
         errorMessage: message,
       );

  bool get isDeployable =>
      phase == DeploymentReadinessViewPhase.ready && snapshot?.ready == true;

  @override
  List<Object?> get props => [phase, snapshot, errorMessage];
}

abstract class TwinOverviewState extends Equatable {
  const TwinOverviewState();

  @override
  List<Object?> get props => [];
}

/// Initial loading state
class TwinOverviewLoading extends TwinOverviewState {
  const TwinOverviewLoading();
}

/// Error state when loading fails
class TwinOverviewError extends TwinOverviewState {
  final String message;

  const TwinOverviewError(this.message);

  @override
  List<Object?> get props => [message];
}

/// Loaded state with all twin data
class TwinOverviewLoaded extends TwinOverviewState {
  final String twinId;
  final String projectName;
  final String? cloudResourceName;
  final String twinState;

  // Calculated permissions based on state
  final bool canDeploy;
  final bool canDestroy;
  final bool canEdit;
  final bool canDelete;

  final DeploymentReadinessViewState deploymentReadiness;

  // Deployment operation and independent trace utility state
  final DeploymentOperationViewState deploymentOperation;
  final bool isTracing;
  final String? traceId;

  // Error handling
  final String? lastError;
  final String? lastDeploymentLogs;

  final bool showTraceTerminal;
  final List<String> traceTerminalLogs;

  // Optimization data
  final Map<String, dynamic>? optimizerResult;
  final Map<String, dynamic>? optimizerParams;
  final Map<String, dynamic>? cheapestPath; // {l1: 'aws', l2: 'azure', ...}
  final String? calculatedAt;

  // Pricing snapshots
  final Map<String, dynamic>? pricingAws;
  final String? pricingAwsUpdatedAt;
  final Map<String, dynamic>? pricingAzure;
  final String? pricingAzureUpdatedAt;
  final Map<String, dynamic>? pricingGcp;
  final String? pricingGcpUpdatedAt;

  // Deployer config for display
  final Map<String, dynamic>? deployerConfig;

  // Success/error/info messages
  final String? successMessage;
  final String? errorMessage;
  final String? infoMessage;

  // Terraform outputs from most recent successful deployment
  final Map<String, dynamic>? deploymentOutputs;
  final DateTime? outputsTimestamp;
  final String? outputsError;

  // Simulator download state
  final bool isDownloadingSimulator;
  final Uint8List? simulatorBytes;
  final String? simulatorFilename;

  const TwinOverviewLoaded({
    required this.twinId,
    required this.projectName,
    this.cloudResourceName,
    required this.twinState,
    required this.canDeploy,
    required this.canDestroy,
    required this.canEdit,
    required this.canDelete,
    this.deploymentReadiness = const DeploymentReadinessViewState.initial(),
    this.deploymentOperation = const DeploymentOperationViewState(),
    this.isTracing = false,
    this.traceId,
    this.lastError,
    this.lastDeploymentLogs,
    this.showTraceTerminal = false,
    this.traceTerminalLogs = const [],
    this.optimizerResult,
    this.optimizerParams,
    this.cheapestPath,
    this.calculatedAt,
    this.pricingAws,
    this.pricingAwsUpdatedAt,
    this.pricingAzure,
    this.pricingAzureUpdatedAt,
    this.pricingGcp,
    this.pricingGcpUpdatedAt,
    this.deployerConfig,
    this.successMessage,
    this.errorMessage,
    this.infoMessage,
    this.deploymentOutputs,
    this.outputsTimestamp,
    this.outputsError,
    this.isDownloadingSimulator = false,
    this.simulatorBytes,
    this.simulatorFilename,
  });

  bool get isDeploying =>
      deploymentOperation.isActive &&
      deploymentOperation.operationType == DeploymentOperationType.deploy;

  bool get isDestroying =>
      deploymentOperation.isActive &&
      deploymentOperation.operationType == DeploymentOperationType.destroy;

  bool get showTerminal => deploymentOperation.showLogs || showTraceTerminal;

  List<String> get terminalLogs => showTraceTerminal
      ? List.unmodifiable(traceTerminalLogs)
      : deploymentOperation.formattedLogs;

  /// Create copy with updated fields
  TwinOverviewLoaded copyWith({
    String? twinId,
    String? projectName,
    String? cloudResourceName,
    String? twinState,
    bool? canDeploy,
    bool? canDestroy,
    bool? canEdit,
    bool? canDelete,
    DeploymentReadinessViewState? deploymentReadiness,
    DeploymentOperationViewState? deploymentOperation,
    bool? isTracing,
    String? traceId,
    String? lastError,
    String? lastDeploymentLogs,
    bool? showTraceTerminal,
    List<String>? traceTerminalLogs,
    Map<String, dynamic>? optimizerResult,
    Map<String, dynamic>? optimizerParams,
    Map<String, dynamic>? cheapestPath,
    String? calculatedAt,
    Map<String, dynamic>? pricingAws,
    String? pricingAwsUpdatedAt,
    Map<String, dynamic>? pricingAzure,
    String? pricingAzureUpdatedAt,
    Map<String, dynamic>? pricingGcp,
    String? pricingGcpUpdatedAt,
    Map<String, dynamic>? deployerConfig,
    String? successMessage,
    String? errorMessage,
    String? infoMessage,
    Map<String, dynamic>? deploymentOutputs,
    DateTime? outputsTimestamp,
    String? outputsError,
    bool? isDownloadingSimulator,
    Uint8List? simulatorBytes,
    String? simulatorFilename,
    bool clearSuccess = false,
    bool clearError = false,
    bool clearInfo = false,
    bool clearOutputsError = false,
    bool clearLastError = false,
    bool clearDeploymentOutputs = false,
    bool clearOutputsTimestamp = false,
    bool clearTraceId = false,
    bool clearSimulatorBytes = false,
    bool clearSimulatorFilename = false,
  }) {
    return TwinOverviewLoaded(
      twinId: twinId ?? this.twinId,
      projectName: projectName ?? this.projectName,
      cloudResourceName: cloudResourceName ?? this.cloudResourceName,
      twinState: twinState ?? this.twinState,
      canDeploy: canDeploy ?? this.canDeploy,
      canDestroy: canDestroy ?? this.canDestroy,
      canEdit: canEdit ?? this.canEdit,
      canDelete: canDelete ?? this.canDelete,
      deploymentReadiness: deploymentReadiness ?? this.deploymentReadiness,
      deploymentOperation: deploymentOperation ?? this.deploymentOperation,
      isTracing: isTracing ?? this.isTracing,
      traceId: clearTraceId ? null : (traceId ?? this.traceId),
      lastError: clearLastError ? null : (lastError ?? this.lastError),
      lastDeploymentLogs: lastDeploymentLogs ?? this.lastDeploymentLogs,
      showTraceTerminal: showTraceTerminal ?? this.showTraceTerminal,
      traceTerminalLogs: traceTerminalLogs ?? this.traceTerminalLogs,
      optimizerResult: optimizerResult ?? this.optimizerResult,
      optimizerParams: optimizerParams ?? this.optimizerParams,
      cheapestPath: cheapestPath ?? this.cheapestPath,
      calculatedAt: calculatedAt ?? this.calculatedAt,
      pricingAws: pricingAws ?? this.pricingAws,
      pricingAwsUpdatedAt: pricingAwsUpdatedAt ?? this.pricingAwsUpdatedAt,
      pricingAzure: pricingAzure ?? this.pricingAzure,
      pricingAzureUpdatedAt:
          pricingAzureUpdatedAt ?? this.pricingAzureUpdatedAt,
      pricingGcp: pricingGcp ?? this.pricingGcp,
      pricingGcpUpdatedAt: pricingGcpUpdatedAt ?? this.pricingGcpUpdatedAt,
      deployerConfig: deployerConfig ?? this.deployerConfig,
      successMessage: clearSuccess
          ? null
          : (successMessage ?? this.successMessage),
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      infoMessage: clearInfo ? null : (infoMessage ?? this.infoMessage),
      deploymentOutputs: clearDeploymentOutputs
          ? null
          : (deploymentOutputs ?? this.deploymentOutputs),
      outputsTimestamp: clearOutputsTimestamp
          ? null
          : (outputsTimestamp ?? this.outputsTimestamp),
      outputsError: clearOutputsError
          ? null
          : (outputsError ?? this.outputsError),
      isDownloadingSimulator:
          isDownloadingSimulator ?? this.isDownloadingSimulator,
      simulatorBytes: clearSimulatorBytes
          ? null
          : (simulatorBytes ?? this.simulatorBytes),
      simulatorFilename: clearSimulatorFilename
          ? null
          : (simulatorFilename ?? this.simulatorFilename),
    );
  }

  @override
  List<Object?> get props => [
    twinId,
    projectName,
    cloudResourceName,
    twinState,
    canDeploy,
    canDestroy,
    canEdit,
    canDelete,
    deploymentReadiness,
    deploymentOperation,
    isTracing,
    traceId,
    lastError,
    lastDeploymentLogs,
    showTraceTerminal,
    traceTerminalLogs,
    optimizerResult,
    optimizerParams,
    cheapestPath,
    calculatedAt,
    pricingAws,
    pricingAwsUpdatedAt,
    pricingAzure,
    pricingAzureUpdatedAt,
    pricingGcp,
    pricingGcpUpdatedAt,
    deployerConfig,
    successMessage,
    errorMessage,
    infoMessage,
    deploymentOutputs,
    outputsTimestamp,
    outputsError,
    isDownloadingSimulator,
    simulatorBytes,
    simulatorFilename,
  ];
}
