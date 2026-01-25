// lib/bloc/twin_overview/twin_overview_bloc.dart
// BLoC for the twin overview screen

import 'dart:async';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../services/api_service.dart';
import '../../utils/api_error_handler.dart';
import 'twin_overview_event.dart';
import 'twin_overview_state.dart';

class TwinOverviewBloc extends Bloc<TwinOverviewEvent, TwinOverviewState> {
  final ApiService _api;
  String? _currentTwinId;
  Timer? _pollingTimer;

  TwinOverviewBloc({required ApiService api})
    : _api = api,
      super(const TwinOverviewLoading()) {
    on<TwinOverviewLoad>(_onLoad);
    on<TwinOverviewRefresh>(_onRefresh);
    on<TwinOverviewDeploy>(_onDeploy);
    on<TwinOverviewDestroy>(_onDestroy);
    on<TwinOverviewDelete>(_onDelete);
    on<TwinOverviewLogReceived>(_onLogReceived);
    on<TwinOverviewDeploymentComplete>(_onDeploymentComplete);
    on<TwinOverviewClearMessages>(_onClearMessages);
  }

  Future<void> _onLoad(
    TwinOverviewLoad event,
    Emitter<TwinOverviewState> emit,
  ) async {
    _currentTwinId = event.twinId;
    emit(const TwinOverviewLoading());

    try {
      // Load twin basic data
      final twin = await _api.getTwin(event.twinId);

      // Load optimizer config (includes pricing snapshots)
      Map<String, dynamic>? optimizerConfig;
      try {
        optimizerConfig = await _api.getOptimizerConfig(event.twinId);
      } catch (e) {
        // Optimizer config may not exist yet
      }

      // Load deployer config
      Map<String, dynamic>? deployerConfig;
      try {
        deployerConfig = await _api.getDeployerConfig(event.twinId);
      } catch (e) {
        // Deployer config may not exist yet
      }

      final twinState = twin['state'] as String? ?? 'draft';

      emit(
        _buildLoadedState(
          twinId: event.twinId,
          twin: twin,
          twinState: twinState,
          optimizerConfig: optimizerConfig,
          deployerConfig: deployerConfig,
        ),
      );
    } catch (e) {
      emit(
        TwinOverviewError(
          'Failed to load twin: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onRefresh(
    TwinOverviewRefresh event,
    Emitter<TwinOverviewState> emit,
  ) async {
    if (_currentTwinId != null) {
      add(TwinOverviewLoad(_currentTwinId!));
    }
  }

  Future<void> _onDeploy(
    TwinOverviewDeploy event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    emit(
      currentState.copyWith(
        isDeploying: true,
        twinState: 'deploying',
        terminalLogs: ['> Starting deployment...'],
      ),
    );

    try {
      // Call backend to start deployment
      // This is a synchronous call - backend waits for Terraform to complete
      final result = await _api.deployTwin(currentState.twinId);

      // Deployment completed successfully
      emit(
        currentState.copyWith(
          isDeploying: false,
          twinState: result['status'] as String? ?? 'deployed',
          terminalLogs: [
            '> Starting deployment...',
            '> Deployment initiated',
            '> Running terraform apply...',
            '> ✓ ${result['message'] ?? 'Deployment successful'}',
          ],
          successMessage: 'Deployment successful',
        ),
      );

      // Reload to get updated twin data
      add(TwinOverviewLoad(currentState.twinId));
    } catch (e) {
      emit(
        currentState.copyWith(
          isDeploying: false,
          twinState: 'error',
          errorMessage:
              'Deployment failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onDestroy(
    TwinOverviewDestroy event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    emit(
      currentState.copyWith(
        isDestroying: true,
        twinState: 'destroying',
        terminalLogs: ['> Starting resource destruction...'],
      ),
    );

    try {
      // Call backend to start destruction
      // This is a synchronous call - backend waits for Terraform to complete
      final result = await _api.destroyTwin(currentState.twinId);

      // Destruction completed successfully
      emit(
        currentState.copyWith(
          isDestroying: false,
          twinState: result['status'] as String? ?? 'destroyed',
          terminalLogs: [
            '> Starting resource destruction...',
            '> Destroy operation initiated',
            '> Running terraform destroy...',
            '> ✓ ${result['message'] ?? 'Destruction successful'}',
          ],
          successMessage: 'Resources destroyed successfully',
        ),
      );

      // Reload to get updated twin data
      add(TwinOverviewLoad(currentState.twinId));
    } catch (e) {
      emit(
        currentState.copyWith(
          isDestroying: false,
          twinState: 'error',
          errorMessage: 'Destroy failed: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  Future<void> _onDelete(
    TwinOverviewDelete event,
    Emitter<TwinOverviewState> emit,
  ) async {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    try {
      await _api.deleteTwin(currentState.twinId);
      // Navigation will be handled by the screen listener
      emit(currentState.copyWith(successMessage: 'deleted'));
    } catch (e) {
      emit(
        currentState.copyWith(
          errorMessage:
              'Failed to delete: ${ApiErrorHandler.extractMessage(e)}',
        ),
      );
    }
  }

  void _onLogReceived(
    TwinOverviewLogReceived event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    final newLogs = [...currentState.terminalLogs, event.log];
    emit(currentState.copyWith(terminalLogs: newLogs));
  }

  void _onDeploymentComplete(
    TwinOverviewDeploymentComplete event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    if (event.success) {
      // Reload to get updated state
      add(TwinOverviewLoad(currentState.twinId));
    } else {
      emit(
        currentState.copyWith(
          isDeploying: false,
          isDestroying: false,
          twinState: event.newState ?? 'error',
          lastError: event.message,
        ),
      );
    }
  }

  void _onClearMessages(
    TwinOverviewClearMessages event,
    Emitter<TwinOverviewState> emit,
  ) {
    final currentState = state;
    if (currentState is! TwinOverviewLoaded) return;

    emit(currentState.copyWith(clearSuccess: true, clearError: true));
  }

  /// Start polling for deployment status updates
  void _startPolling(String twinId, Emitter<TwinOverviewState> emit) {
    _stopPolling();

    _pollingTimer = Timer.periodic(const Duration(seconds: 3), (_) async {
      try {
        final status = await _api.getDeploymentStatus(twinId);
        final newState = status['state'] as String?;

        if (newState != null) {
          // Check if operation completed
          if (newState == 'deployed' || newState == 'destroyed') {
            _stopPolling();
            add(
              TwinOverviewDeploymentComplete(success: true, newState: newState),
            );
          } else if (newState == 'error') {
            _stopPolling();
            add(
              TwinOverviewDeploymentComplete(
                success: false,
                newState: 'error',
                message: status['last_error'] as String?,
              ),
            );
          }
          // For deploying/destroying, just continue polling
        }
      } catch (e) {
        // Log error but continue polling
        add(
          TwinOverviewLogReceived(
            '> [WARNING] Status check failed: ${ApiErrorHandler.extractMessage(e)}',
          ),
        );
      }
    });
  }

  void _stopPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = null;
  }

  @override
  Future<void> close() {
    _stopPolling();
    return super.close();
  }

  /// Build loaded state with calculated permissions based on twin state
  TwinOverviewLoaded _buildLoadedState({
    required String twinId,
    required Map<String, dynamic> twin,
    required String twinState,
    Map<String, dynamic>? optimizerConfig,
    Map<String, dynamic>? deployerConfig,
  }) {
    // State-based permission matrix (from implementation plan)
    final canDeploy = ['configured', 'destroyed', 'error'].contains(twinState);
    final canDestroy = ['deployed', 'error'].contains(twinState);
    final canEdit = ![
      'deploying',
      'destroying',
      'deployed',
    ].contains(twinState);
    final canDelete = ![
      'deploying',
      'destroying',
      'deployed',
    ].contains(twinState);

    return TwinOverviewLoaded(
      twinId: twinId,
      projectName: twin['name'] as String? ?? 'Unnamed Twin',
      cloudResourceName:
          deployerConfig?['deployer_digital_twin_name'] as String?,
      twinState: twinState,
      canDeploy: canDeploy,
      canDestroy: canDestroy,
      canEdit: canEdit,
      canDelete: canDelete,
      lastError: twin['last_error'] as String?,
      lastDeploymentLogs: twin['last_deployment_logs'] as String?,
      // Optimizer result and params
      optimizerResult: optimizerConfig?['result'] as Map<String, dynamic>?,
      optimizerParams: optimizerConfig?['params'] as Map<String, dynamic>?,
      cheapestPath: optimizerConfig?['cheapest_path'] as Map<String, dynamic>?,
      calculatedAt: optimizerConfig?['calculated_at'] as String?,
      // Pricing snapshots - match API field names
      pricingAws:
          optimizerConfig?['pricing_aws_snapshot'] as Map<String, dynamic>?,
      pricingAwsUpdatedAt:
          optimizerConfig?['pricing_aws_updated_at'] as String?,
      pricingAzure:
          optimizerConfig?['pricing_azure_snapshot'] as Map<String, dynamic>?,
      pricingAzureUpdatedAt:
          optimizerConfig?['pricing_azure_updated_at'] as String?,
      pricingGcp:
          optimizerConfig?['pricing_gcp_snapshot'] as Map<String, dynamic>?,
      pricingGcpUpdatedAt:
          optimizerConfig?['pricing_gcp_updated_at'] as String?,
      deployerConfig: deployerConfig,
    );
  }
}
