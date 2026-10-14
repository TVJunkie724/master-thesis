import 'package:flutter/material.dart';

import '../theme/spacing.dart';

abstract class ProfileBootstrapStrings {
  static const loading = 'Loading local PoC profile';
  static const failed = 'Local PoC profile unavailable';
  static const retry = 'Retry';
}

class ProfileBootstrapScreen extends StatelessWidget {
  const ProfileBootstrapScreen({
    required this.isLoading,
    required this.errorMessage,
    required this.onRetry,
    super.key,
  });

  final bool isLoading;
  final String? errorMessage;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    // MaterialApp.builder runs above the Navigator overlay. Keep this
    // bootstrap surface independent from SelectableScaffold, which requires
    // an Overlay ancestor for its SelectionArea.
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppSpacing.authCardMaxWidth,
          ),
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: Semantics(
                liveRegion: true,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (isLoading) ...[
                      const CircularProgressIndicator(),
                      const SizedBox(height: AppSpacing.lg),
                      Text(
                        ProfileBootstrapStrings.loading,
                        style: Theme.of(context).textTheme.titleMedium,
                        textAlign: TextAlign.center,
                      ),
                    ] else ...[
                      Icon(
                        Icons.person_off_outlined,
                        size: AppSpacing.iconMd,
                        color: Theme.of(context).colorScheme.error,
                      ),
                      const SizedBox(height: AppSpacing.md),
                      Text(
                        ProfileBootstrapStrings.failed,
                        style: Theme.of(context).textTheme.titleMedium,
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        errorMessage ?? ProfileBootstrapStrings.failed,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                        textAlign: TextAlign.center,
                      ),
                      const SizedBox(height: AppSpacing.lg),
                      FilledButton.icon(
                        onPressed: onRetry,
                        icon: const Icon(Icons.refresh),
                        label: const Text(ProfileBootstrapStrings.retry),
                      ),
                    ],
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
