import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../utils/api_error_handler.dart';
import '../../utils/json_syntax_highlighter.dart';

/// Split-view config block for config.json with:
/// - Static fields from previous steps (mode, storage days)
/// - Editable field (digital_twin_name)
/// - Validation button with inline result
/// 
/// Matches the layout of ConfigVisualizationBlock but allows partial editing.
class ConfigJsonVisualizationBlock extends StatefulWidget {
  final String? twinName;
  final String? mode;  // From Step 1
  final int hotStorageDays;   // From Step 2
  final int coldStorageDays;  // From Step 2
  final bool isValidated;     // From BLoC - persisted validation state
  final Function(String) onTwinNameChanged;
  final Future<Map<String, dynamic>> Function(Map<String, dynamic>)? onValidate;
  final VoidCallback? onValidationSuccess;  // Called when validation succeeds (to update BLoC)
  
  const ConfigJsonVisualizationBlock({
    super.key,
    required this.twinName,
    required this.mode,
    required this.hotStorageDays,
    required this.coldStorageDays,
    this.isValidated = false,
    required this.onTwinNameChanged,
    this.onValidate,
    this.onValidationSuccess,
  });

  @override
  State<ConfigJsonVisualizationBlock> createState() => _ConfigJsonVisualizationBlockState();
}

class _ConfigJsonVisualizationBlockState extends State<ConfigJsonVisualizationBlock> {
  late TextEditingController _twinNameController;
  bool _isValidating = false;
  bool? _isValid;
  String? _validationMessage;
  
  static const Color _accentColor = Color(0xFFD81B60);

  @override
  void initState() {
    super.initState();
    _twinNameController = TextEditingController(text: widget.twinName ?? '');
    // Initialize validation state from BLoC (persists across navigation)
    if (widget.isValidated) {
      _isValid = true;
      _validationMessage = 'Configuration is valid ✓';
    }
  }

  @override
  void didUpdateWidget(ConfigJsonVisualizationBlock oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Update controller if external twin name changed
    if (widget.twinName != oldWidget.twinName && widget.twinName != _twinNameController.text) {
      _twinNameController.text = widget.twinName ?? '';
    }
  }

  @override
  void dispose() {
    _twinNameController.dispose();
    super.dispose();
  }

  Map<String, dynamic> _buildConfigJson() {
    return {
      'digital_twin_name': _twinNameController.text.trim(),
      'mode': (widget.mode ?? 'production').toUpperCase(),  // Deployer expects uppercase
      'hot_storage_size_in_days': widget.hotStorageDays,
      'cold_storage_size_in_days': widget.coldStorageDays,
    };
  }

  String get _jsonContent {
    return const JsonEncoder.withIndent('  ').convert(_buildConfigJson());
  }

