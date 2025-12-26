import 'package:flutter/material.dart';
import '../../models/calc_result.dart';

/// Warning card explaining why a non-cheapest provider was selected
class OptimizationWarning extends StatelessWidget {
  final String layer;
  final OptimizationOverride optimizationOverride;

  const OptimizationWarning({
    super.key,
    required this.layer,
    required this.optimizationOverride,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.amber[50],
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.amber[300]!),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.info_outline, color: Colors.amber[700]),
              const SizedBox(width: 8),
              Text(
                '$layer: Optimization Override',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  color: Colors.amber[900],
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Selected ${optimizationOverride.selectedProvider.toUpperCase()} instead of cheapest ${optimizationOverride.cheapestProvider.toUpperCase()}',
            style: TextStyle(color: Colors.amber[900]),
          ),
          const SizedBox(height: 4),
          Text(
            'This ensures optimal data flow and minimizes cross-cloud transfer costs.',
            style: TextStyle(
              color: Colors.amber[800],
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }
}
