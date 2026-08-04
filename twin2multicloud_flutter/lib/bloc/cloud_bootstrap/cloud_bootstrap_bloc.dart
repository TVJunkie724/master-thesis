import 'dart:math';

import 'package:flutter_bloc/flutter_bloc.dart';

import '../../models/cloud_bootstrap.dart';
import '../../models/cloud_connection.dart';
import '../../services/management_api.dart';
import '../../utils/api_error_handler.dart';
import 'cloud_bootstrap_event.dart';
import 'cloud_bootstrap_state.dart';

class CloudBootstrapBloc
    extends Bloc<CloudBootstrapEvent, CloudBootstrapState> {
  final CloudBootstrapApi _api;

  CloudBootstrapBloc({
    required CloudBootstrapApi api,
    required CloudProvider provider,
    required CloudBootstrapEntryPoint entryPoint,
    String? twinId,
  }) : _api = api,
       super(
         CloudBootstrapState(
           provider: provider,
           entryPoint: entryPoint,
           twinId: twinId,
         ),
       ) {
    on<CloudBootstrapOpened>(_onOpened);
    on<CloudBootstrapGuideRequested>(_onGuideRequested);
    on<CloudBootstrapSessionStarted>(_onSessionStarted);
    on<CloudBootstrapExecuteSubmitted>(_onExecute);
    on<CloudBootstrapSessionRechecked>(_onRecheck);
    on<CloudBootstrapCredentialReentryRequested>(_onCredentialReentry);
    on<CloudBootstrapManualRevocationAcknowledged>(_onAcknowledge);
    on<CloudBootstrapCancelled>(_onCancel);
    on<CloudBootstrapStartNewRequested>(_onStartNew);
    on<CloudBootstrapClosed>(_onClosed);
  }

  Future<void> _onOpened(
    CloudBootstrapOpened event,
    Emitter<CloudBootstrapState> emit,
  ) async {
    var retryTarget = event.initialTarget;
    emit(
      state.copyWith(
        phase: CloudBootstrapPhase.loading,
        target: retryTarget,
        clearError: true,
      ),
    );
    try {
      final sessions = await _api.listCloudBootstrapSessions(
        provider: state.provider,
      );
      final scoped = sessions
          .where(
            (session) =>
                event.initialTarget == null ||
                session.target == event.initialTarget,
          )
          .toList(growable: false);
      final exact = scoped.where(
        (session) =>
            session.entryPoint == state.entryPoint &&
            session.twinId == state.twinId,
      );
      final session = exact.isNotEmpty
          ? exact.first
          : scoped.length == 1
          ? scoped.single
          : null;
      if (session != null) {
        retryTarget = session.target;
        final guide = await _api.getCloudBootstrapGuide(
          state.provider,
          session.target,
        );
        emit(_stateForSession(session, guide: guide));
        return;
      }
      final target = event.initialTarget;
      if (target == null) {
        emit(state.copyWith(phase: CloudBootstrapPhase.target));
      } else {
        final guide = await _api.getCloudBootstrapGuide(state.provider, target);
        emit(
          state.copyWith(
            phase: CloudBootstrapPhase.guide,
            target: target,
            guide: guide,
            clearError: true,
          ),
        );
      }
    } catch (error) {
      emit(
        state.copyWith(
          phase: retryTarget == null
              ? CloudBootstrapPhase.target
              : CloudBootstrapPhase.loading,
          target: retryTarget,
          safeError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onGuideRequested(
    CloudBootstrapGuideRequested event,
    Emitter<CloudBootstrapState> emit,
  ) async {
    if (state.commandInProgress || event.target.provider != state.provider) {
      return;
    }
    emit(
      state.copyWith(
        phase: CloudBootstrapPhase.loading,
        target: event.target,
        clearError: true,
      ),
    );
    try {
      final guide = await _api.getCloudBootstrapGuide(
        state.provider,
        event.target,
      );
      emit(
        state.copyWith(
          phase: CloudBootstrapPhase.guide,
          guide: guide,
          clearError: true,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          phase: CloudBootstrapPhase.target,
          safeError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onSessionStarted(
    CloudBootstrapSessionStarted event,
    Emitter<CloudBootstrapState> emit,
  ) async {
    final guide = state.guide;
    if (guide == null || state.commandInProgress) return;
    emit(
      state.copyWith(
        phase: CloudBootstrapPhase.command,
        commandInProgress: true,
        clearError: true,
      ),
    );
    try {
      final session = await _api.createCloudBootstrapSession(
        guide: guide,
        entryPoint: state.entryPoint,
        displayName: event.displayName.trim(),
        twinId: state.twinId,
        idempotencyKey: _idempotencyKey('create'),
      );
      emit(_stateForSession(session, guide: guide));
    } catch (error) {
      emit(
        state.copyWith(
          phase: CloudBootstrapPhase.guide,
          commandInProgress: false,
          safeError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onExecute(
    CloudBootstrapExecuteSubmitted event,
    Emitter<CloudBootstrapState> emit,
  ) async {
    final session = state.session;
    if (session == null ||
        state.commandInProgress ||
        event.request.provider != state.provider ||
        !session.commandPermissions.contains('execute')) {
      event.request.dispose();
      return;
    }
    emit(
      state.copyWith(
        phase: CloudBootstrapPhase.command,
        commandInProgress: true,
        requiresRecheck: false,
        clearError: true,
      ),
    );
    try {
      final updated = await _api.executeCloudBootstrapSession(
        session.id,
        event.request,
      );
      emit(_stateForSession(updated, guide: state.guide));
    } catch (error) {
      event.request.dispose();
      emit(
        state.copyWith(
          phase: CloudBootstrapPhase.result,
          commandInProgress: false,
          requiresRecheck: true,
          safeError:
              '${ApiErrorHandler.extractMessage(error)} Check the stored result before trying again.',
        ),
      );
    }
  }

  Future<void> _onRecheck(
    CloudBootstrapSessionRechecked event,
    Emitter<CloudBootstrapState> emit,
  ) async {
    final session = state.session;
    if (session == null || state.commandInProgress) return;
    emit(state.copyWith(commandInProgress: true, clearError: true));
    try {
      final updated = await _api.getCloudBootstrapSession(session.id);
      emit(_stateForSession(updated, guide: state.guide));
    } catch (error) {
      emit(
        state.copyWith(
          commandInProgress: false,
          requiresRecheck: true,
          safeError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  void _onCredentialReentry(
    CloudBootstrapCredentialReentryRequested event,
    Emitter<CloudBootstrapState> emit,
  ) {
    final session = state.session;
    if (session?.commandPermissions.contains('execute') == true) {
      emit(
        state.copyWith(
          phase: CloudBootstrapPhase.authority,
          requiresRecheck: false,
          clearError: true,
        ),
      );
    }
  }

  Future<void> _onAcknowledge(
    CloudBootstrapManualRevocationAcknowledged event,
    Emitter<CloudBootstrapState> emit,
  ) async {
    final session = state.session;
    if (session == null ||
        state.commandInProgress ||
        !session.commandPermissions.contains('acknowledge_manual_revocation')) {
      return;
    }
    emit(state.copyWith(commandInProgress: true, clearError: true));
    try {
      final updated = await _api.acknowledgeCloudBootstrapRevocation(
        session.id,
        session.revision,
      );
      emit(_stateForSession(updated, guide: state.guide));
    } catch (error) {
      emit(
        state.copyWith(
          commandInProgress: false,
          safeError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onCancel(
    CloudBootstrapCancelled event,
    Emitter<CloudBootstrapState> emit,
  ) async {
    final session = state.session;
    if (session == null ||
        state.commandInProgress ||
        !session.commandPermissions.contains('cancel')) {
      return;
    }
    emit(state.copyWith(commandInProgress: true, clearError: true));
    try {
      final updated = await _api.cancelCloudBootstrapSession(
        session.id,
        session.revision,
      );
      emit(_stateForSession(updated, guide: state.guide));
    } catch (error) {
      emit(
        state.copyWith(
          commandInProgress: false,
          safeError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onStartNew(
    CloudBootstrapStartNewRequested event,
    Emitter<CloudBootstrapState> emit,
  ) async {
    final session = state.session;
    if (session == null ||
        state.commandInProgress ||
        !session.commandPermissions.contains('start_new')) {
      return;
    }
    emit(state.copyWith(phase: CloudBootstrapPhase.loading, clearError: true));
    try {
      final guide = await _api.getCloudBootstrapGuide(
        state.provider,
        session.target,
      );
      emit(
        CloudBootstrapState(
          provider: state.provider,
          entryPoint: state.entryPoint,
          twinId: state.twinId,
          phase: CloudBootstrapPhase.guide,
          target: session.target,
          guide: guide,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          phase: CloudBootstrapPhase.result,
          safeError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  void _onClosed(
    CloudBootstrapClosed event,
    Emitter<CloudBootstrapState> emit,
  ) {
    emit(
      CloudBootstrapState(
        provider: state.provider,
        entryPoint: state.entryPoint,
        twinId: state.twinId,
      ),
    );
  }

  CloudBootstrapState _stateForSession(
    CloudBootstrapSession session, {
    CloudBootstrapGuide? guide,
  }) {
    _validateSession(session, guide);
    final phase = switch (session.state) {
      CloudBootstrapSessionState.draft ||
      CloudBootstrapSessionState.credentialReentryRequired =>
        CloudBootstrapPhase.authority,
      CloudBootstrapSessionState.bootstrapRunning ||
      CloudBootstrapSessionState.disposalRunning => CloudBootstrapPhase.command,
      _ => CloudBootstrapPhase.result,
    };
    return state.copyWith(
      phase: phase,
      target: session.target,
      guide: guide,
      session: session,
      commandInProgress: false,
      requiresRecheck: session.isMutating,
      completedConnection: session.state == CloudBootstrapSessionState.ready
          ? session.connection
          : null,
      clearCompletion: session.state != CloudBootstrapSessionState.ready,
      clearError: true,
    );
  }

  void _validateSession(
    CloudBootstrapSession session,
    CloudBootstrapGuide? guide,
  ) {
    final currentSession = state.session;
    if (session.provider != state.provider ||
        (currentSession != null && session.id != currentSession.id) ||
        (currentSession != null &&
            (session.revision < currentSession.revision ||
                (session.state != currentSession.state &&
                    session.revision <= currentSession.revision))) ||
        (guide != null &&
            (guide.provider != session.provider ||
                guide.target != session.target ||
                guide.guideDigest != session.guideDigest ||
                guide.bootstrapAuthorityPack.digest !=
                    session.bootstrapAuthorityPack.digest ||
                guide.generatedDeploymentPack.digest !=
                    session.generatedDeploymentPack.digest))) {
      throw const FormatException(
        'Invalid API contract: bootstrap session does not match this flow.',
      );
    }
  }

  static String _idempotencyKey(String prefix) {
    final random = Random.secure();
    final suffix = List.generate(
      24,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
    return '$prefix-${DateTime.now().microsecondsSinceEpoch}-$suffix';
  }
}
