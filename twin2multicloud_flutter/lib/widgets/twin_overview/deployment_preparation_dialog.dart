import 'package:flutter/material.dart';

import '../../models/deployment_readiness.dart';
import '../../theme/spacing.dart';

class DeploymentPreparationDialog extends StatefulWidget {
  final DeploymentPreparationPlan plan;

  const DeploymentPreparationDialog({super.key, required this.plan});

  @override
  State<DeploymentPreparationDialog> createState() =>
      _DeploymentPreparationDialogState();
}

class _DeploymentPreparationDialogState
    extends State<DeploymentPreparationDialog> {
  final Set<String> _acknowledgedManualRequirements = {};

  bool get _canConfirm =>
      widget.plan.actions.isNotEmpty ||
      _acknowledgedManualRequirements.isNotEmpty;

  void _confirm() {
    if (!_canConfirm) return;
    Navigator.of(context).pop(
      DeploymentPreparationRequest(
        planDigest: widget.plan.planDigest,
        requirementsDigest: widget.plan.requirementsDigest,
        manualRequirementIds: _acknowledgedManualRequirements,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return AlertDialog(
      title: const Row(
        children: [
          Icon(Icons.admin_panel_settings_outlined),
          SizedBox(width: AppSpacing.sm),
          Expanded(child: Text('Review provider preparation')),
        ],
      ),
      content: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.dialogContentMaxWidth,
          maxHeight: 560,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(AppSpacing.md),
                decoration: BoxDecoration(
                  color: colors.secondaryContainer,
                  borderRadius: BorderRadius.circular(AppSpacing.sm),
                ),
                child: Text(
                  'Only the listed account-level changes will be automated. '
                  'They are non-destructive, but persist after this Twin is destroyed.',
                  style: TextStyle(color: colors.onSecondaryContainer),
                ),
              ),
              if (widget.plan.actions.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.lg),
                Text(
                  'Automatic changes',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: AppSpacing.sm),
                for (final action in widget.plan.actions)
                  _AutomaticActionTile(action: action),
              ],
              if (widget.plan.manualRequirements.isNotEmpty) ...[
                const SizedBox(height: AppSpacing.lg),
                Text(
                  'External steps',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
                const SizedBox(height: AppSpacing.xs),
                const Text(
                  'Confirm only steps you have actually completed. '
                  'Unselected steps remain pending.',
                ),
                const SizedBox(height: AppSpacing.sm),
                for (final requirement in widget.plan.manualRequirements)
                  CheckboxListTile(
                    key: ValueKey(
                      'manual-preparation-${requirement.requirementId}',
                    ),
                    value: _acknowledgedManualRequirements.contains(
                      requirement.requirementId,
                    ),
                    onChanged: (selected) {
                      setState(() {
                        if (selected == true) {
                          _acknowledgedManualRequirements.add(
                            requirement.requirementId,
                          );
                        } else {
                          _acknowledgedManualRequirements.remove(
                            requirement.requirementId,
                          );
                        }
                      });
                    },
                    controlAffinity: ListTileControlAffinity.leading,
                    contentPadding: EdgeInsets.zero,
                    title: Text(
                      'I completed this ${requirement.provider.label} step',
                    ),
                    subtitle: Text(
                      '${requirement.capabilityId}\n${requirement.reason}',
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton.icon(
          key: const Key('confirm-deployment-preparation'),
          onPressed: _canConfirm ? _confirm : null,
          icon: const Icon(Icons.playlist_add_check),
          label: const Text('Confirm preparation'),
        ),
      ],
    );
  }
}

class _AutomaticActionTile extends StatelessWidget {
  final AccountPreparationAction action;

  const _AutomaticActionTile({required this.action});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const Icon(Icons.settings_suggest_outlined),
      title: Text('${action.provider.label}: ${action.capabilityId}'),
      subtitle: Text('${_actionLabel(action.actionType)}\n${action.reason}'),
    );
  }
}

String _actionLabel(String actionType) => switch (actionType) {
  'register_resource_provider' => 'Register Azure resource provider',
  'enable_project_api' => 'Enable Google Cloud project API',
  _ => actionType,
};
