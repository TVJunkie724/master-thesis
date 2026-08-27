import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/user.dart';
import 'package:twin2multicloud_flutter/providers/profile_provider.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

class _MockManagementApi extends Mock implements ManagementApi {}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test(
    'network runtime loads its configured local profile automatically',
    () async {
      final api = _MockManagementApi();
      final user = User(
        id: 'profile-1',
        email: 'researcher@example.test',
        name: 'Researcher',
      );
      when(() => api.setUnauthorizedHandler(any())).thenReturn(null);
      when(() => api.getCurrentUser()).thenAnswer((_) async => user);
      final container = _container(api);
      addTearDown(container.dispose);

      expect(container.read(profileProvider).isLoading, isTrue);
      await _waitFor(() => container.read(profileProvider).isAvailable);

      expect(container.read(profileProvider).user, same(user));
      verify(() => api.getCurrentUser()).called(1);
    },
  );

  test('failed profile initialization exposes retry and can recover', () async {
    final api = _MockManagementApi();
    var attempt = 0;
    when(() => api.setUnauthorizedHandler(any())).thenReturn(null);
    when(() => api.getCurrentUser()).thenAnswer((_) async {
      if (attempt++ == 0) throw StateError('unavailable');
      return User(id: 'profile-1', email: 'researcher@example.test');
    });
    final container = _container(api);
    addTearDown(container.dispose);
    await _waitFor(
      () => container.read(profileProvider).phase == ProfilePhase.error,
    );

    await container.read(profileProvider.notifier).loadProfile();

    expect(container.read(profileProvider).isAvailable, isTrue);
    verify(() => api.getCurrentUser()).called(2);
  });

  test('unauthorized callback invalidates the active local profile', () async {
    final api = _MockManagementApi();
    void Function()? unauthorized;
    when(() => api.setUnauthorizedHandler(any())).thenAnswer((invocation) {
      unauthorized = invocation.positionalArguments.single as void Function()?;
    });
    when(() => api.getCurrentUser()).thenAnswer(
      (_) async => User(id: 'profile-1', email: 'researcher@example.test'),
    );
    final container = _container(api);
    addTearDown(container.dispose);
    await _waitFor(() => container.read(profileProvider).isAvailable);

    unauthorized!();

    expect(container.read(profileProvider).phase, ProfilePhase.error);
    expect(
      container.read(profileProvider).errorMessage,
      contains('PoC profile'),
    );
  });

  test('demo fixture profile is available synchronously', () {
    final api = _MockManagementApi();
    final user = User(id: 'demo-user', email: 'demo@example.test');
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(const AppRuntimeConfig.demo()),
        apiServiceProvider.overrideWithValue(api),
        initialUserProvider.overrideWithValue(user),
      ],
    );
    addTearDown(container.dispose);

    expect(container.read(profileProvider).user, same(user));
    verifyNever(() => api.getCurrentUser());
  });
}

ProviderContainer _container(ManagementApi api) => ProviderContainer(
  overrides: [
    appRuntimeProvider.overrideWithValue(
      AppRuntimeConfig.development(
        managementApiBaseUri: Uri.parse('http://management.test'),
        pocAuthToken: 'local-token',
      ),
    ),
    apiServiceProvider.overrideWithValue(api),
  ],
);

Future<void> _waitFor(bool Function() condition) async {
  for (var attempt = 0; attempt < 30 && !condition(); attempt++) {
    await Future<void>.delayed(Duration.zero);
  }
  expect(condition(), isTrue);
}
