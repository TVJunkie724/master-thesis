import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:file_picker/file_picker.dart';
import '../../utils/api_error_handler.dart';
import '../../bloc/wizard/wizard_bloc.dart';
import '../../bloc/wizard/wizard_event.dart';
import '../../bloc/wizard/wizard_state.dart';

/// Zip file upload block with drop zone UI.
/// Integrates with WizardBloc to auto-populate Step 3 fields from project.zip.
class ZipUploadBlock extends StatefulWidget {
  const ZipUploadBlock({super.key});

  @override
  State<ZipUploadBlock> createState() => _ZipUploadBlockState();
}

class _ZipUploadBlockState extends State<ZipUploadBlock> {
  String? _selectedFileName;
  bool _isHovering = false;

  // Example project structure (bash tree-like format)
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
│   ├── processors/                   # User processor functions (per device)
│   │   └── device-id/
│   │       └── lambda_function.py    # def lambda_handler(event, context)
│   ├── event_actions/                # Event callback functions
│   │   └── action-name/
│   │       └── lambda_function.py
│   └── event-feedback/               # Feedback handler
│       └── lambda_function.py
│
├── azure_functions/                  # Azure Functions (if layer_2=azure)
│   └── processors/device-id/
│       └── function_app.py           # def main(req: func.HttpRequest)
│
├── cloud_functions/                  # GCP Cloud Functions (if layer_2=google)
│   └── processors/device-id/
│       └── main.py                   # def process(request)
│
├── twin_hierarchy/                   # Digital twin entity hierarchy
│   ├── aws_hierarchy.json            # TwinMaker entities (if layer_4=aws)
│   └── azure_hierarchy.json          # ADT twins/models (if layer_4=azure)
│
├── scene_assets/                     # 3D visualization assets
│   ├── scene.json                    # TwinMaker scene config (if layer_4=aws)
│   ├── 3DScenesConfiguration.json    # Azure 3D Scenes config (if layer_4=azure)
│   └── scene.glb                     # 3D model file (GLTF binary)
│
└── iot_device_simulator/             # Test payload simulator
    └── payloads.json
''';

  Future<void> _pickZipFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['zip'],
        withData: true, // Get bytes for upload
      );

      if (result != null && result.files.isNotEmpty) {
        final file = result.files.single;
        setState(() {
          _selectedFileName = file.name;
        });

        // Trigger upload via BLoC
        if (file.bytes != null && file.path != null && mounted) {
          context.read<WizardBloc>().add(
            WizardZipUploadRequested(
              filePath: file.path!,
              fileBytes: file.bytes!,
              fileName: file.name,
            ),
          );
        }
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Failed to select file: ${ApiErrorHandler.extractMessage(e)}',
          ),
          backgroundColor: Colors.red.shade700,
        ),
      );
    }
  }

  void _showExampleStructureDialog() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.folder_zip, color: Theme.of(context).primaryColor),
            const SizedBox(width: 12),
            const Text('Project Zip Structure'),
          ],
        ),
        content: Container(
          constraints: const BoxConstraints(maxWidth: 700, maxHeight: 500),
          decoration: BoxDecoration(
            color: const Color(0xFF1E1E1E),
            borderRadius: BorderRadius.circular(8),
          ),
          padding: const EdgeInsets.all(16),
          child: SingleChildScrollView(
            child: SelectableText(
              _exampleStructure,
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 12,
                color: Colors.green.shade300,
                height: 1.4,
              ),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _clearSelection() {
    setState(() {
      _selectedFileName = null;
    });
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<WizardBloc, WizardState>(
      listenWhen: (prev, curr) =>
          prev.zipUploadPending != curr.zipUploadPending ||
          prev.zipUploadInProgress != curr.zipUploadInProgress,
      listener: (context, state) {
        // Show confirmation dialog when existing data would be replaced
        if (state.zipUploadPending && state.pendingZipFileName != null) {
          _showConfirmationDialog(context, state);
        }
      },
      builder: (context, state) {
        final isUploading = state.zipUploadInProgress;
        final hasErrors =
            state.errorMessage != null && _selectedFileName != null;
        final isDark = Theme.of(context).brightness == Brightness.dark;
        final primaryColor = Theme.of(context).primaryColor;

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Drop zone
            MouseRegion(
              onEnter: (_) => setState(() => _isHovering = true),
              onExit: (_) => setState(() => _isHovering = false),
              child: GestureDetector(
                onTap: isUploading ? null : _pickZipFile,
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 150),
                  height: 140,
                  decoration: BoxDecoration(
                    color: _isHovering
                        ? primaryColor.withAlpha(20)
                        : (isDark
                              ? Colors.grey.shade800.withAlpha(50)
                              : Colors.grey.shade50),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: _selectedFileName != null
                          ? (hasErrors
                                ? Colors.orange.shade500
                                : Colors.green.shade500)
                          : (_isHovering
                                ? primaryColor
                                : (isDark
                                      ? Colors.grey.shade600
                                      : Colors.grey.shade400)),
                      width: _isHovering || _selectedFileName != null ? 2 : 1,
                      style: BorderStyle.solid,
                    ),
                  ),
                  child: isUploading
                      ? _buildUploadingState()
                      : (_selectedFileName != null
                            ? _buildSelectedState(hasErrors: hasErrors)
                            : _buildEmptyState(isDark)),
                ),
              ),
            ),

            const SizedBox(height: 12),

            // Buttons row
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _showExampleStructureDialog,
                    icon: const Icon(Icons.account_tree, size: 18),
                    label: const Text('Example Structure'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 12),
                    ),
                  ),
                ),
                if (_selectedFileName != null && !isUploading) ...[
                  const SizedBox(width: 12),
                  OutlinedButton.icon(
                    onPressed: _clearSelection,
                    icon: const Icon(Icons.clear, size: 18),
                    label: const Text('Clear'),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        vertical: 12,
                        horizontal: 16,
                      ),
                      foregroundColor: Colors.red.shade400,
                    ),
                  ),
                ],
              ],
            ),

            const SizedBox(height: 8),

            // Info text
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
      },
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
        const SizedBox(height: 12),
        Text(
          'Drop project.zip here or click to upload',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: isDark ? Colors.grey.shade400 : Colors.grey.shade600,
          ),
        ),
        const SizedBox(height: 4),
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

  Widget _buildSelectedState({bool hasErrors = false}) {
    final statusColor = hasErrors ? Colors.orange : Colors.green;
    final statusIcon = hasErrors ? Icons.warning_amber : Icons.check_circle;
    final statusText = hasErrors
        ? 'Extraction complete with errors'
        : 'Extraction complete';

    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(Icons.folder_zip, size: 36, color: statusColor.shade500),
        const SizedBox(width: 16),
        Column(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              _selectedFileName!,
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: statusColor.shade400,
                fontFamily: 'monospace',
              ),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(statusIcon, size: 14, color: statusColor.shade500),
                const SizedBox(width: 6),
                Text(
                  statusText,
                  style: TextStyle(fontSize: 12, color: statusColor.shade400),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildUploadingState() {
    return Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const SizedBox(
          width: 32,
          height: 32,
          child: CircularProgressIndicator(strokeWidth: 3),
        ),
        const SizedBox(height: 12),
        Text(
          'Extracting and validating...',
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: Theme.of(context).primaryColor,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'This may take a few seconds',
          style: TextStyle(fontSize: 11, color: Colors.grey.shade500),
        ),
      ],
    );
  }

  void _showConfirmationDialog(BuildContext context, WizardState state) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        icon: Icon(
          Icons.warning_amber,
          size: 48,
          color: Colors.orange.shade700,
        ),
        title: const Text('Replace Existing Data?'),
        content: const Text(
          'Uploading this zip will replace your current Step 3 configuration.\n\n'
          'This includes events, devices, payloads, processors, and other fields '
          'you have already entered.\n\n'
          'This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              // Cancel - reset pending state
              context.read<WizardBloc>().add(const WizardClearNotifications());
              _clearSelection();
            },
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(ctx);
              // Confirm - proceed with upload
              final bytes = state.pendingZipFileBytes;
              if (bytes != null) {
                context.read<WizardBloc>().add(
                  WizardZipUploadConfirmed(
                    filePath: state.pendingZipFilePath ?? '',
                    fileBytes: bytes,
                    fileName: state.pendingZipFileName ?? '',
                  ),
                );
              }
            },
            style: FilledButton.styleFrom(
              backgroundColor: Colors.orange.shade700,
            ),
            child: const Text('Replace'),
          ),
        ],
      ),
    );
  }
}
