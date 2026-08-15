import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';
import 'package:twin2multicloud_flutter/demo/demo_management_api.dart';
import 'package:twin2multicloud_flutter/models/user_function_extension.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('demo adapter preserves validate, create, and bind parity', () async {
    final store = await DemoFixtureStore.load(
      DemoScenario.showcase,
      clock: () => DateTime.utc(2026, 7, 19),
    );
    final api = DemoManagementApi(store: store, latency: Duration.zero);
    final slot = (await api.listExtensionSlots()).single;
    final twin = (await api.getTwins()).first;
    final upload = UserFunctionArtifactUpload(
      slot: slot,
      draft: UserFunctionSourceDraft(
        filename: 'processor.zip',
        bytes: Uint8List.fromList([1, 2, 3]),
        configuration: const {'scale_factor': 1},
      ),
    );

    final validation = await api.validateUserFunctionArtifact(upload);
    final artifact = await api.createUserFunctionArtifact(upload);
    final idempotent = await api.createUserFunctionArtifact(upload);
    final binding = await api.bindTwinExtensionArtifact(
      twin.id,
      slot,
      artifact.artifactId,
    );

    expect(validation.artifactDigest, artifact.artifactDigest);
    expect(idempotent.artifactId, artifact.artifactId);
    expect(await api.listTwinExtensionBindings(twin.id), contains(binding));
  });

  test('demo adapter rejects secret-shaped configuration', () async {
    final store = await DemoFixtureStore.load(DemoScenario.showcase);
    final api = DemoManagementApi(store: store, latency: Duration.zero);
    final slot = (await api.listExtensionSlots()).single;
    final upload = UserFunctionArtifactUpload(
      slot: slot,
      draft: UserFunctionSourceDraft(
        filename: 'processor.zip',
        bytes: Uint8List.fromList([1]),
        configuration: const {
          'scale_factor': 1,
          'api_token': 'must-not-appear',
        },
      ),
    );

    await expectLater(
      api.validateUserFunctionArtifact(upload),
      throwsA(
        isA<DemoApiException>().having(
          (error) => error.code,
          'code',
          anyOf(
            'EXTENSION_CONFIG_INVALID',
            'EXTENSION_SECRET_MATERIAL_DETECTED',
          ),
        ),
      ),
    );
  });
}
