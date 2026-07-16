import 'dart:typed_data';

import '../core/result.dart';
import '../models/calc_result.dart';
import '../models/authentication.dart';
import '../models/user.dart';
import '../models/calc_params.dart';
import '../models/cloud_access_inventory.dart';
import '../models/cloud_connection.dart';
import '../models/dashboard_stats.dart';
import '../models/deployment_operations.dart';
import '../models/deployment_readiness.dart';
import '../models/deployer_config.dart';
import '../models/optimizer_config.dart';
import '../models/pricing_candidate_review.dart';
import '../models/pricing_health.dart';
import '../models/pricing_refresh_run.dart';
import '../models/pricing_export_snapshot.dart';
import '../models/provider_capability.dart';
import '../models/twin.dart';
import '../models/twin_config.dart';
import '../models/wizard_config_requests.dart';

abstract interface class SessionApi {
  void setToken(String? token);

  void setUnauthorizedHandler(void Function()? handler);

  Future<String?> getAuthToken();
}

abstract interface class AuthenticationApi {
  Future<List<AuthProviderCapability>> getAuthProviders();

  Future<AuthLoginTransaction> startExternalLogin(IdentityProvider provider);

  Future<AuthExchangeResult> exchangeAuthSession(
    AuthLoginTransaction transaction,
  );

  Future<void> cancelAuthSession(AuthLoginTransaction transaction);

  Future<void> logoutSession();

  Future<User> getCurrentUser();
}

abstract interface class UserPreferencesApi {
  Future<Map<String, dynamic>> updateUserPreferences({String? themePreference});
}

abstract interface class CloudAccessApi {
  Future<List<CloudConnection>> listCloudConnections({CloudProvider? provider});

  Future<CloudAccessInventory> getCloudAccessInventory();

  Future<CloudConnection> createCloudConnection(
    CloudConnectionCreateRequest request,
  );

  Future<CloudConnection> updateCloudConnection(
    String id, {
    String? displayName,
    Map<String, dynamic>? cloudScope,
    bool? isDefaultForPricing,
  });

  Future<void> deleteCloudConnection(String id);

  Future<CloudConnectionValidationResult> validateCloudConnection(String id);
}

abstract interface class TwinApi {
  Future<List<Twin>> getTwins();

  Future<DashboardStats> getDashboardStats();

  Future<Twin> getTwin(String twinId);

  Future<Twin> createTwin(String name);

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

abstract interface class PricingApi {
  Future<Map<String, dynamic>> getPricingStatus();

  Future<PricingHealthResponse> getPricingHealth();

  Future<PricingRefreshRun> startPricingRefresh(
    String provider, {
    String? connectionId,
    bool force = true,
  });

  Future<PricingCandidateReportList> listPricingCandidateReports(
    String provider,
    String refreshRunId,
  );

  Future<PricingTrace> getPricingCandidateTrace(String reportId);

  Future<PricingReviewDecision> createPricingReviewDecision(
    String reportId,
    String decision, {
    String? candidateId,
    String? rationale,
  });

  Future<Map<String, dynamic>> getRegionsStatus();

  Future<PricingExportSnapshot> exportPricing(String provider);

  Future<Result<Map<String, dynamic>>> getPricingStatusResult();
}

abstract interface class PlatformCapabilityApi {
  Future<PlatformProviderCapabilities> getProviderCapabilities();
}

abstract interface class OptimizationApi {
  Future<OptimizationResultData> calculateCosts(CalcParams params);

  Future<Result<CalcResult>> calculateCostsResult(CalcParams params);

  Future<OptimizerConfigData?> getOptimizerConfig(String twinId);

  Future<void> saveOptimizerParams(String twinId, CalcParams params);

  Future<void> saveOptimizerResult(
    String twinId, {
    required CalcParams params,
    required OptimizationResultData optimization,
    required CheapestPath cheapestPath,
    required Map<CloudProvider, PricingExportSnapshot> pricingSnapshots,
  });
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

  Future<Map<String, dynamic>> uploadProjectZip(
    String twinId,
    Uint8List fileBytes,
    String filename,
  );
}

abstract interface class DeploymentLifecycleApi {
  Future<DeploymentReadinessSnapshot> getDeploymentReadiness(String twinId);

  Future<DeploymentReadinessSnapshot> runDeploymentPreflight(String twinId);

  Future<OperationSession> deployTwin(String twinId);

  Future<OperationSession> destroyTwin(String twinId);

  Future<DeploymentStatusSnapshot> getDeploymentStatus(String twinId);

  Future<DeploymentOutputsSnapshot> getDeploymentOutputs(String twinId);

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

  Future<Map<String, dynamic>> verifyDataFlow(
    String twinId,
    Map<String, dynamic> payload,
  );
}

abstract interface class ManagementApi
    implements
        SessionApi,
        AuthenticationApi,
        UserPreferencesApi,
        CloudAccessApi,
        TwinApi,
        PricingApi,
        PlatformCapabilityApi,
        OptimizationApi,
        DeploymentConfigurationApi,
        DeploymentLifecycleApi,
        VerificationApi {}
