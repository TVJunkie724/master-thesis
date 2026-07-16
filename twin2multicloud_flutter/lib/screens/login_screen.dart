import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../config/app_runtime.dart';
import '../models/authentication.dart';
import '../providers/auth_provider.dart';
import '../providers/runtime_providers.dart';
import '../theme/spacing.dart';
import '../widgets/selectable_scaffold.dart';
import 'login_strings.dart';

class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final authState = ref.watch(authProvider);
    final runtime = ref.watch(appRuntimeProvider);

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
                      LoginStrings.appName,
                      style: Theme.of(context).textTheme.headlineMedium,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      LoginStrings.tagline,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: AppSpacing.xl),
                    _LoginBody(runtime: runtime, authState: authState),
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

class _LoginBody extends ConsumerWidget {
  const _LoginBody({required this.runtime, required this.authState});

  final AppRuntimeConfig runtime;
  final AuthState authState;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (runtime.mode == AppMode.development) {
      return _DevelopmentLogin(authState: authState);
    }
    if (runtime.mode == AppMode.demo) {
      return Text(
        LoginStrings.demo,
        style: Theme.of(context).textTheme.bodySmall?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
        textAlign: TextAlign.center,
      );
    }
    if (authState.phase == AuthPhase.loadingCapabilities ||
        authState.phase == AuthPhase.startingProvider) {
      return _AuthProgress(
        message: authState.phase == AuthPhase.loadingCapabilities
            ? LoginStrings.loadingProviders
            : LoginStrings.startingProvider,
      );
    }
    if (authState.phase == AuthPhase.waitingForBrowser) {
      return const _ExternalLoginPending();
    }
    return _ProductionProviderActions(authState: authState);
  }
}

class _DevelopmentLogin extends ConsumerWidget {
  const _DevelopmentLogin({required this.authState});

  final AuthState authState;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (authState.isLoading) {
      return const _AuthProgress(message: LoginStrings.startingProvider);
    }
    return FilledButton.icon(
      onPressed: () async {
        try {
          await ref.read(authProvider.notifier).continueInDevelopment();
          if (context.mounted) context.go('/dashboard');
        } on StateError {
          if (!context.mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text(LoginStrings.localSignInError)),
          );
        }
      },
      icon: const Icon(Icons.developer_mode),
      label: const Text(LoginStrings.localSignIn),
      style: _fullWidthButtonStyle(),
    );
  }
}

class _ProductionProviderActions extends ConsumerWidget {
  const _ProductionProviderActions({required this.authState});

  final AuthState authState;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final capabilities = authState.capabilities;
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          LoginStrings.signInHeading,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: AppSpacing.xs),
        Text(
          LoginStrings.signInIntro,
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        for (final capability in capabilities) ...[
          _ProviderAction(capability: capability),
          if (capability != capabilities.last)
            const SizedBox(height: AppSpacing.sm),
        ],
        if (authState.errorMessage != null) ...[
          const SizedBox(height: AppSpacing.md),
          Semantics(
            liveRegion: true,
            child: Text(
              authState.errorMessage!,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.error,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          TextButton.icon(
            onPressed: () => ref.read(authProvider.notifier).loadCapabilities(),
            icon: const Icon(Icons.refresh),
            label: const Text(LoginStrings.retry),
          ),
        ],
      ],
    );
  }
}

class _ProviderAction extends ConsumerWidget {
  const _ProviderAction({required this.capability});

  final AuthProviderCapability capability;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = capability.provider;
    final label = switch (provider) {
      IdentityProvider.uibk => LoginStrings.uibkSignIn,
      IdentityProvider.google => LoginStrings.googleSignIn,
    };
    final icon = switch (provider) {
      IdentityProvider.uibk => Icons.school,
      IdentityProvider.google => Icons.account_circle,
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        FilledButton.icon(
          onPressed: capability.enabled
              ? () => unawaited(
                  ref.read(authProvider.notifier).startExternalLogin(provider),
                )
              : null,
          icon: Icon(icon),
          label: Text(label),
          style: _fullWidthButtonStyle(),
        ),
        if (!capability.enabled) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            LoginStrings.unavailable,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ],
    );
  }
}

class _ExternalLoginPending extends ConsumerWidget {
  const _ExternalLoginPending();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Semantics(
      liveRegion: true,
      label: LoginStrings.browserPending,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: AppSpacing.lg),
          Text(
            LoginStrings.browserPending,
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            LoginStrings.browserPendingHint,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.lg),
          TextButton.icon(
            onPressed: () => unawaited(
              ref.read(authProvider.notifier).cancelExternalLogin(),
            ),
            icon: const Icon(Icons.close),
            label: const Text(LoginStrings.cancelSignIn),
          ),
        ],
      ),
    );
  }
}

class _AuthProgress extends StatelessWidget {
  const _AuthProgress({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      liveRegion: true,
      label: message,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: AppSpacing.md),
          Text(message, textAlign: TextAlign.center),
        ],
      ),
    );
  }
}

ButtonStyle _fullWidthButtonStyle() => FilledButton.styleFrom(
  minimumSize: const Size(double.infinity, AppSpacing.actionButtonHeight),
);
