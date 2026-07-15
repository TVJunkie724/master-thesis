import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../config/app_runtime.dart';
import '../models/user.dart';
import 'runtime_providers.dart';
import 'theme_provider.dart';

final developmentUser = User(
  id: 'local-development-user',
  email: 'developer@example.com',
  name: 'Local Developer',
  authProvider: 'development',
  themePreference: 'dark',
);

final authProvider = NotifierProvider<AuthNotifier, AuthState>(
  AuthNotifier.new,
);

class AuthState {
  final User? user;
  final bool isLoading;

  const AuthState({this.user, this.isLoading = false});

  bool get isAuthenticated => user != null;
}

class AuthNotifier extends Notifier<AuthState> {
  @override
  AuthState build() {
    final initialUser = ref.watch(initialUserProvider);
    if (initialUser != null) {
      return AuthState(user: initialUser);
    }
    return const AuthState();
  }

  Future<void> continueInDevelopment() async {
    final runtime = ref.read(appRuntimeProvider);
    if (runtime.mode != AppMode.development) {
      throw StateError(
        'Local development sign-in is unavailable in this runtime profile.',
      );
    }
    if (state.isLoading || state.isAuthenticated) return;

    final token = runtime.initialAuthToken;
    if (token == null) {
      throw StateError('Development runtime is missing its auth token.');
    }

    state = const AuthState(isLoading: true);
    ref.read(apiServiceProvider).setToken(token);
    final user = ref.read(initialUserProvider) ?? developmentUser;
    state = AuthState(user: user);

    ref.read(themeProvider.notifier).hydrateFromUser(user.themePreference);
  }

  void logout() {
    final runtime = ref.read(appRuntimeProvider);
    final initialUser = ref.read(initialUserProvider);
    if (runtime.isDemo && initialUser != null) {
      state = AuthState(user: initialUser);
      return;
    }
    ref.read(apiServiceProvider).setToken(null);
    state = const AuthState();
  }
}
