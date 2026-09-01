abstract final class TwinOverviewStrings {
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
  static const editBlocked = 'Destroy cloud resources before editing';
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
      'Review cleanup evidence before starting another approved run.';
  static const deployNext = 'Deploy this bounded experiment.';
  static const preflightNext =
      'Run provider preflight and resolve any preparation findings.';
  static const configureNext =
      'Complete the experiment configuration before deployment.';
}
