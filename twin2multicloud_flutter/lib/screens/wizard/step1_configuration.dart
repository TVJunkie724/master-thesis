import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../widgets/credential_section.dart';
import '../../models/wizard_cache.dart';

class Step1Configuration extends ConsumerStatefulWidget {
  final String? twinId;
  final WizardCache cache;
  final bool isSaving;
  final String? nameError; // Error message for duplicate name
  final VoidCallback onNext;
  final VoidCallback onBack;
  final Future<bool> Function() onSaveDraft;
  final VoidCallback onCacheChanged;
  final VoidCallback? onNameErrorClear; // Clear error when user edits name
  
  const Step1Configuration({
    super.key,
    required this.twinId,
    required this.cache,
    required this.isSaving,
    this.nameError,
    required this.onNext,
    required this.onBack,
    required this.onSaveDraft,
    required this.onCacheChanged,
    this.onNameErrorClear,
  });
  
  @override
  ConsumerState<Step1Configuration> createState() => _Step1ConfigurationState();
}

class _Step1ConfigurationState extends ConsumerState<Step1Configuration> {
  final _nameController = TextEditingController();
  String? _error;

  @override
  void initState() {
    super.initState();
    // Initialize form from cache (already populated by WizardScreen)
    _nameController.text = widget.cache.twinName ?? '';
  }
  
