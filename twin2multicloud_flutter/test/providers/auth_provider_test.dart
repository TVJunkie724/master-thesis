import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/providers/auth_provider.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

class _MockManagementApi extends Mock implements ManagementApi {}

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

    container.read(authProvider.notifier).logout();

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

  test('demo logout preserves its fixture identity and offline session', () {
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

    container.read(authProvider.notifier).logout();

    expect(container.read(authProvider).isAuthenticated, isTrue);
    expect(container.read(authProvider).user, same(demoIdentity));
    verifyNever(() => api.setToken(any()));
  });
}

ProviderContainer _container(
  AppRuntimeConfig runtime,
  ManagementApi managementApi,
) {
  return ProviderContainer(
    overrides: [
      appRuntimeProvider.overrideWithValue(runtime),
      apiServiceProvider.overrideWithValue(managementApi),
    ],
  );
}
