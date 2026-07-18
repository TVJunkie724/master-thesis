import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/deployer_config.dart';
import 'package:twin2multicloud_flutter/models/optimizer_config.dart';
import 'package:twin2multicloud_flutter/models/twin_config.dart';

import '../fixtures/test_fixtures.dart';

void main() {
  group('DeployerConfigData', () {
    test('keeps decoded artifact collections immutable', () {
      final data = DeployerConfigData.fromJson({
        'processor_contents': {'processor-a': 'code'},
        'processor_validated': {'processor-a': true},
      });

      expect(
        () => data.processorContents['processor-b'] = 'code',
        throwsUnsupportedError,
      );
      expect(
        () => data.processorValidated['processor-b'] = false,
        throwsUnsupportedError,
      );
    });

    test('rejects malformed optional fields with secret-safe messages', () {
      const secret = 'must-not-appear';

      expect(
        () => DeployerConfigData.fromJson({
          'config_events_json': {'secret': secret},
        }),
        throwsA(
          isA<FormatException>()
              .having(
                (error) => error.message,
                'field message',
                contains('config_events_json'),
              )
              .having(
                (error) => error.message,
                'secret-safe message',
                isNot(contains(secret)),
              ),
        ),
      );
      expect(
        () => DeployerConfigData.fromJson({'scene_glb_uploaded': 'yes'}),
        throwsA(isA<FormatException>()),
      );
      expect(
        () => DeployerConfigData.fromJson({
          'processor_contents': {1: 'code'},
        }),
        throwsA(isA<FormatException>()),
      );
    });
  });

  group('TwinConfigData', () {
    test('decodes canonical cloud bindings and optimizer data', () {
      final data = TwinConfigData.fromJson(
        _twinConfigJson(
          awsConnectionId: 'aws-1',
          optimizerResult: _calculationPayload,
        ),
      );

      expect(data.id, 'config-1');
      expect(data.twinId, 'twin-1');
      expect(data.provider(CloudProvider.aws).usesCloudConnection, isTrue);
      expect(
        data.provider(CloudProvider.aws).cloudConnection?.displayName,
        'AWS Deployment',
      );
      expect(data.configuredProviders, {CloudProvider.aws});
      expect(data.optimizerParams?.numberOfDevices, 100);
      expect(data.optimization?.result.cheapestPath, isNotEmpty);
    });

    test('accepts unknown additive response fields', () {
      final data = TwinConfigData.fromJson({
        ..._twinConfigJson(),
        'future_contract_field': true,
      });

      expect(data.providers, hasLength(3));
    });

    test('rejects inconsistent configured metadata', () {
      expect(
        () => TwinConfigData.fromJson({
          ..._twinConfigJson(),
          'aws_configured': true,
        }),
        throwsA(isA<FormatException>()),
      );
    });

    test('rejects a bound connection with a mismatched ID', () {
      final json = _twinConfigJson(awsConnectionId: 'aws-1');
      final cloudConnections = Map<String, dynamic>.from(
        json['cloud_connections'] as Map,
      );
      json['cloud_connections'] = cloudConnections;
      cloudConnections['aws'] = <String, dynamic>{
        ...Map<String, dynamic>.from(cloudConnections['aws'] as Map),
        'id': 'aws-2',
      };

      expect(
        () => TwinConfigData.fromJson(json),
        throwsA(isA<FormatException>()),
      );
    });

    test(
      'rejects malformed optimizer result instead of treating it as empty',
      () {
        expect(
          () => TwinConfigData.fromJson(
            _twinConfigJson(optimizerResult: {'unexpected': true}),
          ),
          throwsA(isA<FormatException>()),
        );
      },
    );
  });

  group('OptimizerConfigData', () {
    test('decodes typed result, path and immutable pricing evidence', () {
      final data = OptimizerConfigData.fromJson(_optimizerConfigJson());

      expect(data.optimization?.result.totalCost, greaterThan(0));
      expect(data.cheapestPath?.l1, CloudProvider.aws);
      expect(data.l1Provider, CloudProvider.aws);
      expect(data.catalog(CloudProvider.aws)?.pricingRegion, 'eu-central-1');
      expect(data.catalog(CloudProvider.gcp)?.pricingRegion, 'europe-west1');
    });

    test('rejects unknown providers in the selected path', () {
      final json = _optimizerConfigJson();
      json['cheapest_path'] = {'l1': 'private-cloud'};

      expect(
        () => OptimizerConfigData.fromJson(json),
        throwsA(isA<FormatException>()),
      );
    });

    test('keeps nested pricing evidence immutable', () {
      final data = OptimizerConfigData.fromJson(_optimizerConfigJson());
      final context = data.pricingCatalogContext!;
      final reference = context.reference(CloudProvider.aws);

      expect(
        () => context.catalogs[CloudProvider.aws] = context.reference(
          CloudProvider.azure,
        ),
        throwsUnsupportedError,
      );
      expect(
        () => reference.mappingVersions.add('mutable'),
        throwsUnsupportedError,
      );
    });

    test('rejects inconsistent persisted and result evidence', () {
      final json = _optimizerConfigJson();
      final context = Map<String, dynamic>.from(
        json['pricing_catalog_context'] as Map,
      );
      final catalogs = Map<String, dynamic>.from(context['catalogs'] as Map);
      context['catalogs'] = catalogs;
      final aws = Map<String, dynamic>.from(catalogs['aws'] as Map);
      catalogs['aws'] = aws;
      aws['pricingRegion'] = 'us-east-1';
      json['pricing_catalog_context'] = context;

      expect(
        () => OptimizerConfigData.fromJson(json),
        throwsA(isA<FormatException>()),
      );
    });
  });

  group('OptimizationResultData', () {
    test('supports wrapped and direct calculation contracts', () {
      final wrapped = OptimizationResultData.fromApiJson({
        'result': _calculationPayload,
      });
      final direct = OptimizationResultData.fromApiJson(_calculationPayload);

      expect(wrapped.result.totalCost, direct.result.totalCost);
      expect(wrapped.toEnvelopeJson()['result'], wrapped.payload);
    });

    test('rejects a missing stable result structure', () {
      expect(
        () => OptimizationResultData.fromApiJson({'message': 'not a result'}),
        throwsA(isA<FormatException>()),
      );
    });

    test('keeps historical payloads readable without catalog context', () {
      final historical = Map<String, dynamic>.from(_calculationPayload)
        ..remove('pricingCatalogs');

      expect(
        OptimizationResultData.fromPayload(
          historical,
        ).result.pricingCatalogContext,
        isNull,
      );
      expect(
        () => OptimizationResultData.fromApiJson(historical),
        throwsA(isA<FormatException>()),
      );
    });
  });
}

