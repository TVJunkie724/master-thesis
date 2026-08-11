import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/demo/demo_management_api.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'demo exposes both active Phase 8 profiles and the pinned selection',
    () async {
      final store = await DemoFixtureStore.load(
        DemoScenario.showcase,
        clock: () => DateTime.utc(2026, 8, 3),
      );
      final api = DemoManagementApi(store: store, latency: Duration.zero);

      final profiles = await api.listArchitectureProfiles();
      expect(profiles, hasLength(2));
      final fiveLayer = profiles.singleWhere(
        (profile) => profile.profileId == 'five-layer-baseline',
      );
      final sixLayer = profiles.singleWhere(
        (profile) => profile.profileId == 'six-layer-eventing',
      );
      expect(fiveLayer.profileVersion, '2');
      expect(fiveLayer.availableProviders, hasLength(3));
      expect(fiveLayer.unsupportedProviders, isEmpty);
      expect(sixLayer.profileVersion, '1');
      expect(sixLayer.responsibilities, hasLength(6));
      final detail = await api.getArchitectureProfile(
        'five-layer-baseline',
        '2',
      );
      expect(detail.logicalComponents, hasLength(7));
      expect(detail.logicalEdges, hasLength(8));
      expect(detail.visualization.nodes, hasLength(7));
      final sixLayerDetail = await api.getArchitectureProfile(
        'six-layer-eventing',
        '1',
      );
      expect(sixLayerDetail.logicalComponents, hasLength(8));
      expect(sixLayerDetail.logicalEdges, hasLength(9));
      expect(
        sixLayerDetail.logicalComponents.any(
          (component) => component.componentId == 'component.eventing',
        ),
        isTrue,
      );
      final selection = await api.getTwinArchitectureSelection('demo-draft');
      expect(selection.profileRef.id, 'five-layer-baseline');
      expect(selection.profileRef.version, '2');
      expect(selection.profileRef.digest, fiveLayer.profileDigest);

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
          profileId: 'six-layer-eventing',
          profileVersion: '1',
          expectedRevision: 1,
        ),
      );
      expect(preview.current.id, 'five-layer-baseline');
      expect(preview.target.id, 'six-layer-eventing');
      expect(preview.target.digest, sixLayer.profileDigest);
      expect(preview.incompatibleWorkloadFields, isEmpty);
      final result = await api.selectTwinArchitectureProfile(
        'demo-draft',
        ArchitectureProfileSelectRequest.fromPreview(preview),
      );
      expect(result.revision, 2);
      expect(result.selection.profileRef, preview.target);
      expect(result.deploymentReadinessState, 'unchanged');

      final updatedSelection = await api.getTwinArchitectureSelection(
        'demo-draft',
      );
      expect(updatedSelection, result.selection);
      expect(updatedSelection.profileRef.id, 'six-layer-eventing');
      expect(updatedSelection.profileRef.version, '1');

      await expectLater(
        api.createOptimizerRun(
          'demo-draft',
          CalcParams.fiveLayerV2(scenario: FiveLayerWorkloadScenario.small),
        ),
        throwsA(
          isA<DemoApiException>().having(
            (error) => error.code,
            'code',
            'DEMO_PROFILE_CALCULATION_UNAVAILABLE',
          ),
        ),
      );
    },
  );
}
