import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/services/api_service.dart';
import 'package:twin2multicloud_flutter/services/log_stream_client.dart';
import 'package:twin2multicloud_flutter/services/management_api.dart';
import 'package:twin2multicloud_flutter/services/sse_service.dart';

void main() {
  test('HTTP adapter implements the complete Management API contract', () {
    final adapter = ApiService(baseUri: Uri.parse('http://management.test'));

    expect(adapter, isA<ManagementApi>());
    expect(adapter, isA<TwinApi>());
    expect(adapter, isA<CloudAccessApi>());
    expect(adapter, isA<PricingApi>());
    expect(adapter, isA<OptimizationApi>());
    expect(adapter, isA<DeploymentConfigurationApi>());
    expect(adapter, isA<DeploymentLifecycleApi>());
    expect(adapter, isA<VerificationApi>());
  });

  test('SSE adapter implements the log stream contract', () {
    final adapter = SseService(
      baseUrl: 'http://management.test',
      authToken: 'local-token',
    );

    expect(adapter, isA<LogStreamClient>());
    adapter.cancel();
  });
}
