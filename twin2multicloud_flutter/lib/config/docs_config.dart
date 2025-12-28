/// Centralized documentation URL configuration for the Twin2MultiCloud application.
/// 
/// Use these instead of hardcoded URLs throughout the codebase to ensure
/// consistent documentation links and easier maintenance.
abstract class DocsConfig {
  // ============================================================
  // Base URLs
  // ============================================================
  
  /// Base URL for Optimizer (pricing calculator) documentation
  /// Points to the 2-twin2clouds container's static documentation server
  static const String optimizerBase = 'http://localhost:5003/documentation/';
  
  /// Base URL for Deployer (infrastructure) documentation
  /// Points to the 3-cloud-deployer container's static documentation server
  static const String deployerBase = 'http://localhost:5004/documentation/';
  
  // ============================================================
  // Credential Setup Guides
  // ============================================================
  
  /// AWS credential setup guide for Optimizer (pricing)
  static const String awsOptimizer = '${optimizerBase}docs-credentials-aws.html';
  
  /// AWS credential setup guide for Deployer (infrastructure)
  static const String awsDeployer = '${deployerBase}docs-credentials-aws.html';
  
  /// Azure credential setup guide for Optimizer (pricing)
  static const String azureOptimizer = '${optimizerBase}docs-credentials-azure.html';
  
  /// Azure credential setup guide for Deployer (infrastructure)
  static const String azureDeployer = '${deployerBase}docs-credentials-azure.html';
  
  /// GCP credential setup guide for Optimizer (pricing)
  static const String gcpOptimizer = '${optimizerBase}docs-credentials-gcp.html';
  
  /// GCP credential setup guide for Deployer (infrastructure)
  static const String gcpDeployer = '${deployerBase}docs-credentials-gcp.html';
  
  // ============================================================
  // Utility Methods
  // ============================================================
  
  /// Get the Optimizer credential docs URL for a provider.
  /// 
  /// Accepts case-insensitive provider names: 'aws', 'azure', 'gcp'.
  static String getOptimizerDocsUrl(String provider) {
    return switch (provider.toLowerCase()) {
      'aws' => awsOptimizer,
      'azure' => azureOptimizer,
      'gcp' => gcpOptimizer,
      _ => optimizerBase,
    };
  }
  
  /// Get the Deployer credential docs URL for a provider.
  /// 
  /// Accepts case-insensitive provider names: 'aws', 'azure', 'gcp'.
  static String getDeployerDocsUrl(String provider) {
    return switch (provider.toLowerCase()) {
      'aws' => awsDeployer,
      'azure' => azureDeployer,
      'gcp' => gcpDeployer,
      _ => deployerBase,
    };
  }
}
