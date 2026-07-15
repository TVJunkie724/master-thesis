import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/domain/configuration_journey.dart';
import 'package:twin2multicloud_flutter/features/configuration_workspace/presentation/deployment/deployment_task_content.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';
import 'package:twin2multicloud_flutter/models/calc_result.dart';
import 'package:twin2multicloud_flutter/models/deployer_artifact_validation.dart';

void main() {
  CalcResult result({
    String layer2 = 'GCP',
    String layer4 = 'AWS',
    String layer5 = 'AZURE',
  }) => CalcResult(
    totalCost: 0,
    awsCosts: ProviderCosts(),
    azureCosts: ProviderCosts(),
    gcpCosts: ProviderCosts(),
    cheapestPath: [
      'L1_AWS',
      'L2_$layer2',
      'L3_hot_GCP',
      'L3_cool_AZURE',
      'L3_archive_AWS',
      'L4_$layer4',
      'L5_$layer5',
    ],
    inputParamsUsed: const InputParamsUsed(),
  );

  final state = WizardState(
    calcParams: CalcParams.defaultParams(),
    calcResult: result(),
  );

  Widget buildTask(
    ConfigurationTaskId? taskId, {
    double width = 1000,
    WizardState? wizardState,
    ValueChanged<WizardEvent>? onEvent,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: SizedBox(
          width: width,
          height: 900,
          child: DeploymentTaskContent(
            state: wizardState ?? state,
            taskId: taskId,
            onEvent: onEvent ?? (_) {},
            zipUploadBlock: const Text('ZIP upload control'),
            onUploadGlb: () {},
            onDeleteGlb: () {},
          ),
        ),
      ),
    );
  }

  testWidgets('data-contract task composes upload, config, and payload views', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildTask(ConfigurationTaskId.dataContracts, width: 640),
    );

    expect(
      find.byKey(const ValueKey('deployment-task-dataContracts')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('deployment-config-section')),
      findsOneWidget,
    );
    expect(find.text('Quick Upload'), findsOneWidget);
    expect(find.text('ZIP upload control'), findsOneWidget);
    expect(find.text('payloads.json'), findsWidgets);
    expect(
      find.byKey(const ValueKey('deployment-user-logic-section')),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('data-contract validation emits the exact typed request', (
    tester,
  ) async {
    final events = <WizardEvent>[];
    await tester.pumpWidget(
      buildTask(
        ConfigurationTaskId.dataContracts,
        wizardState: state.copyWith(deployerDigitalTwinName: 'factory-twin'),
        onEvent: events.add,
      ),
    );

    final validateButton = find.widgetWithText(FilledButton, 'Validate').first;
    await tester.ensureVisible(validateButton);
    await tester.tap(validateButton);
    await tester.pump();

    expect(events, hasLength(1));
    expect(
      events.single,
      isA<WizardArtifactValidationRequested>().having(
        (event) => event.request,
        'request',
        const DeployerArtifactValidationRequest(
          type: DeployerArtifactType.config,
          content:
              '{\n'
              '  "digital_twin_name": "factory-twin",\n'
              '  "mode": "DEBUG",\n'
              '  "hot_storage_size_in_days": 30,\n'
              '  "cold_storage_size_in_days": 90\n'
              '}',
        ),
      ),
    );
  });

  testWidgets('user-logic task excludes unrelated configuration editors', (
    tester,
  ) async {
    await tester.pumpWidget(buildTask(ConfigurationTaskId.userLogic));

    expect(
      find.byKey(const ValueKey('deployment-task-userLogic')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('deployment-user-logic-section')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('deployment-config-section')),
      findsNothing,
    );
    expect(find.text('Quick Upload'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('user-logic task exposes unmet device dependency', (
    tester,
  ) async {
    await tester.pumpWidget(buildTask(ConfigurationTaskId.userLogic));

    expect(
      find.text(
        'Validate config_iot_devices.json first to enable processor function inputs.',
      ),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('user-logic task composes all dynamic artifacts', (tester) async {
    final events = <WizardEvent>[];
    final params = CalcParams.fromJson({
      ...CalcParams.defaultParams().toJson(),
      'useEventChecking': true,
      'triggerNotificationWorkflow': true,
      'returnFeedbackToDevice': true,
    });
    final dynamicState = WizardState(
      calcParams: params,
      calcResult: result(layer2: 'AZURE'),
      configIotDevicesValidated: true,
      configIotDevicesJson: jsonEncode(const {
        'devices': [
          {'device_id': 'sensor-1'},
        ],
      }),
      configEventsValidated: true,
      configEventsJson: jsonEncode(const [
        {
          'actions': [
            {'functionName': 'notify-operator'},
          ],
        },
      ]),
      processorContents: const {'sensor-1': 'def main(): pass'},
    );

    await tester.pumpWidget(
      buildTask(
        ConfigurationTaskId.userLogic,
        wizardState: dynamicState,
        onEvent: events.add,
      ),
    );

    expect(find.text('processors/sensor-1/lambda_function.py'), findsOneWidget);
    expect(find.text('event-feedback/lambda_function.py'), findsOneWidget);
    expect(
      find.text('event_actions/notify-operator/lambda_function.py'),
      findsOneWidget,
    );
    expect(find.text('state_machines/azure_logic_app.json'), findsOneWidget);
    await tester.tap(find.widgetWithText(ElevatedButton, 'Validate').first);
    await tester.pump();
    expect(
      events.single,
      isA<WizardArtifactValidationRequested>().having(
        (event) => event.request,
        'request',
        const DeployerArtifactValidationRequest(
          type: DeployerArtifactType.processor,
          content: 'def main(): pass',
          provider: 'AZURE',
          entityId: 'sensor-1',
        ),
      ),
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('twin-assets task remains usable at compact width', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildTask(ConfigurationTaskId.twinAssets, width: 640),
    );

    expect(
      find.byKey(const ValueKey('deployment-task-twinAssets')),
      findsOneWidget,
    );
    expect(
      find.byKey(const ValueKey('deployment-config-section')),
      findsOneWidget,
    );
    expect(find.text('aws_hierarchy.json'), findsWidgets);
    expect(find.text('config_user.json'), findsWidgets);
    expect(
      find.text(
        '• Define entities with components\n'
        '• Match entity IDs to scene config',
      ),
      findsOneWidget,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('legacy all-task view preserves the layer-aligned shell', (
    tester,
  ) async {
    await tester.pumpWidget(buildTask(null, width: 1200));

    expect(find.byKey(const ValueKey('deployment-task-all')), findsOneWidget);
    expect(find.text('Configuration Files'), findsWidgets);
    expect(find.text('User Functions & Assets'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('twin-assets task uses Azure scene contracts', (tester) async {
    final azureState = WizardState(
      calcParams: CalcParams.fromJson({
        ...CalcParams.defaultParams().toJson(),
        'needs3DModel': true,
      }),
      calcResult: result(layer4: 'AZURE', layer5: 'AZURE'),
      hierarchyValidated: true,
    );

    await tester.pumpWidget(
      buildTask(ConfigurationTaskId.twinAssets, wizardState: azureState),
    );

    expect(find.text('azure_hierarchy.json'), findsWidgets);
    expect(find.text('3DScenesConfiguration.json'), findsWidgets);
    expect(find.text('config_user.json'), findsWidgets);
    expect(find.text('Upload 3D model for visualization'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('twin-assets task uses AWS scene contracts', (tester) async {
    final awsState = WizardState(
      calcParams: CalcParams.fromJson({
        ...CalcParams.defaultParams().toJson(),
        'needs3DModel': true,
      }),
      calcResult: result(layer4: 'AWS', layer5: 'AWS'),
      hierarchyValidated: true,
    );

    await tester.pumpWidget(
      buildTask(ConfigurationTaskId.twinAssets, wizardState: awsState),
    );

    expect(find.text('aws_hierarchy.json'), findsWidgets);
    expect(find.text('scene.json'), findsWidgets);
    expect(find.text('config_user.json'), findsWidgets);
    expect(find.text('Upload 3D model for visualization'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'twin-assets task explains no-3D and unsupported provider paths',
    (tester) async {
      await tester.pumpWidget(
        buildTask(
          ConfigurationTaskId.twinAssets,
          wizardState: WizardState(
            calcParams: CalcParams.defaultParams(),
            calcResult: result(layer4: 'GCP', layer5: 'GCP'),
          ),
        ),
      );

      expect(
        find.text('L4 visualization is not required by the workload intent'),
        findsOneWidget,
      );
      expect(
        find.text(
          'GCP Grafana configuration not supported in this thesis scope',
        ),
        findsOneWidget,
      );
      expect(find.text('aws_hierarchy.json'), findsNothing);
      expect(find.text('azure_hierarchy.json'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('twin-assets task explains unsupported GCP 3D intent', (
    tester,
  ) async {
    await tester.pumpWidget(
      buildTask(
        ConfigurationTaskId.twinAssets,
        wizardState: WizardState(
          calcParams: CalcParams.fromJson({
            ...CalcParams.defaultParams().toJson(),
            'needs3DModel': true,
          }),
          calcResult: result(layer4: 'GCP', layer5: 'GCP'),
        ),
      ),
    );

    expect(
      find.text('GCP does not support 3D visualization in this thesis scope'),
      findsOneWidget,
    );
    expect(find.text('scene.json'), findsNothing);
    expect(find.text('3DScenesConfiguration.json'), findsNothing);
    expect(tester.takeException(), isNull);
  });
}
