import 'package:equatable/equatable.dart';

import '../../models/deployment_verification.dart';

class DeploymentVerificationState extends Equatable {
  final bool isCheckingInfrastructure;
  final InfrastructureVerificationResult? infrastructureResult;
  final String? infrastructureError;
  final bool isRunningDataFlow;
  final String? dataFlowError;
  final List<DataFlowLogEntry> dataFlowLogs;
  final bool isLoadingHistory;
  final String? historyError;
  final List<TelemetryVerificationRecord> verificationHistory;
  final String? activeVerificationId;
  final TelemetryVerificationEvidence? terminalEvidence;
  final TelemetryVerificationRecord? latestDataFlowRecord;

  const DeploymentVerificationState({
    this.isCheckingInfrastructure = false,
    this.infrastructureResult,
    this.infrastructureError,
    this.isRunningDataFlow = false,
    this.dataFlowError,
    this.dataFlowLogs = const [],
    this.isLoadingHistory = false,
    this.historyError,
    this.verificationHistory = const [],
    this.activeVerificationId,
    this.terminalEvidence,
    this.latestDataFlowRecord,
  });

  DataFlowVerificationSummary? get dataFlowSummary {
    final evidence = latestDataFlowRecord?.result ?? terminalEvidence;
    if (evidence == null) return null;
    return DataFlowVerificationSummary(
      passCount: evidence.passCount,
      failCount: evidence.failCount,
      skipCount: evidence.skipCount,
      totalTime: evidence.totalTime,
      failedPhase: evidence.failedPhase,
    );
  }

  DeploymentVerificationState copyWith({
    bool? isCheckingInfrastructure,
    InfrastructureVerificationResult? infrastructureResult,
    bool clearInfrastructureResult = false,
    String? infrastructureError,
    bool clearInfrastructureError = false,
    bool? isRunningDataFlow,
    String? dataFlowError,
    bool clearDataFlowError = false,
    List<DataFlowLogEntry>? dataFlowLogs,
    bool? isLoadingHistory,
    String? historyError,
    bool clearHistoryError = false,
    List<TelemetryVerificationRecord>? verificationHistory,
    String? activeVerificationId,
    bool clearActiveVerificationId = false,
    TelemetryVerificationEvidence? terminalEvidence,
    bool clearTerminalEvidence = false,
    TelemetryVerificationRecord? latestDataFlowRecord,
    bool clearLatestDataFlowRecord = false,
  }) {
    return DeploymentVerificationState(
      isCheckingInfrastructure:
          isCheckingInfrastructure ?? this.isCheckingInfrastructure,
      infrastructureResult: clearInfrastructureResult
          ? null
          : infrastructureResult ?? this.infrastructureResult,
      infrastructureError: clearInfrastructureError
          ? null
          : infrastructureError ?? this.infrastructureError,
      isRunningDataFlow: isRunningDataFlow ?? this.isRunningDataFlow,
      dataFlowError: clearDataFlowError
          ? null
          : dataFlowError ?? this.dataFlowError,
      dataFlowLogs: dataFlowLogs ?? this.dataFlowLogs,
      isLoadingHistory: isLoadingHistory ?? this.isLoadingHistory,
      historyError: clearHistoryError
          ? null
          : historyError ?? this.historyError,
      verificationHistory: verificationHistory ?? this.verificationHistory,
      activeVerificationId: clearActiveVerificationId
          ? null
          : activeVerificationId ?? this.activeVerificationId,
      terminalEvidence: clearTerminalEvidence
          ? null
          : terminalEvidence ?? this.terminalEvidence,
      latestDataFlowRecord: clearLatestDataFlowRecord
          ? null
          : latestDataFlowRecord ?? this.latestDataFlowRecord,
    );
  }

  @override
  List<Object?> get props => [
    isCheckingInfrastructure,
    infrastructureResult,
    infrastructureError,
    isRunningDataFlow,
    dataFlowError,
    dataFlowLogs,
    isLoadingHistory,
    historyError,
    verificationHistory,
    activeVerificationId,
    terminalEvidence,
    latestDataFlowRecord,
  ];
}
