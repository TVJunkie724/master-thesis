import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';

import '../../fixtures/architecture_wizard_fixture.dart';

void main() {
  group('ConfigurationJourney', () {
    test('exposes exactly the four thesis research groups', () {
      final journey = ConfigurationJourney.fromWizardState(
        const WizardState(status: WizardStatus.ready),
      );

      expect(journey.phases.map((phase) => phase.label), [
        'Scenario',
        'Optimize',
        'Prepare',
        'Review',
      ]);
      expect(
        journey.phases.expand((phase) => phase.tasks).map((task) => task.label),
        containsAll(<String>[
          'Define Twin',
          'Scenario and currency',
          'Device traffic',
          'Processing',
          'Retention',
          'Twin capabilities',
          'User logic',
          'Calculate cost allocation',
          'Review immutable result',
          'Cloud access',
          'Data contracts',
          'Twin assets',
          'Summary',
          'Readiness findings',
          'Validation and preflight',
        ]),
      );
    });

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

    test('starts an empty draft at Define Twin and blocks research inputs', () {
      final journey = ConfigurationJourney.fromWizardState(
        const WizardState(status: WizardStatus.ready),
      );

      expect(journey.currentTaskId, ConfigurationTaskId.defineTwin);
      expect(
        journey.task(ConfigurationTaskId.deviceTraffic).status,
        ConfigurationTaskStatus.blocked,
      );
      expect(
        journey.task(ConfigurationTaskId.deviceTraffic).blockingReason,
        'Save the Twin draft first',
      );
      expect(
        journey.task(ConfigurationTaskId.cloudAccess).blockingReason,
        'Calculate the cost allocation first',
      );
    });

    test(
      'blocks scenario work when the canonical contract is incompatible',
      () {
        final journey = ConfigurationJourney.fromWizardState(
          const WizardState(
            status: WizardStatus.ready,
            twinId: 'twin-1',
            twinName: 'Historical Twin',
            architectureDetailPhase: ArchitectureDetailPhase.error,
            architectureDetailError: 'Canonical contract mismatch',
          ),
        );

        expect(journey.recommendedTaskId, ConfigurationTaskId.defineTwin);
        expect(
          journey.task(ConfigurationTaskId.defineTwin).status,
          ConfigurationTaskStatus.current,
        );
        expect(
          journey.task(ConfigurationTaskId.processing).blockingReason,
          contains('six-layer-eventing@1'),
        );
      },
    );

    test('moves directly from complete scenario to cost calculation', () {
      final journey = ConfigurationJourney.fromWizardState(
        architectureReadyWizardState().copyWith(
          calcParams: CalcParams.defaultParams(),
          isCalcFormValid: true,
        ),
      );

      expect(
        journey.recommendedTaskId,
        ConfigurationTaskId.calculateCostAllocation,
      );
      expect(
        journey.task(ConfigurationTaskId.calculateCostAllocation).status,
        ConfigurationTaskStatus.current,
      );
      expect(
        journey.task(ConfigurationTaskId.reviewImmutableResult).status,
        ConfigurationTaskStatus.blocked,
      );
    });

    test('falls back from a blocked requested task deterministically', () {
      final journey = ConfigurationJourney.fromWizardState(
        const WizardState(status: WizardStatus.ready),
        requestedTaskId: ConfigurationTaskId.validationAndPreflight,
      );

      expect(journey.currentTaskId, ConfigurationTaskId.defineTwin);
    });
  });
}
