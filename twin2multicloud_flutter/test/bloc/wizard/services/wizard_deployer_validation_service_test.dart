import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/services/wizard_deployer_validation_service.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

class MockApiService extends Mock implements ApiService {}

void main() {
  late MockApiService api;
  late WizardDeployerValidationService service;

  setUp(() {
    api = MockApiService();
    service = WizardDeployerValidationService(api: api);
  });

  group('WizardDeployerValidationService', () {
    test('validateConfigFile requires saved draft', () async {
      final result = await service.validateConfigFile(
        twinId: null,
        configType: 'config',
        content: '{}',
      );

      expect(result.valid, isFalse);
      expect(result.message, contains('Save draft first'));
      verifyNever(() => api.validateDeployerConfig(any(), any(), any()));
    });

    test('validateL2Content calls API with provider', () async {
      when(
        () => api.validateL2Content('twin-1', 'function-code', 'code', 'aws'),
      ).thenAnswer((_) async => {'valid': true, 'message': 'ok'});

      final result = await service.validateL2Content(
        twinId: 'twin-1',
        provider: 'aws',
        type: 'function-code',
        content: 'code',
      );

      expect(result.valid, isTrue);
      expect(result.message, 'ok');
    });

    test('validateL4Content returns provider guard message', () async {
      final result = await service.validateL4Content(
        twinId: 'twin-1',
        provider: null,
        type: 'user-config',
        content: '{}',
      );

      expect(result.valid, isFalse);
      expect(result.message, 'No L5 provider selected (Step 2)');
    });
  });
}
