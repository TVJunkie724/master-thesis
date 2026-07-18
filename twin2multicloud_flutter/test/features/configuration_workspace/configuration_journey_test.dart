import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/pricing_health.dart';

import '../../fixtures/typed_api_fixtures.dart';

void main() {
  group('ConfigurationJourney', () {
    test('has stable unique task ordering and compatibility mapping', () {
      expect(
        ConfigurationJourney.orderedTaskIds.toSet().length,
        ConfigurationJourney.orderedTaskIds.length,
      );
      expect(
        ConfigurationJourney.orderedTaskIds.map(
          ConfigurationJourney.legacyStepFor,
        ),
        everyElement(inInclusiveRange(0, 2)),
      );
    });

    test('starts an empty draft at twin identity and blocks dependencies', () {
      final journey = ConfigurationJourney.fromWizardState(
        const WizardState(status: WizardStatus.ready),
      );

      expect(journey.currentTaskId, ConfigurationTaskId.defineTwin);
      expect(
        journey.task(ConfigurationTaskId.deviceTraffic).status,
        ConfigurationTaskStatus.blocked,
      );
      expect(
        journey.task(ConfigurationTaskId.cloudAccess).blockingReason,
        'Calculate an architecture first',
      );
    });

    test('moves a named draft to workload description without credentials', () {
      final journey = ConfigurationJourney.fromWizardState(
        const WizardState(status: WizardStatus.ready, twinName: 'Factory twin'),
      );

      expect(
        journey.recommendedTaskId,
        ConfigurationTaskId.scenarioAndCurrency,
      );
      expect(
        journey.task(ConfigurationTaskId.deviceTraffic).status,
        ConfigurationTaskStatus.available,
      );
    });

    test('surfaces pricing attention before architecture calculation', () {
      final journey = ConfigurationJourney.fromWizardState(
        WizardState(
          status: WizardStatus.ready,
          twinName: 'Factory twin',
          calcParams: CalcParams.defaultParams(),
          pricingHealthError: 'Unavailable',
        ),
      );

      expect(journey.recommendedTaskId, ConfigurationTaskId.pricingReadiness);
      expect(
        journey.task(ConfigurationTaskId.pricingReadiness).status,
        ConfigurationTaskStatus.current,
      );
    });

    test('requires access only for providers in selected architecture', () {
      final journey = ConfigurationJourney.fromWizardState(
        WizardState(
          status: WizardStatus.ready,
          twinName: 'Factory twin',
          calcParams: CalcParams.defaultParams(),
          pricingHealth: _healthyPricing(),
          calcResult: _result(const ['L1_AWS', 'L2_AWS', 'L4_AZURE']),
          deploymentRun: TypedApiFixtures.deploymentRun(
            selectedForDeploymentAt: TypedApiFixtures.timestamp,
          ),
        ),
      );

      expect(
        journey.task(ConfigurationTaskId.cloudAccess).status,
        ConfigurationTaskStatus.current,
      );
      expect(journey.recommendedTaskId, ConfigurationTaskId.cloudAccess);
    });

    test('falls back from a blocked requested task deterministically', () {
      final journey = ConfigurationJourney.fromWizardState(
        const WizardState(status: WizardStatus.ready),
        requestedTaskId: ConfigurationTaskId.validationAndPreflight,
      );

      expect(journey.currentTaskId, ConfigurationTaskId.defineTwin);
    });

    test(
      'preserves an available requested task instead of forcing linearity',
      () {
        final journey = ConfigurationJourney.fromWizardState(
          const WizardState(
            status: WizardStatus.ready,
            twinName: 'Factory twin',
          ),
          requestedTaskId: ConfigurationTaskId.retention,
        );

        expect(journey.currentTaskId, ConfigurationTaskId.retention);
        expect(journey.previousNavigableTaskId, ConfigurationTaskId.processing);
      },
    );

    test('finish readiness includes access, artifacts and invalidation', () {
      final ready = WizardState(
        status: WizardStatus.ready,
        twinName: 'Factory twin',
        calcParams: CalcParams.defaultParams(),
        calcResult: _result(const [
          'L1_GCP',
          'L2_GCP',
          'L3_hot_GCP',
          'L4_GCP',
          'L5_GCP',
        ]),
        selectedCloudConnectionIds: const {CloudProvider.gcp: 'gcp-deploy'},
        deployerDigitalTwinName: 'Factory twin',
        configEventsJson: '[]',
        configIotDevicesJson: '[]',
        configJsonValidated: true,
        configEventsValidated: true,
        configIotDevicesValidated: true,
        payloadsJson: '{}',
        payloadsValidated: true,
        deploymentRun: TypedApiFixtures.deploymentRun(
          selectedForDeploymentAt: TypedApiFixtures.timestamp,
        ),
      );

      expect(ready.isConfigurationReadyForFinish, isTrue);
      expect(
        ready.copyWith(step3Invalidated: true).isConfigurationReadyForFinish,
        isFalse,
      );
      expect(
        ready
            .copyWith(selectedCloudConnectionIds: const {})
            .isConfigurationReadyForFinish,
        isFalse,
      );
    });

    test('blocks deployment tasks until the latest run is selected', () {
      final journey = ConfigurationJourney.fromWizardState(
        WizardState(
          status: WizardStatus.ready,
          twinName: 'Factory twin',
          calcParams: CalcParams.defaultParams(),
          pricingHealth: _healthyPricing(),
          calcResult: _result(const ['L1_AWS']),
          deploymentRun: TypedApiFixtures.deploymentRun(),
        ),
      );

      expect(
        journey.task(ConfigurationTaskId.compareAndSelect).label,
        'Review recommendation',
      );
      expect(
        journey.task(ConfigurationTaskId.compareAndSelect).status,
        ConfigurationTaskStatus.current,
      );
      expect(
        journey.task(ConfigurationTaskId.cloudAccess).status,
        ConfigurationTaskStatus.blocked,
      );
      expect(
        journey.task(ConfigurationTaskId.cloudAccess).blockingReason,
        'Confirm the resolved architecture first',
      );
    });
  });
}

PricingHealthResponse _healthyPricing() => PricingHealthResponse.fromJson({
  'schema_version': PricingHealthResponse.supportedSchemaVersion,
  'providers': {
    for (final provider in ['aws', 'azure', 'gcp'])
      provider: {
        'provider': provider,
        'state': 'fresh',
        'severity': 'success',
        'review_required': false,
        'can_calculate': true,
        'calculation_source': 'fresh',
        'pricing_freshness': 'fresh',
        'source_label': provider,
        'credential_summary': {
          'provider': provider,
          'purpose': 'pricing',
          'scope': 'user',
          'identity_label': provider,
          'status': 'active',
        },
        'primary_message': 'Ready',
      },
  },
});

CalcResult _result(List<String> path) => CalcResult.fromJson({
  'awsCosts': const <String, dynamic>{},
  'azureCosts': const <String, dynamic>{},
  'gcpCosts': const <String, dynamic>{},
  'cheapestPath': path,
  'inputParamsUsed': const <String, dynamic>{},
});
