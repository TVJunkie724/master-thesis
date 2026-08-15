import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/core/result.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployment_access.dart';

void main() {
  test('parses all nine supported L4/L5 provider placements', () {
    for (final l4 in CloudProvider.values) {
      for (final l5 in CloudProvider.values) {
        final snapshot = DeploymentAccessSnapshot.fromJson(
          _snapshot(l4: l4, l5: l5),
          expectedTwinId: 'twin-1',
        );

        expect(snapshot.availability, DeploymentAccessAvailability.available);
        expect(snapshot.surfaceFor(DeploymentLayer.l4)?.provider, l4);
        expect(snapshot.surfaceFor(DeploymentLayer.l5)?.provider, l5);
        expect(snapshot.surfaces, hasLength(2));
      }
    }
  });

  test('parses historical unsupported response without surfaces', () {
    final snapshot = DeploymentAccessSnapshot.fromJson({
      'schema_version': 'deployment-access.v1',
      'twin_id': 'twin-1',
      'deployment_id': 'deployment-1',
      'generated_at': '2026-07-31T12:00:00Z',
      'availability': 'unsupported',
      'reason_code': 'unsupported_historical_profile',
      'surfaces': <Object>[],
    });

    expect(snapshot.availability, DeploymentAccessAvailability.unsupported);
    expect(snapshot.surfaces, isEmpty);
  });

  test('rejects schema, twin, URL, duplicate layer, and secret violations', () {
    final wrongSchema = _snapshot()
      ..['schema_version'] = 'deployment-access.v2';
    final wrongTwin = _snapshot();
    final httpUrl = _snapshot();
    ((httpUrl['surfaces'] as List).first as Map)['url'] =
        'http://example.invalid/twin';
    final userInfoUrl = _snapshot();
    ((userInfoUrl['surfaces'] as List).first as Map)['url'] =
        'https://user@example.invalid/twin';
    final duplicateLayer = _snapshot();
    ((duplicateLayer['surfaces'] as List).last as Map)['layer'] = 'l4';
    final secret = _snapshot();
    ((secret['surfaces'] as List).first as Map)['password'] = 'must-reject';

    expect(() => DeploymentAccessSnapshot.fromJson(wrongSchema), contractError);
    expect(
      () => DeploymentAccessSnapshot.fromJson(
        wrongTwin,
        expectedTwinId: 'another-twin',
      ),
      contractError,
    );
    for (final document in [httpUrl, userInfoUrl, duplicateLayer, secret]) {
      expect(() => DeploymentAccessSnapshot.fromJson(document), contractError);
    }
  });

  test('rejects unsupported provider/service/auth/action combinations', () {
    final wrongService = _snapshot();
    ((wrongService['surfaces'] as List).first as Map)['service_id'] =
        'gcp_twin_explorer';
    final wrongAuth = _snapshot(l5: CloudProvider.gcp);
    ((((wrongAuth['surfaces'] as List).last as Map)['auth']) as Map)['mode'] =
        'gcp_iap';
    final wrongAction = _snapshot(l5: CloudProvider.gcp);
    ((((wrongAction['surfaces'] as List).last as Map)['auth'])
            as Map)['credential_action'] =
        'none';

    for (final document in [wrongService, wrongAuth, wrongAction]) {
      expect(() => DeploymentAccessSnapshot.fromJson(document), contractError);
    }
  });

  test('rejects missing, non-list, blank, and duplicate capability data', () {
    final missing = _snapshot();
    ((missing['surfaces'] as List).first as Map).remove('capabilities');
    final nonList = _snapshot();
    ((nonList['surfaces'] as List).first as Map)['capabilities'] = 'browse';
    final blank = _snapshot();
    ((blank['surfaces'] as List).first as Map)['capabilities'] = [''];
    final duplicate = _snapshot();
    ((duplicate['surfaces'] as List).first as Map)['capabilities'] = [
      'browse',
      'browse',
    ];

    for (final document in [missing, nonList, blank, duplicate]) {
      expect(() => DeploymentAccessSnapshot.fromJson(document), contractError);
    }
  });

  test(
    'credential is validated and never exposes password through equality or text',
    () {
      final credential = DeploymentAccessCredential.fromJson({
        'schema_version': 'deployment-access-credential.v1',
        'layer': 'l5',
        'provider': 'gcp',
        'username': 'viewer@example.invalid',
        'password': 'one-time-secret',
        'issued_at': '2026-07-31T12:00:00Z',
      });
      final sameMetadata = DeploymentAccessCredential.fromJson({
        'schema_version': 'deployment-access-credential.v1',
        'layer': 'l5',
        'provider': 'gcp',
        'username': 'viewer@example.invalid',
        'password': 'different-secret',
        'issued_at': '2026-07-31T12:00:00Z',
      });

      expect(credential.password, 'one-time-secret');
      expect(credential, sameMetadata);
      expect(credential.toString(), isNot(contains('one-time-secret')));
      expect(credential.props, isNot(contains('one-time-secret')));
      expect(
        () => DeploymentAccessCredential.fromJson({
          'schema_version': 'deployment-access-credential.v1',
          'layer': 'l4',
          'provider': 'gcp',
          'username': 'viewer@example.invalid',
          'password': 'secret',
          'issued_at': '2026-07-31T12:00:00Z',
        }),
        contractError,
      );
    },
  );

  test('snapshot collections are immutable', () {
    final snapshot = DeploymentAccessSnapshot.fromJson(_snapshot());

    expect(() => snapshot.surfaces.clear(), throwsUnsupportedError);
    expect(
      () => snapshot.surfaces.first.capabilities.add('mutate'),
      throwsUnsupportedError,
    );
  });
}

