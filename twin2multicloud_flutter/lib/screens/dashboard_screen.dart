import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/twins_provider.dart';
import '../providers/theme_provider.dart';
import '../providers/auth_provider.dart';
import '../utils/api_error_handler.dart';
import '../widgets/stat_card.dart';
import '../widgets/branded_app_bar.dart';
import '../models/twin.dart';
import '../theme/colors.dart';
import '../config/docs_config.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  int _sortColumnIndex = 0;
  bool _sortAscending = true;
  String? _selectedStateFilter; // null means "All"

  List<Twin> _sortTwins(List<Twin> twins) {
    final sorted = List<Twin>.from(twins);
    sorted.sort((a, b) {
      int cmp;
      switch (_sortColumnIndex) {
        case 0: // Name
          cmp = a.name.toLowerCase().compareTo(b.name.toLowerCase());
          break;
        case 2: // Last Updated
          final aDate = a.updatedAt ?? DateTime(1970);
          final bDate = b.updatedAt ?? DateTime(1970);
          cmp = aDate.compareTo(bDate);
          break;
        default:
          cmp = 0;
      }
      return _sortAscending ? cmp : -cmp;
    });
    return sorted;
  }

  List<Twin> _filterTwins(List<Twin> twins) {
    if (_selectedStateFilter == null) return twins;
    return twins.where((t) => t.state == _selectedStateFilter).toList();
  }

  @override
  Widget build(BuildContext context) {
    final twinsAsync = ref.watch(twinsProvider);
    
    return Scaffold(
      appBar: BrandedAppBar(
        title: 'Twin2MultiCloud',
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
          const SizedBox(width: 8),
          PopupMenuButton<String>(
            offset: const Offset(0, 56),
            tooltip: 'Profile menu',
            onSelected: (value) {
              switch (value) {
                case 'settings':
                  context.go('/settings');
                  break;
                case 'logout':
                  ref.read(authProvider.notifier).logout();
                  context.go('/login');
                  break;
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(
                value: 'settings',
                child: Row(
                  children: [
                    Icon(Icons.settings, size: 20),
                    SizedBox(width: 12),
                    Text('Settings'),
                  ],
                ),
              ),
              const PopupMenuDivider(),
              PopupMenuItem(
                value: 'logout',
                child: Row(
                  children: [
                    Icon(Icons.logout, size: 20, color: Colors.red),
                    const SizedBox(width: 12),
                    Text('Logout', style: TextStyle(color: Colors.red)),
                  ],
                ),
              ),
            ],
            child: const Padding(
              padding: EdgeInsets.symmetric(horizontal: 8),
              child: CircleAvatar(child: Icon(Icons.person)),
            ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SingleChildScrollView(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1200),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Stat cards row
                  _buildStatsRow(ref),
                  const SizedBox(height: 24),
                  // Twins section - wrapped in Card
                  Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(
                            Theme.of(context).brightness == Brightness.dark ? 0.2 : 0.06
                          ),
                          blurRadius: 12,
                          spreadRadius: 1,
                          offset: const Offset(0, 0),
                        ),
                      ],
                    ),
                    child: Card(
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                        side: BorderSide(
                          color: Theme.of(context).brightness == Brightness.dark 
                            ? Colors.white.withOpacity(0.1) 
                            : Colors.black.withOpacity(0.05),
                          width: 1,
                        ),
                      ),
                      child: Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            // Twins list header
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text('My Digital Twins', style: Theme.of(context).textTheme.headlineSmall),
                                FilledButton.icon(
                                  onPressed: () => _showCredentialSetupDialog(context),
                                  icon: const Icon(Icons.add),
                                  label: const Text('New Twin'),
                                ),
                              ],
                            ),
                            const SizedBox(height: 12),
                            
                            // State filter chips
                            _buildStateFilterChips(),
                            const SizedBox(height: 16),
                            
                            // Twins table
                            twinsAsync.when(
                              data: (twins) => _buildTwinsTable(context, ref, twins),
                              loading: () => const Padding(
                                padding: EdgeInsets.all(48),
                                child: Center(child: CircularProgressIndicator()),
                              ),
                              error: (err, stack) => Padding(
                                padding: const EdgeInsets.all(48),
                                child: Center(
                                  child: Column(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Icon(Icons.cloud_off, size: 64, color: Colors.grey.shade600),
                                      const SizedBox(height: 16),
                                      Text('Failed to load twins', 
                                        style: Theme.of(context).textTheme.titleMedium),
                                      const SizedBox(height: 8),
                                      Text(ApiErrorHandler.extractMessage(err), 
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
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  // State color helper - single source of truth for state colors
  Color _getStateColor(String? state) {
    switch (state) {
      case 'deployed':
        return Colors.green;
      case 'configured':
        return Colors.orange;
      case 'error':
        return Colors.red;
      case 'draft':
        return Colors.grey;
      default:
        return Theme.of(context).colorScheme.primary;
    }
  }

  Widget _buildStateFilterChips() {
    final filters = [
      (null, 'All'),
      ('draft', 'Draft'),
      ('configured', 'Configured'),
      ('deployed', 'Deployed'),
      ('error', 'Error'),
    ];
    
    return Wrap(
      spacing: 8,
      children: filters.map((filter) {
        final (value, label) = filter;
        final isSelected = _selectedStateFilter == value;
        final color = _getStateColor(value);
        
        return FilterChip(
          label: Text(
            label,
            style: TextStyle(
              color: isSelected ? Colors.white : color,
              fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
            ),
          ),
          selected: isSelected,
          onSelected: (_) {
            setState(() => _selectedStateFilter = value);
          },
          backgroundColor: color.withAlpha(25),
          selectedColor: color,
          showCheckmark: false,
          side: BorderSide(color: color.withAlpha(100)),
        );
      }).toList(),
    );
  }

  Widget _buildStatsRow(WidgetRef ref) {
    final statsAsync = ref.watch(dashboardStatsProvider);
    
    return statsAsync.when(
      data: (stats) {
        final deployed = stats['deployed_count'] ?? 0;
        final draft = stats['draft_count'] ?? 0;
        final total = stats['total_twins'] ?? 0;
        final cost = stats['estimated_monthly_cost'] ?? 0.0;
        
        // Format cost
        final costStr = cost > 0 ? '\$${cost.toStringAsFixed(0)}/mo' : '—';
        
        return Row(
          children: [
            StatCard(
              title: 'Deployed',
              value: deployed.toString(),
              icon: Icons.cloud_done,
              color: Colors.green,
            ),
            StatCard(
              title: 'Est. Cost',
              value: costStr,
              icon: Icons.attach_money,
              color: Colors.amber,
              tooltip: 'Static estimate based on optimizer calculations.\nNot live cloud billing data.',
            ),
            StatCard(
              title: 'Total Twins',
              value: total.toString(),
              icon: Icons.cloud_queue,
            ),
            StatCard(
              title: 'Draft',
              value: draft.toString(),
              icon: Icons.edit_note,
              color: Colors.orange,
            ),
          ],
        );
      },
      loading: () => const Row(
        children: [
          StatCard(title: 'Deployed', value: '—', icon: Icons.cloud_done),
          StatCard(title: 'Est. Cost', value: '—', icon: Icons.attach_money),
          StatCard(title: 'Total Twins', value: '—', icon: Icons.cloud_queue),
          StatCard(title: 'Draft', value: '—', icon: Icons.edit_note),
        ],
      ),
      error: (_, __) => const Row(
        children: [
          StatCard(title: 'Deployed', value: '?', icon: Icons.cloud_done),
          StatCard(title: 'Est. Cost', value: '?', icon: Icons.attach_money),
          StatCard(title: 'Total Twins', value: '?', icon: Icons.cloud_queue),
          StatCard(title: 'Draft', value: '?', icon: Icons.edit_note),
        ],
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
                content: Text('Failed to delete: ${ApiErrorHandler.extractMessage(e)}'),
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

    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return SingleChildScrollView(
      child: SizedBox(
        width: double.infinity,
        child: DataTable(
          sortColumnIndex: _sortColumnIndex,
          sortAscending: _sortAscending,
          headingRowColor: WidgetStateProperty.all(
            isDark 
              ? Colors.white.withOpacity(0.05)
              : Theme.of(context).colorScheme.surfaceContainerHighest,
          ),
          columnSpacing: 24,
          columns: [
            DataColumn(
              label: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Name'),
                  const SizedBox(width: 4),
                  Icon(Icons.swap_vert, size: 16, color: Colors.grey.shade500),
                ],
              ),
              onSort: (columnIndex, ascending) {
                setState(() {
                  _sortColumnIndex = columnIndex;
                  _sortAscending = ascending;
                });
              },
            ),
            const DataColumn(label: Text('State')),
            DataColumn(
              label: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text('Last Updated'),
                  const SizedBox(width: 4),
                  Icon(Icons.swap_vert, size: 16, color: Colors.grey.shade500),
                ],
              ),
              onSort: (columnIndex, ascending) {
                setState(() {
                  _sortColumnIndex = columnIndex;
                  _sortAscending = ascending;
                });
              },
            ),
            const DataColumn(label: Text('Last Deploy')),
            const DataColumn(label: Text('Actions')),
          ],
          rows: _sortTwins(_filterTwins(twins)).map((twin) => _buildTwinRow(context, ref, twin)).toList(),
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
        // Last Updated
        DataCell(Text(_formatDate(twin.updatedAt))),
        // Last Deploy
        DataCell(Text(_formatDate(twin.lastDeployedAt))),
        // Actions
        DataCell(
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (twin.state != 'draft')
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

  String _formatDate(DateTime? date) {
    if (date == null) return '—';
    return DateFormat('MMM d, yyyy').format(date);
  }

  void _showCredentialSetupDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 700),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header with title and close button
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      'Set Up Cloud Credentials',
                      style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.close),
                      onPressed: () => Navigator.pop(ctx),
                      tooltip: 'Close',
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  'Need help configuring your cloud credentials? Follow the setup guides below before creating your first twin.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.grey.shade600,
                  ),
                ),
                const SizedBox(height: 24),
                
                // Provider cards
                Row(
                  children: [
                    Expanded(child: _buildProviderCard(
                      context: context,
                      provider: 'AWS',
                      description: 'Configure IAM user with programmatic access',
                      color: AppColors.aws,
                      icon: Icons.cloud_queue,
                    )),
                    const SizedBox(width: 12),
                    Expanded(child: _buildProviderCard(
                      context: context,
                      provider: 'Azure',
                      description: 'Set up Service Principal with contributor role',
                      color: AppColors.azure,
                      icon: Icons.cloud_outlined,
                    )),
                    const SizedBox(width: 12),
                    Expanded(child: _buildProviderCard(
                      context: context,
                      provider: 'GCP',
                      description: 'Create service account with JSON key file',
                      color: AppColors.gcp,
                      icon: Icons.cloud_done,
                    )),
                  ],
                ),
                const SizedBox(height: 24),
                
                // Action buttons
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton(
                      onPressed: () => Navigator.pop(ctx),
                      child: const Text('Cancel'),
                    ),
                    const SizedBox(width: 12),
                    FilledButton(
                      onPressed: () {
                        Navigator.pop(ctx);
                        context.go('/wizard');
                      },
                      child: const Text('Continue to Setup'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProviderCard({
    required BuildContext context,
    required String provider,
    required String description,
    required Color color,
    required IconData icon,
  }) {
    final optimizerUrl = DocsConfig.getOptimizerDocsUrl(provider);
    final deployerUrl = DocsConfig.getDeployerDocsUrl(provider);
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withAlpha(20),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withAlpha(80)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: color, size: 28),
              const SizedBox(width: 8),
              Text(
                provider,
                style: TextStyle(
                  color: color,
                  fontWeight: FontWeight.bold,
                  fontSize: 18,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            description,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Colors.grey.shade600,
            ),
          ),
          const SizedBox(height: 12),
          // Buttons
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              OutlinedButton.icon(
                onPressed: () => _launchUrl(optimizerUrl),
                icon: const Icon(Icons.calculate, size: 16),
                label: const Text('Optimizer Guide'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: color,
                  side: BorderSide(color: color.withAlpha(150)),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                ),
              ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () => _launchUrl(deployerUrl),
                icon: const Icon(Icons.rocket_launch, size: 16),
                label: const Text('Deployer Guide'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: color,
                  side: BorderSide(color: color.withAlpha(150)),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}
