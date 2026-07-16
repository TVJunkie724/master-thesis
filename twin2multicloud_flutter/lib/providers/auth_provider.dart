import 'dart:async';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_runtime.dart';
import '../models/authentication.dart';
import '../models/user.dart';
import '../services/external_auth_launcher.dart';
import '../utils/api_error_handler.dart';
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

enum AuthPhase {
  initial,
  loadingCapabilities,
  ready,
  startingProvider,
  waitingForBrowser,
  authenticated,
  error,
}

class AuthState {
  const AuthState({
    this.phase = AuthPhase.initial,
    this.user,
    this.capabilities = const [],
    this.activeProvider,
    this.pendingTransaction,
    this.errorMessage,
  });

  final AuthPhase phase;
  final User? user;
  final List<AuthProviderCapability> capabilities;
  final IdentityProvider? activeProvider;
  final AuthLoginTransaction? pendingTransaction;
  final String? errorMessage;

  bool get isAuthenticated => user != null;

  bool get isLoading => switch (phase) {
    AuthPhase.loadingCapabilities ||
    AuthPhase.startingProvider ||
    AuthPhase.waitingForBrowser => true,
    _ => false,
  };
}

class AuthNotifier extends Notifier<AuthState> {
  int _operationGeneration = 0;
  bool _disposed = false;
  ExternalAuthLaunchHandle? _activeLaunchHandle;

  @override
  AuthState build() {
    _disposed = false;
    final runtime = ref.watch(appRuntimeProvider);
    final initialUser = ref.watch(initialUserProvider);
    if (runtime.isDemo) {
      return initialUser == null
          ? const AuthState(phase: AuthPhase.ready)
          : AuthState(phase: AuthPhase.authenticated, user: initialUser);
    }

    final api = ref.watch(apiServiceProvider);
    api.setUnauthorizedHandler(_handleUnauthorizedSession);
    ref.onDispose(() {
      _disposed = true;
      _operationGeneration++;
      unawaited(_activeLaunchHandle?.close());
      _activeLaunchHandle = null;
      api.setUnauthorizedHandler(null);
    });

    if (initialUser != null) {
      return AuthState(phase: AuthPhase.authenticated, user: initialUser);
    }

    if (runtime.mode == AppMode.production) {
      unawaited(Future<void>.microtask(loadCapabilities));
      return const AuthState(phase: AuthPhase.loadingCapabilities);
    }
    return const AuthState(phase: AuthPhase.ready);
  }

  Future<void> loadCapabilities() async {
    final runtime = ref.read(appRuntimeProvider);
    if (runtime.mode != AppMode.production) return;
    final generation = ++_operationGeneration;
    state = AuthState(
      phase: AuthPhase.loadingCapabilities,
      capabilities: state.capabilities,
    );
    try {
      final capabilities = await ref
          .read(apiServiceProvider)
          .getAuthProviders();
      if (!_isActive(generation)) return;
      state = AuthState(
        phase: AuthPhase.ready,
        capabilities: capabilities,
        errorMessage: capabilities.any((item) => item.enabled)
            ? null
            : 'No production sign-in provider is currently enabled.',
      );
    } catch (error) {
      if (!_isActive(generation)) return;
      state = AuthState(
        phase: AuthPhase.error,
        capabilities: state.capabilities,
        errorMessage: _safeErrorMessage(error),
      );
    }
  }

  Future<void> startExternalLogin(IdentityProvider provider) async {
    final runtime = ref.read(appRuntimeProvider);
    if (runtime.mode != AppMode.production) {
      throw StateError(
        'External sign-in is available only in the production runtime.',
      );
    }
    final capability = state.capabilities
        .where((item) => item.provider == provider)
        .firstOrNull;
    if (capability == null || !capability.enabled || state.isLoading) return;

    final generation = ++_operationGeneration;
    final launchHandle = ref.read(externalAuthLauncherProvider).reserve();
    _activeLaunchHandle = launchHandle;
    state = AuthState(
      phase: AuthPhase.startingProvider,
      capabilities: state.capabilities,
      activeProvider: provider,
    );
    AuthLoginTransaction? transaction;
    try {
      final api = ref.read(apiServiceProvider);
      transaction = await api.startExternalLogin(provider);
      if (!_isActive(generation)) return;
      final opened = await launchHandle.navigate(transaction.authUri);
      if (!_isActive(generation)) return;
      if (!opened) {
        await api.cancelAuthSession(transaction);
        throw StateError('The system browser could not be opened.');
      }
      state = AuthState(
        phase: AuthPhase.waitingForBrowser,
        capabilities: state.capabilities,
        activeProvider: provider,
        pendingTransaction: transaction,
      );
      await _pollForSession(generation, transaction);
    } catch (error) {
      await launchHandle.close();
      if (identical(_activeLaunchHandle, launchHandle)) {
        _activeLaunchHandle = null;
      }
      if (!_isActive(generation)) return;
      state = AuthState(
        phase: AuthPhase.error,
        capabilities: state.capabilities,
        activeProvider: provider,
        pendingTransaction: transaction,
        errorMessage: _safeErrorMessage(error),
      );
    }
  }

