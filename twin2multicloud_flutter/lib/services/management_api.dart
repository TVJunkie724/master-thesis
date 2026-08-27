import 'dart:typed_data';

import '../core/result.dart';
import '../models/architecture_profile.dart';
import '../models/user.dart';
import '../models/calc_params.dart';
import '../models/cloud_connection.dart';
import '../models/deployment_operations.dart';
import '../models/deployment_access.dart';
import '../models/deployment_readiness.dart';
import '../models/deployment_verification.dart';
import '../models/deployer_config.dart';
import '../models/optimizer_config.dart';
import '../models/provider_capability.dart';
import '../models/resolved_deployment_specification.dart';
import '../models/resolved_twin_architecture.dart';
import '../models/twin.dart';
import '../models/twin_config.dart';
import '../models/twin_transfer.dart';
import '../models/user_function_extension.dart';
import '../models/wizard_config_requests.dart';

abstract interface class SessionApi {
  void setUnauthorizedHandler(void Function()? handler);

  Future<String?> getAuthToken();
}

abstract interface class ProfileApi {
  Future<User> getCurrentUser();
}

abstract interface class UserPreferencesApi {
  Future<Map<String, dynamic>> updateUserPreferences({String? themePreference});
}

abstract interface class CloudAccessApi {
  Future<List<CloudConnection>> listCloudConnections({CloudProvider? provider});

  Future<CloudConnection> createCloudConnection(
    CloudConnectionCreateRequest request,
  );

  Future<CloudConnection> importCloudConnection(
    CloudConnectionImportRequest request,
  );

  Future<void> deleteCloudConnection(String id);

  Future<CloudConnectionValidationResult> validateCloudConnection(String id);
}

abstract interface class TwinApi {
  Future<List<Twin>> getTwins();

  Future<Twin> getTwin(String twinId);

  Future<Twin> createTwin(String name);

  Future<Twin> duplicateTwin(String twinId, TwinDuplicateRequest request);

  Future<Twin> importTwin(TwinImportRequest request);

  Future<PortableTwinDownload> exportTwin(String twinId);

  Future<Twin> updateTwin(String twinId, {String? name, String? state});

  Future<void> deleteTwin(String twinId);

  Future<TwinConfigData> getTwinConfig(String twinId);

  Future<TwinConfigData> updateTwinConfig(
    String twinId,
    Map<String, dynamic> config,
  );

  Future<TwinConfigData> updateTwinConfigRequest(
    String twinId,
    TwinConfigUpdateRequest request,
  );

  Future<Result<TwinConfigData>> getTwinConfigResult(String twinId);
}

abstract interface class PlatformCapabilityApi {
  Future<PlatformProviderCapabilities> getProviderCapabilities();
}

abstract interface class OptimizationApi {
  Future<OptimizerRunData> createOptimizerRun(String twinId, CalcParams params);

  Future<OptimizerDeploymentRunData?> getLatestOptimizerRun(String twinId);

  Future<OptimizerRunSelectionData> selectOptimizerRunForDeployment(
    String twinId,
    String runId,
  );

  Future<OptimizerConfigData?> getOptimizerConfig(String twinId);
}

abstract interface class ArchitectureApi {
  Future<ArchitectureProfileDetail> getCanonicalArchitectureContract();

  Future<TwinArchitectureSelection> getTwinArchitectureContract(String twinId);

  Future<ResolvedTwinArchitectureRead> getSelectedResolvedArchitecture(
    String twinId,
  );

  Future<ResolvedTwinArchitectureRead> getRunResolvedArchitecture(String runId);
}

abstract interface class DeploymentConfigurationApi {
  Future<DeployerConfigData?> getDeployerConfig(String twinId);

  Future<DeployerConfigData> updateDeployerConfig(
    String twinId,
    Map<String, dynamic> config,
  );

  Future<DeployerConfigData> updateDeployerConfigRequest(
    String twinId,
    DeployerConfigUpdateRequest request,
  );

  Future<Map<String, dynamic>> validateDeployerConfig(
    String twinId,
    String configType,
    String content,
  );

  Future<Map<String, dynamic>> validateL2Content(
    String twinId,
    String type,
    String content,
    String provider,
  );

  Future<Map<String, dynamic>> validateL4Content(
    String twinId,
    String type,
    String content,
    String provider,
  );

  Future<Map<String, dynamic>> uploadSceneGlb(
    String twinId,
    Uint8List fileBytes,
    String filename,
  );

  Future<void> deleteSceneGlb(String twinId);
}

abstract interface class UserFunctionExtensionApi {
  Future<List<ExtensionSlot>> listExtensionSlots();

  Future<UserFunctionValidationResult> validateTwinUserFunction(
    String twinId,
    UserFunctionSourceUpload upload,
  );

  Future<TwinUserFunction> saveTwinUserFunction(
    String twinId,
    UserFunctionSourceUpload upload,
  );

  Future<List<TwinUserFunction>> listTwinUserFunctions(String twinId);

  Future<void> deleteTwinUserFunction(String twinId, ExtensionSlot slot);
}

abstract interface class DeploymentLifecycleApi {
  Future<DeploymentReadinessSnapshot> getDeploymentReadiness(String twinId);

  Future<DeploymentReadinessSnapshot> runDeploymentPreflight(String twinId);

  Future<OperationSession> deployTwin(String twinId);

  Future<OperationSession> destroyTwin(String twinId);

  Future<DeploymentStatusSnapshot> getDeploymentStatus(String twinId);

  Future<DeploymentOutputsSnapshot> getDeploymentOutputs(String twinId);

  Future<DeploymentAccessSnapshot> getDeploymentAccess(String twinId);

  Future<DeploymentAccessCredential> rotateGcpGrafanaViewerCredential(
    String twinId,
  );

  Future<DeploymentHistory> getDeploymentHistory(
    String twinId, {
    int limit = 10,
  });

  String getSseUrl(String sseUrl, {int? lastEventId});

  Future<DeploymentLogPage> getDeploymentLogs(
    String twinId, {
    String? sessionId,
    int? afterEventId,
    int limit = 100,
  });

  Future<LogTraceStartResult> startLogTrace(String twinId);

  Future<BinaryDownload> downloadSimulator(String twinId);
}

abstract interface class VerificationApi {
  Future<Map<String, dynamic>> verifyInfrastructure(String twinId);

  Future<TelemetryVerificationStart> verifyDataFlow(
    String twinId,
    Map<String, dynamic> payload,
  );

  Future<TelemetryVerificationHistory> listDataFlowVerifications(
    String twinId, {
    int limit = 25,
  });

  Future<TelemetryVerificationRecord> getDataFlowVerification(
    String twinId,
    String verificationId,
  );
}

abstract interface class ManagementApi
    implements
        SessionApi,
        ProfileApi,
        UserPreferencesApi,
        CloudAccessApi,
        TwinApi,
        PlatformCapabilityApi,
        OptimizationApi,
        ArchitectureApi,
        DeploymentConfigurationApi,
        UserFunctionExtensionApi,
        DeploymentLifecycleApi,
        VerificationApi {}
