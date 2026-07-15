import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../config/app_runtime.dart';
import '../providers/auth_provider.dart';
import '../providers/runtime_providers.dart';
import '../theme/spacing.dart';
import '../widgets/selectable_scaffold.dart';

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final runtime = ref.watch(appRuntimeProvider);
    final isDevelopment = runtime.mode == AppMode.development;

    return SelectableScaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Card(
            child: ConstrainedBox(
              constraints: const BoxConstraints(
                maxWidth: AppSpacing.authCardMaxWidth,
              ),
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.xl),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Image.asset(
                      'assets/images/logo_transparent_attempt.png',
                      width: AppSpacing.authLogoSize,
                      height: AppSpacing.authLogoSize,
                      fit: BoxFit.contain,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    Text(
                      'Twin2MultiCloud',
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      'Multi-cloud Digital Twin Platform',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xl),

                    if (authState.isLoading)
                      const CircularProgressIndicator()
                    else if (isDevelopment)
                      FilledButton.icon(
                        onPressed: () async {
                          try {
                            await ref
                                .read(authProvider.notifier)
                                .continueInDevelopment();
                            if (context.mounted) context.go('/dashboard');
                          } on StateError {
                            if (!context.mounted) return;
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'Local sign-in could not be completed. '
                                  'Check the runtime profile and try again.',
                                ),
                              ),
                            );
                          }
                        },
                        icon: const Icon(Icons.developer_mode),
                        label: const Text('Continue in local development'),
                        style: FilledButton.styleFrom(
                          minimumSize: const Size(
                            double.infinity,
                            AppSpacing.actionButtonHeight,
                          ),
                        ),
                      )
                    else if (runtime.mode == AppMode.production) ...[
                      FilledButton.icon(
                        onPressed: null,
                        icon: const Icon(Icons.school),
                        label: const Text('Sign in with UIBK'),
                        style: FilledButton.styleFrom(
                          minimumSize: const Size(
                            double.infinity,
                            AppSpacing.actionButtonHeight,
                          ),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      FilledButton.icon(
                        onPressed: null,
                        icon: const Icon(Icons.login),
                        label: const Text('Sign in with Google'),
                        style: FilledButton.styleFrom(
                          minimumSize: const Size(
                            double.infinity,
                            AppSpacing.actionButtonHeight,
                          ),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.md),
                      Text(
                        'Production sign-in is not configured in this build.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ] else
                      Text(
                        'The offline demo is opened from its configured scenario.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                        textAlign: TextAlign.center,
                      ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
