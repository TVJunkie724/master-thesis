import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';
import '../providers/twins_provider.dart';
import '../utils/file_reader.dart';

class CredentialField {
  final String name;
  final String label;
  final bool obscure;
  final String? defaultValue;
  final bool required;  // NEW
  
  const CredentialField({
    required this.name,
    required this.label,
    this.obscure = false,
    this.defaultValue,
    this.required = true,  // Default: required
  });
}

class CredentialSection extends ConsumerStatefulWidget {
  final String title;
  final String provider;
  final String? twinId;
  final IconData icon;
  final Color color;
  final List<CredentialField> fields;
  final bool supportsJsonUpload;
  final bool supportsCredentialsUpload;
  final bool isConfigured; // NEW: Indicates backend has hidden credentials
  final Function(bool) onValidationChanged;
  final Function(Map<String, String>) onCredentialsChanged;
  final Function(String)? onJsonUploaded;
  
  const CredentialSection({
    super.key,
    required this.title,
    required this.provider,
    required this.twinId,
    required this.icon,
    required this.color,
    required this.fields,
    required this.onValidationChanged,
    required this.onCredentialsChanged,
    this.onJsonUploaded,
    this.supportsJsonUpload = false,
    this.supportsCredentialsUpload = true,
    this.isConfigured = false,
  });
  
  @override
  ConsumerState<CredentialSection> createState() => _CredentialSectionState();
}

class _CredentialSectionState extends ConsumerState<CredentialSection> {
  bool _isValidating = false;
  
  // Dual validation state
  bool _optimizerValid = false;
  bool _deployerValid = false;
  String? _optimizerMessage;
  String? _deployerMessage;
  
  // Overall valid only if BOTH pass
  bool get _isValid => (_optimizerValid && _deployerValid) || (widget.isConfigured && _optimizerMessage == null && _deployerMessage == null);
  
  final Map<String, TextEditingController> _controllers = {};
  
