import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import '../../utils/api_error_handler.dart';

/// Zip file upload block with drop zone UI.
/// Shows example project structure in a bash-style popup.
class ZipUploadBlock extends StatefulWidget {
  final Function(String path)? onZipSelected;
  
  const ZipUploadBlock({
    super.key,
    this.onZipSelected,
  });
  
  @override
  State<ZipUploadBlock> createState() => _ZipUploadBlockState();
}

class _ZipUploadBlockState extends State<ZipUploadBlock> {
  String? _selectedFilePath;
  String? _selectedFileName;
  bool _isHovering = false;
  
  // Example project structure (bash tree-like format)
  static const String _exampleStructure = '''
project.zip
├── config.json                    # Main config (twin name, storage days)
├── config_credentials.json        # Cloud provider credentials
├── config_events.json             # Event-driven automation rules
├── config_iot_devices.json        # IoT device definitions
├── config_optimization.json       # Optimizer output (layer providers)
├── config_providers.json          # Provider assignments per layer
├── config_user.json               # Platform user config
│
├── lambda_functions/              # AWS Lambda / Azure Functions / GCP Cloud Functions
│   ├── processors/                # User processor functions (per device)
│   │   ├── temperature-sensor-1/
│   │   │   └── index.py
│   │   └── pressure-sensor-1/
│   │       └── index.py
│   ├── event_actions/             # Event callback functions
│   │   └── high-temperature-callback/
│   │       └── index.py
│   └── feedback/                  # Feedback handler functions
│       └── feedback-handler/
│           └── index.py
│
├── state_machines/                # Workflow definitions
│   ├── aws_step_function.json     # AWS Step Functions
│   ├── azure_logic_app.json       # Azure Logic Apps
│   └── google_cloud_workflow.yaml # GCP Workflows
│
├── scene_assets/                  # 3D visualization assets
│   ├── 3DScenesConfiguration.json # Azure Digital Twins 3D config
│   └── models/                    # 3D model files
│       └── factory.glb
│
├── twin_hierarchy/                # Entity hierarchy definitions
│   └── hierarchy.json
│
└── iot_device_simulator/          # Test payload simulator
    └── payloads.json
''';
  
  Future<void> _pickZipFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['zip'],
      );
      
      if (result != null && result.files.isNotEmpty) {
        setState(() {
          _selectedFilePath = result.files.single.path;
          _selectedFileName = result.files.single.name;
        });
        
        if (_selectedFilePath != null) {
          widget.onZipSelected?.call(_selectedFilePath!);
        }
      }
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to select file: ${ApiErrorHandler.extractMessage(e)}'),
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
      _selectedFilePath = null;
      _selectedFileName = null;
    });
  }
  
  @override
  Widget build(BuildContext context) {
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
            onTap: _pickZipFile,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              height: 140,
              decoration: BoxDecoration(
                color: _isHovering 
                    ? primaryColor.withAlpha(20) 
                    : (isDark ? Colors.grey.shade800.withAlpha(50) : Colors.grey.shade50),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(
                  color: _selectedFileName != null 
                      ? Colors.green.shade500
                      : (_isHovering ? primaryColor : (isDark ? Colors.grey.shade600 : Colors.grey.shade400)),
                  width: _isHovering || _selectedFileName != null ? 2 : 1,
                  style: BorderStyle.solid,
                ),
              ),
              child: _selectedFileName != null 
                  ? _buildSelectedState()
                  : _buildEmptyState(isDark),
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
            if (_selectedFileName != null) ...[
              const SizedBox(width: 12),
              OutlinedButton.icon(
                onPressed: _clearSelection,
                icon: const Icon(Icons.clear, size: 18),
                label: const Text('Clear'),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
                  foregroundColor: Colors.red.shade400,
                ),
              ),
            ],
          ],
        ),
        
        const SizedBox(height: 8),
        
        // Info text
        Text(
          'Auto-extraction coming soon. For now, upload individual files below.',
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
  
  Widget _buildSelectedState() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Icon(Icons.folder_zip, size: 36, color: Colors.green.shade500),
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
                color: Colors.green.shade400,
                fontFamily: 'monospace',
              ),
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(Icons.check_circle, size: 14, color: Colors.green.shade500),
                const SizedBox(width: 6),
                Text(
                  'File selected',
                  style: TextStyle(fontSize: 12, color: Colors.green.shade400),
                ),
              ],
            ),
          ],
        ),
      ],
    );
  }
}
