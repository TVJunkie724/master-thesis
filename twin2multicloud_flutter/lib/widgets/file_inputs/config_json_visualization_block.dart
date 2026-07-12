import 'dart:convert';
import 'package:flutter/material.dart';
import '../../models/deployer_artifact_validation.dart';
import 'artifact_validation_feedback_view.dart';

/// Split-view config block for config.json with:
/// - Static fields from previous steps (mode, storage days)
/// - Editable field (digital_twin_name)
/// - Validation button with inline result
///
/// Matches the layout of ConfigVisualizationBlock but allows partial editing.
class ConfigJsonVisualizationBlock extends StatefulWidget {
  final String? twinName;
  final String? mode; // From Step 1
  final int hotStorageDays; // From Step 2
  final int coldStorageDays; // From Step 2
  final bool isValidated; // From BLoC - persisted validation state
  final Function(String) onTwinNameChanged;
  final ValueChanged<Map<String, dynamic>>? onValidate;
  final bool isValidating;
  final DeployerArtifactValidationFeedback? validationFeedback;

  /// When false, skips header row and outer container (for use with CollapsibleBlockWrapper)
  final bool showHeader;

  const ConfigJsonVisualizationBlock({
    super.key,
    required this.twinName,
    required this.mode,
    required this.hotStorageDays,
    required this.coldStorageDays,
    this.isValidated = false,
    required this.onTwinNameChanged,
    this.onValidate,
    this.isValidating = false,
    this.validationFeedback,
    this.showHeader = true,
  });

  @override
  State<ConfigJsonVisualizationBlock> createState() =>
      _ConfigJsonVisualizationBlockState();
}

class _ConfigJsonVisualizationBlockState
    extends State<ConfigJsonVisualizationBlock> {
  late TextEditingController _twinNameController;

  // Neutral color for icons (pink removed)

  @override
  void initState() {
    super.initState();
    _twinNameController = TextEditingController(text: widget.twinName ?? '');
  }

  @override
  void didUpdateWidget(ConfigJsonVisualizationBlock oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Update controller if external twin name changed
    if (widget.twinName != oldWidget.twinName &&
        widget.twinName != _twinNameController.text) {
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
      'mode': (widget.mode ?? 'production')
          .toUpperCase(), // Deployer expects uppercase
      'hot_storage_size_in_days': widget.hotStorageDays,
      'cold_storage_size_in_days': widget.coldStorageDays,
    };
  }

  String get _jsonContent {
    return const JsonEncoder.withIndent('  ').convert(_buildConfigJson());
  }

  void _validate() {
    widget.onValidate?.call(_buildConfigJson());
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final borderColor = isDark ? Colors.grey.shade700 : Colors.grey.shade300;

    // Content column (shared between wrapped and standalone modes)
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Header row (only when not wrapped)
        if (widget.showHeader) ...[
          Row(
            children: [
              Icon(Icons.settings, color: Colors.grey.shade500, size: 22),
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
                        color: isDark
                            ? Colors.grey.shade300
                            : Colors.grey.shade700,
                      ),
                    ),
                    Text(
                      'Core deployment configuration',
                      style: TextStyle(
                        color: Colors.grey.shade600,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              // EDIT badge (same as FileEditorBlock)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFFD81B60),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Text(
                  'EDIT',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              // Auto badge for static fields
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.blue.shade700.withAlpha(isDark ? 80 : 40),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(
                    color: Colors.blue.shade400.withAlpha(100),
                  ),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.auto_mode,
                      size: 12,
                      color: Colors.blue.shade400,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'Generated from configuration',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w500,
                        color: Colors.blue.shade300,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
        ],

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
            setState(() {});
          },
          decoration: InputDecoration(
            hintText: 'e.g., my_digital_twin',
            helperText:
                'Lowercase alphanumeric with hyphens or underscores (e.g., factory_sensor_01)',
            helperStyle: TextStyle(fontSize: 11, color: Colors.grey.shade500),
            prefixIcon: Icon(
              Icons.edit,
              color: Theme.of(context).colorScheme.primary,
              size: 20,
            ),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 14,
              vertical: 14,
            ),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: BorderSide(
                color: Theme.of(context).colorScheme.primary,
                width: 2,
              ),
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
                      color: const Color(
                        0xFF2A2A2A,
                      ), // Slightly grey-tinted dark
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.grey.shade700, width: 1),
                    ),
                    child: SingleChildScrollView(
                      child: SelectableText(
                        _jsonContent,
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 12,
                          height: 1.4,
                          color: Colors
                              .grey
                              .shade500, // Greyed out text - no syntax highlighting
                        ),
                      ),
                    ),
                  ),
                  // Read-only indicator
                  Positioned(
                    top: 6,
                    right: 6,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 6,
                        vertical: 2,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.grey.shade800,
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.lock,
                            size: 10,
                            color: Colors.grey.shade400,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            'Read-only',
                            style: TextStyle(
                              fontSize: 9,
                              color: Colors.grey.shade400,
                            ),
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
                      color: isDark
                          ? Colors.grey.shade300
                          : Colors.grey.shade700,
                    ),
                  ),
                  const SizedBox(height: 10),

                  // Static: Mode
                  _buildStaticField(
                    'Mode',
                    widget.mode ?? 'production',
                    'Identity and mode',
                    isDark,
                  ),

                  const SizedBox(height: 8),

                  // Static: Storage days
                  _buildStaticField(
                    'Hot Storage',
                    '${widget.hotStorageDays} days',
                    'Workload intent',
                    isDark,
                  ),
                  const SizedBox(height: 4),
                  _buildStaticField(
                    'Cold Storage',
                    '${widget.coldStorageDays} days',
                    'Workload intent',
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
          child: Tooltip(
            message: 'Validate config.json',
            child: FilledButton.icon(
              onPressed: widget.isValidating || _twinNameController.text.isEmpty
                  ? null
                  : _validate,
              icon: widget.isValidating
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.check_circle),
              label: const Text('Validate'),
              style: FilledButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                  vertical: 12,
                  horizontal: 24,
                ),
                // Use theme primary instead of pink for consistency with Step 1
              ),
            ),
          ),
        ),

        // Validation result
        if (widget.isValidating || widget.validationFeedback != null) ...[
          const SizedBox(height: 12),
          ArtifactValidationFeedbackView(
            feedback: widget.validationFeedback,
            isValidating: widget.isValidating,
          ),
        ],
      ],
    );

    // When showHeader is false, return content directly (wrapper handles container)
    if (!widget.showHeader) {
      return content;
    }

    // Standalone mode - wrap in Container with border/background
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF2D2D2D) : Colors.grey.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: widget.isValidated ? Colors.green.shade600 : borderColor,
          width: widget.isValidated ? 2 : 1,
        ),
      ),
      child: content,
    );
  }

  Widget _buildStaticField(
    String label,
    String value,
    String source,
    bool isDark,
  ) {
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
