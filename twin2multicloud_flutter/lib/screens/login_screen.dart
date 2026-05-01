import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';
import '../widgets/selectable_scaffold.dart';

/// Login screen with Google OAuth and UIBK SAML authentication options.
///
/// UIBK login uses Shibboleth SAML via the university's Identity Provider.
/// The user logs in with their UIBK username/password (not email), and the
/// IdP provides the email automatically from the university's LDAP directory.
class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);

    return SelectableScaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Card(
            elevation: 8,
            child: Container(
              width: 400,
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                // Logo
                Image.asset(
                  'assets/images/logo_transparent_attempt.png',
                  width: 96,
                  height: 96,
                  fit: BoxFit.contain,
                ),
                const SizedBox(height: 16),
                Text(
                  'Twin2MultiCloud',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Multi-cloud Digital Twin Platform',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: 32),

                if (authState.isLoading)
                  const CircularProgressIndicator()
                else ...[
                  // ============================================================
                  // Login buttons are DISABLED for now.
                  // Backend authentication (Google OAuth + UIBK SAML) is fully
                  // implemented, but the Flutter integration is mocked/disabled
                  // until production deployment requirements are finalized.
                  // ============================================================

                  // UIBK SAML Login Button (disabled)
                  FilledButton.icon(
                    onPressed: null, // Disabled
                    icon: const Icon(Icons.school),
                    label: const Text('Sign in with UIBK'),
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(
                        0xFF003366,
                      ), // UIBK brand color
                      foregroundColor: Colors.white,
                      disabledBackgroundColor: const Color(
                        0xFF003366,
                      ).withValues(alpha: 0.4),
                      disabledForegroundColor: Colors.white.withValues(alpha: 0.6),
                      minimumSize: const Size(double.infinity, 48),
                    ),
                  ),

                  const SizedBox(height: 12),

                  // Google OAuth button (disabled)
                  FilledButton.icon(
                    onPressed: null, // Disabled
                    icon: const Icon(Icons.login),
                    label: const Text('Sign in with Google'),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(double.infinity, 48),
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Skip login link for development
                  TextButton(
                    onPressed: () async {
                      await ref.read(authProvider.notifier).mockLogin();
                      if (context.mounted) {
                        context.go('/dashboard');
                      }
                    },
                    child: const Text('Skip Login (Development)'),
                  ),
                ],

                const SizedBox(height: 8),

                // Info text about authentication status
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 8,
                  ),
                  decoration: BoxDecoration(
                    color: Theme.of(
                      context,
                    ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    'ℹ️ Authentication (Google OAuth & UIBK SAML) is implemented '
                    'in the backend but temporarily disabled in this UI.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                    textAlign: TextAlign.center,
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
}
