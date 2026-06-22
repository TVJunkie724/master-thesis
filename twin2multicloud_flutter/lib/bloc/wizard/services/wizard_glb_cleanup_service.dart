import '../../../services/api_service.dart';

class WizardGlbCleanupService {
  final ApiService _api;

  const WizardGlbCleanupService({required ApiService api}) : _api = api;

  Future<void> deleteUploadedGlb({
    required String? twinId,
    required bool wasUploaded,
  }) async {
    if (twinId == null || !wasUploaded) return;

    try {
      await _api.deleteSceneGlb(twinId);
    } catch (_) {
      // Best-effort cleanup: the local wizard state has already been reset.
    }
  }
}
