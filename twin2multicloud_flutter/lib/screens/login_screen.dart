import 'package:flutter/material.dart';

import '../theme/spacing.dart';
import '../widgets/selectable_scaffold.dart';

abstract class LoginStrings {
  static const appName = 'Twin2MultiCloud';
  static const disabledTitle = 'Interactive sign-in is disabled';
  static const disabledBody =
      'The thesis PoC initializes its configured local user profile '
      'automatically. This screen is intentionally not routed.';
}

/// Dormant presentation seam for a possible later interactive login.
///
/// The thesis PoC does not register a route to this screen and does not ship
/// OAuth, SAML, OIDC, or provider-specific sign-in implementations.
class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
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
                    const SizedBox(height: AppSpacing.lg),
                    Text(
                      LoginStrings.disabledTitle,
                      style: Theme.of(context).textTheme.titleMedium,
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Text(
                      LoginStrings.disabledBody,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
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
