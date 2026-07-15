// lib/widgets/dashboard/twins_table.dart
// Extracted twins table widget from dashboard_screen.dart

import 'package:flutter/material.dart';
import '../../models/twin.dart';

/// Sorting options for twins table
enum TwinSortField { name, state, createdAt, updatedAt, providers }

/// A data table displaying twins with sorting and actions.
///
/// Features:
/// - Sortable columns
/// - Status badges
/// - Provider chips
/// - Edit/Delete actions
/// - Empty state
class TwinsTable extends StatefulWidget {
  final List<Twin> twins;
  final VoidCallback onRefresh;
  final Function(Twin) onEdit;
  final Function(Twin) onDelete;
  final Function(Twin)? onDeploy;

  const TwinsTable({
    super.key,
    required this.twins,
    required this.onRefresh,
    required this.onEdit,
    required this.onDelete,
    this.onDeploy,
  });

  @override
  State<TwinsTable> createState() => _TwinsTableState();
}

class _TwinsTableState extends State<TwinsTable> {
  TwinSortField _sortField = TwinSortField.updatedAt;
  bool _sortAscending = false;

  List<Twin> get _sortedTwins {
    final sorted = List<Twin>.from(widget.twins);
    sorted.sort((a, b) {
      int comparison;
      switch (_sortField) {
        case TwinSortField.name:
          comparison = a.name.compareTo(b.name);
          break;
        case TwinSortField.state:
          comparison = a.state.compareTo(b.state);
          break;
        case TwinSortField.createdAt:
          comparison = a.createdAt.compareTo(b.createdAt);
          break;
        case TwinSortField.updatedAt:
          comparison = a.updatedAt.compareTo(b.updatedAt);
          break;
        case TwinSortField.providers:
          comparison = a.providers.length.compareTo(b.providers.length);
          break;
      }
      return _sortAscending ? comparison : -comparison;
    });
    return sorted;
  }

  void _onSort(TwinSortField field) {
    setState(() {
      if (_sortField == field) {
        _sortAscending = !_sortAscending;
      } else {
        _sortField = field;
        _sortAscending = true;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (widget.twins.isEmpty) {
      return _buildEmptyState(theme);
    }

    return DataTable(
      headingRowColor: WidgetStateProperty.all(
        theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
      ),
      columns: [
        _buildColumn('Name', TwinSortField.name),
        _buildColumn('State', TwinSortField.state),
        _buildColumn('Providers', TwinSortField.providers),
        _buildColumn('Updated', TwinSortField.updatedAt),
        const DataColumn(label: Text('Actions')),
      ],
      rows: _sortedTwins.map((twin) => _buildRow(twin, theme)).toList(),
    );
  }

  DataColumn _buildColumn(String label, TwinSortField field) {
    return DataColumn(
      label: InkWell(
        onTap: () => _onSort(field),
        child: Row(
          children: [
            Text(label),
            const SizedBox(width: 4),
            if (_sortField == field)
              Icon(
                _sortAscending ? Icons.arrow_upward : Icons.arrow_downward,
                size: 14,
              ),
          ],
        ),
      ),
    );
  }

  DataRow _buildRow(Twin twin, ThemeData theme) {
    return DataRow(
      cells: [
        DataCell(Text(twin.name)),
        DataCell(_buildStateChip(twin.state, theme)),
        DataCell(_buildProviderChips(twin.providers, theme)),
        DataCell(Text(_formatDate(twin.updatedAt))),
        DataCell(_buildActions(twin, theme)),
      ],
    );
  }

  Widget _buildStateChip(String state, ThemeData theme) {
    Color color;
    IconData icon;

    switch (state.toLowerCase()) {
      case 'deployed':
        color = Colors.green;
        icon = Icons.check_circle;
        break;
      case 'draft':
        color = Colors.orange;
        icon = Icons.edit;
        break;
      case 'error':
        color = Colors.red;
        icon = Icons.error;
        break;
      case 'destroyed':
        color = Colors.grey;
        icon = Icons.delete;
        break;
      default:
        color = Colors.grey;
        icon = Icons.circle;
    }

    return Chip(
      avatar: Icon(icon, size: 16, color: color),
      label: Text(
        state.toUpperCase(),
        style: TextStyle(
          fontSize: 11,
          color: color,
          fontWeight: FontWeight.bold,
        ),
      ),
      backgroundColor: color.withValues(alpha: 0.1),
      side: BorderSide.none,
      padding: EdgeInsets.zero,
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _buildProviderChips(List<String> providers, ThemeData theme) {
    return Wrap(
      spacing: 4,
      children: providers.map((p) => _buildProviderChip(p)).toList(),
    );
  }

  Widget _buildProviderChip(String provider) {
    Color color;
    switch (provider.toUpperCase()) {
      case 'AWS':
        color = Colors.orange;
        break;
      case 'AZURE':
        color = Colors.blue;
        break;
      case 'GCP':
        color = Colors.red;
        break;
      default:
        color = Colors.grey;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        provider,
        style: TextStyle(
          fontSize: 10,
          color: color,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  Widget _buildActions(Twin twin, ThemeData theme) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          icon: const Icon(Icons.edit, size: 20),
          tooltip: 'Edit',
          onPressed: () => widget.onEdit(twin),
        ),
        IconButton(
          icon: Icon(Icons.delete, size: 20, color: theme.colorScheme.error),
          tooltip: 'Delete',
          onPressed: () => widget.onDelete(twin),
        ),
        if (widget.onDeploy != null && twin.state != 'deployed')
          IconButton(
            icon: Icon(
              Icons.rocket_launch,
              size: 20,
              color: theme.colorScheme.primary,
            ),
            tooltip: 'Deploy',
            onPressed: () => widget.onDeploy!(twin),
          ),
      ],
    );
  }

  Widget _buildEmptyState(ThemeData theme) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.view_in_ar_outlined,
            size: 64,
            color: theme.colorScheme.outline,
          ),
          const SizedBox(height: 16),
          Text(
            'No Digital Twins Yet',
            style: theme.textTheme.titleLarge?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Create your first twin to get started',
            style: TextStyle(color: theme.colorScheme.onSurfaceVariant),
          ),
        ],
      ),
    );
  }

  String _formatDate(DateTime date) {
    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${date.day}/${date.month}/${date.year}';
  }
}
