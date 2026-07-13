import 'package:flutter_bloc/flutter_bloc.dart';

import '../../services/management_api.dart';
import '../../utils/api_error_handler.dart';
import 'cloud_access_event.dart';
import 'cloud_access_state.dart';

class CloudAccessBloc extends Bloc<CloudAccessEvent, CloudAccessState> {
  final CloudAccessApi _api;

  CloudAccessBloc(this._api) : super(const CloudAccessState()) {
    on<CloudAccessStarted>(_onLoad);
    on<CloudAccessReloadRequested>(_onLoad);
    on<CloudAccessCreateRequested>(_onCreate);
    on<CloudAccessValidateRequested>(_onValidate);
    on<CloudAccessDefaultRequested>(_onSetDefault);
    on<CloudAccessDeleteRequested>(_onDelete);
    on<CloudAccessFeedbackCleared>(
      (_, emit) => emit(state.copyWith(clearFeedback: true)),
    );
  }

  Future<void> _onLoad(
    CloudAccessEvent event,
    Emitter<CloudAccessState> emit,
  ) async {
    emit(state.copyWith(isLoading: true, clearLoadError: true));
    try {
      final inventory = await _api.getCloudAccessInventory();
      emit(
        state.copyWith(
          inventory: inventory,
          isLoading: false,
          clearLoadError: true,
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          isLoading: false,
          loadError: ApiErrorHandler.extractMessage(error),
        ),
      );
    }
  }

  Future<void> _onCreate(
    CloudAccessCreateRequested event,
    Emitter<CloudAccessState> emit,
  ) async {
    if (state.isCreating) return;
    emit(state.copyWith(isCreating: true, clearFeedback: true));
    try {
      await _api.createCloudConnection(event.request);
      await _reloadAfterMutation(
        emit,
        successMessage:
            '${event.request.provider.label} ${event.request.purpose.label.toLowerCase()} created.',
        isCreating: false,
      );
    } catch (error) {
      emit(
        state.copyWith(
          isCreating: false,
          feedback: CloudAccessFeedback.error(
            ApiErrorHandler.extractMessage(error),
          ),
        ),
      );
    }
  }

  Future<void> _onValidate(
    CloudAccessValidateRequested event,
    Emitter<CloudAccessState> emit,
  ) {
    return _runConnectionCommand(
      event.connectionId,
      emit,
      command: () => _api.validateCloudConnection(event.connectionId),
      successMessage: 'Cloud access validation completed.',
    );
  }

  Future<void> _onSetDefault(
    CloudAccessDefaultRequested event,
    Emitter<CloudAccessState> emit,
  ) {
    return _runConnectionCommand(
      event.connectionId,
      emit,
      command: () => _api.updateCloudConnection(
        event.connectionId,
        isDefaultForPricing: true,
      ),
      successMessage: 'Default pricing access updated.',
    );
  }

  Future<void> _onDelete(
    CloudAccessDeleteRequested event,
    Emitter<CloudAccessState> emit,
  ) {
    return _runConnectionCommand(
      event.connectionId,
      emit,
      command: () => _api.deleteCloudConnection(event.connectionId),
      successMessage: 'Cloud access deleted.',
    );
  }

  Future<void> _runConnectionCommand(
    String connectionId,
    Emitter<CloudAccessState> emit, {
    required Future<void> Function() command,
    required String successMessage,
  }) async {
    if (state.busyConnectionIds.contains(connectionId)) return;
    emit(
      state.copyWith(
        busyConnectionIds: {...state.busyConnectionIds, connectionId},
        clearFeedback: true,
      ),
    );
    try {
      await command();
      await _reloadAfterMutation(
        emit,
        successMessage: successMessage,
        completedConnectionId: connectionId,
      );
    } catch (error) {
      final busy = {...state.busyConnectionIds}..remove(connectionId);
      emit(
        state.copyWith(
          busyConnectionIds: busy,
          feedback: CloudAccessFeedback.error(
            ApiErrorHandler.extractMessage(error),
          ),
        ),
      );
    }
  }

  Future<void> _reloadAfterMutation(
    Emitter<CloudAccessState> emit, {
    required String successMessage,
    String? completedConnectionId,
    bool? isCreating,
  }) async {
    final busy = {...state.busyConnectionIds};
    if (completedConnectionId != null) busy.remove(completedConnectionId);
    try {
      final inventory = await _api.getCloudAccessInventory();
      emit(
        state.copyWith(
          inventory: inventory,
          busyConnectionIds: busy,
          isCreating: isCreating,
          clearLoadError: true,
          feedback: CloudAccessFeedback.success(successMessage),
        ),
      );
    } catch (error) {
      emit(
        state.copyWith(
          busyConnectionIds: busy,
          isCreating: isCreating,
          loadError: ApiErrorHandler.extractMessage(error),
          feedback: CloudAccessFeedback.success(
            '$successMessage Refresh cloud access to update this view.',
          ),
        ),
      );
    }
  }
}
