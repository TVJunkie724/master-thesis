import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../providers/auth_provider.dart';

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
    
    return Scaffold(
      body: Center(
        child: Card(
          elevation: 8,
          child: Container(
            width: 400,
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Logo
                Icon(
                  Icons.cloud_sync,
                  size: 64,
                  color: Theme.of(context).colorScheme.primary,
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
                  // Google OAuth button
                  FilledButton.icon(
                    onPressed: () async {
                      // In dev mode, use mock login
                      if (kDebugMode) {
                        await ref.read(authProvider.notifier).mockLogin();
                        if (context.mounted) {
                          context.go('/dashboard');
                        }
                        return;
                      }
                      // TODO: Production OAuth flow
                    },
                    icon: const Icon(Icons.login),
                    label: const Text('Sign in with Google'),
                    style: FilledButton.styleFrom(
                      minimumSize: const Size(double.infinity, 48),
                    ),
                  ),
                  
                  // ============================================================
                  // UIBK SAML Login Button - COMMENTED OUT until SAML is configured
                  // Uncomment when ACOnet registration is complete and SAML_ENABLED=true
                  // ============================================================
                  // const SizedBox(height: 12),
                  // FilledButton.icon(
                  //   onPressed: () async {
                  //     // In dev mode, use mock login
                  //     if (kDebugMode) {
                  //       await ref.read(authProvider.notifier).mockLogin();
                  //       if (context.mounted) {
                  //         context.go('/dashboard');
                  //       }
                  //       return;
                  //     }
                  //     // TODO: Production SAML flow via /auth/uibk/login
                  //   },
                  //   icon: const Icon(Icons.school),
                  //   label: const Text('Sign in with UIBK'),
                  //   style: FilledButton.styleFrom(
                  //     backgroundColor: const Color(0xFF003366), // UIBK brand color
                  //     foregroundColor: Colors.white,
                  //     minimumSize: const Size(double.infinity, 48),
                  //   ),
                  // ),
                ],
                
                const SizedBox(height: 16),
                Text(
                  'Development Mode: Mock Login',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
                ),
                
                // Hint about UIBK login (for future)
                // const SizedBox(height: 8),
                // Text(
                //   'University members can use their UIBK credentials',
                //   style: Theme.of(context).textTheme.bodySmall?.copyWith(
                //     color: Theme.of(context).colorScheme.outline,
                //   ),
                //   textAlign: TextAlign.center,
                // ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

