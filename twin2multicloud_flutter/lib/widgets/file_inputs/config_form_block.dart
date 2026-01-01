import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../../utils/api_error_handler.dart';
import '../../utils/file_reader.dart';

/// Form-style input block for config.json.
/// Similar to CredentialSection but for deployment configuration.
/// 
/// Fields:
/// - digital_twin_name (text)
/// - hot_storage_size_in_days (number)
/// - cold_storage_size_in_days (number)
/// 
/// NOTE: mode field is NOT included (already set in Step 1)
class ConfigFormBlock extends StatefulWidget {
  final Function(Map<String, dynamic>)? onConfigChanged;
  final Future<Map<String, dynamic>> Function(Map<String, dynamic>)? onValidate;
  final bool autoValidateOnUpload;  // NEW: Auto-validate after file upload
  
  const ConfigFormBlock({
    super.key,
    this.onConfigChanged,
    this.onValidate,
    this.autoValidateOnUpload = false,  // Default: false for backward compat
  });
  
  @override
  State<ConfigFormBlock> createState() => _ConfigFormBlockState();
}

class _ConfigFormBlockState extends State<ConfigFormBlock> {
  final _twinNameController = TextEditingController();
  final _hotDaysController = TextEditingController(text: '30');
  final _coldDaysController = TextEditingController(text: '90');
  
  bool _isValidating = false;
  bool? _isValid;
  String? _validationMessage;
  
  static const Color _accentColor = Color(0xFFD81B60);  // Same as editable color
  
  // Example JSON content
  static const String _exampleJson = '''{
  "digital_twin_name": "my-digital-twin",
  "hot_storage_size_in_days": 30,
  "cold_storage_size_in_days": 90
}''';
  
  @override
  void dispose() {
    _twinNameController.dispose();
    _hotDaysController.dispose();
    _coldDaysController.dispose();
    super.dispose();
  }
  
  Map<String, dynamic> _buildConfigJson() {
    return {
      'digital_twin_name': _twinNameController.text.trim(),
      'hot_storage_size_in_days': int.tryParse(_hotDaysController.text) ?? 30,
      'cold_storage_size_in_days': int.tryParse(_coldDaysController.text) ?? 90,
    };
  }
  
  void _notifyChange() {
    widget.onConfigChanged?.call(_buildConfigJson());
  }
  
