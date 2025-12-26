import 'dart:convert';
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
  final bool supportsCredentialsUpload;  // NEW - for config_credentials.json style uploads
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
    this.supportsCredentialsUpload = true,  // Default: allow credentials JSON upload for all
  });
  
  @override
  ConsumerState<CredentialSection> createState() => _CredentialSectionState();
}

class _CredentialSectionState extends ConsumerState<CredentialSection> {
  bool _isExpanded = false;
  bool _isValidating = false;
  bool _isValid = false;
  String? _validationMessage;
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
  
  Future<void> _validateCredentials() async {
    setState(() {
      _isValidating = true;
      _validationMessage = null;
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
      
      // Use inline validation (no twin required)
      final result = await api.validateCredentialsInline(widget.provider, credentials);
      
      setState(() {
        _isValid = result['valid'] ?? false;
        _validationMessage = result['message'] ?? 'Validation complete';
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
        _isValid = false;
        _validationMessage = errorMsg;
      });
      widget.onValidationChanged(false);
    } catch (e) {
      setState(() {
        _isValid = false;
        _validationMessage = '❌ Validation failed: $e';
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
      
      setState(() {
        _validationMessage = 'JSON file loaded: ${file.name}';
      });
      
      _notifyCredentialsChanged();
    } catch (e) {
      setState(() {
        _validationMessage = 'Failed to load JSON: $e';
        _isValid = false;
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
          _validationMessage = '⚠️ No "${widget.provider}" section found in JSON. '
              'Expected format: { "${widget.provider}": { ... } }';
          _isValid = false;
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
          _validationMessage = '⚠️ No matching fields found in "${widget.provider}" section. '
              'Check the expected format (ℹ️ button).';
          _isValid = false;
        });
      } else {
        setState(() {
          _validationMessage = '✓ Loaded $fieldsPopulated field(s) from ${file.name}';
        });
      }
      
      _notifyCredentialsChanged();
    } catch (e) {
      setState(() {
        _validationMessage = '❌ Failed to parse JSON: $e';
        _isValid = false;
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
    return Card(
      child: Column(
        children: [
          ListTile(
            leading: Icon(widget.icon, color: widget.color),
            title: Text(widget.title),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Schema info button
                IconButton(
                  icon: const Icon(Icons.info_outline, size: 18),
                  tooltip: 'Show expected JSON format',
                  onPressed: _showSchemaDialog,
                ),
                // Upload credentials JSON button
                if (widget.supportsCredentialsUpload)
                  IconButton(
                    icon: const Icon(Icons.upload_file, size: 20),
                    tooltip: 'Upload credentials JSON',
                    onPressed: _uploadCredentialsJson,
                  ),
                if (_isValid)
                  const Icon(Icons.check_circle, color: Colors.green, size: 20),
                Icon(_isExpanded ? Icons.expand_less : Icons.expand_more),
              ],
            ),
            onTap: () => setState(() => _isExpanded = !_isExpanded),
          ),
          
          if (_isExpanded) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // GCP Service Account JSON Upload button
                  if (widget.supportsJsonUpload) ...[
                    OutlinedButton.icon(
                      onPressed: _pickJsonFile,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Upload Service Account JSON'),
                    ),
                    const SizedBox(height: 16),
                    const Text('Or enter credentials manually:', 
                      style: TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
                    const SizedBox(height: 8),
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
                        border: const OutlineInputBorder(),
                      ),
                      obscureText: field.obscure,
                      onChanged: (_) {
                        _notifyCredentialsChanged();
                        setState(() {});  // Refresh UI for button state
                      },
                    ),
                  )),
                  
                  // Validation button and status
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Expanded(
                        child: ElevatedButton(
                          onPressed: (_isValidating || !_areRequiredFieldsFilled()) 
                              ? null 
                              : _validateCredentials,
                          child: _isValidating
                            ? const SizedBox(
                                width: 16, height: 16,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Text('Validate Credentials'),
                        ),
                      ),
                    ],
                  ),
                  if (!_areRequiredFieldsFilled()) ...[
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
                  
                  if (_validationMessage != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      _validationMessage!,
                      style: TextStyle(
                        color: _isValid ? Colors.green : Colors.red,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
