import 'package:flutter/material.dart';

/// A widget that displays the cheapest path as a horizontal flow of
/// layer segments with arrows between them.
///
/// Used in Step 2 (Optimizer) and the Twin Overview page.
class CheapestPathVisualization extends StatelessWidget {
  /// List of path segments like ['L1_AWS', 'L2_AZURE', 'L3_hot_GCP', ...]
  final List<String> path;

  /// Optional: custom segment style
  final double? fontSize;

  const CheapestPathVisualization({
    super.key,
    required this.path,
    this.fontSize,
  });

  // Provider Colors
  static const Color awsColor = Colors.orange;
  static const Color azureColor = Colors.blue;
  static const Color gcpColor = Colors.green;

  @override
  Widget build(BuildContext context) {
    if (path.isEmpty) {
      return Text(
        'No optimization result available',
        style: Theme.of(
          context,
        ).textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
      );
    }

    return Wrap(
      spacing: 8,
      runSpacing: 16,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (int i = 0; i < path.length; i++) ...[
          _buildPathSegment(path[i]),
          if (i < path.length - 1)
            const Icon(Icons.arrow_forward, color: Colors.grey, size: 20),
        ],
      ],
    );
  }

  Widget _buildPathSegment(String segment) {
    final parts = segment.split('_');
    String layer = '';
    String provider = '';

    if (segment.startsWith('L3')) {
      if (parts.length >= 3) {
        layer = 'L3 ${parts[1]}';
        provider = parts[2];
      } else {
        layer = parts[0];
        provider = parts.length > 1 ? parts[1] : '?';
      }
    } else {
      layer = parts[0];
      provider = parts.length > 1 ? parts[1] : '?';
    }

    Color bgColor;
    switch (provider.toUpperCase()) {
      case 'AWS':
        bgColor = awsColor;
        break;
      case 'AZURE':
        bgColor = azureColor;
        break;
      case 'GCP':
        bgColor = gcpColor;
        break;
      default:
        bgColor = Colors.grey;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: bgColor.withAlpha(100),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Text(
        '$layer $provider'.toUpperCase(),
        style: TextStyle(
          color: Colors.white,
          fontWeight: FontWeight.bold,
          fontSize: fontSize ?? 12,
        ),
      ),
    );
  }
}
