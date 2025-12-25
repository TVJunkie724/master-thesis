import 'package:flutter/material.dart';
import '../models/twin.dart';

class TwinListItem extends StatelessWidget {
  final Twin twin;
  final VoidCallback? onView;
  final VoidCallback? onEdit;

  const TwinListItem({
    super.key,
    required this.twin,
    this.onView,
    this.onEdit,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        leading: _buildStateIcon(),
        title: Text(twin.name),
        subtitle: Text(twin.providers.isEmpty 
          ? 'No providers configured' 
          : twin.providers.join(', ')),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconButton(
              icon: const Icon(Icons.visibility),
              onPressed: onView,
              tooltip: 'View',
            ),
            IconButton(
              icon: const Icon(Icons.edit),
              onPressed: onEdit,
              tooltip: 'Edit',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStateIcon() {
    IconData iconData;
    Color color;
    
    switch (twin.state) {
      case 'deployed':
        iconData = Icons.cloud_done;
        color = Colors.green;
        break;
      case 'configured':
        iconData = Icons.cloud_outlined;
        color = Colors.orange;
        break;
      case 'error':
        iconData = Icons.cloud_off;
        color = Colors.red;
        break;
      case 'draft':
      default:
        iconData = Icons.cloud_queue;
        color = Colors.grey;
    }
    
    return Icon(iconData, color: color);
  }
}
