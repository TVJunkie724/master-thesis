import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import 'cloud_connection_strings.dart';

class CloudConnectionSelector extends StatelessWidget {
  final CloudProvider provider;
  final List<CloudConnection> connections;
  final String? selectedConnectionId;
  final bool enabled;
  final ValueChanged<String?> onChanged;

  const CloudConnectionSelector({
    super.key,
    required this.provider,
    required this.connections,
    required this.selectedConnectionId,
    required this.enabled,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final hasSelectedConnection = connections.any(
      (connection) => connection.id == selectedConnectionId,
    );

    return DropdownButtonFormField<String>(
      initialValue: hasSelectedConnection ? selectedConnectionId : null,
      isExpanded: true,
      decoration: InputDecoration(
        labelText:
            '${provider.label} ${CloudConnectionStrings.selectConnection}',
        border: const OutlineInputBorder(),
      ),
      items: [
        for (final connection in connections)
          DropdownMenuItem(
            value: connection.id,
            child: Text(connection.displayName),
          ),
      ],
      onChanged: enabled ? onChanged : null,
    );
  }
}
