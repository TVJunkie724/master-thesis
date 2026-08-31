abstract class CloudConnectionStrings {
  static const title = 'Cloud Connections';
  static const newConnection = 'Import existing (advanced)';
  static const selectConnection = 'Select connection';
  static const validate = 'Check';
  static const unbind = 'Unbind';
  static const delete = 'Delete';
  static const cancel = 'Cancel';
  static const create = 'Create';
  static const setupGuide = 'Setup guide';
  static const targetScope = 'Target scope';
  static const deploymentPrincipal = 'Deployment principal';
  static const preparationPrincipal = 'Preparation principal';
  static const deploymentPrincipalHelp =
      'Creates and destroys Azure resources.';
  static const preparationPrincipalHelp =
      'Creates only approved role assignments and graph-required Entra objects.';
  static const preparationClientId = 'Preparation client ID';
  static const preparationClientSecret = 'Preparation client secret';
  static const azureBundleSummary =
      'Separate deployment and preparation principals';
  static const noConnectionSelected = 'No connection selected';
  static const notValidated = 'Not validated';
  static const deleteConflict =
      'This Cloud Connection is still bound to one or more twins.';
}
