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
  
  const CredentialField({
    required this.name,
    required this.label,
    this.obscure = false,
    this.defaultValue,
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
      
    } catch (e) {
      setState(() {
        _isValid = false;
        _validationMessage = 'Validation failed: $e';
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
                  // JSON Upload button (for GCP)
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
                        labelText: field.label,
                        border: const OutlineInputBorder(),
                      ),
                      obscureText: field.obscure,
                      onChanged: (_) => _notifyCredentialsChanged(),
                    ),
                  )),
                  
                  const SizedBox(height: 8),
                  
                  // Validation button and status
                  Row(
                    children: [
                      FilledButton.icon(
                        onPressed: _isValidating ? null : _validateCredentials,
                        icon: _isValidating 
                          ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.verified_user, size: 18),
                        label: Text(_isValidating ? 'Validating...' : 'Validate'),
                      ),
                      const SizedBox(width: 12),
                      if (_validationMessage != null)
                        Expanded(
                          child: Text(
                            _validationMessage!,
                            style: TextStyle(
                              fontSize: 12,
                              color: _isValid ? Colors.green : Colors.red,
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
