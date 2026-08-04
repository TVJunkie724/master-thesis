import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
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
    'keeps the historical profile readable and the active catalog empty',
    (tester) async {
      final catalog = await _api.listArchitectureProfiles();
      expect(catalog, isEmpty);

      final twin = await _api.createTwin(
        'Architecture boundary ${DateTime.now().microsecondsSinceEpoch}',
      );
      try {
        final selection = await _api.getTwinArchitectureSelection(twin.id);
        expect(selection.twinId, twin.id);
        expect(selection.profileRef.id, 'five-layer-baseline');
        expect(selection.profileRef.version, '1');
        expect(selection.revision, greaterThanOrEqualTo(1));
        expect(
          catalog.any((profile) => profile.ref == selection.profileRef),
          isFalse,
        );

        await _expectArchitectureError(
          'ARCH_PROFILE_NOT_ACTIVE',
          () => _api.getArchitectureProfile(
            selection.profileRef.id,
            selection.profileRef.version,
          ),
        );
        await _expectArchitectureError(
          'ARCH_PROFILE_NOT_ACTIVE',
          () => _api.previewTwinArchitectureProfileChange(
            twin.id,
            ArchitectureProfileChangePreviewRequest(
              profileId: selection.profileRef.id,
              profileVersion: selection.profileRef.version,
              expectedRevision: selection.revision,
            ),
          ),
        );
      } finally {
        await _api.deleteTwin(twin.id);
      }
    },
  );
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
    expect((payload as Map)['error_code'], expectedCode);
  }
}
