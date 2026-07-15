import 'package:flutter/material.dart';
import 'file_editor_block.dart';
import 'collapsible_block_wrapper.dart';
import 'artifact_validation_feedback_view.dart';
import '../../models/deployer_artifact_validation.dart';

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
  final ValueChanged<String>? onValidate;
  final bool isValidating;
  final DeployerArtifactValidationFeedback? validationFeedback;

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
    this.isValidating = false,
    this.validationFeedback,
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

  @override
  void initState() {
    super.initState();
    // Show requirements section if content exists (hydrated from DB)
    _showRequirements =
        widget.requirementsContent != null &&
        widget.requirementsContent!.isNotEmpty;
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
    widget.onCodeChanged(content);
  }

  /// Validate the current code content
  void _validateCode() {
    if (widget.onValidate == null) return;
    if (widget.codeContent == null || widget.codeContent!.isEmpty) return;
    widget.onValidate!(widget.codeContent!);
  }

  /// Wrapper for FileEditorBlock that auto-validates after upload
  void _autoValidateWrapper(String content) {
    widget.onValidate?.call(content);
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
            isValidating: widget.isValidating,
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
              child: Tooltip(
                message: 'Validate ${widget.codeFilename}',
                child: ElevatedButton.icon(
                  onPressed:
                      widget.isValidating ||
                          (widget.codeContent?.isEmpty ?? true)
                      ? null
                      : _validateCode,
                  icon: widget.isValidating
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Icon(
                          widget.isCodeValidated
                              ? Icons.check_circle
                              : Icons.play_arrow,
                          size: 18,
                        ),
                  label: Text(
                    widget.isValidating ? 'Validating...' : 'Validate',
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: widget.isCodeValidated
                        ? Colors.green.shade600
                        : primaryColor,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            ),
          ],

          // 5. Validation feedback
          if (widget.isValidating || widget.validationFeedback != null) ...[
            const SizedBox(height: 12),
            ArtifactValidationFeedbackView(
              feedback: widget.validationFeedback,
              isValidating: widget.isValidating,
            ),
          ],
        ],
      ),
    );
  }
}
