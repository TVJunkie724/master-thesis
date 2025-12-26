import 'package:flutter/material.dart';

/// Card showing cost comparison for a single layer across providers
class LayerCostCard extends StatelessWidget {
  final String layer;
  final double? awsCost;
  final double? azureCost;
  final double? gcpCost;
  final List<String> cheapestPath;

  const LayerCostCard({
    super.key,
    required this.layer,
    this.awsCost,
    this.azureCost,
    this.gcpCost,
    required this.cheapestPath,
  });

  @override
  Widget build(BuildContext context) {
    final layerKey = layer.split(' - ')[0]; // Extract L1, L2, etc.
    
    // Find which provider is selected for this layer
    String? selectedProvider;
    for (final segment in cheapestPath) {
      if (segment.startsWith(layerKey)) {
        final parts = segment.split('_');
        if (parts.length > 1) {
          selectedProvider = parts[1];
        }
        break;
      }
    }

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Text(
              layer,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const Divider(),
            
            // Provider costs
            _buildProviderRow(
              context, 
              'AWS', 
              awsCost, 
              Colors.orange,
              selectedProvider?.toUpperCase() == 'AWS',
            ),
            const SizedBox(height: 8),
            _buildProviderRow(
              context, 
              'Azure', 
              azureCost, 
              Colors.blue,
              selectedProvider?.toUpperCase() == 'AZURE',
            ),
            const SizedBox(height: 8),
            _buildProviderRow(
              context, 
              'GCP', 
              gcpCost, 
              Colors.red,
              selectedProvider?.toUpperCase() == 'GCP',
            ),
          ],
        ),
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
      padding: isSelected ? const EdgeInsets.all(4) : null,
      decoration: isSelected
          ? BoxDecoration(
              color: color.withAlpha(25),
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: color, width: 2),
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
                const SizedBox(width: 4),
                Icon(Icons.check_circle, color: color, size: 16),
              ],
            ],
          ),
          Text(
            '\$${cost.toStringAsFixed(2)}/mo',
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
