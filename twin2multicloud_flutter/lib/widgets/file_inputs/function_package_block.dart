import 'package:flutter/material.dart';
import 'file_editor_block.dart';
import 'collapsible_block_wrapper.dart';

/// A composite widget for Python function packages (code + optional requirements.txt).
/// 
/// Uses composition over mutation - wraps two FileEditorBlock instances instead
/// of adding complexity to FileEditorBlock directly.
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
  
  /// Validation callback for Python code only
  final Future<Map<String, dynamic>> Function(String code)? onValidate;
  
  /// Whether the code is validated (from BLoC)
  final bool isCodeValidated;
  
  /// Optional constraints text to display
  final String? constraints;
  
  /// Optional example content for the code editor
  final String? exampleContent;
  
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
  });
  
  @override
  State<FunctionPackageBlock> createState() => _FunctionPackageBlockState();
}

class _FunctionPackageBlockState extends State<FunctionPackageBlock> {
  bool _showRequirements = false;
  
  @override
  void initState() {
    super.initState();
    // Show requirements section if content exists (hydrated from DB)
    _showRequirements = widget.requirementsContent != null && 
                        widget.requirementsContent!.isNotEmpty;
  }
  
  @override
  void didUpdateWidget(FunctionPackageBlock oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Sync visibility when content changes externally (hydration)
    if (widget.requirementsContent != oldWidget.requirementsContent) {
      final hasContent = widget.requirementsContent != null && 
                         widget.requirementsContent!.isNotEmpty;
      if (hasContent && !_showRequirements) {
        setState(() => _showRequirements = true);
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
  
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return CollapsibleBlockWrapper(
      title: widget.codeFilename,
      subtitle: widget.description,
      icon: Icons.code,
      isValid: widget.isCodeValidated ? true : null,
      showEditBadge: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Python code editor (no validate button - we'll add our own at bottom)
          FileEditorBlock(
            filename: widget.codeFilename,
            description: widget.description,
            initialContent: widget.codeContent,
            isValidated: widget.isCodeValidated,
            onContentChanged: widget.onCodeChanged,
            // No onValidate here - button is at bottom
            constraints: widget.constraints,
            exampleContent: widget.exampleContent,
            isHighlighted: true,
            showHeader: false,
          ),
          
          const SizedBox(height: 16),
          
          // Requirements toggle button
          Center(
            child: TextButton.icon(
              onPressed: _toggleRequirements,
              icon: Icon(
                _showRequirements ? Icons.remove_circle_outline : Icons.add_circle_outline,
                size: 18,
              ),
              label: Text(
                _showRequirements ? 'Remove requirements.txt' : 'Add requirements.txt',
                style: const TextStyle(fontSize: 13),
              ),
              style: TextButton.styleFrom(
                foregroundColor: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
              ),
            ),
          ),
          
          // Requirements editor (when visible)
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
              onContentChanged: (content) => widget.onRequirementsChanged(content),
              showHeader: false,
            ),
          ],
          
          // Validate button at bottom (only if validation is supported)
          if (widget.onValidate != null) ...[
            const SizedBox(height: 16),
            Center(
              child: _ValidateButton(
                isValidated: widget.isCodeValidated,
                onValidate: () async {
                  if (widget.codeContent == null || widget.codeContent!.isEmpty) return;
                  await widget.onValidate!(widget.codeContent!);
                },
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Validate button widget extracted for cleaner code
class _ValidateButton extends StatefulWidget {
  final bool isValidated;
  final Future<void> Function() onValidate;
  
  const _ValidateButton({
    required this.isValidated,
    required this.onValidate,
  });
  
  @override
  State<_ValidateButton> createState() => _ValidateButtonState();
}

class _ValidateButtonState extends State<_ValidateButton> {
  bool _isValidating = false;
  
  Future<void> _handleValidate() async {
    setState(() => _isValidating = true);
    try {
      await widget.onValidate();
    } finally {
      if (mounted) {
        setState(() => _isValidating = false);
      }
    }
  }
  
  @override
  Widget build(BuildContext context) {
    final primaryColor = Theme.of(context).colorScheme.primary;
    
    return ElevatedButton.icon(
      onPressed: _isValidating ? null : _handleValidate,
      icon: _isValidating
          ? const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : Icon(
              widget.isValidated ? Icons.check_circle : Icons.play_arrow,
              size: 18,
            ),
      label: Text(_isValidating ? 'Validating...' : 'Validate'),
      style: ElevatedButton.styleFrom(
        backgroundColor: widget.isValidated ? Colors.green.shade600 : primaryColor,
        foregroundColor: Colors.white,
      ),
    );
  }
}
