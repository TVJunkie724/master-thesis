import 'package:flutter/material.dart';
import '../../models/calc_result.dart';
import '../../theme/colors.dart';
import '../../theme/spacing.dart';

/// Card showing cost comparison for a single layer across providers
class LayerCostCard extends StatelessWidget {
  final String layer;
  final LayerCost? awsLayer;
  final LayerCost? azureLayer;
  final LayerCost? gcpLayer;
  final List<String> cheapestPath;
  final String? infoTitle;
  final String? infoBody;
  /// If true, hides the GCP row (used for L4/L5 where GCP is not implemented)
  final bool hideGcp;

  const LayerCostCard({
    super.key,
    required this.layer,
    this.awsLayer,
    this.azureLayer,
    this.gcpLayer,
    required this.cheapestPath,
    this.infoTitle,
    this.infoBody,
    this.hideGcp = false,
  });

  @override
  Widget build(BuildContext context) {
    // Extract L1, L2, L3_hot, etc. key for matching
    final layerKey = _getLayerKey(layer);
    
    // Find selected provider
    String? selectedProvider;
    for (final segment in cheapestPath) {
      if (segment.startsWith(layerKey)) {
        final parts = segment.split('_');
        // Handle L3_hot_GCP vs L1_GCP
        if (layerKey.startsWith('L3')) {
           // parts: [L3, hot, GCP] -> provider is index 2
           if (parts.length > 2) selectedProvider = parts[2];
        } else {
           // parts: [L1, GCP] -> provider is index 1
           if (parts.length > 1) selectedProvider = parts[1];
        }
        break;
      }
    }

    final Color borderColor = selectedProvider != null 
        ? AppColors.getProviderColor(selectedProvider)
        : Colors.transparent;

    // Check for glue code (heuristic: any component with 'dispatcher' or 'glue' or 'mover')
    bool includesGlueCode = _checkGlueCode(awsLayer) || 
                          _checkGlueCode(azureLayer) || 
                          _checkGlueCode(gcpLayer);

    return Card(
      elevation: AppSpacing.cardElevation,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
        side: BorderSide(color: borderColor.withAlpha(100), width: 2),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header Row
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        layer,
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      if (includesGlueCode)
                        Padding(
                          padding: const EdgeInsets.only(top: 4.0),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.cyan.shade100,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.hub, size: 10, color: Colors.cyan),
                                const SizedBox(width: 4),
                                Text(
                                  'Includes Glue Code',
                                  style: TextStyle(
                                    fontSize: 10, 
                                    color: Colors.cyan.shade900, 
                                    fontWeight: FontWeight.bold
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.info_outline, color: Colors.grey),
                  onPressed: () => _showInfoDialog(context, selectedProvider),
                  tooltip: 'Show breakdown',
                  constraints: const BoxConstraints(),
                  padding: EdgeInsets.zero,
                ),
              ],
            ),
            const Divider(height: 24),
            
