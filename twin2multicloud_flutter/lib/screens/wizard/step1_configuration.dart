import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../bloc/wizard/wizard.dart';
import '../../widgets/credential_section.dart';

/// Step 1: Configuration - BLoC version
/// Handles twin naming, debug mode, and credential configuration
class Step1Configuration extends StatefulWidget {
  const Step1Configuration({super.key});

  @override
  State<Step1Configuration> createState() => _Step1ConfigurationState();
}

class _Step1ConfigurationState extends State<Step1Configuration> {
  final _nameController = TextEditingController();
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    // Safe to use context here - widget is mounted
    if (!_initialized) {
      final state = context.read<WizardBloc>().state;
      _nameController.text = state.twinName ?? '';
      _initialized = true;
    }
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<WizardBloc, WizardState>(
      listenWhen: (prev, curr) => prev.twinName != curr.twinName,
      listener: (context, state) {
        // Sync controller when BLoC state changes externally (e.g., loading twin)
        if (_nameController.text != (state.twinName ?? '')) {
          _nameController.text = state.twinName ?? '';
        }
      },
      child: BlocBuilder<WizardBloc, WizardState>(
        builder: (context, state) {
          final bloc = context.read<WizardBloc>();
        
        return SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 800),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Twin Name
                  Text('Digital Twin Name', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _nameController,
                    decoration: const InputDecoration(
                      hintText: 'e.g., Smart Home IoT',
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (value) {
                      bloc.add(WizardTwinNameChanged(value));
                    },
                  ),
                  
                  const SizedBox(height: 24),
                  
                  // Mode toggle
                  Row(
                    children: [
                      Text('Mode:', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(width: 16),
                      ChoiceChip(
                        label: const Text('Production'),
                        selected: !state.debugMode,
                        onSelected: (selected) {
                          bloc.add(const WizardDebugModeChanged(false));
                        },
                      ),
                      const SizedBox(width: 8),
                      ChoiceChip(
                        label: const Text('Debug'),
                        selected: state.debugMode,
                        onSelected: (selected) {
                          bloc.add(const WizardDebugModeChanged(true));
                        },
                      ),
                    ],
                  ),
                  
                  const SizedBox(height: 32),
                  const Divider(),
                  const SizedBox(height: 16),
                  
                  // AWS Section
                  CredentialSection(
                    title: 'AWS Credentials',
                    provider: 'aws',
                    twinId: state.twinId,
                    icon: Icons.cloud,
                    color: Colors.orange,
                    isConfigured: state.aws.isValid,
                    onValidationChanged: (valid) {
                      bloc.add(WizardCredentialsValidated('aws', valid));
                    },
                    onCredentialsChanged: (creds) {
                      bloc.add(WizardCredentialsChanged('aws', creds));
                    },
                    fields: [
                      CredentialField(
                        name: 'access_key_id', 
                        label: 'Access Key ID', 
                        defaultValue: state.aws.values['access_key_id'],
                      ),
                      CredentialField(
                        name: 'secret_access_key', 
                        label: 'Secret Access Key', 
                        obscure: true,
                        defaultValue: state.aws.values['secret_access_key'],
                      ),
                      CredentialField(
                        name: 'region', 
                        label: 'Region', 
                        defaultValue: state.aws.values['region'] ?? '',
                      ),
                      CredentialField(
                        name: 'sso_region', 
                        label: 'SSO Region (if different)', 
                        required: false,
                        defaultValue: state.aws.values['sso_region'] ?? '',
                      ),
                      CredentialField(
                        name: 'session_token', 
                        label: 'Session Token', 
                        obscure: true, 
                        required: false,
                        defaultValue: state.aws.values['session_token'],
                      ),
                    ],
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // Azure Section
                  CredentialSection(
                    title: 'Azure Credentials',
                    provider: 'azure',
                    twinId: state.twinId,
                    icon: Icons.cloud_circle,
                    color: Colors.blue,
                    isConfigured: state.azure.isValid,
                    onValidationChanged: (valid) {
                      bloc.add(WizardCredentialsValidated('azure', valid));
                    },
                    onCredentialsChanged: (creds) {
                      bloc.add(WizardCredentialsChanged('azure', creds));
                    },
                    fields: [
                      CredentialField(
                        name: 'subscription_id', 
                        label: 'Subscription ID',
                        defaultValue: state.azure.values['subscription_id'],
                      ),
                      CredentialField(
                        name: 'client_id', 
                        label: 'Client ID',
                        defaultValue: state.azure.values['client_id'],
                      ),
                      CredentialField(
                        name: 'client_secret', 
                        label: 'Client Secret', 
                        obscure: true,
                        defaultValue: state.azure.values['client_secret'],
                      ),
                      CredentialField(
                        name: 'tenant_id', 
                        label: 'Tenant ID',
                        defaultValue: state.azure.values['tenant_id'],
                      ),
                      CredentialField(
                        name: 'region', 
                        label: 'Region', 
                        defaultValue: state.azure.values['region'] ?? '',
                      ),
                    ],
                  ),
                  
                  const SizedBox(height: 16),
                  
                  // GCP Section
                  CredentialSection(
                    title: 'GCP Credentials',
                    provider: 'gcp',
                    twinId: state.twinId,
                    icon: Icons.cloud_queue,
                    color: Colors.green,
                    isConfigured: state.gcp.isValid,
                    onValidationChanged: (valid) {
                      bloc.add(WizardCredentialsValidated('gcp', valid));
                    },
                    onCredentialsChanged: (creds) {
                      bloc.add(WizardCredentialsChanged('gcp', creds));
                    },
                    onJsonUploaded: (json) {
                      // TODO: Add gcpServiceAccountJson to BLoC state
                      bloc.add(WizardCredentialsChanged('gcp', {'service_account_json': json}));
                    },
                    fields: [
                      CredentialField(
                        name: 'project_id', 
                        label: 'Project ID', 
                        required: false,
                        defaultValue: state.gcp.values['project_id'],
                      ),
                      CredentialField(
                        name: 'billing_account', 
                        label: 'Billing Account', 
                        required: false,
                        defaultValue: state.gcp.values['billing_account'],
                      ),
                      CredentialField(
                        name: 'region', 
                        label: 'Region', 
                        defaultValue: state.gcp.values['region'] ?? '',
                      ),
                    ],
                    supportsJsonUpload: true,
                  ),
                  
                  const SizedBox(height: 32),
                  const Divider(),
                  const SizedBox(height: 16),
                  
                  if (!state.canProceedToStep2) ...[
                    const SizedBox(height: 8),
                    Text(
                      'To proceed: Give your twin a name and validate at least one provider\'s credentials.',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Theme.of(context).colorScheme.outline,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        );
        },
      ),
    );
  }
}
