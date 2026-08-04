import 'package:equatable/equatable.dart';

import '../../models/cloud_bootstrap.dart';
import '../../models/cloud_connection.dart';

enum CloudBootstrapPhase {
  idle,
  loading,
  target,
  guide,
  authority,
  command,
  result,
}

class CloudBootstrapState extends Equatable {
  final CloudProvider provider;
  final CloudBootstrapEntryPoint entryPoint;
  final String? twinId;
  final CloudBootstrapPhase phase;
  final CloudBootstrapTarget? target;
  final CloudBootstrapGuide? guide;
  final CloudBootstrapSession? session;
  final String? safeError;
  final bool commandInProgress;
  final bool requiresRecheck;
  final CloudBootstrapConnectionSummary? completedConnection;

  const CloudBootstrapState({
    required this.provider,
    required this.entryPoint,
    this.twinId,
    this.phase = CloudBootstrapPhase.idle,
    this.target,
    this.guide,
    this.session,
    this.safeError,
    this.commandInProgress = false,
    this.requiresRecheck = false,
    this.completedConnection,
  });

  CloudBootstrapState copyWith({
    CloudBootstrapPhase? phase,
    CloudBootstrapTarget? target,
    CloudBootstrapGuide? guide,
    CloudBootstrapSession? session,
    String? safeError,
    bool clearError = false,
    bool? commandInProgress,
    bool? requiresRecheck,
    CloudBootstrapConnectionSummary? completedConnection,
    bool clearCompletion = false,
  }) {
    return CloudBootstrapState(
      provider: provider,
      entryPoint: entryPoint,
      twinId: twinId,
      phase: phase ?? this.phase,
      target: target ?? this.target,
      guide: guide ?? this.guide,
      session: session ?? this.session,
      safeError: clearError ? null : safeError ?? this.safeError,
      commandInProgress: commandInProgress ?? this.commandInProgress,
      requiresRecheck: requiresRecheck ?? this.requiresRecheck,
      completedConnection: clearCompletion
          ? null
          : completedConnection ?? this.completedConnection,
    );
  }

  @override
  List<Object?> get props => [
    provider,
    entryPoint,
    twinId,
    phase,
    target,
    guide,
    session,
    safeError,
    commandInProgress,
    requiresRecheck,
    completedConnection,
  ];
}