            // Provider costs
            _buildProviderRow(
              context, 
              'AWS', 
              awsLayer?.cost, 
              AppColors.aws,
              selectedProvider?.toUpperCase() == 'AWS',
            ),
            const SizedBox(height: AppSpacing.sm),
            _buildProviderRow(
              context, 
              'Azure', 
              azureLayer?.cost, 
              AppColors.azure,
              selectedProvider?.toUpperCase() == 'AZURE',
            ),
            // Only show GCP row if not hidden (L4/L5 has GCP not implemented)
            if (!hideGcp) ...[
              const SizedBox(height: AppSpacing.sm),
              _buildProviderRow(
                context, 
                'GCP', 
                gcpLayer?.cost, 
                AppColors.gcp,
                selectedProvider?.toUpperCase() == 'GCP',
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _getLayerKey(String layerTitle) {
    if (layerTitle.contains('L1')) return 'L1';
    if (layerTitle.contains('L2')) return 'L2';
    if (layerTitle.contains('Hot')) return 'L3_hot';
    if (layerTitle.contains('Cool')) return 'L3_cool';
    if (layerTitle.contains('Archive')) return 'L3_archive';
    if (layerTitle.contains('L4')) return 'L4';
    if (layerTitle.contains('L5')) return 'L5';
    return 'L1';
  }

  bool _checkGlueCode(LayerCost? layer) {
    if (layer == null) return false;
    // Check if any component likely represents glue code
    // Common keys: dispatcher, glue, mover, orchestration
    for (final key in layer.components.keys) {
      final k = key.toLowerCase();
      if (k.contains('dispatcher') || 
          k.contains('glue') || 
          k.contains('mover')) {
        return true;
      }
    }
    return false;
  }

  void _showInfoDialog(BuildContext context, String? selectedProvider) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(layer),
        content: SizedBox(
          width: 400,
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildInfoSection(ctx, 'AWS', awsLayer, AppColors.aws, selectedProvider?.toUpperCase() == 'AWS'),
                const SizedBox(height: AppSpacing.md),
                _buildInfoSection(ctx, 'Azure', azureLayer, AppColors.azure, selectedProvider?.toUpperCase() == 'AZURE'),
                // Only show GCP section if not hidden
                if (!hideGcp) ...[
                  const SizedBox(height: AppSpacing.md),
                  _buildInfoSection(ctx, 'GCP', gcpLayer, AppColors.gcp, selectedProvider?.toUpperCase() == 'GCP'),
                ],
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  /// Check if a component key is glue code
  bool _isGlueCodeComponent(String key) {
    final k = key.toLowerCase();
    return k.contains('dispatcher') || k.contains('glue') || k.contains('mover');
  }

  Widget _buildInfoSection(BuildContext context, String title, LayerCost? layer, Color color, bool isSelected) {
    if (layer == null) return const SizedBox.shrink();
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: isSelected ? color : color.withAlpha(50), width: isSelected ? 2 : 1),
        borderRadius: BorderRadius.circular(8),
        color: isSelected ? color.withAlpha(25) : color.withAlpha(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Text(title, style: TextStyle(fontWeight: FontWeight.bold, color: color)),
              if (isSelected) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text('SELECTED', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
                ),
              ],
            ],
          ),
          const Divider(),
          ...layer.components.entries.map((e) {
            final isGlue = _isGlueCodeComponent(e.key);
            return Padding(
              padding: const EdgeInsets.only(bottom: 2),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      isGlue ? '${e.key} (Glue Code)' : e.key, 
                      style: TextStyle(
                        fontSize: 12,
                        fontStyle: isGlue ? FontStyle.italic : FontStyle.normal,
                        color: isGlue ? Colors.cyan.shade700 : null,
                      ),
                    ),
                  ),
                  Text('\$${e.value.toStringAsFixed(4)}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
                ],
              ),
            );
          }),
          const Divider(),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Total', style: TextStyle(fontWeight: FontWeight.bold)),
              Text('\$${layer.cost.toStringAsFixed(2)}', style: TextStyle(fontWeight: FontWeight.bold, color: color)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildProviderRow(
    BuildContext context,
    String provider,
    double? cost,
    Color color,
    bool isSelected,
  ) {
    if (cost == null) {
      return Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: color.withAlpha(76),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                provider,
                style: TextStyle(color: Colors.grey[400]),
              ),
            ],
          ),
          Text(
            'N/A',
            style: TextStyle(color: Colors.grey[400]),
          ),
        ],
      );
    }

    return Container(
      padding: isSelected ? const EdgeInsets.all(8) : const EdgeInsets.symmetric(vertical: 4),
      decoration: isSelected
          ? BoxDecoration(
              color: color.withAlpha(25),
              borderRadius: BorderRadius.circular(6),
            )
          : null,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: color,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                provider,
                style: TextStyle(
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                ),
              ),
              if (isSelected) ...[
                const SizedBox(width: 6),
                Icon(Icons.check_circle, color: color, size: 16),
              ],
            ],
          ),
          Text(
            '\$${cost.toStringAsFixed(2)}', // Removed /mo for cleaner look
            style: TextStyle(
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
              color: isSelected ? color : null,
            ),
          ),
        ],
      ),
    );
  }
}
