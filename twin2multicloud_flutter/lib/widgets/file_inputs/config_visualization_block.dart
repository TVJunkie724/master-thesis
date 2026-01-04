import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../theme/colors.dart';


/// Split-view config block with visual summary on left and JSON on right.
/// Used for auto-generated config_optimization.json and config_providers.json.
class ConfigVisualizationBlock extends StatelessWidget {
  final String filename;
  final String description;
  final String jsonContent;
  final IconData icon;
  final String? sourceLabel;
  final Widget visualContent;
  
  const ConfigVisualizationBlock({
    super.key,
    required this.filename,
    required this.description,
    required this.jsonContent,
    required this.visualContent,
    this.icon = Icons.code,
    this.sourceLabel,
  });
  
  void _copyToClipboard(BuildContext context) {
    Clipboard.setData(ClipboardData(text: jsonContent));
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$filename copied to clipboard'),
        duration: const Duration(seconds: 2),
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
        color: isDark ? Colors.grey.shade800.withAlpha(100) : Colors.grey.shade100,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark ? Colors.grey.shade700 : Colors.grey.shade300,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header row
          Row(
            children: [
              Icon(icon, color: Colors.grey.shade500, size: 20),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      filename,
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        fontFamily: 'monospace',
                        fontSize: 14,
                        color: isDark ? Colors.grey.shade300 : Colors.grey.shade700,
                      ),
                    ),
                    Text(
                      description,
                      style: TextStyle(
                        fontSize: 12,
                        color: isDark ? Colors.grey.shade500 : Colors.grey.shade600,
                      ),
                    ),
                  ],
                ),
              ),
              // Auto-generated badge
              if (sourceLabel != null)
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
                        sourceLabel!,
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
                onPressed: () => _copyToClipboard(context),
                icon: Icon(Icons.copy, size: 18, color: Colors.grey.shade500),
                tooltip: 'Copy to clipboard',
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
              ),
            ],
          ),
          
          const SizedBox(height: 12),
          
          // Split content: Visual on left, JSON on right
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Left: JSON code view (2/3 width)
              Expanded(
                flex: 2,
                child: Container(
                  height: 200,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1E1E1E),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: SingleChildScrollView(
                    child: SelectableText(
                      jsonContent.isEmpty ? '// No content' : jsonContent,
                      style: TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 11,
                        height: 1.4,
                        color: jsonContent.isEmpty ? Colors.grey : Colors.grey.shade400,
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 16),
              // Right: Visual representation (1/3 width)
              Expanded(
                flex: 1,
                child: visualContent,
              ),
            ],
          ),
        ],
      ),
    );
  }
  
  /// Build visual representation for config_providers.json
  static Widget buildProvidersVisual(Map<String, String> layerProviders) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Layer Assignments',
          style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
        const SizedBox(height: 12),
        ...layerProviders.entries.map((e) => _buildLayerProviderRow(e.key, e.value)),
      ],
    );
  }
  
  static Widget _buildLayerProviderRow(String layer, String? provider) {
    final color = AppColors.getProviderColor(provider ?? '');
    final layerName = _layerDisplayName(layer);
    
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        children: [
          Container(
            width: 100,
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.grey.shade800,
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              layerName,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: Colors.white70,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Icon(Icons.arrow_forward, size: 14, color: Colors.grey.shade500),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: color.withAlpha(40),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: color.withAlpha(120)),
            ),
            child: Text(
              provider?.toUpperCase() ?? 'N/A',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ),
        ],
      ),
    );
  }
  
  static String _layerDisplayName(String key) {
    switch (key) {
      case 'layer_1_provider': return 'L1 Ingestion';
      case 'layer_2_provider': return 'L2 Processing';
      case 'layer_3_hot_provider': return 'L3 Hot Storage';
      case 'layer_3_cold_provider': return 'L3 Cold Storage';
      case 'layer_3_archive_provider': return 'L3 Archive';
      case 'layer_4_provider': return 'L4 Twin Mgmt';
      case 'layer_5_provider': return 'L5 Visualization';
      default: return key;
    }
  }
  
  /// Build visual representation for config_optimization.json
  static Widget buildOptimizationVisual({
    required Map<String, bool> inputParams,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Features Enabled',
          style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
        ),
        const SizedBox(height: 12),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: inputParams.entries
              .map((e) => _buildFeatureBadge(e.key, e.value))
              .toList(),
        ),
      ],
    );
  }
  
  static Widget _buildFeatureBadge(String feature, bool enabled) {
    final displayName = _featureDisplayName(feature);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: enabled ? Colors.green.withAlpha(30) : Colors.grey.withAlpha(20),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: enabled ? Colors.green.withAlpha(100) : Colors.grey.withAlpha(50),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            enabled ? Icons.check_circle : Icons.cancel,
            size: 12,
            color: enabled ? Colors.green.shade400 : Colors.grey.shade500,
          ),
          const SizedBox(width: 4),
          Text(
            displayName,
            style: TextStyle(
              fontSize: 10,
              color: enabled ? Colors.green.shade300 : Colors.grey.shade500,
            ),
          ),
        ],
      ),
    );
  }
  
  static String _featureDisplayName(String key) {
    switch (key) {
      case 'useEventChecking': return 'Event Checking';
      case 'triggerNotificationWorkflow': return 'Workflows';
      case 'returnFeedbackToDevice': return 'Device Feedback';
      // case 'integrateErrorHandling': return 'Error Handling';
      case 'needs3DModel': return '3D Scenes';
      default: return key;
    }
  }
}
