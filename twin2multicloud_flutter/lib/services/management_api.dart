import 'dart:typed_data';

import '../core/result.dart';
import '../models/calc_result.dart';
import '../models/cloud_access_inventory.dart';
import '../models/cloud_connection.dart';
import '../models/dashboard_stats.dart';
import '../models/deployment_operations.dart';
import '../models/deployment_readiness.dart';
import '../models/pricing_candidate_review.dart';
import '../models/pricing_health.dart';
import '../models/pricing_refresh_run.dart';
import '../models/wizard_config_requests.dart';

abstract interface class SessionApi {
  void setToken(String token);

  Future<String?> getAuthToken();
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
  Future<List<dynamic>> getTwins();

  Future<DashboardStats> getDashboardStats();

  Future<Map<String, dynamic>> getTwin(String twinId);

  Future<Map<String, dynamic>> createTwin(String name);

  Future<Map<String, dynamic>> updateTwin(
    String twinId, {
    String? name,
    String? state,
  });

  Future<void> deleteTwin(String twinId);

  Future<Map<String, dynamic>> getTwinConfig(String twinId);

  Future<Map<String, dynamic>> updateTwinConfig(
    String twinId,
    Map<String, dynamic> config,
  );

  Future<Map<String, dynamic>> updateTwinConfigRequest(
    String twinId,
    TwinConfigUpdateRequest request,
  );

  Future<Map<String, dynamic>> validateCredentials(
    String twinId,
    String provider,
  );

  Future<Map<String, dynamic>> validateCredentialsInline(
    String provider,
    Map<String, dynamic> credentials,
  );

  Future<Map<String, dynamic>> validateCredentialsDual(
    String provider,
    Map<String, dynamic> credentials,
  );

  Future<Map<String, dynamic>> validateStoredCredentialsDual(
    String twinId,
    String provider,
  );

  Future<Result<Map<String, dynamic>>> getTwinConfigResult(String twinId);
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

  Future<Map<String, dynamic>> exportPricing(String provider);

  Future<Result<Map<String, dynamic>>> getPricingStatusResult();
}

abstract interface class OptimizationApi {
  Future<Map<String, dynamic>> calculateCosts(Map<String, dynamic> params);

  Future<Result<CalcResult>> calculateCostsResult(Map<String, dynamic> params);

  Future<Map<String, dynamic>> getOptimizerConfig(String twinId);

  Future<void> saveOptimizerParams(String twinId, Map<String, dynamic> params);

  Future<void> saveOptimizerResult(
    String twinId, {
    required Map<String, dynamic> params,
    required Map<String, dynamic> result,
    required Map<String, String?> cheapestPath,
    required Map<String, dynamic> pricingSnapshots,
    required Map<String, String?> pricingTimestamps,
  });
}

abstract interface class DeploymentConfigurationApi {
  Future<Map<String, dynamic>> getDeployerConfig(String twinId);

  Future<Map<String, dynamic>> updateDeployerConfig(
    String twinId,
    Map<String, dynamic> config,
  );

  Future<Map<String, dynamic>> updateDeployerConfigRequest(
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
        UserPreferencesApi,
        CloudAccessApi,
        TwinApi,
        PricingApi,
        OptimizationApi,
        DeploymentConfigurationApi,
        DeploymentLifecycleApi,
        VerificationApi {}
