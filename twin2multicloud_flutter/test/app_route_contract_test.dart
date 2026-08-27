import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:twin2multicloud_flutter/app.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/providers/auth_provider.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';

void main() {
  test('router exposes only the bounded research workflow routes', () {
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(
          AppRuntimeConfig.demo(demoScenario: DemoScenario.empty),
        ),
        initialUserProvider.overrideWithValue(developmentUser),
      ],
    );
    addTearDown(container.dispose);

    final paths = container
        .read(routerProvider)
        .configuration
        .routes
        .whereType<GoRoute>()
        .map((route) => route.path)
        .toList(growable: false);

    expect(paths, [
      '/login',
      '/dashboard',
      '/settings',
      '/wizard',
      '/wizard/:twinId',
      '/twins/:id/overview',
    ]);
    expect(paths, isNot(contains('/pricing-review')));
  });
}
