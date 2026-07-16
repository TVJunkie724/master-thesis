// lib/bloc/wizard/wizard_bloc.dart
// BLoC for wizard state machine
// Refactored to use service extraction pattern for testability

import 'dart:typed_data';

import 'package:flutter_bloc/flutter_bloc.dart';
import '../../core/app_logger.dart';
import '../../models/calc_result.dart';
import '../../models/cloud_connection.dart';
import '../../models/deployer_artifact_validation.dart';
import '../../models/optimizer_config.dart';
import '../../services/management_api.dart';
import '../../utils/api_error_handler.dart';
import 'wizard_event.dart';
import 'wizard_state.dart';
import 'helpers/helpers.dart';
import 'services/wizard_glb_cleanup_service.dart';
import 'services/wizard_deployer_validation_service.dart';
import 'services/wizard_init_service.dart';
import 'services/wizard_zip_service.dart';

part 'handlers/wizard_artifact_content_handlers.dart';
part 'handlers/wizard_initialization_cloud_access_handlers.dart';
part 'handlers/wizard_optimization_persistence_handlers.dart';
part 'handlers/wizard_transfer_command_handlers.dart';

/// WizardBloc - State machine for the multi-step wizard
///
/// Manages:
/// - Step navigation with validation gates
/// - Transient UI state (notifications) that clear on step change
/// - Persistent data (credentials, calc results) that survives navigation
/// - Create vs Edit mode distinction
class WizardBloc extends Bloc<WizardEvent, WizardState> {
  final WizardInitService _initService;
  final WizardZipService _zipService;
  final WizardGlbCleanupService _glbCleanupService;
  final WizardDeployerValidationService _deployerValidationService;
  final ManagementApi _api;
  final AppLogger _logger;
  final int _maxSceneGlbBytes;
  final int _maxProjectZipBytes;

  WizardBloc({
    required ManagementApi api,
    WizardInitService? initService,
    WizardZipService? zipService,
    WizardGlbCleanupService? glbCleanupService,
    AppLogger logger = const AppLogger(),
    int maxSceneGlbBytes = 100 * 1024 * 1024,
    int maxProjectZipBytes = 100 * 1024 * 1024,
  }) : _api = api,
       _initService = initService ?? WizardInitService(),
       _zipService = zipService ?? WizardZipService(),
       _glbCleanupService =
           glbCleanupService ?? WizardGlbCleanupService(api: api),
       _deployerValidationService = WizardDeployerValidationService(api: api),
       _logger = logger,
       _maxSceneGlbBytes = maxSceneGlbBytes,
       _maxProjectZipBytes = maxProjectZipBytes,
       super(const WizardState()) {
    // === Initialization ===
    on<WizardInitCreate>(_onInitCreate);
    on<WizardInitEdit>(_onInitEdit);
    on<WizardProviderCapabilitiesLoadRequested>(
      _onProviderCapabilitiesLoadRequested,
    );

    // === Navigation ===
    on<WizardNextStep>(_onNextStep);
    on<WizardPreviousStep>(_onPreviousStep);
    on<WizardGoToStep>(_onGoToStep);

    // === Step 1: Configuration ===
    on<WizardTwinNameChanged>(_onTwinNameChanged);
    on<WizardDebugModeChanged>(_onDebugModeChanged);
    on<WizardCredentialsChanged>(_onCredentialsChanged);
    on<WizardCredentialsValidated>(_onCredentialsValidated);
    on<WizardCredentialsCleared>(_onCredentialsCleared);
    on<WizardCloudConnectionsLoadRequested>(_onCloudConnectionsLoadRequested);
    on<WizardCloudConnectionSelected>(_onCloudConnectionSelected);
    on<WizardCloudConnectionCreateRequested>(_onCloudConnectionCreateRequested);
    on<WizardCloudConnectionValidateRequested>(
      _onCloudConnectionValidateRequested,
    );
    on<WizardCloudConnectionUnbound>(_onCloudConnectionUnbound);
    on<WizardCloudConnectionDeleteRequested>(_onCloudConnectionDeleteRequested);

    // === Step 2: Optimizer ===
    on<WizardPricingHealthLoadRequested>(_onPricingHealthLoadRequested);
    on<WizardCalcParamsChanged>(_onCalcParamsChanged);
    on<WizardCalcFormValidChanged>(_onCalcFormValidChanged);
    on<WizardCalculateRequested>(_onCalculateRequested);

    // === Persistence ===
    on<WizardSaveDraft>(_onSaveDraft);
    on<WizardFinish>(_onFinish);

    // === UI Feedback ===
    on<WizardClearNotifications>(_onClearNotifications);
    on<WizardDismissError>(_onDismissError);

    // === Step 3 Invalidation ===
    on<WizardProceedWithNewResults>(_onProceedWithNewResults);
    on<WizardRestoreOldResults>(_onRestoreOldResults);
    on<WizardProceedAndSave>(_onProceedAndSave);
    on<WizardProceedAndNext>(_onProceedAndNext);
    on<WizardClearInvalidation>(_onClearInvalidation);

    // === Step 3 Section 2: Config Files ===
    on<WizardArtifactValidationRequested>(_onArtifactValidationRequested);
    on<WizardDeployerTwinNameChanged>(_onDeployerTwinNameChanged);
    on<WizardConfigEventsChanged>(_onConfigEventsChanged);
    on<WizardConfigIotDevicesChanged>(_onConfigIotDevicesChanged);

    // === Step 3 Section 3: L1 Payloads ===
    on<WizardPayloadsChanged>(_onPayloadsChanged);

    // === Step 3 Section 3: L2 User Functions ===
    on<WizardProcessorContentChanged>(_onProcessorContentChanged);
    on<WizardEventFeedbackContentChanged>(_onEventFeedbackContentChanged);
    on<WizardEventActionContentChanged>(_onEventActionContentChanged);
    on<WizardStateMachineContentChanged>(_onStateMachineContentChanged);

    // === Step 3 Section 3: L2 Requirements ===
    on<WizardProcessorRequirementsChanged>(_onProcessorRequirementsChanged);
    on<WizardEventFeedbackRequirementsChanged>(
      _onEventFeedbackRequirementsChanged,
    );
    on<WizardEventActionRequirementsChanged>(_onEventActionRequirementsChanged);

    // === Step 3: L4 Hierarchy ===
    on<WizardHierarchyContentChanged>(_onHierarchyContentChanged);

    // === Step 3: L4 Scene ===
    on<WizardSceneConfigContentChanged>(_onSceneConfigContentChanged);
    on<WizardSceneGlbUploadRequested>(_onSceneGlbUploadRequested);
    on<WizardSceneGlbDeleteRequested>(_onSceneGlbDeleteRequested);

    // === Step 3: L4/L5 User Config ===
    on<WizardUserConfigContentChanged>(_onUserConfigContentChanged);

    // === Step 3: L4 Cleanup ===
    on<WizardL4CleanupRequested>(_onL4CleanupRequested);

    // === Step 3: Zip Upload ===
    on<WizardZipUploadRequested>(_onZipUploadRequested);
  }
}
