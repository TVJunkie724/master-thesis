import 'package:flutter/material.dart';

import '../../theme/spacing.dart';

/// Presentation-only project ZIP selector.
class ZipUploadBlock extends StatefulWidget {
  final String? selectedFileName;
  final bool isUploading;
  final bool hasError;
  final Future<void> Function() onSelect;
  final VoidCallback onClear;

  const ZipUploadBlock({
    super.key,
    required this.selectedFileName,
    required this.isUploading,
    required this.hasError,
    required this.onSelect,
    required this.onClear,
  });

  @override
  State<ZipUploadBlock> createState() => _ZipUploadBlockState();
}

class _ZipUploadBlockState extends State<ZipUploadBlock> {
  bool _isHovering = false;

  static const String _exampleStructure = '''
project.zip
├── config.json                       # Main config (twin name, storage days)
├── config_credentials.json           # Cloud provider credentials (not committed)
├── config_events.json                # Event-driven automation rules
├── config_iot_devices.json           # IoT device definitions
├── config_optimization.json          # Optimizer output (layer providers)
├── config_providers.json             # Provider assignments per layer
├── config_user.json                  # Platform user config (Grafana admin)
│
├── lambda_functions/                 # AWS Lambda functions (if layer_2=aws)
│   ├── processors/device-id/
│   │   └── lambda_function.py
│   ├── event_actions/action-name/
│   │   └── lambda_function.py
│   └── event-feedback/
│       └── lambda_function.py
├── azure_functions/processors/device-id/function_app.py
├── cloud_functions/processors/device-id/main.py
├── twin_hierarchy/
│   ├── aws_hierarchy.json
│   └── azure_hierarchy.json
├── scene_assets/
│   ├── scene.json
│   ├── 3DScenesConfiguration.json
│   └── scene.glb
└── iot_device_simulator/
    └── payloads.json
''';

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final primaryColor = Theme.of(context).colorScheme.primary;
    final selectedFileName = widget.selectedFileName;
    final hasErrors = widget.hasError && selectedFileName != null;

    return Column(
      key: const ValueKey('zip-upload-block'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        MouseRegion(
          onEnter: (_) => setState(() => _isHovering = true),
          onExit: (_) => setState(() => _isHovering = false),
          child: GestureDetector(
            onTap: widget.isUploading ? null : widget.onSelect,
            child: AnimatedContainer(
              duration: const Duration(
                milliseconds: AppSpacing.animationFastMs,
              ),
              height: 140,
              decoration: BoxDecoration(
                color: _isHovering
                    ? primaryColor.withAlpha(20)
                    : (isDark
                          ? Colors.grey.shade800.withAlpha(50)
                          : Colors.grey.shade50),
                borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
                border: Border.all(
                  color: selectedFileName != null
                      ? (hasErrors
                            ? Colors.orange.shade500
                            : Colors.green.shade500)
                      : (_isHovering
                            ? primaryColor
                            : (isDark
                                  ? Colors.grey.shade600
                                  : Colors.grey.shade400)),
                  width: _isHovering || selectedFileName != null ? 2 : 1,
                ),
              ),
              child: widget.isUploading
                  ? _buildUploadingState(context)
                  : selectedFileName != null
                  ? _buildSelectedState(selectedFileName, hasErrors: hasErrors)
                  : _buildEmptyState(isDark),
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.md - AppSpacing.xs),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => _showExampleStructureDialog(context),
                icon: const Icon(Icons.account_tree, size: AppSpacing.iconMd),
                label: const Text('Example Structure'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    vertical: AppSpacing.md - AppSpacing.xs,
                  ),
                ),
              ),
            ),
            if (selectedFileName != null && !widget.isUploading) ...[
              const SizedBox(width: AppSpacing.md - AppSpacing.xs),
              OutlinedButton.icon(
                onPressed: widget.onClear,
                icon: const Icon(Icons.clear, size: AppSpacing.iconMd),
                label: const Text('Clear'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    vertical: AppSpacing.md - AppSpacing.xs,
                    horizontal: AppSpacing.md,
                  ),
                  foregroundColor: Colors.red.shade400,
                ),
              ),
            ],
          ],
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Upload project.zip to auto-populate all fields below.',
          style: TextStyle(
            fontSize: 11,
            color: isDark ? Colors.grey.shade500 : Colors.grey.shade600,
            fontStyle: FontStyle.italic,
          ),
        ),
      ],
    );
  }

  Widget _buildEmptyState(bool isDark) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(
          Icons.cloud_upload_outlined,
          size: 40,
          color: isDark ? Colors.grey.shade500 : Colors.grey.shade400,
        ),
        const SizedBox(height: AppSpacing.md - AppSpacing.xs),
        Text(
          'Drop project.zip here or click to upload',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          'Supports .zip files only',
          style: TextStyle(
            fontSize: 11,
            color: isDark ? Colors.grey.shade600 : Colors.grey.shade500,
          ),
        ),
      ],
    );
  }

  Widget _buildSelectedState(
    String selectedFileName, {
    required bool hasErrors,
  }) {
    final statusColor = hasErrors ? Colors.orange : Colors.green;
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(Icons.folder_zip, size: 36, color: statusColor.shade500),
        const SizedBox(width: AppSpacing.md),
        Flexible(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                selectedFileName,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: statusColor.shade400,
                  fontFamily: 'monospace',
                ),
              ),
              const SizedBox(height: AppSpacing.xs),
              Row(
                children: [
                  Icon(
                    hasErrors ? Icons.warning_amber : Icons.check_circle,
                    size: 14,
                    color: statusColor.shade500,
                  ),
                  const SizedBox(width: AppSpacing.sm - AppSpacing.xxs),
                  Flexible(
                    child: Text(
                      hasErrors
                          ? 'Extraction complete with errors'
                          : 'Extraction complete',
                      style: TextStyle(
                        fontSize: 12,
                        color: statusColor.shade400,
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildUploadingState(BuildContext context) {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const SizedBox(
          width: AppSpacing.xl,
          height: AppSpacing.xl,
          child: CircularProgressIndicator(strokeWidth: 3),
        ),
        const SizedBox(height: AppSpacing.md - AppSpacing.xs),
        Text(
          'Extracting and validating...',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: Theme.of(context).colorScheme.primary,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          'This may take a few seconds',
          style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
        ),
      ],
    );
  }

  void _showExampleStructureDialog(BuildContext context) {
    showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Row(
          children: [
            Icon(
              Icons.folder_zip,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: AppSpacing.md - AppSpacing.xs),
            const Text('Project Zip Structure'),
          ],
        ),
        content: Container(
          constraints: const BoxConstraints(maxWidth: 700, maxHeight: 500),
          decoration: BoxDecoration(
            color: const Color(0xFF1E1E1E),
            borderRadius: BorderRadius.circular(AppSpacing.borderRadiusSm),
          ),
          padding: const EdgeInsets.all(AppSpacing.md),
          child: const SingleChildScrollView(
            child: SelectableText(
              _exampleStructure,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: Color(0xFFA5D6A7),
                height: 1.4,
              ),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}
