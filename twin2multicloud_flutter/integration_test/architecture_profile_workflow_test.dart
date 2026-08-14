import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:archive/archive_io.dart';
import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
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

  testWidgets(
    'evaluates active Five-layer v2 and keeps live deployment blocked',
    (tester) async {
      final catalog = await _api.listArchitectureProfiles();
      expect(catalog, hasLength(2));
      final fiveLayer = catalog.singleWhere(
        (item) =>
            item.ref.id == 'five-layer-baseline' && item.ref.version == '2',
      );
      final sixLayer = catalog.singleWhere(
        (item) =>
            item.ref.id == 'six-layer-eventing' && item.ref.version == '1',
      );

      final fiveLayerProfile = await _api.getArchitectureProfile(
        fiveLayer.ref.id,
        fiveLayer.ref.version,
      );
      final sixLayerProfile = await _api.getArchitectureProfile(
        sixLayer.ref.id,
        sixLayer.ref.version,
      );
      expect(fiveLayerProfile.summary.ref, fiveLayer.ref);
      expect(sixLayerProfile.summary.ref, sixLayer.ref);
      expect(
        fiveLayerProfile.logicalComponents.map((item) => item.componentId),
        isNot(contains('component.eventing')),
      );
      expect(
        sixLayerProfile.logicalComponents.map((item) => item.componentId),
        contains('component.eventing'),
      );

      final twin = await _api.createTwin(
        'Five-layer v2 boundary ${DateTime.now().microsecondsSinceEpoch}',
      );
      try {
        final selection = await _api.getTwinArchitectureSelection(twin.id);
        expect(selection.twinId, twin.id);
        expect(selection.profileRef.id, 'five-layer-baseline');
        expect(selection.profileRef.version, '2');
        expect(selection.revision, greaterThanOrEqualTo(1));
        expect(fiveLayer.ref, selection.profileRef);

        await _bindProcessor(twin.id, filename: 'five-layer-v2-processor.zip');

        final run = await _requestOrFail(
          'Five-layer v2 optimizer run',
          () => _api.createOptimizerRun(
            twin.id,
            CalcParams.fiveLayerV2(scenario: FiveLayerWorkloadScenario.small),
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
            run.deploymentRun.specification!
                as ResolvedDeploymentSpecificationV2;
        expect(specification.architectureProfileRef.id, 'five-layer-baseline');
        expect(specification.architectureProfileRef.version, '2');
        expect(specification.readiness.evaluationOnly, isTrue);
        expect(specification.readiness.blockingGateIds, isNotEmpty);
        expect(
          specification.readiness.blockingGateIds,
          everyElement(
            anyOf(
              startsWith('gate.live-capacity.'),
              startsWith('gate.live-pricing.'),
            ),
          ),
        );
        expect(
          specification.readiness.blockingGateIds,
          contains(startsWith('gate.live-capacity.')),
        );

        final resolved = await _api.getRunResolvedArchitecture(run.id);
        expect(resolved.twinId, twin.id);
        expect(resolved.origin, ResolvedArchitectureOrigin.nativeV2);
        expect(
          resolved.architecture.schemaVersion,
          ResolvedTwinArchitecture.v2SchemaVersion,
        );
        expect(
          resolved.architecture.resolutionStatus,
          'offline_contract_fixture',
        );
        expect(resolved.architecture.profileRef.id, 'five-layer-baseline');
        expect(resolved.architecture.profileRef.version, '2');

        final latest = await _api.getLatestOptimizerRun(twin.id);
        expect(latest?.id, run.id);
        expect(latest?.selectedForDeploymentAt, isNull);

        await _expectArchitectureError(
          'ARCH_PROFILE_NOT_ACTIVE',
          () => _api.getArchitectureProfile('five-layer-baseline', '1'),
        );
        await _expectArchitectureError(
          'DEPLOYMENT_CAPACITY_EVIDENCE_PENDING',
          () => _api.selectOptimizerRunForDeployment(twin.id, run.id),
        );
      } finally {
        await _api.deleteTwin(twin.id);
      }
    },
  );

  testWidgets(
    'evaluates active Six-layer v1 with an independent Eventing component',
    (tester) async {
      final catalog = await _api.listArchitectureProfiles();
      final sixLayer = catalog.singleWhere(
        (item) =>
            item.ref.id == 'six-layer-eventing' && item.ref.version == '1',
      );
      final twin = await _api.createTwin(
        'Six-layer v1 boundary ${DateTime.now().microsecondsSinceEpoch}',
      );
      try {
        final initialSelection = await _api.getTwinArchitectureSelection(
          twin.id,
        );
        expect(initialSelection.profileRef.id, 'five-layer-baseline');
        expect(initialSelection.profileRef.version, '2');

        final preview = await _api.previewTwinArchitectureProfileChange(
          twin.id,
          ArchitectureProfileChangePreviewRequest(
            profileId: sixLayer.ref.id,
            profileVersion: sixLayer.ref.version,
            expectedRevision: initialSelection.revision,
          ),
        );
        expect(preview.current, initialSelection.profileRef);
        expect(preview.target, sixLayer.ref);
        expect(preview.incompatibleWorkloadFields, isEmpty);
        expect(preview.incompatibleExtensionBindings, isEmpty);

        final profileChange = await _api.selectTwinArchitectureProfile(
          twin.id,
          ArchitectureProfileSelectRequest.fromPreview(preview),
        );
        expect(profileChange.selection.profileRef, sixLayer.ref);
        expect(profileChange.revision, initialSelection.revision + 1);

        await _bindProcessor(twin.id, filename: 'six-layer-v1-processor.zip');

        final run = await _requestOrFail(
          'Six-layer v1 optimizer run',
          () => _api.createOptimizerRun(
            twin.id,
            CalcParams.fiveLayerV2(scenario: FiveLayerWorkloadScenario.small),
          ),
        );
        expect(run.deploymentRun.compatibility, DeploymentCompatibility.ready);
        expect(
          run.deploymentRun.specification,
          isA<ResolvedDeploymentSpecificationV2>(),
        );
        final specification =
            run.deploymentRun.specification!
                as ResolvedDeploymentSpecificationV2;
        expect(specification.architectureProfileRef.id, 'six-layer-eventing');
        expect(specification.architectureProfileRef.version, '1');
        expect(
          specification.componentSelections.map(
            (item) => item.logicalComponentId,
          ),
          contains('component.eventing'),
        );
        expect(specification.readiness.evaluationOnly, isTrue);
        expect(specification.readiness.blockingGateIds, isNotEmpty);

        final resolved = await _api.getRunResolvedArchitecture(run.id);
        expect(resolved.origin, ResolvedArchitectureOrigin.nativeV2);
        expect(resolved.architecture.profileRef, sixLayer.ref);
        expect(
          resolved.architecture.componentAssignments.map(
            (item) => item.logicalComponentId,
          ),
          contains('component.eventing'),
        );

        await _expectArchitectureError(
          'DEPLOYMENT_CAPACITY_EVIDENCE_PENDING',
          () => _api.selectOptimizerRunForDeployment(twin.id, run.id),
        );
      } finally {
        await _api.deleteTwin(twin.id);
      }
    },
  );
}

Future<void> _bindProcessor(String twinId, {required String filename}) async {
  final slots = await _api.listExtensionSlots();
  final processorSlot = slots.singleWhere(
    (slot) => slot.slotId == 'processor.telemetry',
  );
  final artifact = await _api.createUserFunctionArtifact(
    UserFunctionArtifactUpload(
      slot: processorSlot,
      draft: UserFunctionSourceDraft(
        filename: filename,
        bytes: _processorSourceArchive(),
        configuration: const {'scale_factor': 1},
      ),
    ),
  );
  expect(artifact.isValid, isTrue);
  final binding = await _api.bindTwinExtensionArtifact(
    twinId,
    processorSlot,
    artifact.artifactId,
  );
  expect(binding.slotId, 'processor.telemetry');
  expect(binding.artifactDigest, artifact.artifactDigest);
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

Future<void> _expectArchitectureError(
  String expectedCode,
  Future<void> Function() request,
) async {
  try {
    await request();
    fail('Expected $expectedCode');
  } on DioException catch (error) {
    final payload = error.response?.data;
    expect(payload, isA<Map>());
    final errorPayload = payload as Map;
    final detail = errorPayload['detail'];
    final actualCode =
        errorPayload['error_code'] ??
        (detail is Map ? detail['error_code'] : null);
    expect(actualCode, expectedCode);
  }
}
