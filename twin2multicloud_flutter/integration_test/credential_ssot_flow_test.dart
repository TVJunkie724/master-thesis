import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:twin2multicloud_flutter/config/api_config.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMessageHandler('flutter/keyevent', (_) async => null);
  TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMessageHandler('flutter/rawKeyboard', (_) async => null);

  group('Credential SSOT Management API integration', () {
    testWidgets('uses the local Management API URL from runtime config', (
      tester,
    ) async {
      expect(ApiConfig.baseUrl, 'http://localhost:5005');
    });

    testWidgets('lists Cloud Connections through the Management API', (
      tester,
    ) async {
      try {
        final connections = await ApiService().listCloudConnections();

        expect(connections, isA<List>());
      } on DioException catch (error) {
        fail(
          'Management API is not reachable at ${ApiConfig.baseUrl}. '
          'Start it with `docker compose up -d management-api 2twin2clouds 3cloud-deployer` '
          'before running this integration test. Dio error: ${error.type}',
        );
      }
    });
  });
}
