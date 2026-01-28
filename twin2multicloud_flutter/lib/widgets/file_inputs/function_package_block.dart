import 'package:flutter/material.dart';
import 'file_editor_block.dart';
import 'collapsible_block_wrapper.dart';

/// A composite widget for Python function packages (code + optional requirements.txt).
///
/// Uses composition over mutation - wraps two FileEditorBlock instances instead
/// of adding complexity to FileEditorBlock directly.
///
/// Features:
/// - Auto-validates on file upload (calls onValidate automatically)
/// - Displays validation error/success feedback
/// - Supports optional requirements.txt companion file
///
/// Layout order:
/// 1. Code editor (with Upload/Example buttons)
/// 2. "+ Add requirements.txt" toggle
/// 3. Requirements editor (when visible)
/// 4. Validate button
/// 5. Validation feedback
///
/// TODO(future-work-18): Add requirements.txt validation
/// See 3-cloud-deployer/docs/future-work.md#18
class FunctionPackageBlock extends StatefulWidget {
  /// Filename for the Python code (e.g., 'processors/sensor-1/lambda_function.py')
  final String codeFilename;

  /// Description shown in the header
  final String description;

  /// Current Python code content
  final String? codeContent;

  /// Callback when code content changes
  final Function(String) onCodeChanged;

  /// Current requirements.txt content (null if not added)
  final String? requirementsContent;

  /// Callback when requirements content changes (null = removed)
  final Function(String?) onRequirementsChanged;

  /// Validation callback for Python code - returns {valid: bool, message: String}
  final Future<Map<String, dynamic>> Function(String code)? onValidate;

  /// Whether the code is validated (from BLoC)
  final bool isCodeValidated;

  /// Optional constraints text to display
  final String? constraints;

  /// Optional example content for the code editor
  final String? exampleContent;

  /// Whether to start expanded (defaults to true)
  /// Set to false for valid blocks in edit mode
  final bool initiallyExpanded;

  /// If true, forces the block to collapse (used for auto-collapse after zip upload)
  final bool forceCollapsed;

  const FunctionPackageBlock({
    super.key,
    required this.codeFilename,
    required this.description,
    this.codeContent,
    required this.onCodeChanged,
    this.requirementsContent,
    required this.onRequirementsChanged,
    this.onValidate,
    this.isCodeValidated = false,
    this.constraints,
    this.exampleContent,
    this.initiallyExpanded = true,
    this.forceCollapsed = false,
  });

  @override
  State<FunctionPackageBlock> createState() => _FunctionPackageBlockState();
}

class _FunctionPackageBlockState extends State<FunctionPackageBlock> {
  bool _showRequirements = false;
  bool _isValidating = false;

  // Validation state (local UI feedback, NOT persisted to BLoC)
  bool? _isValid;
  String? _validationMessage;

  @override
  void initState() {
    super.initState();
    // Show requirements section if content exists (hydrated from DB)
    _showRequirements =
        widget.requirementsContent != null &&
        widget.requirementsContent!.isNotEmpty;
    // Sync initial validation state from BLoC
    if (widget.isCodeValidated) {
      _isValid = true;
      _validationMessage = 'Valid ✓';
    }
  }

  @override
  void didUpdateWidget(FunctionPackageBlock oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Sync visibility when content changes externally (hydration)
    if (widget.requirementsContent != oldWidget.requirementsContent) {
      final hasContent =
          widget.requirementsContent != null &&
          widget.requirementsContent!.isNotEmpty;
      if (hasContent && !_showRequirements) {
        setState(() => _showRequirements = true);
      }
    }
    // Sync validation state from BLoC (for hydration and cascade clearing)
    if (widget.isCodeValidated != oldWidget.isCodeValidated) {
      if (widget.isCodeValidated) {
        setState(() {
          _isValid = true;
          _validationMessage = 'Valid ✓';
        });
      } else {
        setState(() {
          _isValid = null;
          _validationMessage = null;
        });
      }
    }
  }

  void _toggleRequirements() {
    setState(() {
      _showRequirements = !_showRequirements;
      if (!_showRequirements) {
        // Remove requirements when hidden
        widget.onRequirementsChanged(null);
      }
    });
  }

  /// Clear validation state when content changes
  void _onCodeChanged(String content) {
    // Clear local validation feedback
    if (_isValid != null) {
      setState(() {
        _isValid = null;
        _validationMessage = null;
      });
    }
    widget.onCodeChanged(content);
  }

