import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/demo/demo_management_api.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'demo exposes the active Six-layer profile and pinned selection',
    () async {
      final store = await DemoFixtureStore.load(
        DemoScenario.showcase,
        clock: () => DateTime.utc(2026, 8, 3),
      );
      final api = DemoManagementApi(store: store, latency: Duration.zero);

      final profiles = await api.listArchitectureProfiles();
      expect(profiles, hasLength(1));
      final sixLayer = profiles.singleWhere(
        (profile) => profile.profileId == 'six-layer-eventing',
      );
      expect(sixLayer.availableProviders, hasLength(3));
      expect(sixLayer.unsupportedProviders, isEmpty);
      expect(sixLayer.profileVersion, '1');
      expect(sixLayer.responsibilities, hasLength(6));
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
      expect(selection.profileRef.id, 'six-layer-eventing');
      expect(selection.profileRef.version, '1');
      expect(selection.profileRef.digest, sixLayer.profileDigest);

      await expectLater(
        api.getArchitectureProfile('six-layer-eventing', '2'),
        throwsA(
          isA<DemoApiException>().having(
            (error) => error.code,
            'code',
            'ARCH_PROFILE_NOT_ACTIVE',
          ),
        ),
      );
      final run = await api.createOptimizerRun(
        'demo-draft',
        CalcParams.sixLayer(scenario: SixLayerWorkloadScenario.small),
      );
      expect(run.optimization.isNativeSixLayer, isTrue);
      expect(
        run.deploymentRun.specification?.schemaVersion,
        'resolved-deployment-specification.v2',
      );
    },
  );
}
