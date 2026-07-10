import 'package:equatable/equatable.dart';

import '../../models/deployment_verification.dart';

class DeploymentVerificationState extends Equatable {
  final bool isCheckingInfrastructure;
  final InfrastructureVerificationResult? infrastructureResult;
  final String? infrastructureError;
  final bool isRunningDataFlow;
  final String? dataFlowError;
  final List<DataFlowLogEntry> dataFlowLogs;
  final DataFlowVerificationSummary? dataFlowSummary;

  const DeploymentVerificationState({
    this.isCheckingInfrastructure = false,
    this.infrastructureResult,
    this.infrastructureError,
    this.isRunningDataFlow = false,
    this.dataFlowError,
    this.dataFlowLogs = const [],
    this.dataFlowSummary,
  });

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
    DataFlowVerificationSummary? dataFlowSummary,
    bool clearDataFlowSummary = false,
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
      dataFlowSummary: clearDataFlowSummary
          ? null
          : dataFlowSummary ?? this.dataFlowSummary,
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
    dataFlowSummary,
  ];
}
