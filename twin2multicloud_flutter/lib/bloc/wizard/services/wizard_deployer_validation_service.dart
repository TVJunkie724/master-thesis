import '../../../models/validation_result.dart';
import '../../../services/api_service.dart';
import '../../../utils/api_error_handler.dart';

class WizardDeployerValidationService {
  final ApiService _api;

  const WizardDeployerValidationService({required ApiService api}) : _api = api;

  Future<ValidationResult> validateConfigFile({
    required String? twinId,
    required String configType,
    required String content,
  }) async {
    if (twinId == null) {
      return const ValidationResult(
        valid: false,
        message: 'Save draft first to enable validation',
      );
    }
    if (content.trim().isEmpty) {
      return const ValidationResult(
        valid: false,
        message: 'No content to validate',
      );
    }

    try {
      final result = await _api.validateDeployerConfig(
        twinId,
        configType,
        content,
      );
      return ValidationResult.fromJson(result, validMessage: 'Valid');
    } catch (error) {
      return ValidationResult(
        valid: false,
        message: 'Validation failed: ${ApiErrorHandler.extractMessage(error)}',
      );
    }
  }

  Future<ValidationResult> validateL2Content({
    required String? twinId,
    required String? provider,
    required String type,
    required String content,
  }) async {
    if (twinId == null) {
      return const ValidationResult(valid: false, message: 'Save draft first');
    }
    if (provider == null) {
      return const ValidationResult(
        valid: false,
        message: 'Complete Step 2 first',
      );
    }
    if (content.trim().isEmpty) {
      return const ValidationResult(valid: false, message: 'No content');
    }

    try {
      final result = await _api.validateL2Content(
        twinId,
        type,
        content,
        provider,
      );
      return ValidationResult.fromJson(result, validMessage: 'Valid');
    } catch (error) {
      return ValidationResult(
        valid: false,
        message: ApiErrorHandler.extractMessage(error),
      );
    }
  }

  Future<ValidationResult> validateL4Content({
    required String? twinId,
    required String? provider,
    required String type,
    required String content,
  }) async {
    if (twinId == null) {
      return const ValidationResult(valid: false, message: 'Save draft first');
    }
    if (provider == null) {
      final layer = type == 'user-config' ? 'L5' : 'L4';
      return ValidationResult(
        valid: false,
        message: 'No $layer provider selected (Step 2)',
      );
    }

    try {
      final result = await _api.validateL4Content(
        twinId,
        type,
        content,
        provider.toLowerCase(),
      );
      return ValidationResult.fromJson(result, validMessage: 'Valid');
    } catch (error) {
      return ValidationResult(
        valid: false,
        message: ApiErrorHandler.extractMessage(error),
      );
    }
  }
}
