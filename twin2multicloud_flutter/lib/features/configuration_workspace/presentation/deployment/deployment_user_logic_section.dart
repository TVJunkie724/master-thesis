import 'package:flutter/material.dart';

import '../../../../bloc/wizard/wizard.dart';
import '../../../../config/step3_constraints.dart';
import '../../../../models/deployer_artifact_validation.dart';
import '../../../../theme/spacing.dart';
import '../../../../widgets/file_inputs/collapsible_block_wrapper.dart';
import '../../../../widgets/file_inputs/file_editor_block.dart';
import '../../../../widgets/step3/info_cards.dart';
import 'deployment_contracts.dart';
import 'user_function_extension_panel.dart';

class DeploymentUserLogicSection extends StatelessWidget {
  final WizardState state;
  final WizardEventSink onEvent;

  const DeploymentUserLogicSection({
    super.key,
    required this.state,
    required this.onEvent,
  });

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[
      if (state.userFunctionsLoading)
        const Center(
          child: Padding(
            padding: EdgeInsets.all(AppSpacing.lg),
            child: CircularProgressIndicator(),
          ),
        )
      else if (state.extensionErrors['_sources'] case final message?)
        Step3InfoCards.dependencyInfo(context, message)
      else if (state.extensionSlots.isEmpty)
        Step3InfoCards.emptyState(
          context,
          'No reviewed user-function extension slots are available.',
        )
      else
        ExtensionSlotList(state: state, onEvent: onEvent),
    ];
    _addStateMachine(children);
    return Column(
      key: const ValueKey('deployment-user-logic-section'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    );
  }

  void _addStateMachine(List<Widget> children) {
    if (!state.shouldShowStateMachine) return;
    final filename = state.stateMachineFilename ?? 'state_machine.json';
    children.add(const SizedBox(height: AppSpacing.md));
    children.add(
      CollapsibleBlockWrapper(
        title: filename,
        subtitle: 'Workflow / state machine definition',
        icon: Icons.account_tree,
        isValid: state.stateMachineValidated ? true : null,
        showEditBadge: true,
        initiallyExpanded: !state.stateMachineValidated,
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
            onEvent(
              WizardArtifactValidationRequested(
                buildDeploymentValidationRequest(
                  state: state,
                  type: DeployerArtifactType.stateMachine,
                  content: content,
                ),
              ),
            );
          },
          autoValidateOnUpload: true,
        ),
      ),
    );
  }
}
