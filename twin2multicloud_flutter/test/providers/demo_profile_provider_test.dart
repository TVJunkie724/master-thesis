import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/user.dart';
import 'package:twin2multicloud_flutter/providers/profile_provider.dart';
import 'package:twin2multicloud_flutter/providers/runtime_providers.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final demoUser = User(
    id: 'demo-user',
    email: 'demo@example.com',
    name: 'Demo Operator',
  );

  test('demo profile is available synchronously at startup', () {
    final container = ProviderContainer(
      overrides: [
        appRuntimeProvider.overrideWithValue(const AppRuntimeConfig.demo()),
        initialUserProvider.overrideWithValue(demoUser),
      ],
    );
    addTearDown(container.dispose);

    final profile = container.read(profileProvider);

    expect(profile.isAvailable, isTrue);
    expect(profile.isLoading, isFalse);
    expect(profile.user?.id, 'demo-user');
  });

  test(
    'network runtime loads a profile instead of exposing a login state',
    () async {
      final api = _ProfileApi();
      final container = ProviderContainer(
        overrides: [
          appRuntimeProvider.overrideWithValue(
            AppRuntimeConfig.production(
              managementApiBaseUri: Uri.parse('https://management.test'),
              pocAuthToken: 'local-token',
            ),
          ),
          apiServiceProvider.overrideWithValue(api),
        ],
      );
      addTearDown(container.dispose);

      expect(container.read(profileProvider).isLoading, isTrue);
      for (
        var attempt = 0;
        attempt < 20 && !container.read(profileProvider).isAvailable;
        attempt++
      ) {
        await Future<void>.delayed(Duration.zero);
      }
      expect(container.read(profileProvider).isAvailable, isTrue);
    },
  );
}

class _ProfileApi extends Fake implements ManagementApi {
  @override
  void setUnauthorizedHandler(void Function()? handler) {}

  @override
  Future<User> getCurrentUser() async =>
      User(id: 'profile-user', email: 'profile@example.test');
}
