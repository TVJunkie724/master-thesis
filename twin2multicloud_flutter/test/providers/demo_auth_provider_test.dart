import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/user.dart';
import 'package:twin2multicloud_flutter/providers/auth_provider.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';

void main() {
  final demoUser = User(
    id: 'demo-user',
    email: 'demo@example.com',
    name: 'Demo Operator',
    authProvider: 'demo',
  );

  test('demo identity is authenticated synchronously at startup', () {
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(const AppRuntimeConfig.demo()),
        initialUserProvider.overrideWithValue(demoUser),
      ],
    );
    addTearDown(container.dispose);

    final auth = container.read(authProvider);

    expect(auth.isAuthenticated, isTrue);
    expect(auth.isLoading, isFalse);
    expect(auth.user?.id, 'demo-user');
  });

  test('real runtime remains unauthenticated without an initial user', () {
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(
          AppRuntimeConfig.production(
            managementApiBaseUri: Uri.parse('https://management.test'),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    expect(container.read(authProvider).isAuthenticated, isFalse);
  });
}