  Future<void> cancelExternalLogin() async {
    final transaction = state.pendingTransaction;
    if (transaction == null) return;
    ++_operationGeneration;
    final launchHandle = _activeLaunchHandle;
    _activeLaunchHandle = null;
    try {
      await ref.read(apiServiceProvider).cancelAuthSession(transaction);
      if (_disposed) return;
      state = AuthState(
        phase: AuthPhase.ready,
        capabilities: state.capabilities,
      );
    } catch (error) {
      if (_disposed) return;
      state = AuthState(
        phase: AuthPhase.error,
        capabilities: state.capabilities,
        errorMessage: _safeErrorMessage(error),
      );
    } finally {
      await launchHandle?.close();
    }
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

    state = const AuthState(phase: AuthPhase.startingProvider);
    ref.read(apiServiceProvider).setToken(token);
    final user = ref.read(initialUserProvider) ?? developmentUser;
    state = AuthState(phase: AuthPhase.authenticated, user: user);
    ref.read(themeProvider.notifier).hydrateFromUser(user.themePreference);
  }

  Future<void> logout() async {
    final runtime = ref.read(appRuntimeProvider);
    final initialUser = ref.read(initialUserProvider);
    if (runtime.isDemo && initialUser != null) {
      state = AuthState(phase: AuthPhase.authenticated, user: initialUser);
      return;
    }
    ++_operationGeneration;
    unawaited(_activeLaunchHandle?.close());
    _activeLaunchHandle = null;
    final api = ref.read(apiServiceProvider);
    try {
      if (runtime.mode == AppMode.production && state.isAuthenticated) {
        await api.logoutSession();
      }
    } finally {
      api.setToken(null);
      if (!_disposed) {
        state = AuthState(
          phase: runtime.mode == AppMode.production
              ? AuthPhase.loadingCapabilities
              : AuthPhase.ready,
        );
        if (runtime.mode == AppMode.production) {
          unawaited(loadCapabilities());
        }
      }
    }
  }

  Future<void> _pollForSession(
    int generation,
    AuthLoginTransaction transaction,
  ) async {
    var transientFailures = 0;
    while (_isActive(generation)) {
      if (!ref.read(authClockProvider)().isBefore(transaction.expiresAt)) {
        throw StateError('The sign-in request expired. Please try again.');
      }
      await ref.read(authPollDelayProvider)(transaction.pollInterval);
      if (!_isActive(generation)) return;
      try {
        final result = await ref
            .read(apiServiceProvider)
            .exchangeAuthSession(transaction);
        transientFailures = 0;
        switch (result) {
          case AuthExchangePending():
            continue;
          case AuthExchangeAuthenticated():
            final api = ref.read(apiServiceProvider);
            api.setToken(result.accessToken);
            state = AuthState(
              phase: AuthPhase.authenticated,
              user: result.user,
              capabilities: state.capabilities,
            );
            ref
                .read(themeProvider.notifier)
                .hydrateFromUser(result.user.themePreference);
            await _activeLaunchHandle?.close();
            _activeLaunchHandle = null;
            return;
        }
      } on DioException catch (error) {
        if (!_isTransient(error) || ++transientFailures > 3) rethrow;
      }
    }
  }

  void _handleUnauthorizedSession() {
    if (_disposed || ref.read(appRuntimeProvider).mode != AppMode.production) {
      return;
    }
    ++_operationGeneration;
    unawaited(_activeLaunchHandle?.close());
    _activeLaunchHandle = null;
    state = AuthState(
      phase: AuthPhase.error,
      capabilities: state.capabilities,
      errorMessage: 'Your session expired. Sign in again to continue.',
    );
  }

  bool _isActive(int generation) =>
      !_disposed && generation == _operationGeneration;

  static bool _isTransient(DioException error) => switch (error.type) {
    DioExceptionType.connectionTimeout ||
    DioExceptionType.sendTimeout ||
    DioExceptionType.receiveTimeout ||
    DioExceptionType.connectionError => true,
    _ => false,
  };

  static String _safeErrorMessage(Object error) {
    if (error is DioException) return ApiErrorHandler.extractMessage(error);
    if (error is FormatException) {
      return 'The authentication service returned an invalid response.';
    }
    if (error is StateError) {
      return error.message.toString();
    }
    return 'Sign-in could not be completed. Please try again.';
  }
}