Map<String, dynamic> _snapshot({
  CloudProvider l4 = CloudProvider.aws,
  CloudProvider l5 = CloudProvider.azure,
}) {
  return {
    'schema_version': 'deployment-access.v1',
    'twin_id': 'twin-1',
    'deployment_id': 'deployment-1',
    'generated_at': '2026-07-31T12:00:00Z',
    'availability': 'available',
    'reason_code': null,
    'surfaces': [
      _surface(DeploymentLayer.l4, l4),
      _surface(DeploymentLayer.l5, l5),
    ],
  };
}

Map<String, dynamic> _surface(DeploymentLayer layer, CloudProvider provider) {
  final configuration = switch ((layer, provider)) {
    (DeploymentLayer.l4, CloudProvider.aws) => (
      'aws_iot_twinmaker',
      'aws_identity_center',
      'none',
    ),
    (DeploymentLayer.l4, CloudProvider.azure) => (
      'azure_digital_twins',
      'azure_entra',
      'none',
    ),
    (DeploymentLayer.l4, CloudProvider.gcp) => (
      'gcp_twin_explorer',
      'gcp_iap',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.aws) => (
      'aws_managed_grafana',
      'aws_identity_center',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.azure) => (
      'azure_managed_grafana',
      'azure_entra',
      'none',
    ),
    (DeploymentLayer.l5, CloudProvider.gcp) => (
      'gcp_grafana_oss',
      'generated_viewer',
      'rotate',
    ),
  };
  return {
    'layer': layer.name,
    'provider': provider.apiValue,
    'service_id': configuration.$1,
    'display_name': '${layer.name.toUpperCase()} ${provider.label}',
    'url': 'https://${layer.name}-${provider.apiValue}.example.invalid/',
    'auth': {
      'mode': configuration.$2,
      'principal_label': 'researcher@example.invalid',
      'credential_action': configuration.$3,
    },
    'readiness': {
      'resource': 'ready',
      'access_binding': 'ready',
      'content': 'pending',
      'data_probe': 'pending',
      'browser_sign_in': 'unverified',
    },
    'capabilities': ['browse'],
    'limitations': ['Browser sign-in remains user verified.'],
  };
}

Matcher get contractError => throwsA(
  isA<AppException>().having(
    (error) => error.code,
    'code',
    'DEPLOYMENT_ACCESS_CONTRACT_INVALID',
  ),
);
