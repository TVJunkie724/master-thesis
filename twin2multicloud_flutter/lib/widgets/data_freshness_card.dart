import 'package:flutter/material.dart';

/// Card showing data freshness status for a cloud provider
class DataFreshnessCard extends StatelessWidget {
  final String provider;
  final String label; // e.g., 'Pricing', 'Regions'
  final Map<String, dynamic>? status;
  final VoidCallback? onRefresh;

  const DataFreshnessCard({
    super.key,
    required this.provider,
    this.label = 'Pricing',
    this.status,
    this.onRefresh,
  });

  @override
  Widget build(BuildContext context) {
    // Optimizer API returns: age (string), status (schema validity), is_fresh (bool), threshold_days (int)
    final hasError = status?['error'] != null || status?['status'] == 'error' || status?['status'] == 'missing';
    final ageString = status?['age'] as String? ?? 'Unknown';
    final isFresh = status?['is_fresh'] as bool? ?? false;
    final thresholdDays = status?['threshold_days'] as int? ?? 7;

    Color providerColor;
    IconData providerIcon;
    switch (provider.toLowerCase()) {
      case 'aws':
        providerColor = Colors.orange;
        providerIcon = Icons.cloud;
        break;
      case 'azure':
        providerColor = Colors.blue;
        providerIcon = Icons.cloud_queue;
        break;
      case 'gcp':
        providerColor = Colors.green;
        providerIcon = Icons.cloud_circle;
        break;
      default:
        providerColor = Colors.grey;
        providerIcon = Icons.cloud_outlined;
    }

    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with provider + label (e.g., "AWS PRICING")
            Row(
              children: [
                Icon(providerIcon, color: providerColor),
                const SizedBox(width: 8),
                Text(
                  '${provider.toUpperCase()} ${label.toUpperCase()}',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: providerColor,
                  ),
                ),
                const Spacer(),
                _buildStatusBadge(isFresh, hasError),
              ],
            ),
            const SizedBox(height: 12),

            // Age info
            if (hasError)
              Text(
                'Error loading status',
                style: TextStyle(color: Colors.red[600], fontSize: 12),
              )
            else ...[
              Text(
                'Age: $ageString',
                style: TextStyle(color: Colors.grey[600], fontSize: 12),
              ),
              const SizedBox(height: 4),
              Text(
                'Max age: $thresholdDays days',
                style: TextStyle(color: Colors.grey[500], fontSize: 11),
              ),
            ],

            const SizedBox(height: 12),

            // Refresh button
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: onRefresh,
                icon: const Icon(Icons.refresh, size: 16),
                label: const Text('Refresh'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: providerColor,
                  side: BorderSide(color: providerColor),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBadge(bool isFresh, bool hasError) {
    if (hasError) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.red[100],
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Text(
          'Error',
          style: TextStyle(color: Colors.red, fontSize: 11),
        ),
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isFresh ? Colors.green[100] : Colors.yellow[100],
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        isFresh ? 'Fresh' : 'Stale',
        style: TextStyle(
          color: isFresh ? Colors.green[700] : Colors.orange[700],
          fontSize: 11,
        ),
      ),
    );
  }
}
