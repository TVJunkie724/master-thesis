import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:archive/archive_io.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';
import 'package:twin2multicloud_flutter/models/user_function_extension.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

final _runtime = AppRuntimeConfig.fromEnvironment();
final _apiUri =
    _runtime.managementApiBaseUri ??
    (throw StateError('Integration runtime requires a Management API origin.'));
final _authToken =
    _runtime.initialAuthToken ??
    (throw StateError('Integration tests require the development profile.'));
final _api = ApiService(baseUri: _apiUri, initialAuthToken: _authToken);

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('publishes and selects active Six-layer without deploying', (
    tester,
  ) async {
    final sixLayerProfile = await _api.getCanonicalArchitectureContract();
    final sixLayer = sixLayerProfile.summary;
    expect(
      sixLayerProfile.logicalComponents.map((item) => item.componentId),
      contains('component.eventing'),
    );

    final twin = await _api.createTwin(
      'Six-layer boundary ${DateTime.now().microsecondsSinceEpoch}',
    );
    try {
      final selection = await _api.getTwinArchitectureContract(twin.id);
      expect(selection.twinId, twin.id);
      expect(selection.profileRef.id, 'six-layer-eventing');
      expect(selection.profileRef.version, '1');
      expect(selection.revision, greaterThanOrEqualTo(1));
      expect(sixLayer.ref, selection.profileRef);

      await _bindProcessor(twin.id, filename: 'six-layer-processor.zip');

      final run = await _requestOrFail(
        'Six-layer optimizer run',
        () => _api.createOptimizerRun(
          twin.id,
          CalcParams.sixLayer(scenario: SixLayerWorkloadScenario.small),
        ),
      );
      expect(run.twinId, twin.id);
      expect(run.currency, 'USD');
      expect(run.totalMonthlyCost, greaterThanOrEqualTo(0));
      expect(run.deploymentRun.compatibility, DeploymentCompatibility.ready);
      expect(
        run.deploymentRun.specification,
        isA<ResolvedDeploymentSpecificationV2>(),
      );
      final specification =
          run.deploymentRun.specification! as ResolvedDeploymentSpecificationV2;
      expect(specification.architectureProfileRef.id, 'six-layer-eventing');
      expect(specification.architectureProfileRef.version, '1');
      expect(specification.readiness.deploymentReady, isTrue);
      expect(specification.readiness.blockingGateIds, isEmpty);

      final resolved = await _api.getRunResolvedArchitecture(run.id);
      expect(resolved.twinId, twin.id);
      expect(resolved.origin, ResolvedArchitectureOrigin.nativeV2);
      expect(
        resolved.architecture.schemaVersion,
        ResolvedTwinArchitecture.v2SchemaVersion,
      );
      expect(resolved.architecture.resolutionStatus, 'publishable');
      expect(resolved.architecture.profileRef.id, 'six-layer-eventing');
      expect(resolved.architecture.profileRef.version, '1');

      final latest = await _api.getLatestOptimizerRun(twin.id);
      expect(latest?.id, run.id);
      expect(latest?.selectedForDeploymentAt, isNull);

      final deploymentSelection = await _requestOrFail(
        'Six-layer deployment selection',
        () => _api.selectOptimizerRunForDeployment(twin.id, run.id),
      );
      expect(deploymentSelection.run.id, run.id);
      expect(deploymentSelection.run.selectedForDeploymentAt, isNotNull);

      final selected = await _api.getLatestOptimizerRun(twin.id);
      expect(selected?.id, run.id);
      expect(selected?.selectedForDeploymentAt, isNotNull);
    } finally {
      await _api.deleteTwin(twin.id);
    }
  });
}

Future<void> _bindProcessor(String twinId, {required String filename}) async {
  final slots = await _api.listExtensionSlots();
  final processorSlot = slots.singleWhere(
    (slot) => slot.slotId == 'processor.telemetry',
  );
  final userFunction = await _api.saveTwinUserFunction(
    twinId,
    UserFunctionSourceUpload(
      slot: processorSlot,
      draft: UserFunctionSourceDraft(
        filename: filename,
        bytes: _processorSourceArchive(),
        configuration: const {'scale_factor': 1},
      ),
    ),
  );
  expect(userFunction.slotId, 'processor.telemetry');
  expect(userFunction.artifactDigest, startsWith('sha256:'));
}

Uint8List _processorSourceArchive() {
  const process = '''
def process(payload, configuration, context):
    value = payload["value"] * configuration["scale_factor"]
    return {"value": value, "quality": "accepted"}
''';
  final archive = Archive()
    ..addFile(ArchiveFile.string('process.py', process)..mode = 0x81A4)
    ..addFile(ArchiveFile.string('requirements.lock', '\n')..mode = 0x81A4);
  return Uint8List.fromList(ZipEncoder().encode(archive));
}

Future<T> _requestOrFail<T>(String label, Future<T> Function() request) async {
  try {
    return await request();
  } on DioException catch (error) {
    fail(
      '$label failed with HTTP ${error.response?.statusCode}: '
      '${error.response?.data}',
    );
  }
}