  void _updateCache() {
    widget.cache.twinName = _nameController.text;
    widget.cache.markDirty();
    widget.onCacheChanged();
  }
  
  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 800),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Error banner
              if (_error != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      const Icon(Icons.error, color: Colors.red),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_error!, style: const TextStyle(color: Colors.red))),
                      IconButton(
                        icon: const Icon(Icons.close, size: 18),
                        onPressed: () => setState(() => _error = null),
                      ),
                    ],
                  ),
                ),
              
              // Top Navigation Buttons
              _buildNavigationButtons(),
              const SizedBox(height: 24),
              const Divider(),
              const SizedBox(height: 16),
              
              // Twin Name
              Text('Digital Twin Name', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              TextField(
                controller: _nameController,
                decoration: InputDecoration(
                  hintText: 'e.g., Smart Home IoT',
                  border: const OutlineInputBorder(),
                  errorText: widget.nameError,
                  errorBorder: OutlineInputBorder(
                    borderSide: BorderSide(color: Colors.red.shade400, width: 2),
                  ),
                  focusedErrorBorder: OutlineInputBorder(
                    borderSide: BorderSide(color: Colors.red.shade400, width: 2),
                  ),
                ),
                onChanged: (_) {
                  _updateCache();
                  widget.onNameErrorClear?.call(); // Clear error on edit
                  setState(() {});
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
                    selected: !widget.cache.debugMode,
                    onSelected: (selected) {
                      setState(() => widget.cache.debugMode = false);
                      widget.cache.markDirty();
                      widget.onCacheChanged();
                    },
                  ),
                  const SizedBox(width: 8),
                  ChoiceChip(
                    label: const Text('Debug'),
                    selected: widget.cache.debugMode,
                    onSelected: (selected) {
                      setState(() => widget.cache.debugMode = true);
                      widget.cache.markDirty();
                      widget.onCacheChanged();
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
                twinId: widget.twinId,
                icon: Icons.cloud,
                color: Colors.orange,
                isConfigured: widget.cache.awsValid,
                onValidationChanged: (valid) {
                  setState(() => widget.cache.awsValid = valid);
                  if (valid) widget.cache.markAwsNewlyEntered(); // Ensure marked as new
                  widget.cache.markDirty();
                  widget.onCacheChanged();
                },
                onCredentialsChanged: (creds) {
                  widget.cache.awsCredentials = creds;
                  widget.cache.markAwsNewlyEntered(); // Mark as newly entered
                  widget.cache.markDirty();
                  widget.onCacheChanged();
                },
                fields: [
                  CredentialField(
                    name: 'access_key_id', 
                    label: 'Access Key ID', 
                    defaultValue: widget.cache.awsCredentials['access_key_id'],
                  ),
                  CredentialField(
                    name: 'secret_access_key', 
                    label: 'Secret Access Key', 
                    obscure: true,
                    defaultValue: widget.cache.awsCredentials['secret_access_key'],
                  ),
                  CredentialField(
                    name: 'region', 
                    label: 'Region', 
                    defaultValue: widget.cache.awsCredentials['region'] ?? '',
                  ),
                  CredentialField(
                    name: 'session_token', 
                    label: 'Session Token', 
                    obscure: true, 
                    required: false,
                    defaultValue: widget.cache.awsCredentials['session_token'],
                  ),
                ],
              ),
              
              const SizedBox(height: 16),
              
              // Azure Section
              CredentialSection(
                title: 'Azure Credentials',
                provider: 'azure',
                twinId: widget.twinId,
                icon: Icons.cloud_circle,
                color: Colors.blue,
                isConfigured: widget.cache.azureValid,
                onValidationChanged: (valid) {
                  setState(() => widget.cache.azureValid = valid);
                  if (valid) widget.cache.markAzureNewlyEntered(); // Ensure marked as new
                  widget.cache.markDirty();
                  widget.onCacheChanged();
                },
                onCredentialsChanged: (creds) {
                  widget.cache.azureCredentials = creds;
                  widget.cache.markAzureNewlyEntered(); // Mark as newly entered
                  widget.cache.markDirty();
                  widget.onCacheChanged();
                },
                fields: [
                  CredentialField(
                    name: 'subscription_id', 
                    label: 'Subscription ID',
                    defaultValue: widget.cache.azureCredentials['subscription_id'],
                  ),
                  CredentialField(
                    name: 'client_id', 
                    label: 'Client ID',
                    defaultValue: widget.cache.azureCredentials['client_id'],
                  ),
                  CredentialField(
                    name: 'client_secret', 
                    label: 'Client Secret', 
                    obscure: true,
                    defaultValue: widget.cache.azureCredentials['client_secret'],
                  ),
                  CredentialField(
                    name: 'tenant_id', 
                    label: 'Tenant ID',
                    defaultValue: widget.cache.azureCredentials['tenant_id'],
                  ),
                  CredentialField(
                    name: 'region', 
                    label: 'Region', 
                    defaultValue: widget.cache.azureCredentials['region'] ?? '',
                  ),
                ],
              ),
              
              const SizedBox(height: 16),
              
              // GCP Section
              CredentialSection(
                title: 'GCP Credentials',
                provider: 'gcp',
                twinId: widget.twinId,
                icon: Icons.cloud_queue,
                color: Colors.green,
                isConfigured: widget.cache.gcpValid,
                onValidationChanged: (valid) {
                  setState(() => widget.cache.gcpValid = valid);
                  if (valid) widget.cache.markGcpNewlyEntered(); // Ensure marked as new
                  widget.cache.markDirty();
                  widget.onCacheChanged();
                },
                onCredentialsChanged: (creds) {
                  widget.cache.gcpCredentials = creds;
                  widget.cache.markGcpNewlyEntered(); // Mark as newly entered
                  widget.cache.markDirty();
                  widget.onCacheChanged();
                },
                onJsonUploaded: (json) {
                  widget.cache.gcpServiceAccountJson = json;
                  widget.cache.markGcpNewlyEntered(); // Mark as newly entered
                  widget.cache.markDirty();
                  widget.onCacheChanged();
                },
                fields: [
                  CredentialField(
                    name: 'project_id', 
                    label: 'Project ID', 
                    required: false,
                    defaultValue: widget.cache.gcpCredentials['project_id'],
                  ),
                  CredentialField(
                    name: 'billing_account', 
                    label: 'Billing Account', 
                    required: false,
                    defaultValue: widget.cache.gcpCredentials['billing_account'],
                  ),
                  CredentialField(
                    name: 'region', 
                    label: 'Region', 
                    defaultValue: widget.cache.gcpCredentials['region'] ?? '',
                  ),
                ],
                supportsJsonUpload: true,
              ),
              
              const SizedBox(height: 32),
              const Divider(),
              const SizedBox(height: 16),
              
              // Action buttons
              _buildNavigationButtons(),
              
              if (!widget.cache.canProceedToStep2) ...[
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
  }

  Widget _buildNavigationButtons() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        OutlinedButton.icon(
          onPressed: widget.onBack,
          icon: const Icon(Icons.arrow_back),
          label: const Text('Back'),
        ),
        Row(
          children: [
            // Save Draft button with unsaved changes indicator
            OutlinedButton.icon(
              onPressed: widget.isSaving ? null : () async {
                await widget.onSaveDraft();
              },
              icon: Stack(
                clipBehavior: Clip.none,
                children: [
                  widget.isSaving 
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.save),
                  if (widget.cache.hasUnsavedChanges && !widget.isSaving)
                    Positioned(
                      right: -4,
                      top: -4,
                      child: Container(
                        width: 10,
                        height: 10,
                        decoration: const BoxDecoration(
                          color: Colors.orange,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                ],
              ),
              label: const Text('Save Draft'),
            ),
            const SizedBox(width: 16),
            FilledButton(
              onPressed: widget.cache.canProceedToStep2 ? widget.onNext : null,
              child: const Text('Next Step →'),
            ),
          ],
        ),
      ],
    );
  }
}
