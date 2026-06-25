import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/services/wizard_glb_cleanup_service.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;
  late WizardGlbCleanupService service;

  setUp(() {
    api = MockApiService();
    service = WizardGlbCleanupService(api: api);
  });

  group('WizardGlbCleanupService', () {
    test('skips cleanup when no twin exists', () async {
      await service.deleteUploadedGlb(twinId: null, wasUploaded: true);

      verifyNever(() => api.deleteSceneGlb(any()));
    });

    test('deletes uploaded GLB for saved twin', () async {
      when(() => api.deleteSceneGlb('twin-1')).thenAnswer((_) async {});

      await service.deleteUploadedGlb(twinId: 'twin-1', wasUploaded: true);

      verify(() => api.deleteSceneGlb('twin-1')).called(1);
    });

    test('swallows cleanup errors as best effort', () async {
      when(() => api.deleteSceneGlb('twin-1')).thenThrow(Exception('gone'));

      await service.deleteUploadedGlb(twinId: 'twin-1', wasUploaded: true);

      verify(() => api.deleteSceneGlb('twin-1')).called(1);
    });
  });
}