  Future<void> _pickJsonFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['json'],
      );
      
      if (result == null || result.files.isEmpty) return;
      
      final content = await readPickedFile(result.files.single);
      final json = jsonDecode(content) as Map<String, dynamic>;
      
      setState(() {
        if (json['digital_twin_name'] != null) {
          _twinNameController.text = json['digital_twin_name'].toString();
        }
        if (json['hot_storage_size_in_days'] != null) {
          _hotDaysController.text = json['hot_storage_size_in_days'].toString();
        }
        if (json['cold_storage_size_in_days'] != null) {
          _coldDaysController.text = json['cold_storage_size_in_days'].toString();
        }
        _isValid = null;
        _validationMessage = null;
      });
      
      _notifyChange();
      
      // Auto-validate if enabled (matches CredentialSection pattern)
      if (widget.autoValidateOnUpload) {
        await _validate();
      }
    } catch (e) {
      if (!mounted) return;  // Guard against async context use
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to parse JSON: ${ApiErrorHandler.extractMessage(e)}'),
          backgroundColor: Colors.red.shade700,
        ),
      );
    }
  }
  
  void _showExampleDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.description_outlined),
            SizedBox(width: 12),
            Text('Example: config.json'),
          ],
        ),
        content: Container(
          constraints: const BoxConstraints(maxWidth: 500, maxHeight: 300),
          decoration: BoxDecoration(
            color: const Color(0xFF1E1E1E),
            borderRadius: BorderRadius.circular(8),
          ),
          padding: const EdgeInsets.all(16),
          child: SelectableText(
            _exampleJson,
            style: TextStyle(
              fontFamily: 'monospace',
              fontSize: 13,
              color: Colors.green.shade300,
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close'),
          ),
          FilledButton(
            onPressed: () {
              // Fill form with example values
              setState(() {
                _twinNameController.text = 'my-digital-twin';
                _hotDaysController.text = '30';
                _coldDaysController.text = '90';
              });
              _notifyChange();
              Navigator.pop(ctx);
            },
            child: const Text('Use Example'),
          ),
        ],
      ),
    );
  }
  
  Future<void> _validate() async {
    if (widget.onValidate == null) {
      // Client-side validation only
      setState(() {
        final name = _twinNameController.text.trim();
        final hotDays = int.tryParse(_hotDaysController.text);
        final coldDays = int.tryParse(_coldDaysController.text);
        
        if (name.isEmpty) {
          _isValid = false;
          _validationMessage = 'Digital twin name is required';
        } else if (!RegExp(r'^[a-z0-9-]+$').hasMatch(name)) {
          _isValid = false;
          _validationMessage = 'Name must be lowercase alphanumeric with hyphens only';
        } else if (hotDays == null || hotDays < 1 || hotDays > 365) {
          _isValid = false;
          _validationMessage = 'Hot storage days must be 1-365';
        } else if (coldDays == null || coldDays < 1 || coldDays > 730) {
          _isValid = false;
          _validationMessage = 'Cold storage days must be 1-730';
        } else {
          _isValid = true;
          _validationMessage = 'Configuration is valid ✓';
        }
      });
      return;
    }
    
    setState(() {
      _isValidating = true;
      _validationMessage = null;
    });
    
    try {
      final result = await widget.onValidate!(_buildConfigJson());
      setState(() {
        _isValid = result['valid'] == true;
        _validationMessage = result['message']?.toString() ?? 
          (_isValid! ? 'Valid ✓' : 'Validation failed');
      });
    } catch (e) {
      setState(() {
        _isValid = false;
        _validationMessage = 'Validation error: ${ApiErrorHandler.extractMessage(e)}';
      });
    } finally {
      setState(() => _isValidating = false);
    }
  }
  
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        // Use neutral colors - no pink tint
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: _isValid == true ? Colors.green.shade600 : 
                 _isValid == false ? Colors.red.shade400 : Colors.grey.shade300,
          width: _isValid != null ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Icon(Icons.settings, color: _accentColor, size: 22),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'config.json',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontFamily: 'monospace',
                        fontSize: 14,
                        color: _accentColor,
                      ),
                    ),
                    Text(
                      'Core deployment configuration',
                      style: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                decoration: BoxDecoration(
                  color: _accentColor,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  'REQUIRED',
                  style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          
          const SizedBox(height: 20),
          
          // Form and buttons row
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Form fields (2/3)
              Expanded(
                flex: 2,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildTextField(
                      label: 'Digital Twin Name',
                      controller: _twinNameController,
                      hint: 'e.g., my-digital-twin',
                      helperText: 'Lowercase, alphanumeric, hyphens only',
                      isDark: isDark,
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: _buildNumberField(
                            label: 'Hot Storage (days)',
                            controller: _hotDaysController,
                            min: 1,
                            max: 365,
                            isDark: isDark,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: _buildNumberField(
                            label: 'Cold Storage (days)',
                            controller: _coldDaysController,
                            min: 1,
                            max: 730,
                            isDark: isDark,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              
              const SizedBox(width: 24),
              
              // Buttons column (1/3)
              Expanded(
                flex: 1,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    FilledButton.tonalIcon(
                      onPressed: _pickJsonFile,
                      icon: const Icon(Icons.upload_file),
                      label: const Text('Upload JSON'),
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                    const SizedBox(height: 8),
                    OutlinedButton.icon(
                      onPressed: _showExampleDialog,
                      icon: const Icon(Icons.description_outlined, size: 16),
                      label: const Text('Example'),
                      style: OutlinedButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 10),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'Constraints:',
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.grey.shade500,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '• Name: lowercase with hyphens\n• Hot: 1-365 days\n• Cold: 1-730 days',
                      style: TextStyle(
                        fontSize: 10,
                        color: Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          
          // Validation button
          const SizedBox(height: 20),
          Center(
            child: FilledButton.icon(
              onPressed: _isValidating ? null : _validate,
              icon: _isValidating
                  ? const SizedBox(
                      width: 16, height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                    )
                  : const Icon(Icons.check_circle),
              label: const Text('Validate'),
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 24),
                // Use theme primary instead of pink for consistency with Step 1
              ),
            ),
          ),
          
          // Validation result
          if (_validationMessage != null) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: _isValid == true 
                    ? Colors.green.withAlpha(38)
                    : Colors.red.withAlpha(38),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: _isValid == true ? Colors.green.shade600 : Colors.red.shade400,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    _isValid == true ? Icons.check_circle : Icons.error,
                    color: _isValid == true ? Colors.green.shade400 : Colors.red.shade400,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _validationMessage!,
                      style: TextStyle(
                        color: _isValid == true ? Colors.green.shade300 : Colors.red.shade300,
                        fontSize: 12,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
  
  Widget _buildTextField({
    required String label,
    required TextEditingController controller,
    required String hint,
    String? helperText,
    required bool isDark,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
          ),
        ),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          onChanged: (_) => _notifyChange(),
          decoration: InputDecoration(
            hintText: hint,
            helperText: helperText,
            helperStyle: TextStyle(fontSize: 10, color: Colors.grey.shade500),
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          style: const TextStyle(fontSize: 14),
        ),
      ],
    );
  }
  
  Widget _buildNumberField({
    required String label,
    required TextEditingController controller,
    required int min,
    required int max,
    required bool isDark,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
          ),
        ),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          onChanged: (_) => _notifyChange(),
          keyboardType: TextInputType.number,
          decoration: InputDecoration(
            hintText: '$min-$max',
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
            ),
          ),
          style: const TextStyle(fontSize: 14),
        ),
      ],
    );
  }
}
