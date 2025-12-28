import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import '../providers/twins_provider.dart';
import '../providers/theme_provider.dart';
import '../widgets/stat_card.dart';
import '../models/twin.dart';

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final twinsAsync = ref.watch(twinsProvider);
    
    return Scaffold(
      appBar: AppBar(
        title: const Text('Twin2MultiCloud'),
        backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
        actions: [
          IconButton(
            icon: Icon(
              ref.watch(themeProvider) == ThemeMode.dark
                  ? Icons.light_mode
                  : Icons.dark_mode,
            ),
            onPressed: () => ref.read(themeProvider.notifier).toggle(),
            tooltip: 'Toggle theme',
          ),
          const CircleAvatar(child: Icon(Icons.person)),
          const SizedBox(width: 16),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1200),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Stat cards row
                Row(
                  children: const [
                    StatCard(title: 'Deployed', value: '3', icon: Icons.cloud_done),
                    StatCard(title: 'Est. Cost', value: '\$142/mo', icon: Icons.attach_money),
                    StatCard(title: 'Devices', value: '347', icon: Icons.devices),
                    StatCard(title: 'Errors', value: '0', icon: Icons.error_outline),
                  ],
                ),
                const SizedBox(height: 32),
                
                // Twins list header
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('My Digital Twins', style: Theme.of(context).textTheme.headlineSmall),
                    FilledButton.icon(
                      onPressed: () => context.go('/wizard'),
                      icon: const Icon(Icons.add),
                      label: const Text('New Twin'),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                
                // Twins table
                Expanded(
                  child: twinsAsync.when(
                    data: (twins) => _buildTwinsTable(context, ref, twins),
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (err, stack) => Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.cloud_off, size: 64, color: Colors.grey.shade600),
                          const SizedBox(height: 16),
                          Text('Failed to load twins', 
                            style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 8),
                          Text('$err', 
                            style: TextStyle(color: Colors.grey.shade600)),
                          const SizedBox(height: 16),
                          OutlinedButton.icon(
                            onPressed: () => ref.invalidate(twinsProvider),
                            icon: const Icon(Icons.refresh),
                            label: const Text('Retry'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _handleDelete(BuildContext context, WidgetRef ref, Twin twin) async {
    if (twin.isDeployed) {
      // Show warning - can't delete deployed twins
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: Icon(Icons.warning_amber_rounded, color: Colors.orange.shade400, size: 48),
          title: const Text('Cannot Delete'),
          content: const Text(
            'This digital twin is currently deployed. You must destroy all cloud resources before deleting.\n\n'
            'Go to the Deployer step and run "Destroy" first.',
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('OK'),
            ),
          ],
        ),
      );
    } else {
      // Show confirmation dialog
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          icon: Icon(Icons.delete_forever, color: Colors.red.shade400, size: 48),
          title: const Text('Delete Twin?'),
          content: Text(
            'Are you sure you want to delete "${twin.name}"?\n\n'
            'This action cannot be undone.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: Colors.red),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Delete'),
            ),
          ],
        ),
      );
      
      if (confirmed == true) {
        try {
          final api = ref.read(apiServiceProvider);
          await api.deleteTwin(twin.id);
          ref.invalidate(twinsProvider); // Refresh list
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Deleted "${twin.name}"')),
            );
          }
        } catch (e) {
          if (context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text('Failed to delete: $e'),
                backgroundColor: Colors.red,
              ),
            );
          }
        }
      }
    }
  }

  Widget _buildTwinsTable(BuildContext context, WidgetRef ref, List<Twin> twins) {
    if (twins.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_queue, size: 64, color: Colors.grey.shade600),
            const SizedBox(height: 16),
            Text('No digital twins yet', 
              style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text('Create your first twin to get started',
              style: TextStyle(color: Colors.grey.shade600)),
          ],
        ),
      );
    }

    return SingleChildScrollView(
      child: SizedBox(
        width: double.infinity,
        child: Card(
          clipBehavior: Clip.antiAlias,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
          child: DataTable(
            headingRowColor: WidgetStateProperty.all(
              Theme.of(context).colorScheme.surfaceContainerHighest,
            ),
            columnSpacing: 24,
            columns: const [
              DataColumn(label: Text('Name')),
              DataColumn(label: Text('State')),
              DataColumn(label: Text('Providers')),
              DataColumn(label: Text('Last Updated')),
              DataColumn(label: Text('Last Deploy')),
              DataColumn(label: Text('Actions')),
            ],
            rows: twins.map((twin) => _buildTwinRow(context, ref, twin)).toList(),
          ),
        ),
      ),
    );
  }

  DataRow _buildTwinRow(BuildContext context, WidgetRef ref, Twin twin) {
    return DataRow(
      cells: [
        // Name
        DataCell(
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildStateIcon(twin.state),
              const SizedBox(width: 8),
              Text(twin.name, style: const TextStyle(fontWeight: FontWeight.w500)),
            ],
          ),
        ),
        // State
        DataCell(_buildStateBadge(twin.state)),
        // Providers
        DataCell(
          twin.providers.isEmpty
            ? Text('—', style: TextStyle(color: Colors.grey.shade600))
            : Wrap(
                spacing: 4,
                children: twin.providers.map((p) => _buildProviderChip(p)).toList(),
              ),
        ),
        // Last Updated
        DataCell(Text(_formatDate(twin.updatedAt))),
        // Last Deploy
        DataCell(Text(_formatDate(twin.lastDeployedAt))),
        // Actions
        DataCell(
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                icon: const Icon(Icons.visibility, size: 20),
                onPressed: () {},
                tooltip: 'View',
              ),
              IconButton(
                icon: const Icon(Icons.edit, size: 20),
                onPressed: () => context.go('/wizard/${twin.id}'),
                tooltip: 'Edit',
              ),
              IconButton(
                icon: const Icon(Icons.delete_outline, size: 20),
                onPressed: () => _handleDelete(context, ref, twin),
                tooltip: twin.isDeployed ? 'Destroy resources first' : 'Delete',
                color: twin.isDeployed ? Colors.grey.shade500 : Colors.red.shade400,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildStateIcon(String state) {
    IconData iconData;
    Color color;
    
    switch (state) {
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
    
    return Icon(iconData, color: color, size: 20);
  }

  Widget _buildStateBadge(String state) {
    Color bgColor;
    Color textColor;
    String label;
    
    switch (state) {
      case 'deployed':
        bgColor = Colors.green.withAlpha(38);
        textColor = Colors.green.shade400;
        label = 'Deployed';
        break;
      case 'configured':
        bgColor = Colors.orange.withAlpha(38);
        textColor = Colors.orange.shade400;
        label = 'Configured';
        break;
      case 'error':
        bgColor = Colors.red.withAlpha(38);
        textColor = Colors.red.shade400;
        label = 'Error';
        break;
      case 'draft':
      default:
        bgColor = Colors.grey.withAlpha(38);
        textColor = Colors.grey.shade400;
        label = 'Draft';
    }
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label, style: TextStyle(
        color: textColor,
        fontSize: 12,
        fontWeight: FontWeight.w500,
      )),
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
        color: color.withAlpha(38),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withAlpha(76)),
      ),
      child: Text(
        provider.toUpperCase(),
        style: TextStyle(
          color: color,
          fontSize: 10,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }

  String _formatDate(DateTime? date) {
    if (date == null) return '—';
    return DateFormat('MMM d, yyyy').format(date);
  }
}