  @override
  void initState() {
    super.initState();
    for (final field in widget.fields) {
      _controllers[field.name] = TextEditingController(text: field.defaultValue);
    }
  }
  
  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.dispose();
    }
    super.dispose();
  }
  
  /// Check if all required fields have values
  bool _areRequiredFieldsFilled() {
    for (final field in widget.fields) {
      if (field.required) {
        final controller = _controllers[field.name];
        if (controller == null || controller.text.trim().isEmpty) {
          return false;
        }
      }
    }
    return true;
  }
  
  /// Validate credentials against BOTH Optimizer and Deployer APIs
  Future<void> _validateCredentials() async {
    setState(() {
      _isValidating = true;
      _optimizerMessage = null;
      _deployerMessage = null;
    });
    
    try {
      final api = ref.read(apiServiceProvider);
      
      // Build credentials from form fields
      final credentials = <String, dynamic>{};
      for (final entry in _controllers.entries) {
        if (entry.value.text.isNotEmpty) {
          credentials[entry.key] = entry.value.text;
        }
      }
      
      // Use DUAL validation (calls both Optimizer and Deployer)
      Map<String, dynamic> result;
      
      // Determine validation mode: Stored vs New
      if (widget.twinId != null && widget.isConfigured && !_areRequiredFieldsFilled()) {
        // Mode 1: Validate Stored Credentials
        debugPrint('Validating STORED credentials for ${widget.provider}');
        result = await api.validateStoredCredentialsDual(widget.twinId!, widget.provider);
        debugPrint('Stored validation result: $result');
      } else {
        // Mode 2: Validate New/Existing (Typed) Credentials
        debugPrint('Validating TYPED credentials for ${widget.provider}');
        result = await api.validateCredentialsDual(widget.provider, credentials);
      }
      
      final optimizer = result['optimizer'] as Map<String, dynamic>? ?? {};
      final deployer = result['deployer'] as Map<String, dynamic>? ?? {};
      
      // Helper to detect success from message
      bool isSuccessMessage(String? msg) {
        if (msg == null) return false;
        final lower = msg.toLowerCase();
        return lower.contains('all required permissions') ||
               lower.contains('permissions are present') ||
               lower.contains('valid') ||
               lower.contains('success') ||
               msg.startsWith('✓');
      }
      
      // Parse valid flag OR detect from message
      final optimizerMsg = optimizer['message']?.toString() ?? 'Validation complete';
      final deployerMsg = deployer['message']?.toString() ?? 'Validation complete';
      
      setState(() {
        _optimizerValid = (optimizer['valid'] == true) || isSuccessMessage(optimizerMsg);
        _optimizerMessage = optimizerMsg;
        _deployerValid = (deployer['valid'] == true) || isSuccessMessage(deployerMsg);
        _deployerMessage = deployerMsg;
      });
      
      widget.onValidationChanged(_isValid);
      
    } on DioException catch (e) {
      String errorMsg;
      if (e.type == DioExceptionType.connectionError || 
          e.type == DioExceptionType.connectionTimeout) {
        errorMsg = '❌ Cannot connect to server. Please ensure the Management API is running (docker compose up -d management-api).';
      } else if (e.type == DioExceptionType.receiveTimeout) {
        errorMsg = '❌ Server timeout. Please try again.';
      } else {
        errorMsg = '❌ Connection error: ${e.message}';
      }
      setState(() {
        _optimizerValid = false;
        _deployerValid = false;
        _optimizerMessage = errorMsg;
        _deployerMessage = errorMsg;
      });
      widget.onValidationChanged(false);
    } catch (e) {
      setState(() {
        _optimizerValid = false;
        _deployerValid = false;
        _optimizerMessage = '❌ Validation failed: $e';
        _deployerMessage = '❌ Validation failed: $e';
      });
      widget.onValidationChanged(false);
    } finally {
      setState(() => _isValidating = false);
    }
  }
  
  Future<void> _pickJsonFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['json'],
      );
      
      if (result == null || result.files.isEmpty) return;
      
      final file = result.files.single;
      final jsonString = await readPickedFile(file);
      final jsonData = jsonDecode(jsonString);
      
      if (jsonData['project_id'] != null) {
        _controllers['project_id']?.text = jsonData['project_id'];
      }
      
      widget.onJsonUploaded?.call(jsonString);
      
      _notifyCredentialsChanged();
      
      // Auto-trigger validation after GCP JSON upload
      await _validateCredentials();
    } catch (e) {
      setState(() {
        _optimizerMessage = 'Failed to load JSON: $e';
        _deployerMessage = null;
        _optimizerValid = false;
        _deployerValid = false;
      });
    }
  }
  
  /// Upload credentials JSON and auto-fill form fields
  Future<void> _uploadCredentialsJson() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['json'],
      );
      
      if (result == null || result.files.isEmpty) return;
      
      final file = result.files.single;
      final jsonString = await readPickedFile(file);
      final jsonData = jsonDecode(jsonString) as Map<String, dynamic>;
      
      // Look for nested provider-specific data (e.g., jsonData["aws"]["aws_access_key_id"])
      final providerData = jsonData[widget.provider] as Map<String, dynamic>?;
      
      if (providerData == null) {
        // Show warning if provider section not found
        setState(() {
          _optimizerMessage = '⚠️ No "${widget.provider}" section found in JSON. '
              'Expected format: { "${widget.provider}": { ... } }';
          _deployerMessage = null;
          _optimizerValid = false;
          _deployerValid = false;
        });
        return;
      }
      
      // Auto-fill form fields from nested provider data
      int fieldsPopulated = 0;
      for (final field in widget.fields) {
        final jsonKey = '${widget.provider}_${field.name}';
        if (providerData.containsKey(jsonKey) && providerData[jsonKey] != null) {
          final value = providerData[jsonKey].toString();
          if (value.isNotEmpty) {
            _controllers[field.name]?.text = value;
            fieldsPopulated++;
          }
        }
      }
      
      if (fieldsPopulated == 0) {
        setState(() {
          _optimizerMessage = '⚠️ No matching fields found in "${widget.provider}" section. '
              'Check the expected format (ℹ️ button).';
          _deployerMessage = null;
          _optimizerValid = false;
          _deployerValid = false;
        });
      } else {
        _notifyCredentialsChanged();
        
        // Auto-trigger dual validation after file upload
        await _validateCredentials();
        return;  // Validation sets all state
      }
      
      _notifyCredentialsChanged();
    } catch (e) {
      setState(() {
        _optimizerMessage = '❌ Failed to parse JSON: $e';
        _deployerMessage = null;
        _optimizerValid = false;
        _deployerValid = false;
      });
    }
  }
  
  /// Get schema example for this provider
  String _getSchemaExample() {
    switch (widget.provider) {
      case 'aws':
        return '{\n  "aws": {\n    "aws_access_key_id": "XXXX...",\n    "aws_secret_access_key": "...",\n    "aws_session_token": "OPTIONAL",\n    "aws_region": "eu-central-1"\n  }\n}';
      case 'azure':
        return '{\n  "azure": {\n    "azure_subscription_id": "...",\n    "azure_client_id": "...",\n    "azure_client_secret": "...",\n    "azure_tenant_id": "...",\n    "azure_region": "westeurope"\n  }\n}';
      case 'gcp':
        return '{\n  "gcp": {\n    "gcp_project_id": "...",\n    "gcp_billing_account": "XXXXXX-...",\n    "gcp_region": "europe-west1"\n  }\n}';
      default:
        return '{}';
    }
  }
  
  void _showSchemaDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('${widget.title} JSON Format'),
        content: SelectableText(_getSchemaExample()),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
  
  void _notifyCredentialsChanged() {
    final creds = <String, String>{};
    for (final entry in _controllers.entries) {
      creds[entry.key] = entry.value.text;
    }
    widget.onCredentialsChanged(creds);
  }
  @override
  Widget build(BuildContext context) {
    // Use actual _isValid (getter that checks both optimizer AND deployer)
    final bool showAsValid = _isValid;
    debugPrint('CredentialSection Build: provider=${widget.provider}, isConfigured=${widget.isConfigured}, showAsValid=$showAsValid');
    for(final f in widget.fields) {
       debugPrint('Field ${f.name}: text="${_controllers[f.name]?.text}", isEmpty=${_controllers[f.name]?.text.isEmpty}');
    }

    final bool hasAnyValidation = _optimizerMessage != null || _deployerMessage != null;
    
    return Card(
      // Use green border instead of light green background for dark mode compatibility
      shape: showAsValid 
        ? RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: Colors.green.shade600, width: 2),
          )
        : null,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row with title and validation status
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: showAsValid 
                      ? Colors.green.shade600
                      : widget.color.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(
                    showAsValid ? Icons.check : widget.icon, 
                    color: showAsValid ? Colors.white : widget.color, 
                    size: 24,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.title,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      if (showAsValid)
                        Text(
                          (widget.isConfigured && !_optimizerValid && !_deployerValid) 
                              ? 'Credentials Configured (Hidden) ✓'
                              : 'Credentials validated ✓',
                          style: TextStyle(
                            fontSize: 12,
                            color: Colors.green.shade400,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                    ],
                  ),
                ),
                if (showAsValid)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.green.shade600,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.check_circle, color: Colors.white, size: 16),
                        SizedBox(width: 4),
                        Text('Valid', style: TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                        )),
                      ],
                    ),
                  ),
              ],
            ),
            
            // Prominent success banner when both validations pass
            if (showAsValid) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.shade600,
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.verified, color: Colors.white, size: 24),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Section Complete',
                            style: TextStyle(
                              color: Colors.white,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          Text(
                            'Both pricing and infrastructure permissions verified',
                            style: TextStyle(
                              color: Colors.white70,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Icon(Icons.check_circle, color: Colors.white, size: 20),
                  ],
                ),
              ),
            ],
            
            const SizedBox(height: 16),
            
            // Action buttons row - Upload first, then View Format
            Row(
              children: [
                // Upload credentials button (FIRST)
                if (widget.supportsCredentialsUpload)
                  Expanded(
                    child: FilledButton.tonalIcon(
                      onPressed: _uploadCredentialsJson,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Upload Credentials'),
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                if (widget.supportsCredentialsUpload)
                  const SizedBox(width: 12),
                // Format info button (SECOND)
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _showSchemaDialog,
                    icon: const Icon(Icons.info_outline),
                    label: const Text('View JSON Format'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'Upload config_credentials.json to auto-fill fields below',
              style: TextStyle(
                fontSize: 11,
                color: showAsValid 
                  ? Colors.green.shade700 
                  : Theme.of(context).colorScheme.outline,
              ),
            ),
            
            const SizedBox(height: 16),
            Divider(color: showAsValid ? Colors.green.shade200 : null),
            const SizedBox(height: 16),
            
            // GCP Service Account JSON Upload button (special case)
            if (widget.supportsJsonUpload) ...[
              FilledButton.icon(
                onPressed: _pickJsonFile,
                icon: const Icon(Icons.cloud_upload),
                label: const Text('Upload Service Account JSON'),
                style: FilledButton.styleFrom(
                  minimumSize: const Size(double.infinity, 48),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'Upload your GCP service account key file (.json)',
                style: TextStyle(
                  fontSize: 11,
                  color: showAsValid 
                    ? Colors.green.shade700 
                    : Theme.of(context).colorScheme.outline,
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(child: Divider(color: showAsValid ? Colors.green.shade600 : null)),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Text('OR', style: TextStyle(
                      fontSize: 12,
                      color: showAsValid 
                        ? Colors.green.shade400 
                        : Theme.of(context).colorScheme.outline,
                    )),
                  ),
                  Expanded(child: Divider(color: showAsValid ? Colors.green.shade600 : null)),
                ],
              ),
              const SizedBox(height: 16),
            ],
            
            // Credential fields
            ...widget.fields.map((field) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: TextField(
                controller: _controllers[field.name],
                decoration: InputDecoration(
                  labelText: field.required 
                    ? field.label 
                    : '${field.label} (optional)',
                  hintText: (widget.isConfigured && _controllers[field.name]?.text.isEmpty == true)
                      ? '•••••••••••••••• (Stored Securely)' 
                      : null,
                  hintStyle: TextStyle(
                    color: Colors.green.shade700,
                    fontWeight: FontWeight.w500,
                    fontStyle: FontStyle.italic,
                  ),
                  floatingLabelBehavior: FloatingLabelBehavior.always, // Ensure hint is visible
                  border: const OutlineInputBorder(),
                  // Don't change field colors when valid - keep default theme colors
                ),
                obscureText: field.obscure && _controllers[field.name]?.text.isNotEmpty == true, // Hide typed text, show hint otherwise
                onChanged: (_) {
                  _notifyCredentialsChanged();
                  setState(() {});  // Refresh UI for button state
                },
              ),
            )),
            
            // Validation button and status
            const SizedBox(height: 8),
            // Validation button and status
            const SizedBox(height: 8),
            SizedBox(
              width: double.infinity,
              child: showAsValid 
                ? OutlinedButton.icon(
                    onPressed: _isValidating ? null : _validateCredentials,
                    icon: _isValidating 
                      ? const SizedBox(
                          width: 16, height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.refresh),
                    label: const Text('Re-validate'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      foregroundColor: Colors.green.shade400,
                      side: BorderSide(color: Colors.green.shade600),
                    ),
                  )
                : ElevatedButton.icon(
                    // Enable button if fields are filled OR if we can validate stored credentials
                    onPressed: (_isValidating || (!_areRequiredFieldsFilled() && !widget.isConfigured)) 
                        ? null 
                        : _validateCredentials,
                    icon: _isValidating
                      ? const SizedBox(
                          width: 16, height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.verified_user),
                    label: Text(
                      (widget.isConfigured && !_areRequiredFieldsFilled())
                          ? 'Validate Stored Credentials'
                          : 'Validate Credentials'
                    ),
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
            ),
            if (!_areRequiredFieldsFilled() && !widget.isConfigured && !showAsValid) ...[
              const SizedBox(height: 4),
              Text(
                'Fill all required fields to enable validation',
                style: TextStyle(
                  fontSize: 11,
                  color: Theme.of(context).colorScheme.outline,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
            
            // DUAL Validation Results - Two separate boxes
            if (hasAnyValidation) ...[
              const SizedBox(height: 12),
              
              // Optimizer result (Pricing permissions)
              if (_optimizerMessage != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: _optimizerValid 
                      ? Colors.green.withOpacity(0.15) 
                      : Colors.red.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: _optimizerValid ? Colors.green.shade600 : Colors.red.shade400,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _optimizerValid ? Icons.check_circle : Icons.error,
                        color: _optimizerValid ? Colors.green.shade400 : Colors.red.shade400,
                        size: 18,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Optimizer (Pricing)',
                              style: TextStyle(
                                color: _optimizerValid ? Colors.green.shade400 : Colors.red.shade400,
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            Text(
                              _optimizerMessage!,
                              style: TextStyle(
                                color: _optimizerValid ? Colors.green.shade300 : Colors.red.shade300,
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              
              const SizedBox(height: 8),
              
              // Deployer result (Infrastructure permissions)
              if (_deployerMessage != null)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: _deployerValid 
                      ? Colors.green.withOpacity(0.15) 
                      : Colors.red.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: _deployerValid ? Colors.green.shade600 : Colors.red.shade400,
                    ),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        _deployerValid ? Icons.check_circle : Icons.error,
                        color: _deployerValid ? Colors.green.shade400 : Colors.red.shade400,
                        size: 18,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Deployer (Infrastructure)',
                              style: TextStyle(
                                color: _deployerValid ? Colors.green.shade400 : Colors.red.shade400,
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            Text(
                              _deployerMessage!,
                              style: TextStyle(
                                color: _deployerValid ? Colors.green.shade300 : Colors.red.shade300,
                                fontSize: 13,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

