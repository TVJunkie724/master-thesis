import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../providers/theme_provider.dart';
import '../models/user.dart';
import '../widgets/branded_app_bar.dart';

/// Settings screen for viewing profile info and linking accounts.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  bool _isLinkingGoogle = false;
  bool _isLinkingUibk = false;
  
  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final user = authState.user;
    
    if (user == null) {
      return Scaffold(
        appBar: const BrandedAppBar(title: 'Settings', showLogo: false),
        body: const Center(child: Text('Not logged in')),
      );
    }
    
    return Scaffold(
      appBar: BrandedAppBar(
        title: 'Settings',
        showLogo: false,
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
                  // Already on settings
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
                enabled: false,
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
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 600),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Profile section
                _buildProfileSection(user),
                const SizedBox(height: 32),
                
                // Linked accounts section
                _buildLinkedAccountsSection(user),
              ],
            ),
          ),
        ),
      ),
    );
  }
  
  Widget _buildProfileSection(User user) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 40,
                  backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                  child: user.pictureUrl != null
                    ? ClipOval(child: Image.network(user.pictureUrl!, width: 80, height: 80, fit: BoxFit.cover))
                    : Text(
                        user.name?.isNotEmpty == true ? user.name![0].toUpperCase() : '?',
                        style: TextStyle(
                          fontSize: 32,
                          color: Theme.of(context).colorScheme.onPrimaryContainer,
                        ),
                      ),
                ),
                const SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        user.name ?? 'Unknown User',
                        style: Theme.of(context).textTheme.headlineSmall,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        user.email,
                        style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                          color: Colors.grey.shade600,
                        ),
                      ),
                      const SizedBox(height: 8),
                      _buildAuthProviderBadge(user.authProvider),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildAuthProviderBadge(String provider) {
    final isGoogle = provider == 'google';
    final color = isGoogle ? Colors.blue : const Color(0xFF003366);
    final icon = isGoogle ? Icons.g_mobiledata : Icons.school;
    final label = isGoogle ? 'Google Account' : 'UIBK Account';
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withAlpha(30),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withAlpha(100)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 6),
          Text(
            'Logged in with $label',
            style: TextStyle(color: color, fontWeight: FontWeight.w500, fontSize: 12),
          ),
        ],
      ),
    );
  }
  
  Widget _buildLinkedAccountsSection(User user) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Linked Accounts',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              'Link multiple accounts to access your data from different login methods.',
              style: TextStyle(color: Colors.grey.shade600),
            ),
            const SizedBox(height: 20),
            
            // Google account
            _buildAccountLinkRow(
              icon: Icons.g_mobiledata,
              label: 'Google',
              isLinked: user.googleLinked,
              isLoading: _isLinkingGoogle,
              color: Colors.blue,
              onLink: () => _linkAccount('google'),
            ),
            const Divider(height: 24),
            
            // UIBK account
            _buildAccountLinkRow(
              icon: Icons.school,
              label: 'UIBK (University of Innsbruck)',
              isLinked: user.uibkLinked,
              isLoading: _isLinkingUibk,
              color: const Color(0xFF003366),
              onLink: () => _linkAccount('uibk'),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildAccountLinkRow({
    required IconData icon,
    required String label,
    required bool isLinked,
    required bool isLoading,
    required Color color,
    required VoidCallback onLink,
  }) {
    return Row(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: color.withAlpha(30),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: color),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontWeight: FontWeight.w500)),
              Text(
                isLinked ? 'Connected' : 'Not connected',
                style: TextStyle(
                  color: isLinked ? Colors.green : Colors.grey.shade600,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
        if (isLoading)
          const SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        else if (isLinked)
          const Icon(Icons.check_circle, color: Colors.green)
        else
          OutlinedButton(
            onPressed: onLink,
            child: const Text('Link'),
          ),
      ],
    );
  }

  
  Future<void> _linkAccount(String provider) async {
    // TODO: Implement actual OAuth/SAML flow for account linking
    // For now, show a message
    setState(() {
      if (provider == 'google') {
        _isLinkingGoogle = true;
      } else {
        _isLinkingUibk = true;
      }
    });
    
    try {
      // Simulate API call
      await Future.delayed(const Duration(seconds: 1));
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Account linking for $provider is not yet implemented. '
                'This will redirect to the $provider login page.'),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          if (provider == 'google') {
            _isLinkingGoogle = false;
          } else {
            _isLinkingUibk = false;
          }
        });
      }
    }
  }
}
