import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../widgets/credential_section.dart';
import '../../providers/twins_provider.dart';

class Step1Configuration extends ConsumerStatefulWidget {
  final String? twinId;
  final bool isCreatingTwin;
  final Future<String> Function(String name) onCreateTwin;
  final VoidCallback onNext;
  final VoidCallback onSaveDraft;
  
  const Step1Configuration({
    super.key,
    required this.twinId,
    required this.isCreatingTwin,
    required this.onCreateTwin,
    required this.onNext,
    required this.onSaveDraft,
  });
  
  @override
  ConsumerState<Step1Configuration> createState() => _Step1ConfigurationState();
}

class _Step1ConfigurationState extends ConsumerState<Step1Configuration> {
  final _nameController = TextEditingController();
  bool _debugMode = false;
  bool _isSaving = false;
  String? _error;
  
  bool _awsValid = false;
  bool _azureValid = false;
  bool _gcpValid = false;
  
  Map<String, String> _awsCredentials = {};
  Map<String, String> _azureCredentials = {};
  Map<String, String> _gcpCredentials = {};
  String? _gcpServiceAccountJson;
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    if (widget.twinId != null) {
      _isLoading = true;
      _loadTwinData();
    }
  }

  Future<void> _loadTwinData() async {
    // setState(() => _isLoading = true); // Already set in initState
    try {
      final api = ref.read(apiServiceProvider);
      
      // Fetch twin details (name) and config (credentials)
      final results = await Future.wait([
        api.getTwin(widget.twinId!),
        api.getTwinConfig(widget.twinId!),
      ]);
      
      final twinData = results[0];
      final configData = results[1];
      
      debugPrint('LOADED TWIN DATA: $twinData');
      debugPrint('LOADED CONFIG DATA: $configData');
      
      _nameController.text = twinData['name'] ?? '';
      _debugMode = configData['debug_mode'] ?? false;
      
      // Parse AWS credentials
      if (configData['aws_configured'] == true) {
        _awsCredentials = {
          'region': configData['aws_region']?.toString() ?? 'eu-central-1',
          'access_key_id': '', // Secrets hidden by backend
          'secret_access_key': '',
          'session_token': '',
        };
        _awsValid = true; // Mark as valid to allow proceeding
        debugPrint('PARSED AWS (Configured): $_awsCredentials');
      } else {
        // Fallback or explicit region if present but not configured
         if (configData['aws_region'] != null) {
            _awsCredentials['region'] = configData['aws_region'].toString();
         }
      }
      
      // Parse Azure credentials
      if (configData['azure_configured'] == true) {
        _azureCredentials = {
          'region': configData['azure_region']?.toString() ?? 'westeurope',
          'subscription_id': '', // Secrets hidden
          'client_id': '',
          'client_secret': '',
          'tenant_id': '',
        };
        _azureValid = true;
      } else {
         if (configData['azure_region'] != null) {
            _azureCredentials['region'] = configData['azure_region'].toString();
         }
      }
      
      // Parse GCP credentials
      if (configData['gcp_configured'] == true) {
        _gcpCredentials = {
          'project_id': configData['gcp_project_id']?.toString() ?? '',
          'region': configData['gcp_region']?.toString() ?? 'europe-west1',
          'billing_account': '', // Hidden
        };
        if (_gcpCredentials['project_id']?.isNotEmpty == true) {
           _gcpValid = true;
        }
      } else {
         if (configData['gcp_region'] != null) {
            _gcpCredentials['region'] = configData['gcp_region'].toString();
         }
         if (configData['gcp_project_id'] != null) {
            _gcpCredentials['project_id'] = configData['gcp_project_id'].toString();
         }
      }
      
    } catch (e) {
      setState(() => _error = 'Failed to load twin data: $e');
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }
  
  bool get _canProceed {
    return _nameController.text.isNotEmpty && 
           (_awsValid || _azureValid || _gcpValid);
  }
  
  Future<void> _saveConfig() async {
    if (_nameController.text.isEmpty) {
      return;
    }
    
    // Strict Validation for Draft Save:
    // If a provider has credentials (is configured or typed), it MUST be valid.
    final hasAws = _awsCredentials.values.any((v) => v.isNotEmpty) || 
                   (_awsCredentials['region'] != null && _awsCredentials.length > 1); // >1 means more than just default region
    // Robust check for AWS: configured (valid=true) OR has typed data
    // Simply checking _awsValid is enough because:
    // 1. If configured (hidden), _awsValid is true.
    // 2. If typed & validated, _awsValid is true.
    // 3. If typed & invalid/not-validated, _awsValid is false.
    // 4. If empty, we don't care.
    
    // We need to know if data is entered but NOT valid.
    // Helper to check if provider has data but is invalid
    bool isInvalid(Map<String, String> creds, bool isValidFlag) {
       // Filter out default region if that's the only thing
       final nonRegionKeys = creds.keys.where((k) => k != 'region');
       final hasData = nonRegionKeys.any((k) => creds[k]?.isNotEmpty == true);
       
       if (hasData && !isValidFlag) {
         return true;
       }
       return false;
    }

    if (isInvalid(_awsCredentials, _awsValid)) {
      setState(() => _error = 'Please validate your AWS credentials before saving.');
      return;
    }
    if (isInvalid(_azureCredentials, _azureValid)) {
      setState(() => _error = 'Please validate your Azure credentials before saving.');
      return;
    }
    // GCP is special (service account json)
    bool gcpHasData = _gcpCredentials['project_id']?.isNotEmpty == true || 
                      _gcpCredentials['billing_account']?.isNotEmpty == true ||
                      _gcpServiceAccountJson != null;
    if (gcpHasData && !_gcpValid) {
       setState(() => _error = 'Please validate your GCP credentials before saving.');
       return;
    }

    setState(() {
      _isSaving = true;
      _error = null;
    });
    
    try {
      final twinId = await widget.onCreateTwin(_nameController.text);
      final api = ref.read(apiServiceProvider);
      final configData = <String, dynamic>{'debug_mode': _debugMode};
      
      if (_awsCredentials.isNotEmpty && 
          _awsCredentials['access_key_id']?.isNotEmpty == true) {
        final awsConfig = {
          'access_key_id': _awsCredentials['access_key_id'],
          'secret_access_key': _awsCredentials['secret_access_key'],
          'region': _awsCredentials['region'] ?? 'eu-central-1',
        };
        if (_awsCredentials['session_token']?.isNotEmpty == true) {
          awsConfig['session_token'] = _awsCredentials['session_token']!;
        }
        configData['aws'] = awsConfig;
      }
      
      if (_azureCredentials.isNotEmpty &&
          _azureCredentials['subscription_id']?.isNotEmpty == true) {
        configData['azure'] = {
          'subscription_id': _azureCredentials['subscription_id'],
          'client_id': _azureCredentials['client_id'],
          'client_secret': _azureCredentials['client_secret'],
          'tenant_id': _azureCredentials['tenant_id'],
          'region': _azureCredentials['region'] ?? 'westeurope',
        };
      }
      
      if (_gcpCredentials['project_id']?.isNotEmpty == true || 
          _gcpCredentials['billing_account']?.isNotEmpty == true ||
          _gcpServiceAccountJson != null) {
        configData['gcp'] = {
          'project_id': _gcpCredentials['project_id'],
          'billing_account': _gcpCredentials['billing_account'],
          'region': _gcpCredentials['region'] ?? 'europe-west1',
          'service_account_json': _gcpServiceAccountJson,
        };
      }
      
      await api.updateTwinConfig(twinId, configData);
      widget.onSaveDraft();
      
    } catch (e) {
      setState(() => _error = 'Failed to save: $e');
    } finally {
      setState(() => _isSaving = false);
    }
  }
  
  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }
  
  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }
    
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
              
              // Twin Name
              Text('Digital Twin Name', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              TextField(
                controller: _nameController,
                decoration: const InputDecoration(
                  hintText: 'e.g., Smart Home IoT',
                  border: OutlineInputBorder(),
                ),
                onChanged: (_) => setState(() {}),
              ),
              
              const SizedBox(height: 24),
              
              // Mode toggle
              Row(
                children: [
                  Text('Mode:', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(width: 16),
                  ChoiceChip(
                    label: const Text('Production'),
                    selected: !_debugMode,
                    onSelected: (selected) => setState(() => _debugMode = false),
                  ),
                  const SizedBox(width: 8),
                  ChoiceChip(
                    label: const Text('Debug'),
                    selected: _debugMode,
                    onSelected: (selected) => setState(() => _debugMode = true),
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
                isConfigured: _awsValid, // Pass configured status
                onValidationChanged: (valid) => setState(() => _awsValid = valid),
                onCredentialsChanged: (creds) => _awsCredentials = creds,
                fields: [
                  CredentialField(
                    name: 'access_key_id', 
                    label: 'Access Key ID', 
                    defaultValue: _awsCredentials['access_key_id'],
                  ),
                  CredentialField(
                    name: 'secret_access_key', 
                    label: 'Secret Access Key', 
                    obscure: true,
                    defaultValue: _awsCredentials['secret_access_key'],
                  ),
                  CredentialField(
                    name: 'region', 
                    label: 'Region', 
                    defaultValue: _awsCredentials['region'] ?? 'eu-central-1',
                  ),
                  CredentialField(
                    name: 'session_token', 
                    label: 'Session Token', 
                    obscure: true, 
                    required: false,
                    defaultValue: _awsCredentials['session_token'],
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
                isConfigured: _azureValid,
                onValidationChanged: (valid) => setState(() => _azureValid = valid),
                onCredentialsChanged: (creds) => _azureCredentials = creds,
                fields: [
                  CredentialField(
                    name: 'subscription_id', 
                    label: 'Subscription ID',
                    defaultValue: _azureCredentials['subscription_id'],
                  ),
                  CredentialField(
                    name: 'client_id', 
                    label: 'Client ID',
                    defaultValue: _azureCredentials['client_id'],
                  ),
                  CredentialField(
                    name: 'client_secret', 
                    label: 'Client Secret', 
                    obscure: true,
                    defaultValue: _azureCredentials['client_secret'],
                  ),
                  CredentialField(
                    name: 'tenant_id', 
                    label: 'Tenant ID',
                    defaultValue: _azureCredentials['tenant_id'],
                  ),
                  CredentialField(
                    name: 'region', 
                    label: 'Region', 
                    defaultValue: _azureCredentials['region'] ?? 'westeurope',
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
                color: Colors.red,
                isConfigured: _gcpValid,
                onValidationChanged: (valid) => setState(() => _gcpValid = valid),
                onCredentialsChanged: (creds) => _gcpCredentials = creds,
                onJsonUploaded: (json) => _gcpServiceAccountJson = json,
                fields: [
                  CredentialField(
                    name: 'project_id', 
                    label: 'Project ID', 
                    required: false,
                    defaultValue: _gcpCredentials['project_id'],
                  ),
                  CredentialField(
                    name: 'billing_account', 
                    label: 'Billing Account', 
                    required: false,
                    defaultValue: _gcpCredentials['billing_account'],
                  ),
                  CredentialField(
                    name: 'region', 
                    label: 'Region', 
                    defaultValue: _gcpCredentials['region'] ?? 'europe-west1',
                  ),
                ],
                supportsJsonUpload: true,
              ),
              
              const SizedBox(height: 32),
              const Divider(),
              const SizedBox(height: 16),
              
              // Action buttons
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  OutlinedButton(
                    onPressed: (_isSaving || widget.isCreatingTwin) ? null : _saveConfig,
                    child: _isSaving 
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('Save Draft'),
                  ),
                  const SizedBox(width: 16),
                  FilledButton(
                    onPressed: _canProceed ? () async {
                      await _saveConfig();
                      widget.onNext();
                    } : null,
                    child: const Text('Next Step →'),
                  ),
                ],
              ),
              
              if (!_canProceed) ...[
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
}
