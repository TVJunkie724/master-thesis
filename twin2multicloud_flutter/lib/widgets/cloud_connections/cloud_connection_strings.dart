abstract class CloudConnectionStrings {
  static const cloudAccessTitle = 'Cloud access';
  static const providerConnectionsTitle = 'Provider connections';
  static const providerConnectionsHelp =
      'Import one administrator connection for each provider used by the thesis PoC. Stored connections are reused only for readiness, deployment, and cleanup.';
  static const title = 'Cloud Connections';
  static const newConnection = 'Import existing (advanced)';
  static const selectConnection = 'Select connection';
  static const validate = 'Check';
  static const unbind = 'Unbind';
  static const delete = 'Delete';
  static const cancel = 'Cancel';
  static const create = 'Create';
  static const setupGuide = 'Setup guide';
  static const enterManually = 'Enter manually';
  static const importCsv = 'Import CSV';
  static const importJson = 'Import JSON';
  static const refreshProviders = 'Refresh provider connections';
  static const targetScope = 'Target scope';
  static const azurePocAdministrator = 'Azure PoC administrator';
  static const azurePocAdministratorHelp =
      'Creates and destroys resources, role assignments, and required Entra objects in the isolated thesis subscription.';
  static const azureDefaultDisplayName = 'Azure administrator';
  static const azureFormatHelpTitle = 'Accepted Azure JSON formats';
  static const azureFormatHelpIntro =
      'Use either a standard Azure service-principal JSON or the Azure member of the Twin2MultiCloud compatibility file.';
  static const azureStandardFormatTitle = 'Standard Azure JSON';
  static const azureStandardFormatHelp =
      'Use the administrator app ID and secret. Existing clientId/clientSecret, tenantId, subscription, displayName, and name aliases are also accepted.';
  static const azureBundleFormatTitle = 'Twin2MultiCloud Azure bundle';
  static const azureBundleFormatHelp =
      'The Azure member prefills the administrator and known regions. Legacy preparation fields, plus allowed AWS and GCP members, are ignored locally and never uploaded.';
  static const azureStandardJsonExample = '''{
  "appId": "<administrator-client-id>",
  "password": "<administrator-client-secret>",
  "tenant": "<tenant-id>",
  "subscriptionId": "<subscription-id>"
}''';
  static const azureBundleJsonExample = '''{
  "azure": {
    "azure_subscription_id": "<subscription-id>",
    "azure_tenant_id": "<tenant-id>",
    "azure_client_id": "<administrator-client-id>",
    "azure_client_secret": "<administrator-client-secret>",
    "azure_region": "westeurope"
  }
}''';
  static const azureServicePrincipalDetected =
      'Azure service-principal JSON detected';
  static const azureBundleDetected = 'Twin2MultiCloud Azure JSON detected';
  static const azureInvalidFileSize =
      'Azure credential JSON must be between 1 byte and 128 KiB.';
  static const azureInvalidEncoding =
      'Azure credential JSON must be valid UTF-8 text.';
  static const azureInvalidJson =
      'Azure credential JSON must contain one valid JSON object.';
  static const azureUnsupportedShape =
      'Azure credential JSON does not match a supported format.';
  static const azureMissingAdministratorFields =
      'Azure service-principal JSON is missing required administrator fields.';
  static const azureIncompleteBundle =
      'The Azure JSON must contain the subscription, tenant, administrator client ID, and administrator secret.';
  static const azureCredentialFileHelp =
      'The selected file is parsed locally. Only normalized Azure administrator credentials are sent for server-side validation; credential values are never previewed.';
  static const azureAdministratorSummary = 'Single PoC administrator';
  static const noConnectionSelected = 'No connection selected';
  static const notValidated = 'Not validated';
  static const deleteConflict =
      'This Cloud Connection is still bound to one or more twins.';
}
