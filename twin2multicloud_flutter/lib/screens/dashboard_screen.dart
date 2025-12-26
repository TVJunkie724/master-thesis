import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/twins_provider.dart';
import '../providers/theme_provider.dart';
import '../widgets/stat_card.dart';
import '../widgets/twin_list_item.dart';

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
                
                // Twins list
                Expanded(
                  child: twinsAsync.when(
                    data: (twins) => ListView.builder(
                      itemCount: twins.length,
                      itemBuilder: (context, index) => TwinListItem(twin: twins[index]),
                    ),
                    loading: () => const Center(child: CircularProgressIndicator()),
                    error: (err, stack) => Center(child: Text('Error: $err')),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
