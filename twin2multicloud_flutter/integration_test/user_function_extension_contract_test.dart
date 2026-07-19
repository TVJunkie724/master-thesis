import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:archive/archive_io.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
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
    'validates, persists, and binds one provider-neutral artifact offline',
    (tester) async {
      final slots = await _api.listExtensionSlots();
      expect(slots.map((slot) => slot.slotId), contains('processor.telemetry'));
      final slot = slots.firstWhere(
        (item) => item.slotId == 'processor.telemetry',
      );
      final twin = await _api.createTwin(
        'Extension contract ${DateTime.now().microsecondsSinceEpoch}',
      );
      try {
        final upload = UserFunctionArtifactUpload(
          slot: slot,
          draft: UserFunctionSourceDraft(
            filename: 'processor.zip',
            bytes: _sourceArchive(),
            configuration: const {'scale_factor': 1},
          ),
        );
        final validation = await _api.validateUserFunctionArtifact(upload);
        expect(validation.artifactDigest, startsWith('sha256:'));
        expect(validation.checks, contains('secret_scan_passed'));

        final artifact = await _api.createUserFunctionArtifact(upload);
        expect(artifact.isValid, isTrue);
        expect(artifact.sourceFiles, contains('process.py'));

        final binding = await _api.bindTwinExtensionArtifact(
          twin.id,
          slot,
          artifact.artifactId,
        );
        expect(binding.artifactDigest, artifact.artifactDigest);
        expect(
          await _api.listTwinExtensionBindings(twin.id),
          contains(binding),
        );
      } finally {
        await _api.deleteTwin(twin.id);
      }
    },
  );
}

Uint8List _sourceArchive() {
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
