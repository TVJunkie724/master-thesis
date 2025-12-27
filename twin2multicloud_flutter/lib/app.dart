import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/wizard/wizard_screen.dart';
import 'providers/auth_provider.dart';
import 'providers/theme_provider.dart';

// Router configuration
final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);
  
  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final isLoggedIn = authState.isAuthenticated;
      final isLoggingIn = state.matchedLocation == '/login';
      
      if (!isLoggedIn && !isLoggingIn) return '/login';
      if (isLoggedIn && isLoggingIn) return '/dashboard';
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginScreen(),
      ),
      GoRoute(
        path: '/dashboard',
        builder: (context, state) => const DashboardScreen(),
      ),
      GoRoute(
        path: '/auth/callback',
        builder: (context, state) {
          // Handle OAuth callback (future implementation)
          // TODO: Store token from state.uri.queryParameters['token'] and redirect
          return const DashboardScreen();
        },
      ),
      GoRoute(
        path: '/wizard',
        builder: (context, state) => const WizardScreen(),
      ),
      GoRoute(
        path: '/wizard/:twinId',
        builder: (context, state) => WizardScreen(
          twinId: state.pathParameters['twinId'],
        ),
      ),
    ],
  );
});

class Twin2MultiCloudApp extends ConsumerWidget {
  const Twin2MultiCloudApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);
    
    return MaterialApp.router(
      title: 'Twin2MultiCloud',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.blue,
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      themeMode: ref.watch(themeProvider),
      routerConfig: router,
    );
  }
}
