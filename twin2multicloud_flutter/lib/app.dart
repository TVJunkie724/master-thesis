import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'screens/dashboard_screen.dart';
import 'screens/profile_bootstrap_screen.dart';
import 'screens/settings_screen.dart';
import 'screens/wizard/wizard_screen.dart';
import 'screens/twin_overview/twin_overview_screen.dart';
import 'providers/profile_provider.dart';
import 'providers/runtime_providers.dart';
import 'providers/theme_provider.dart';
import 'widgets/demo_mode_banner.dart';

// Router configuration
final routerProvider = Provider<GoRouter>((ref) {
  final router = GoRouter(
    initialLocation: '/dashboard',
    routes: [
      GoRoute(
        path: '/dashboard',
        builder: (context, state) => const DashboardScreen(),
      ),
      GoRoute(
        path: '/settings',
        builder: (context, state) => const SettingsScreen(),
      ),
      GoRoute(
        path: '/wizard',
        builder: (context, state) => const WizardScreen(),
      ),
      GoRoute(
        path: '/wizard/:twinId',
        builder: (context, state) =>
            WizardScreen(twinId: state.pathParameters['twinId']),
      ),
      // Twin Overview page (Phase 1)
      GoRoute(
        path: '/twins/:id/overview',
        builder: (context, state) =>
            TwinOverviewScreen(twinId: state.pathParameters['id']!),
      ),
    ],
  );
  ref.onDispose(router.dispose);
  return router;
});

class Twin2MultiCloudApp extends ConsumerWidget {
  const Twin2MultiCloudApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    final runtime = ref.watch(appRuntimeProvider);
    final profileState = ref.watch(profileProvider);

    // Simple Material theme - uses Material 3 defaults with blue primary
    const Color primaryBlue = Color(0xFF1976D2);

    // Light Theme - Standard Material defaults
    final lightTheme = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryBlue,
        brightness: Brightness.light,
      ),
    );

    // Dark Theme - Standard Material defaults
    final darkTheme = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryBlue,
        brightness: Brightness.dark,
      ),
    );

    return MaterialApp.router(
      title: 'Twin2MultiCloud',
      debugShowCheckedModeBanner: false,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: ref.watch(themeProvider),
      routerConfig: router,
      builder: (context, child) {
        Widget content = child ?? const SizedBox();
        if (!profileState.isAvailable) {
          content = ProfileBootstrapScreen(
            isLoading: profileState.isLoading,
            errorMessage: profileState.errorMessage,
            onRetry: () => ref.read(profileProvider.notifier).loadProfile(),
          );
        }
        if (runtime.isDemo) {
          content = DemoModeBanner(
            scenario: runtime.demoScenario,
            child: content,
          );
        }
        return content;
      },
    );
  }
}
