import '../../models/deployment_operations.dart';

abstract final class TwinOverviewStrings {
  static String operationFailure(DeploymentOperationType? type) =>
      switch (type) {
        DeploymentOperationType.destroy => 'Cleanup incomplete',
        DeploymentOperationType.deploy => 'Deployment failed',
        _ => 'Operation failed',
      };
  static const cleanupErrorNext =
      'Review cleanup evidence and logs; retry Cleanup when safe.';
  static const cleanupErrorDetail =
      'Cleanup is not confirmed complete. Inspect the reported residuals before retrying. Earlier verification results remain separate.';
  static const operationErrorDetail =
      'Orphaned cloud resources may exist. Inspect cleanup evidence before a new experiment.';
  static const recordedVerification = 'Recorded verification';
  static const recordedVerificationScope =
      'Historical telemetry results, not a live resource check or proof of completed cleanup. No new test is started.';
  static const appTitle = 'Twin2MultiCloud';
  static const backToExperiments = 'Back to Twin experiments';
  static const toggleTheme = 'Toggle theme';
  static const openCloudAccess = 'Open cloud access';
  static const dismissMessage = 'Dismiss message';
  static const cloudResource = 'Cloud resource';
  static const notConfigured = 'Not configured';
  static const nextStep = 'Next';
  static const moreActions = 'More actions';
  static const editConfiguration = 'Edit configuration';
  static const deleteTwin = 'Delete Twin';
  static const editBlocked =
      'Busy or immutable Twin. Use Duplicate in Twin experiments for a new definition.';
  static const deleteBlocked = 'Destroy cloud resources before deleting';
  static const prepareAndDeploy = 'Prepare and deploy';
  static const prepareNextRun = 'Prepare the next run';
  static const verifyAndAccess = 'Verify and access';
  static const destroyAndCleanup = 'Destroy and cleanup';
  static const configurationEvidence = 'Configuration evidence';
  static const preparingDescription =
      'Resolve provider readiness, then deploy the bounded experiment.';
  static const nextRunDescription =
      'Start another run only after cleanup evidence is complete.';
  static const verificationDescription =
      'Verify layer access, telemetry, commands and persisted evidence.';
  static const cleanupDescription =
      'Destroy resources and confirm residual inventory immediately.';
  static const evidenceDescription =
      'Inspect the immutable graph, cost and configuration artifacts.';

  static const deployingNext =
      'Follow the persisted deployment progress before verification.';
  static const destroyingNext =
      'Wait for Destroy to finish, then inspect cleanup evidence.';
  static const errorNext =
      'Run Cleanup and inspect logs before attempting another deployment.';
  static const deployedNext =
      'Verify L1-L3 and Event, then L4/L5, telemetry and commands; Destroy afterward.';
  static const destroyedNext =
      'Review cleanup evidence. For a previously deployed Twin, use Duplicate in Twin experiments for a new run.';
  static const immutableNext =
      'This definition has already been deployed. Use Duplicate in Twin experiments for a new run.';
  static const reconfigureNext =
      'Review cleanup evidence, then reopen configuration and preflight before a first successful deployment.';
  static const deployNext = 'Deploy this bounded experiment.';
  static const preflightNext =
      'Run provider preflight and resolve any preparation findings.';
  static const configureNext =
      'Complete the experiment configuration before deployment.';
  static const infrastructureScope =
      'Read-only inspection of deployed resources. This does not prove telemetry, command delivery or L4/L5 data; duration and provider API charges vary.';
  static const telemetryScope =
      'Send one telemetry sample and inspect the returned verification checkpoints. This is not automatically a full command/L4/L5 test; provider requests may incur charges.';
  static const simulatorScope =
      'Use the downloaded simulator for device telemetry and command receipt. L4 projection requires projection_candidate: true in the sample. Verify exact L3/L4 values and L5 timestamps separately.';
  static const cleanupScope =
      'Recorded cleanup covers the reported Terraform/provider checks, not a global account inventory. Inactive deletion markers and supplementary research checks are not classified by this read model.';
  static const snapshotScope =
      'Open fetches one authenticated Raw/Hourly snapshot through Management. It does not require a Grafana login, poll continuously, or mark data as verified. Allow a new browser window if blocked.';
  static const grafanaSignInHint =
      'Select Open and sign in with the user shown above. Complete any first-time password setup and provider-required MFA. As the account administrator, follow Cloud access > Setup guide for AWS or Azure if the login is not yet set up.';
  static const deployCostWarning =
      'This creates billable cloud resources. The monthly model estimate is not this run’s bill or a spending cap. Verify promptly, then Destroy and inspect cleanup evidence.';
}
