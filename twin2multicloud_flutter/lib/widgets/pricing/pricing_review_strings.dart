import '../../models/cloud_access_inventory.dart';
import '../../models/pricing_candidate_review.dart';
import '../../models/pricing_refresh_run.dart';

abstract class PricingReviewStrings {
  static const providers = ['aws', 'azure', 'gcp'];
  static const pageTitle = 'Pricing Review';
  static const screenTitle = 'Cloud pricing readiness';
  static const screenDescription =
      'Refresh and verify provider pricing evidence.';
  static const backToDashboard = 'Back to dashboard';
  static const reloadPricingState = 'Reload pricing state';
  static const dismissMessage = 'Dismiss message';
  static const dashboardTitle = 'Pricing readiness';
  static const dashboardLoadError = 'Pricing readiness could not be loaded.';
  static const reviewPricing = 'Review pricing';
  static const retry = 'Retry';
  static const loading = 'Loading';
  static const checkingPricingState = 'Checking pricing state';
  static const noPricingStatus = 'No pricing status available';
  static const fetching = 'Fetching';
  static const refresh = 'Refresh';
  static const cancel = 'Cancel';
  static const loadingPricingAccess = 'Loading pricing access…';
  static const configurePricingAccess =
      'Configure pricing access in Profile to refresh.';
  static const fetchingMayTakeSeveralMinutes =
      'Fetching provider pricing. This can take several minutes.';
  static const latestRefresh = 'Latest refresh';
  static const noCandidateEvidence =
      'No candidate evidence was produced by this refresh.';
  static const candidateEvidenceCollapsed =
      'Candidate evidence is collapsed by default.';
  static const aiDisabled =
      'AI review is disabled. Contract-valid candidates remain available.';
  static const saveSelection = 'Save selection';
  static const decideLater = 'Decide later';
  static const traceTitle = 'Intent and matching trace';
  static const contractSelection = 'Contract selection';
  static const aiSuggestion = 'AI suggestion';
  static const noCandidate = 'no candidate';
  static const notAssigned = 'not assigned';
  static const decisionSaved = 'Pricing decision saved.';

  static String providerName(String provider) => provider.toUpperCase();

  static String refreshDialogTitle(String provider) =>
      'Refresh ${providerName(provider)} pricing?';

  static String refreshDialogBody(CloudAccessEntry? access) =>
      'Pricing will be fetched using ${accessLabel(access)}.';

  static String runId(String runId) => 'Run ID: $runId';

  static String age(String age) => 'Age: $age';

  static String reviewResults(int count) => 'Review results ($count)';

  static String candidateCount(String state, int count) =>
      '$state · $count candidate(s)';

  static String aiSuggests(String? candidateId, String rationale) =>
      'AI suggests ${candidateId ?? noCandidate}: $rationale';

  static String savedDecision(String decision) => 'Saved decision: $decision';

  static String refreshFailed(String provider) =>
      '${providerName(provider)} pricing refresh failed.';

  static String refreshRequestFailed(String provider, String message) =>
      'Failed to refresh ${providerName(provider)} pricing: $message';

  static String refreshSucceeded(String provider) =>
      '${providerName(provider)} pricing refreshed. Review the evidence below.';

  static String evidenceLoadFailed(String provider, String message) =>
      '${providerName(provider)} pricing was refreshed, but its review evidence could not be loaded: $message';

  static String decisionSaveFailed(String message) =>
      'Pricing decision could not be saved: $message';

  static String traceText(PricingTrace trace) =>
      'Intent: ${trace.intent}\n'
      'Query: ${trace.queryScope}\n'
      'Selected candidate: ${trace.selectedCandidate}\n'
      'Close candidates: ${trace.closeCandidates}\n'
      'Rejected candidates: ${trace.rejectedCandidates}\n'
      'Checks: ${trace.hardChecks}\n'
      'Normalization: ${trace.normalization}\n'
      'Formula: ${trace.formulaRef ?? notAssigned}\n'
      'Secret free: ${trace.sanitization.secretFree}\n'
      'Bounded: ${trace.sanitization.bounded}\n'
      'Omitted raw rows: ${trace.sanitization.omittedRawRows}';

  static String healthLabel(String? state) => switch (state) {
    'fresh' => 'Fresh',
    'stale' => 'Stale',
    'review_required' => 'Review',
    'missing' => 'Missing',
    'failed' => 'Failed',
    _ => 'Unknown',
  };

  static String accessLabel(CloudAccessEntry? access) {
    if (access == null) return 'Access unavailable';
    if (access.providerAccountId != null) {
      return 'Account ${access.providerAccountId}';
    }
    if (access.providerProjectId != null) {
      return 'Project ${access.providerProjectId}';
    }
    if (access.providerSubscriptionId != null) {
      return 'Subscription ${access.providerSubscriptionId}';
    }
    return access.identityLabel;
  }

  static String runAccessLabel(PricingRefreshCredentialSummary access) {
    if (access.providerAccountId != null) {
      return 'Account ${access.providerAccountId}';
    }
    if (access.providerProjectId != null) {
      return 'Project ${access.providerProjectId}';
    }
    if (access.providerSubscriptionId != null) {
      return 'Subscription ${access.providerSubscriptionId}';
    }
    return access.identityLabel;
  }

  static String candidateValue(Object? value, String? currency, String? unit) {
    final parts = [
      if (value != null) value.toString(),
      if (currency != null) currency,
      if (unit != null) unit,
    ];
    return parts.isEmpty ? 'No value' : parts.join(' ');
  }
}
