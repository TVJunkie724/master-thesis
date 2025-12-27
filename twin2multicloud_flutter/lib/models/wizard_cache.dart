import '../models/calc_params.dart';
import '../models/calc_result.dart';

/// Tracks whether credentials came from DB (inherited) or were newly entered
enum CredentialSource {
  /// Credentials are inherited from database (already saved, encrypted)
  /// These should NOT be sent on update (would overwrite with empty values)
  inherited,
  
  /// Credentials were newly entered by user
  /// These SHOULD be sent on update
  newlyEntered,
  
  /// No credentials configured
  none,
}

/// In-memory cache for wizard form data.
/// 
/// This cache holds all form data across wizard steps and is only
/// persisted to the database when the user explicitly clicks "Save Draft".
/// 
/// The cache is cleared when:
/// - User clicks "Discard Changes" in exit dialog
/// - User navigates away from wizard (after save or discard)
class WizardCache {
  // ============================================================
  // Step 1: Configuration Data
  // ============================================================
  
  /// Twin name (required)
  String? twinName;
  
  /// Debug mode flag
  bool debugMode = false;
  
  /// AWS credentials (access_key_id, secret_access_key, region, session_token)
  Map<String, String> awsCredentials = {};
  
  /// Azure credentials (subscription_id, client_id, client_secret, tenant_id, region)
  Map<String, String> azureCredentials = {};
  
  /// GCP credentials (project_id, billing_account, region)
  Map<String, String> gcpCredentials = {};
  
  /// GCP service account JSON (raw JSON string)
  String? gcpServiceAccountJson;
  
  /// Validation status for each provider
  bool awsValid = false;
  bool azureValid = false;
  bool gcpValid = false;
  
  /// Track whether credentials are inherited from DB or newly entered
  /// This is CRITICAL to avoid overwriting encrypted credentials with empty values
  CredentialSource awsCredentialSource = CredentialSource.none;
  CredentialSource azureCredentialSource = CredentialSource.none;
  CredentialSource gcpCredentialSource = CredentialSource.none;
  
  /// Mark provider credentials as inherited from database
  void markAwsInherited() {
    awsCredentialSource = CredentialSource.inherited;
    awsValid = true;
  }
  
  void markAzureInherited() {
    azureCredentialSource = CredentialSource.inherited;
    azureValid = true;
  }
  
  void markGcpInherited() {
    gcpCredentialSource = CredentialSource.inherited;
    gcpValid = true;
  }
  
  /// Mark provider credentials as newly entered (will be saved)
  void markAwsNewlyEntered() {
    awsCredentialSource = CredentialSource.newlyEntered;
  }
  
  void markAzureNewlyEntered() {
    azureCredentialSource = CredentialSource.newlyEntered;
  }
  
  void markGcpNewlyEntered() {
    gcpCredentialSource = CredentialSource.newlyEntered;
  }
  
  /// Check if provider has new credentials that need saving
  bool get hasNewAwsCredentials => awsCredentialSource == CredentialSource.newlyEntered;
  bool get hasNewAzureCredentials => azureCredentialSource == CredentialSource.newlyEntered;
  bool get hasNewGcpCredentials => gcpCredentialSource == CredentialSource.newlyEntered;
  
  // ============================================================
  // Step 2: Optimizer Data
  // ============================================================
  
  /// Calculation parameters
  CalcParams? calcParams;
  
  /// Calculation result (after user clicks Calculate)
  CalcResult? calcResult;
  
  /// Raw API response for result (needed for persistence)
  Map<String, dynamic>? calcResultRaw;
  
  /// Pricing snapshots at time of calculation
  Map<String, dynamic>? pricingSnapshots;
  
  /// Pricing timestamps at time of calculation
  Map<String, String?>? pricingTimestamps;
  
  // ============================================================
  // Step 3: Deployer Data (Future)
  // ============================================================
  
  // Reserved for Sprint 4
  
  // ============================================================
  // State Tracking
  // ============================================================
  
  /// True if any data has been modified since last save
  bool hasUnsavedChanges = false;
  
  /// Mark as having unsaved changes
  void markDirty() {
    hasUnsavedChanges = true;
  }
  
  /// Mark as saved (no unsaved changes)
  void markClean() {
    hasUnsavedChanges = false;
  }
  
  /// Clear all cached data (on discard or after save+exit)
  void clear() {
    // Step 1
    twinName = null;
    debugMode = false;
    awsCredentials = {};
    azureCredentials = {};
    gcpCredentials = {};
    gcpServiceAccountJson = null;
    awsValid = false;
    azureValid = false;
    gcpValid = false;
    awsCredentialSource = CredentialSource.none;
    azureCredentialSource = CredentialSource.none;
    gcpCredentialSource = CredentialSource.none;
    
    // Step 2
    calcParams = null;
    calcResult = null;
    calcResultRaw = null;
    pricingSnapshots = null;
    pricingTimestamps = null;
    
    // State
    hasUnsavedChanges = false;
  }
  
  /// Check if Step 1 is complete (name + at least one valid provider)
  bool get canProceedToStep2 {
    return (twinName?.isNotEmpty ?? false) && 
           (awsValid || azureValid || gcpValid);
  }
  
  /// Check if Step 2 has a calculation result
  bool get hasCalculationResult => calcResult != null;
  
  /// Get set of configured provider names (uppercase)
  Set<String> get configuredProviders {
    final providers = <String>{};
    if (awsValid) providers.add('AWS');
    if (azureValid) providers.add('AZURE');
    if (gcpValid) providers.add('GCP');
    return providers;
  }
}
