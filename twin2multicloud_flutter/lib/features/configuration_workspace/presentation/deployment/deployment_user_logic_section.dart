import 'package:flutter/material.dart';

import '../../../../bloc/wizard/wizard.dart';
import '../../../../config/step3_constraints.dart';
import '../../../../models/deployer_artifact_validation.dart';
import '../../../../theme/spacing.dart';
import '../../../../widgets/file_inputs/collapsible_block_wrapper.dart';
import '../../../../widgets/file_inputs/file_editor_block.dart';
import '../../../../widgets/file_inputs/function_package_block.dart';
import '../../../../widgets/step3/info_cards.dart';
import 'deployment_contracts.dart';

class DeploymentUserLogicSection extends StatelessWidget {
  final WizardState state;
  final WizardEventSink onEvent;

  const DeploymentUserLogicSection({
    super.key,
    required this.state,
    required this.onEvent,
  });

  void _validate(
    DeployerArtifactType type,
    String content, {
    String? entityId,
  }) {
    onEvent(
      WizardArtifactValidationRequested(
        buildDeploymentValidationRequest(
          state: state,
          type: type,
          content: content,
          entityId: entityId,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final editors = <Widget>[];
    _addProcessors(context, editors);
    _addFeedbackFunction(editors);
    _addEventActions(context, editors);
    _addStateMachine(editors);

    if (editors.isEmpty) {
      editors.add(
        Step3InfoCards.emptyState(
          context,
          'Enable orchestration or device feedback in Processing to add user-logic inputs.',
        ),
      );
    }

    return Column(
      key: const ValueKey('deployment-user-logic-section'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: editors,
    );
  }

  void _addProcessors(BuildContext context, List<Widget> editors) {
    if (!state.configIotDevicesValidated) {
      editors.add(
        Step3InfoCards.dependencyInfo(
          context,
          'Validate config_iot_devices.json first to enable processor function inputs.',
        ),
      );
      return;
    }
    if (state.deviceIds.isEmpty) {
      editors.add(
        Step3InfoCards.emptyState(
          context,
          'No devices found in config_iot_devices.json',
        ),
      );
      return;
    }

    for (final deviceId in state.deviceIds) {
      editors.add(
        FunctionPackageBlock(
          codeFilename: 'processors/$deviceId/lambda_function.py',
          description: 'Processor Lambda for $deviceId',
          codeContent: state.processorContents[deviceId] ?? '',
          isCodeValidated: state.processorValidated[deviceId] ?? false,
          isValidating: state.isArtifactValidating('processor:$deviceId'),
          validationFeedback: state.artifactFeedback('processor:$deviceId'),
          onCodeChanged: (content) {
            onEvent(WizardProcessorContentChanged(deviceId, content));
          },
          requirementsContent: state.processorRequirements[deviceId],
          onRequirementsChanged: (content) {
            onEvent(WizardProcessorRequirementsChanged(deviceId, content));
          },
          onValidate: (content) {
            _validate(
              DeployerArtifactType.processor,
              content,
              entityId: deviceId,
            );
          },
          constraints: Step3Constraints.getFunctionConstraints(
            state.layer2Provider,
          ),
          exampleContent: Step3Constraints.getProcessorExample(
            state.layer2Provider,
          ),
          initiallyExpanded: !(state.processorValidated[deviceId] ?? false),
          forceCollapsed: state.forceCollapseSections,
        ),
      );
      editors.add(const SizedBox(height: AppSpacing.md));
    }
  }

  void _addFeedbackFunction(List<Widget> editors) {
    if (!state.shouldShowFeedbackFunction) return;

    editors.add(
      FunctionPackageBlock(
        codeFilename: 'event-feedback/lambda_function.py',
        description: 'Event feedback Lambda',
        codeContent: state.eventFeedbackContent ?? '',
        isCodeValidated: state.eventFeedbackValidated,
        isValidating: state.isArtifactValidating('event-feedback'),
        validationFeedback: state.artifactFeedback('event-feedback'),
        onCodeChanged: (content) {
          onEvent(WizardEventFeedbackContentChanged(content));
        },
        requirementsContent: state.eventFeedbackRequirements,
        onRequirementsChanged: (content) {
          onEvent(WizardEventFeedbackRequirementsChanged(content));
        },
        onValidate: (content) {
          _validate(DeployerArtifactType.eventFeedback, content);
        },
        constraints: Step3Constraints.getFunctionConstraints(
          state.layer2Provider,
        ),
        exampleContent: Step3Constraints.getProcessorExample(
          state.layer2Provider,
        ),
        initiallyExpanded: !state.eventFeedbackValidated,
        forceCollapsed: state.forceCollapseSections,
      ),
    );
    editors.add(const SizedBox(height: AppSpacing.md));
  }

  void _addEventActions(BuildContext context, List<Widget> editors) {
    if (state.calcParams?.useEventChecking != true) return;

    if (!state.configEventsValidated) {
      editors.add(
        Step3InfoCards.dependencyInfo(
          context,
          'Validate config_events.json first to enable event action function inputs.',
        ),
      );
      return;
    }
    if (state.eventActionFunctionNames.isEmpty) {
      editors.add(
        Step3InfoCards.emptyState(
          context,
          'No event actions with functionName defined.',
        ),
      );
      return;
    }

    for (final functionName in state.eventActionFunctionNames) {
      editors.add(
        FunctionPackageBlock(
          codeFilename: 'event_actions/$functionName/lambda_function.py',
          description: 'Event action: $functionName',
          codeContent: state.eventActionContents[functionName] ?? '',
          isCodeValidated: state.eventActionValidated[functionName] ?? false,
          isValidating: state.isArtifactValidating(
            'event-action:$functionName',
          ),
          validationFeedback: state.artifactFeedback(
            'event-action:$functionName',
          ),
          onCodeChanged: (content) {
            onEvent(WizardEventActionContentChanged(functionName, content));
          },
          requirementsContent: state.eventActionRequirements[functionName],
          onRequirementsChanged: (content) {
            onEvent(
              WizardEventActionRequirementsChanged(functionName, content),
            );
          },
          onValidate: (content) {
            _validate(
              DeployerArtifactType.eventAction,
              content,
              entityId: functionName,
            );
          },
          constraints: Step3Constraints.getFunctionConstraints(
            state.layer2Provider,
          ),
          exampleContent: Step3Constraints.getProcessorExample(
            state.layer2Provider,
          ),
          initiallyExpanded:
              !(state.eventActionValidated[functionName] ?? false),
          forceCollapsed: state.forceCollapseSections,
        ),
      );
      editors.add(const SizedBox(height: AppSpacing.md));
    }
  }

  void _addStateMachine(List<Widget> editors) {
    if (!state.shouldShowStateMachine) return;

    final filename = state.stateMachineFilename ?? 'state_machine.json';
    editors.add(
      CollapsibleBlockWrapper(
        title: filename,
        subtitle: 'Workflow / state machine definition',
        icon: Icons.account_tree,
        isValid: state.stateMachineValidated ? true : null,
        showEditBadge: true,
        initiallyExpanded: !state.stateMachineValidated,
        forceCollapsed: state.forceCollapseSections,
        child: FileEditorBlock(
          showHeader: false,
          filename: filename,
          description: 'Workflow / state machine definition',
          icon: Icons.account_tree,
          isHighlighted: true,
          constraints: Step3Constraints.getStateMachineConstraints(
            state.layer2Provider,
          ),
          exampleContent: Step3Constraints.getStateMachineExample(
            state.layer2Provider,
          ),
          initialContent: state.stateMachineContent ?? '',
          isValidated: state.stateMachineValidated,
          isValidating: state.isArtifactValidating('state-machine'),
          validationFeedback: state.artifactFeedback('state-machine'),
          onContentChanged: (content) {
            onEvent(WizardStateMachineContentChanged(content));
          },
          onValidate: (content) {
            _validate(DeployerArtifactType.stateMachine, content);
          },
          autoValidateOnUpload: true,
        ),
      ),
    );
  }
}