  Future<void> _validate() async {
    if (widget.onValidate == null) {
      // Client-side validation only
      setState(() {
        final name = _twinNameController.text.trim();
        if (name.isEmpty) {
          _isValid = false;
          _validationMessage = 'Digital twin name is required';
        } else if (!RegExp(r'^[a-z0-9_-]+$').hasMatch(name)) {
          _isValid = false;
          _validationMessage = 'Name must be lowercase alphanumeric with hyphens or underscores only';
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
      final isValid = result['valid'] == true;
      setState(() {
        _isValid = isValid;
        _validationMessage = result['message']?.toString() ??
            (isValid ? 'Valid ✓' : 'Validation failed');
      });
      // Notify parent/BLoC of validation success
      if (isValid && widget.onValidationSuccess != null) {
        widget.onValidationSuccess!();
      }
    } catch (e) {
      setState(() {
        _isValid = false;
        _validationMessage = 'Validation error: ${ApiErrorHandler.extractMessage(e)}';
      });
    } finally {
      setState(() => _isValidating = false);
    }
  }

  void _copyToClipboard() {
    Clipboard.setData(ClipboardData(text: _jsonContent));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('config.json copied to clipboard'),
        duration: Duration(seconds: 2),
        behavior: SnackBarBehavior.floating,
      ),
    );
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
          color: _isValid == true
              ? Colors.green.shade600
              : _isValid == false
                  ? Colors.red.shade400
                  : Colors.grey.shade300,
          width: _isValid != null ? 2 : 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row
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
              // Auto badge for static fields
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.blue.shade700.withAlpha(isDark ? 80 : 40),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: Colors.blue.shade400.withAlpha(100)),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.auto_mode, size: 12, color: Colors.blue.shade400),
                    const SizedBox(width: 4),
                    Text(
                      'From Step 1 & 2',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: Colors.blue.shade300,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              // Copy button
              IconButton(
                onPressed: _copyToClipboard,
                icon: Icon(Icons.copy, size: 18, color: Colors.grey.shade500),
                tooltip: 'Copy to clipboard',
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              ),
            ],
          ),

          const SizedBox(height: 16),

          // Prominent twin name input (ABOVE split view)
          Text(
            'Digital Twin Name',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.grey.shade200 : Colors.grey.shade800,
            ),
          ),
          const SizedBox(height: 6),
          TextField(
            controller: _twinNameController,
            onChanged: (value) {
              widget.onTwinNameChanged(value);
              // Reset validation on change AND trigger rebuild for button state
              setState(() {
                _isValid = null;
                _validationMessage = null;
              });
            },
            decoration: InputDecoration(
              hintText: 'e.g., my_digital_twin',
              helperText: 'Lowercase alphanumeric with hyphens or underscores (e.g., factory_sensor_01)',
              helperStyle: TextStyle(fontSize: 11, color: Colors.grey.shade500),
              prefixIcon: Icon(Icons.edit, color: _accentColor, size: 20),
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: _accentColor),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide(color: _accentColor, width: 2),
              ),
            ),
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
          ),

          const SizedBox(height: 20),

          // Split view: JSON left | Static visualization right
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Left: JSON preview (2/3 width) - READ-ONLY
              Expanded(
                flex: 2,
                child: Stack(
                  children: [
                    Container(
                      height: 140,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: const Color(0xFF2A2A2A), // Slightly grey-tinted dark
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: Colors.grey.shade700,
                          width: 1,
                        ),
                      ),
                      child: SingleChildScrollView(
                        child: SelectableText(
                          _jsonContent,
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 12,
                            height: 1.4,
                            color: Colors.grey.shade500, // Greyed out text - no syntax highlighting
                          ),
                        ),
                      ),
                    ),
                    // Read-only indicator
                    Positioned(
                      top: 6,
                      right: 6,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: Colors.grey.shade800,
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(Icons.lock, size: 10, color: Colors.grey.shade400),
                            const SizedBox(width: 4),
                            Text(
                              'Read-only',
                              style: TextStyle(fontSize: 9, color: Colors.grey.shade400),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(width: 16),

              // Right: Static visualization (1/3 width)
              Expanded(
                flex: 1,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Configuration Summary',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                      ),
                    ),
                    const SizedBox(height: 10),
                    
                    // Static: Mode
                    _buildStaticField(
                      'Mode',
                      widget.mode ?? 'production',
                      'From Step 1',
                      isDark,
                    ),

                    const SizedBox(height: 8),

                    // Static: Storage days
                    _buildStaticField(
                      'Hot Storage',
                      '${widget.hotStorageDays} days',
                      'From Step 2',
                      isDark,
                    ),
                    const SizedBox(height: 4),
                    _buildStaticField(
                      'Cold Storage',
                      '${widget.coldStorageDays} days',
                      'From Step 2',
                      isDark,
                    ),
                  ],
                ),
              ),
            ],
          ),

          // Validate button
          const SizedBox(height: 16),
          Center(
            child: FilledButton.icon(
              onPressed: _isValidating || _twinNameController.text.isEmpty ? null : _validate,
              icon: _isValidating
                  ? const SizedBox(
                      width: 16,
                      height: 16,
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

  Widget _buildStaticField(String label, String value, String source, bool isDark) {
    return Row(
      children: [
        Text(
          '$label: ',
          style: TextStyle(
            fontSize: 11,
            color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
            ),
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
          decoration: BoxDecoration(
            color: Colors.grey.withAlpha(20),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Text(
            source,
            style: TextStyle(fontSize: 8, color: Colors.grey.shade500),
          ),
        ),
      ],
    );
  }
}
