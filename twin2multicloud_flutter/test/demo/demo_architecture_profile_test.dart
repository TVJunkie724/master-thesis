import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/demo/demo_management_api.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'demo exposes the active Five-layer v2 catalog and pinned selection',
    () async {
      final store = await DemoFixtureStore.load(
        DemoScenario.showcase,
        clock: () => DateTime.utc(2026, 8, 3),
      );
      final api = DemoManagementApi(store: store, latency: Duration.zero);

      final profiles = await api.listArchitectureProfiles();
      expect(profiles, hasLength(1));
      expect(profiles.single.profileId, 'five-layer-baseline');
      expect(profiles.single.profileVersion, '2');
      expect(profiles.single.availableProviders, hasLength(3));
      expect(profiles.single.unsupportedProviders, isEmpty);
      final detail = await api.getArchitectureProfile(
        'five-layer-baseline',
        '2',
      );
      expect(detail.logicalComponents, hasLength(7));
      expect(detail.logicalEdges, hasLength(8));
      expect(detail.visualization.nodes, hasLength(7));
      final selection = await api.getTwinArchitectureSelection('demo-draft');
      expect(selection.profileRef.id, 'five-layer-baseline');
      expect(selection.profileRef.version, '2');
      expect(selection.profileRef.digest, profiles.single.profileDigest);

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
      final preview = await api.previewTwinArchitectureProfileChange(
        'demo-draft',
        const ArchitectureProfileChangePreviewRequest(
          profileId: 'five-layer-baseline',
          profileVersion: '2',
          expectedRevision: 1,
        ),
      );
      expect(preview.current, preview.target);
      expect(preview.incompatibleWorkloadFields, isEmpty);
      final result = await api.selectTwinArchitectureProfile(
        'demo-draft',
        ArchitectureProfileSelectRequest.fromPreview(preview),
      );
      expect(result.revision, 1);
      expect(result.deploymentReadinessState, 'unchanged');
    },
  );
}
