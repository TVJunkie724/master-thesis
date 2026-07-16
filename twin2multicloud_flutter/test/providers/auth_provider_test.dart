import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/authentication.dart';
import 'package:twin2multicloud_flutter/models/user.dart';
import 'package:twin2multicloud_flutter/providers/auth_provider.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/services/external_auth_launcher.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

class _MockManagementApi extends Mock implements ManagementApi {}

class _MockExternalAuthLauncher extends Mock implements ExternalAuthLauncher {}

class _MockExternalAuthLaunchHandle extends Mock
    implements ExternalAuthLaunchHandle {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test(
    'development sign-in installs the configured token and identity',
    () async {
      final api = _MockManagementApi();
      final container = _container(
        AppRuntimeConfig.development(
          managementApiBaseUri: Uri.parse('http://management.test'),
          developmentAuthToken: 'local-token',
        ),
        api,
      );
      addTearDown(container.dispose);

      await container.read(authProvider.notifier).continueInDevelopment();

      final state = container.read(authProvider);
      expect(state.isAuthenticated, isTrue);
      expect(state.isLoading, isFalse);
      expect(state.user?.authProvider, 'development');
      verify(() => api.setToken('local-token')).called(1);
    },
  );

  test('logout clears the in-memory bearer token and identity', () async {
    final api = _MockManagementApi();
    final container = _container(
      AppRuntimeConfig.development(
        managementApiBaseUri: Uri.parse('http://management.test'),
        developmentAuthToken: 'local-token',
      ),
      api,
    );
    addTearDown(container.dispose);
    await container.read(authProvider.notifier).continueInDevelopment();

    await container.read(authProvider.notifier).logout();

    expect(container.read(authProvider).isAuthenticated, isFalse);
    expect(container.read(authProvider).user, isNull);
    verify(() => api.setToken(null)).called(1);
  });

  for (final entry in <String, AppRuntimeConfig>{
    'production': AppRuntimeConfig.production(
      managementApiBaseUri: Uri.parse('https://management.test'),
    ),
    'demo': const AppRuntimeConfig.demo(),
  }.entries) {
    test('${entry.key} rejects the development sign-in command', () async {
      final api = _MockManagementApi();
      if (entry.value.mode == AppMode.production) {
        when(() => api.getAuthProviders()).thenAnswer((_) async => const []);
      }
      final container = _container(entry.value, api);
      addTearDown(container.dispose);

      await expectLater(
        container.read(authProvider.notifier).continueInDevelopment(),
        throwsA(isA<StateError>()),
      );

      expect(container.read(authProvider).isAuthenticated, isFalse);
      verifyNever(() => api.setToken(any()));
    });
  }

  test(
    'demo logout preserves its fixture identity and offline session',
    () async {
      final api = _MockManagementApi();
      final demoIdentity = developmentUser;
      final container = ProviderContainer(
        overrides: [
          appRuntimeProvider.overrideWithValue(const AppRuntimeConfig.demo()),
          apiServiceProvider.overrideWithValue(api),
          initialUserProvider.overrideWithValue(demoIdentity),
        ],
      );
      addTearDown(container.dispose);

      await container.read(authProvider.notifier).logout();

      expect(container.read(authProvider).isAuthenticated, isTrue);
      expect(container.read(authProvider).user, same(demoIdentity));
      verifyNever(() => api.setToken(any()));
    },
  );

  test('production login opens browser, polls, and installs session', () async {
    final api = _MockManagementApi();
    final launcher = _MockExternalAuthLauncher();
    final launchHandle = _MockExternalAuthLaunchHandle();
    final transaction = _transaction();
    final user = User(
      id: 'user-1',
      email: 'person@example.test',
      name: 'Test Person',
      authProvider: 'google',
      googleLinked: true,
    );
    when(() => api.setUnauthorizedHandler(any())).thenReturn(null);
    when(
      () => api.getAuthProviders(),
    ).thenAnswer((_) async => [_googleCapability(enabled: true)]);
    when(
      () => api.startExternalLogin(IdentityProvider.google),
    ).thenAnswer((_) async => transaction);
    when(() => launcher.reserve()).thenReturn(launchHandle);
    when(
      () => launchHandle.navigate(transaction.authUri),
    ).thenAnswer((_) async => true);
    when(() => launchHandle.close()).thenAnswer((_) async {});
    var polls = 0;
    when(() => api.exchangeAuthSession(transaction)).thenAnswer((_) async {
      if (polls++ == 0) return const AuthExchangePending();
      return AuthExchangeAuthenticated(
        accessToken: 'production-token',
        expiresIn: const Duration(hours: 1),
        user: user,
      );
    });

    final container = _container(
      AppRuntimeConfig.production(
        managementApiBaseUri: Uri.parse('https://management.test'),
      ),
      api,
      launcher: launcher,
      pollDelay: (_) async {},
    );
    addTearDown(container.dispose);
    await _waitFor(() => container.read(authProvider).phase == AuthPhase.ready);

    await container
        .read(authProvider.notifier)
        .startExternalLogin(IdentityProvider.google);

    final state = container.read(authProvider);
    expect(state.phase, AuthPhase.authenticated);
    expect(state.user, same(user));
    verify(() => launcher.reserve()).called(1);
    verify(() => launchHandle.navigate(transaction.authUri)).called(1);
    verify(() => api.setToken('production-token')).called(1);
    verify(() => api.exchangeAuthSession(transaction)).called(2);
  });

  test('browser launch failure cancels durable transaction', () async {
    final api = _MockManagementApi();
    final launcher = _MockExternalAuthLauncher();
    final launchHandle = _MockExternalAuthLaunchHandle();
    final transaction = _transaction();
    when(() => api.setUnauthorizedHandler(any())).thenReturn(null);
    when(
      () => api.getAuthProviders(),
    ).thenAnswer((_) async => [_googleCapability(enabled: true)]);
    when(
      () => api.startExternalLogin(IdentityProvider.google),
    ).thenAnswer((_) async => transaction);
    when(() => launcher.reserve()).thenReturn(launchHandle);
    when(
      () => launchHandle.navigate(transaction.authUri),
    ).thenAnswer((_) async => false);
    when(() => launchHandle.close()).thenAnswer((_) async {});
    when(() => api.cancelAuthSession(transaction)).thenAnswer((_) async {});
    final container = _container(
      AppRuntimeConfig.production(
        managementApiBaseUri: Uri.parse('https://management.test'),
      ),
      api,
      launcher: launcher,
    );
    addTearDown(container.dispose);
    await _waitFor(() => container.read(authProvider).phase == AuthPhase.ready);

    await container
        .read(authProvider.notifier)
        .startExternalLogin(IdentityProvider.google);

    expect(container.read(authProvider).phase, AuthPhase.error);
    expect(
      container.read(authProvider).errorMessage,
      'The system browser could not be opened.',
    );
    verify(() => api.cancelAuthSession(transaction)).called(1);
  });

  test('user cancellation stops polling and cancels server state', () async {
    final api = _MockManagementApi();
    final launcher = _MockExternalAuthLauncher();
    final launchHandle = _MockExternalAuthLaunchHandle();
    final transaction = _transaction();
    final delayStarted = Completer<void>();
    final releaseDelay = Completer<void>();
    when(
      () => api.getAuthProviders(),
    ).thenAnswer((_) async => [_googleCapability(enabled: true)]);
    when(
      () => api.startExternalLogin(IdentityProvider.google),
    ).thenAnswer((_) async => transaction);
    when(() => launcher.reserve()).thenReturn(launchHandle);
    when(
      () => launchHandle.navigate(transaction.authUri),
    ).thenAnswer((_) async => true);
    when(() => launchHandle.close()).thenAnswer((_) async {});
    when(() => api.cancelAuthSession(transaction)).thenAnswer((_) async {});
    final container = _container(
      AppRuntimeConfig.production(
        managementApiBaseUri: Uri.parse('https://management.test'),
      ),
      api,
      launcher: launcher,
      pollDelay: (_) {
        if (!delayStarted.isCompleted) delayStarted.complete();
        return releaseDelay.future;
      },
    );
    addTearDown(container.dispose);
    await _waitFor(() => container.read(authProvider).phase == AuthPhase.ready);

    final login = container
        .read(authProvider.notifier)
        .startExternalLogin(IdentityProvider.google);
    await delayStarted.future;
    await container.read(authProvider.notifier).cancelExternalLogin();
    releaseDelay.complete();
    await login;

    expect(container.read(authProvider).phase, AuthPhase.ready);
    verify(() => api.cancelAuthSession(transaction)).called(1);
    verifyNever(() => api.exchangeAuthSession(transaction));
  });

  test('unauthorized callback removes the production identity', () async {
    final api = _MockManagementApi();
    void Function()? unauthorized;
    when(() => api.setUnauthorizedHandler(any())).thenAnswer((invocation) {
      unauthorized = invocation.positionalArguments.single as void Function()?;
    });
    when(() => api.getAuthProviders()).thenAnswer((_) async => const []);
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(
          AppRuntimeConfig.production(
            managementApiBaseUri: Uri.parse('https://management.test'),
          ),
        ),
        apiServiceProvider.overrideWithValue(api),
        initialUserProvider.overrideWithValue(
          User(
            id: 'user-1',
            email: 'person@example.test',
            authProvider: 'google',
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    expect(container.read(authProvider).isAuthenticated, isTrue);

    unauthorized!();

    expect(container.read(authProvider).isAuthenticated, isFalse);
    expect(container.read(authProvider).phase, AuthPhase.error);
    expect(
      container.read(authProvider).errorMessage,
      contains('session expired'),
    );
  });
}

ProviderContainer _container(
  AppRuntimeConfig runtime,
  ManagementApi managementApi, {
  ExternalAuthLauncher? launcher,
  Future<void> Function(Duration)? pollDelay,
}) {
  return ProviderContainer(
    overrides: [
      appRuntimeProvider.overrideWithValue(runtime),
      apiServiceProvider.overrideWithValue(managementApi),
      if (launcher != null)
        externalAuthLauncherProvider.overrideWithValue(launcher),
      if (pollDelay != null) authPollDelayProvider.overrideWithValue(pollDelay),
    ],
  );
}

AuthLoginTransaction _transaction() => AuthLoginTransaction(
  authUri: Uri.parse('https://accounts.example.test/sign-in'),
  transactionId: '11111111-1111-4111-8111-111111111111',
  pollVerifier: 'poll-verifier-with-at-least-thirty-two-characters',
  expiresAt: DateTime.now().toUtc().add(const Duration(minutes: 5)),
  pollInterval: const Duration(seconds: 1),
);

AuthProviderCapability _googleCapability({required bool enabled}) =>
    AuthProviderCapability(
      provider: IdentityProvider.google,
      displayName: 'Google',
      enabled: enabled,
      unavailableReason: enabled ? null : 'not_configured',
    );

Future<void> _waitFor(bool Function() condition) async {
  for (var attempt = 0; attempt < 20 && !condition(); attempt++) {
    await Future<void>.delayed(Duration.zero);
  }
  expect(condition(), isTrue);
}
