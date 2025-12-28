import 'package:flutter/material.dart';

class StatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color? color;
  final String? tooltip;

  const StatCard({
    super.key,
    required this.title,
    required this.value,
    required this.icon,
    this.color,
    this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    Widget cardContent = Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, color: color ?? Theme.of(context).colorScheme.primary),
                const SizedBox(width: 8),
                Text(
                  title,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                if (tooltip != null) ...[
                  const SizedBox(width: 4),
                  Icon(Icons.info_outline, size: 14, color: Colors.grey.shade500),
                ],
              ],
            ),
            const SizedBox(height: 8),
            Text(
              value,
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
    
    if (tooltip != null) {
      cardContent = Tooltip(
        message: tooltip!,
        child: cardContent,
      );
    }
    
    return Expanded(child: cardContent);
  }
}

