import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/app_runtime.dart';
import 'package:twin2multicloud_flutter/demo/demo_fixture_store.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  final fixedNow = DateTime.parse('2026-07-13T10:00:00Z');

  group('DemoFixtureStore', () {
    for (final scenario in DemoScenario.values) {
      test('loads and validates the ${scenario.name} scenario', () async {
        final store = await DemoFixtureStore.load(
          scenario,
          clock: () => fixedNow,
        );

        expect(store.scenario, scenario.name);
        expect(store.user['id'], isNotEmpty);
      });
    }

    test('returns defensive copies of fixture collections', () async {
      final store = await DemoFixtureStore.load(DemoScenario.showcase);
      final twins = store.twins;
      twins.first['name'] = 'Mutated outside the store';

      expect(store.twins.first['name'], 'Factory Draft');
    });

    test('persists mutations during the in-memory session', () async {
      final store = await DemoFixtureStore.load(
        DemoScenario.empty,
        clock: () => fixedNow,
      );
      store.addTwin({
        'id': 'created-twin',
        'name': 'Created Twin',
        'state': 'draft',
        'providers': <String>[],
        'created_at': fixedNow.toIso8601String(),
        'updated_at': fixedNow.toIso8601String(),
      });
      store.setTwinConfig('created-twin', {'highest_step_reached': 0});
      store.updateTwin('created-twin', {'name': 'Updated Twin'});

      expect(store.twin('created-twin')['name'], 'Updated Twin');
      expect(
        store.twin('created-twin')['updated_at'],
        fixedNow.toIso8601String(),
      );
      expect(store.twinConfig('created-twin'), {'highest_step_reached': 0});
    });

    test('blocks deletion of a bound cloud connection', () async {
      final store = await DemoFixtureStore.load(DemoScenario.showcase);

      expect(
        () => store.removeCloudConnection('demo-aws-deployment'),
        throwsA(
          isA<DemoApiException>().having(
            (error) => error.code,
            'code',
            'DEMO_CONNECTION_IN_USE',
          ),
        ),
      );
    });

    test('rejects an unsupported fixture schema version', () {
      expect(
        () => DemoFixtureStore.fromJson(_minimalFixture(schemaVersion: 2)),
        throwsA(
          isA<DemoApiException>().having(
            (error) => error.code,
            'code',
            'DEMO_FIXTURE_VERSION_UNSUPPORTED',
          ),
        ),
      );
    });

    test('rejects duplicate entity IDs', () {
      final fixture = _minimalFixture();
      fixture['twins'] = [
        {'id': 'duplicate', 'state': 'draft'},
        {'id': 'duplicate', 'state': 'configured'},
      ];

      expect(
        () => DemoFixtureStore.fromJson(fixture),
        throwsA(
          isA<DemoApiException>().having(
            (error) => error.code,
            'code',
            'DEMO_FIXTURE_ENTITY_ID_INVALID',
          ),
        ),
      );
    });

    test('rejects dangling cloud connection references', () {
      final fixture = _minimalFixture();
      fixture['twins'] = [
        {'id': 'twin-1', 'state': 'draft'},
      ];
      fixture['twin_configs'] = {
        'twin-1': {'aws_cloud_connection_id': 'missing-connection'},
      };

      expect(
        () => DemoFixtureStore.fromJson(fixture),
        throwsA(
          isA<DemoApiException>().having(
            (error) => error.code,
            'code',
            'DEMO_FIXTURE_DANGLING_CONNECTION_REFERENCE',
          ),
        ),
      );
    });
  });
}

Map<String, dynamic> _minimalFixture({int schemaVersion = 1}) {
  return {
    'schema_version': schemaVersion,
    'scenario': 'empty',
    'user': {'id': 'user-1'},
    'twins': <dynamic>[],
    'cloud_connections': <dynamic>[],
    'twin_configs': <String, dynamic>{},
    'optimizer_configs': <String, dynamic>{},
    'optimizer_runs': <String, dynamic>{},
    'deployer_configs': <String, dynamic>{},
    'pricing_health': <String, dynamic>{},
    'pricing_reports': <String, dynamic>{},
    'pricing_traces': <String, dynamic>{},
    'deployment_outputs': <String, dynamic>{},
    'deployment_logs': <String, dynamic>{},
    'verification': <String, dynamic>{},
  };
}
