import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'screens/login_screen.dart';
import 'screens/dashboard_screen.dart';
import 'screens/settings_screen.dart';
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
        path: '/settings',
        builder: (context, state) => const SettingsScreen(),
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
    
    // ═══════════════════════════════════════════════════════════════════════════
    // TWIN2MULTICLOUD PREMIUM THEME
    // A cohesive design system inspired by multi-cloud (AWS/Azure/GCP)
    // Primary: Deep Azure Blue | Accent: Warm Cloud Orange | Surface: Rich Dark
    // ═══════════════════════════════════════════════════════════════════════════
    
    // Brand palette
    const Color cloudOrange = Color(0xFFFF9900);    // AWS-inspired warm accent
    const Color deepAzure = Color(0xFF1565C0);       // Rich azure blue (primary)
    const Color techGreen = Color(0xFF2E7D32);       // Muted tech green
    
    // Light Theme - Clean & Professional
    final lightTheme = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: deepAzure,
        brightness: Brightness.light,
        primary: deepAzure,
        secondary: cloudOrange,
        tertiary: techGreen,
      ),
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 2,
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF1a1a2e),
        surfaceTintColor: deepAzure.withAlpha(20),
      ),
      cardTheme: CardThemeData(
        elevation: 2,
        shadowColor: deepAzure.withAlpha(30),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: deepAzure,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: deepAzure,
          side: BorderSide(color: deepAzure.withAlpha(150)),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: BorderSide(color: deepAzure, width: 2),
        ),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
      dividerTheme: DividerThemeData(
        color: deepAzure.withAlpha(20),
      ),
    );
    
    // Dark Theme - Premium & Rich
    final darkTheme = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: deepAzure,
        brightness: Brightness.dark,
        primary: const Color(0xFF64B5F6),       // Lighter blue for dark mode
        secondary: cloudOrange,
        tertiary: const Color(0xFF81C784),       // Lighter green for dark mode
        surface: const Color(0xFF1a1a2e),        // Deep navy surface
        surfaceContainerHighest: const Color(0xFF252540), // Elevated surfaces
      ),
      scaffoldBackgroundColor: const Color(0xFF12121f),  // Deep dark background
      appBarTheme: const AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 2,
        backgroundColor: Color(0xFF1a1a2e),
        surfaceTintColor: Color(0xFF64B5F6),
      ),
      cardTheme: CardThemeData(
        elevation: 4,
        color: const Color(0xFF1e1e35),
        shadowColor: Colors.black45,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: const Color(0xFF1976D2),
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFF64B5F6),
          side: const BorderSide(color: Color(0xFF64B5F6)),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
          borderSide: const BorderSide(color: Color(0xFF64B5F6), width: 2),
        ),
        filled: true,
        fillColor: const Color(0xFF252540),
      ),
      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: Color(0xFF303050),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: const Color(0xFF1e1e35),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: const Color(0xFF303050),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
    );
    
    return MaterialApp.router(
      title: 'Twin2MultiCloud',
      debugShowCheckedModeBanner: false,
      theme: lightTheme,
      darkTheme: darkTheme,
      themeMode: ref.watch(themeProvider),
      routerConfig: router,
    );
  }
}