Map<String, dynamic> _twinConfigJson({
  String? awsConnectionId,
  Map<String, dynamic>? optimizerResult,
}) {
  final awsConfigured = awsConnectionId != null;
  return {
    'id': 'config-1',
    'twin_id': 'twin-1',
    'twin_state': 'draft',
    'debug_mode': false,
    'aws_configured': awsConfigured,
    'aws_validated': awsConfigured,
    'aws_credential_source': awsConfigured ? 'cloud_connection' : null,
    'aws_cloud_connection_id': awsConnectionId,
    'aws_region': 'eu-central-1',
    'aws_sso_region': null,
    'azure_configured': false,
    'azure_validated': false,
    'azure_credential_source': null,
    'azure_cloud_connection_id': null,
    'azure_region': null,
    'azure_region_iothub': null,
    'azure_region_digital_twin': null,
    'gcp_configured': false,
    'gcp_validated': false,
    'gcp_credential_source': null,
    'gcp_cloud_connection_id': null,
    'gcp_project_id': null,
    'gcp_billing_account_configured': false,
    'gcp_region': null,
    'configured_providers': awsConfigured ? ['aws'] : <String>[],
    'credential_sources': {
      'aws': awsConfigured ? 'cloud_connection' : null,
      'azure': null,
      'gcp': null,
    },
    'cloud_connections': {
      'aws': awsConfigured
          ? {
              'id': awsConnectionId,
              'provider': 'aws',
              'display_name': 'AWS Deployment',
              'auth_type': 'access_key',
              'validation_status': 'valid',
              'last_validated_at': '2026-07-15T08:00:00Z',
            }
          : null,
      'azure': null,
      'gcp': null,
    },
    'highest_step_reached': 2,
    'optimizer_params': TestFixtures.defaultCalcParams.toJson(),
    'optimizer_result': optimizerResult,
    'updated_at': '2026-07-15T08:00:00Z',
  };
}

Map<String, dynamic> _optimizerConfigJson() => {
  'id': 'optimizer-1',
  'twin_id': 'twin-1',
  'params': TestFixtures.defaultCalcParams.toJson(),
  'result': _calculationPayload,
  'cheapest_path': {'l1': 'AWS', 'l2': 'azure'},
  'calculated_at': '2026-07-15T08:00:00Z',
  'pricing_catalog_context': TestFixtures.pricingCatalogContextJson,
  'updated_at': '2026-07-15T08:00:00Z',
};

Map<String, dynamic> get _calculationPayload =>
    Map<String, dynamic>.from(TestFixtures.calcResultJson['result'] as Map);