  /// Validate the current code content
  Future<void> _validateCode() async {
    if (widget.onValidate == null) return;
    if (widget.codeContent == null || widget.codeContent!.isEmpty) return;

    setState(() => _isValidating = true);

    try {
      final result = await widget.onValidate!(widget.codeContent!);
      final valid = result['valid'] == true;
      final message =
          result['message']?.toString() ??
          (valid ? 'Valid ✓' : 'Validation failed');

      if (mounted) {
        setState(() {
          _isValid = valid;
          _validationMessage = message;
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isValidating = false);
      }
    }
  }

  /// Wrapper for FileEditorBlock that auto-validates after upload
  Future<Map<String, dynamic>> _autoValidateWrapper(String content) async {
    if (widget.onValidate == null) {
      return {'valid': false, 'message': 'Validation not configured'};
    }

    final result = await widget.onValidate!(content);
    final valid = result['valid'] == true;
    final message =
        result['message']?.toString() ??
        (valid ? 'Valid ✓' : 'Validation failed');

    // Update local UI state
    if (mounted) {
      setState(() {
        _isValid = valid;
        _validationMessage = message;
      });
    }

    return result;
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primaryColor = Theme.of(context).colorScheme.primary;

    return CollapsibleBlockWrapper(
      title: widget.codeFilename,
      subtitle: widget.description,
      icon: Icons.code,
      isValid: widget.isCodeValidated ? true : null,
      showEditBadge: true,
      initiallyExpanded: widget.initiallyExpanded,
      forceCollapsed: widget.forceCollapsed,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // 1. Code editor (no validate button - we add our own at bottom)
          FileEditorBlock(
            filename: widget.codeFilename,
            description: widget.description,
            initialContent: widget.codeContent,
            isValidated: widget.isCodeValidated,
            onContentChanged: _onCodeChanged,
            // Pass onValidate for auto-validate on upload, but hide the button
            onValidate: widget.onValidate != null ? _autoValidateWrapper : null,
            autoValidateOnUpload: true,
            showValidateButton:
                false, // We manage our own validate button below
            constraints: widget.constraints,
            exampleContent: widget.exampleContent,
            isHighlighted: true,
            showHeader: false,
          ),

          const SizedBox(height: 16),

          // 2. Requirements toggle button
          Center(
            child: TextButton.icon(
              onPressed: _toggleRequirements,
              icon: Icon(
                _showRequirements
                    ? Icons.remove_circle_outline
                    : Icons.add_circle_outline,
                size: 18,
              ),
              label: Text(
                _showRequirements
                    ? 'Remove requirements.txt'
                    : 'Add requirements.txt',
                style: const TextStyle(fontSize: 13),
              ),
              style: TextButton.styleFrom(
                foregroundColor: isDark
                    ? Colors.grey.shade400
                    : Colors.grey.shade600,
              ),
            ),
          ),

          // 3. Requirements editor (when visible)
          if (_showRequirements) ...[
            const SizedBox(height: 8),
            Divider(
              color: isDark ? Colors.grey.shade700 : Colors.grey.shade300,
              height: 1,
            ),
            const SizedBox(height: 16),

            // Requirements filename header
            Row(
              children: [
                Icon(Icons.list_alt, color: Colors.grey.shade500, size: 18),
                const SizedBox(width: 8),
                Text(
                  'requirements.txt',
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    fontFamily: 'monospace',
                    fontSize: 13,
                    color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // Requirements editor
            FileEditorBlock(
              filename: 'requirements.txt',
              description: 'Python package dependencies',
              initialContent: widget.requirementsContent ?? '',
              onContentChanged: (content) =>
                  widget.onRequirementsChanged(content),
              showHeader: false,
            ),
          ],

          // 4. Validate button (only if validation is supported)
          if (widget.onValidate != null) ...[
            const SizedBox(height: 16),
            Center(
              child: ElevatedButton.icon(
                onPressed:
                    _isValidating || (widget.codeContent?.isEmpty ?? true)
                    ? null
                    : _validateCode,
                icon: _isValidating
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(
                        _isValid == true
                            ? Icons.check_circle
                            : Icons.play_arrow,
                        size: 18,
                      ),
                label: Text(_isValidating ? 'Validating...' : 'Validate'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: _isValid == true
                      ? Colors.green.shade600
                      : primaryColor,
                  foregroundColor: Colors.white,
                ),
              ),
            ),
          ],

          // 5. Validation feedback
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
                  color: _isValid == true
                      ? Colors.green.shade600
                      : Colors.red.shade400,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    _isValid == true ? Icons.check_circle : Icons.error,
                    color: _isValid == true
                        ? Colors.green.shade400
                        : Colors.red.shade400,
                    size: 18,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _validationMessage!,
                      style: TextStyle(
                        color: _isValid == true
                            ? Colors.green.shade300
                            : Colors.red.shade300,
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
}
