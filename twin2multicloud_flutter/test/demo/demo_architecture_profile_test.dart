import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/demo/demo_management_api.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'demo keeps the active catalog empty and historical selection read-only',
    () async {
      final store = await DemoFixtureStore.load(
        DemoScenario.showcase,
        clock: () => DateTime.utc(2026, 8, 3),
      );
      final api = DemoManagementApi(store: store, latency: Duration.zero);

      expect(await api.listArchitectureProfiles(), isEmpty);
      final selection = await api.getTwinArchitectureSelection('demo-draft');
      expect(selection.profileRef.id, 'five-layer-baseline');
      expect(selection.profileRef.version, '1');

      await expectLater(
        api.getArchitectureProfile('five-layer-baseline', '1'),
        throwsA(
          isA<DemoApiException>().having(
            (error) => error.code,
            'code',
            'ARCH_PROFILE_NOT_ACTIVE',
          ),
        ),
      );
      await expectLater(
        api.previewTwinArchitectureProfileChange(
          'demo-draft',
          const ArchitectureProfileChangePreviewRequest(
            profileId: 'fixture-profile',
            profileVersion: '2',
            expectedRevision: 1,
          ),
        ),
        throwsA(
          isA<DemoApiException>().having(
            (error) => error.code,
            'code',
            'ARCH_PROFILE_NOT_ACTIVE',
          ),
        ),
      );
    },
  );
}
