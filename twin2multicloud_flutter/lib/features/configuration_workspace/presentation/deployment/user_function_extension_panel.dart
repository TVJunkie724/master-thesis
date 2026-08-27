import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../../../bloc/wizard/wizard.dart';
import '../../../../models/user_function_extension.dart';
import '../../../../theme/spacing.dart';
import '../../../../widgets/file_inputs/platform_file_selection_button.dart';
import 'deployment_contracts.dart';

class ExtensionSlotList extends StatelessWidget {
  final WizardState state;
  final WizardEventSink onEvent;

  const ExtensionSlotList({
    super.key,
    required this.state,
    required this.onEvent,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const ValueKey('extension-slot-list'),
      children: [
        for (final slot in state.extensionSlots) ...[
          ExtensionSlotPanel(slot: slot, state: state, onEvent: onEvent),
          const SizedBox(height: AppSpacing.md),
        ],
      ],
    );
  }
}

class ExtensionSlotPanel extends StatelessWidget {
  final ExtensionSlot slot;
  final WizardState state;
  final WizardEventSink onEvent;

  const ExtensionSlotPanel({
    super.key,
    required this.slot,
    required this.state,
    required this.onEvent,
  });

  @override
  Widget build(BuildContext context) {
    final phase = state.extensionPhase(slot.slotId);
    final draft = state.extensionDraft(slot.slotId);
    final validation = state.extensionValidation(slot.slotId);
    final userFunction = state.twinUserFunction(slot.slotId);
    final error = state.extensionErrors[slot.slotId];
    return Semantics(
      key: ValueKey('extension-slot-${slot.slotId}'),
      container: true,
      label: '${slot.displayName} extension slot',
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.lg),
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact =
                  constraints.maxWidth <
                  AppSpacing.userFunctionCompactBreakpoint;
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _StatusHeader(slot: slot, phase: phase),
                  const SizedBox(height: AppSpacing.md),
                  _SourceActions(
                    compact: compact,
                    selectedFileName: draft?.filename,
                    isValidating: phase == UserFunctionWorkflowPhase.validating,
                    onSelected: (bytes, filename) {
                      onEvent(
                        WizardExtensionSourceSelected(
                          slotId: slot.slotId,
                          fileBytes: bytes,
                          fileName: filename,
                        ),
                      );
                    },
                    onValidate:
                        draft?.bytes.isNotEmpty == true &&
                            phase != UserFunctionWorkflowPhase.validating
                        ? () => onEvent(
                            WizardExtensionValidationRequested(slot.slotId),
                          )
                        : null,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  _RuntimeSummary(slot: slot, compact: compact),
                  const SizedBox(height: AppSpacing.sm),
                  _DependencySummary(validation: validation),
                  const SizedBox(height: AppSpacing.md),
                  DynamicConfigurationForm(
                    key: ValueKey('extension-config-${slot.slotId}'),
                    slot: slot,
                    values: draft?.configuration ?? const {},
                    onChanged: (field, value) {
                      onEvent(
                        WizardExtensionConfigurationChanged(
                          slotId: slot.slotId,
                          field: field,
                          value: value,
                        ),
                      );
                    },
                  ),
                  if (error != null) ...[
                    const SizedBox(height: AppSpacing.sm),
                    Semantics(
                      liveRegion: true,
                      child: Text(
                        error,
                        key: ValueKey('extension-error-${slot.slotId}'),
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.sm),
                  ValidationDetails(
                    validation: validation,
                    userFunction: userFunction,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  Align(
                    alignment: compact
                        ? Alignment.centerLeft
                        : Alignment.centerRight,
                    child: Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: AppSpacing.sm,
                      children: [
                        if (userFunction != null)
                          OutlinedButton.icon(
                            key: ValueKey('extension-delete-${slot.slotId}'),
                            onPressed: phase == UserFunctionWorkflowPhase.saving
                                ? null
                                : () => onEvent(
                                    WizardExtensionDeleteRequested(slot.slotId),
                                  ),
                            icon: const Icon(Icons.delete_outline),
                            label: const Text('Remove function'),
                          ),
                        _AsyncActionButton(
                          key: ValueKey('extension-save-${slot.slotId}'),
                          label: userFunction == null
                              ? 'Save function'
                              : 'Replace function',
                          isLoading: phase == UserFunctionWorkflowPhase.saving,
                          onPressed:
                              phase == UserFunctionWorkflowPhase.valid &&
                                  state.twinId != null
                              ? () => onEvent(
                                  WizardExtensionSaveRequested(slot.slotId),
                                )
                              : null,
                        ),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

class _StatusHeader extends StatelessWidget {
  final ExtensionSlot slot;
  final UserFunctionWorkflowPhase phase;

  const _StatusHeader({required this.slot, required this.phase});

  @override
  Widget build(BuildContext context) {
    final status = switch (phase) {
      UserFunctionWorkflowPhase.draft => 'Draft',
      UserFunctionWorkflowPhase.validating => 'Validating',
      UserFunctionWorkflowPhase.invalid => 'Invalid',
      UserFunctionWorkflowPhase.valid => 'Valid',
      UserFunctionWorkflowPhase.saving => 'Saving',
      UserFunctionWorkflowPhase.saved => 'Saved',
      UserFunctionWorkflowPhase.stale => 'Stale',
      UserFunctionWorkflowPhase.error => 'Error',
    };
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Icon(Icons.extension_outlined),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                slot.displayName,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text(
                'Slot: ${slot.slotId}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
        Semantics(
          label: 'Extension status $status',
          child: Chip(
            key: ValueKey('extension-status-${slot.slotId}'),
            label: Text(status),
          ),
        ),
      ],
    );
  }
}

class _SourceActions extends StatelessWidget {
  final bool compact;
  final String? selectedFileName;
  final bool isValidating;
  final void Function(Uint8List bytes, String filename) onSelected;
  final VoidCallback? onValidate;

  const _SourceActions({
    required this.compact,
    required this.selectedFileName,
    required this.isValidating,
    required this.onSelected,
    required this.onValidate,
  });

  @override
  Widget build(BuildContext context) {
    final picker = ArtifactSourcePicker(
      selectedFileName: selectedFileName,
      onSelected: onSelected,
    );
    final validate = FilledButton.icon(
      key: const ValueKey('extension-validate'),
      onPressed: onValidate,
      icon: isValidating
          ? const SizedBox.square(
              dimension: AppSpacing.md,
              child: CircularProgressIndicator(strokeWidth: AppSpacing.xxs),
            )
          : const Icon(Icons.verified_outlined),
      label: Text(isValidating ? 'Validating' : 'Validate'),
    );
    if (compact) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          picker,
          const SizedBox(height: AppSpacing.sm),
          validate,
        ],
      );
    }
    return Row(
      children: [
        Expanded(child: picker),
        const SizedBox(width: AppSpacing.sm),
        validate,
      ],
    );
  }
}

class ArtifactSourcePicker extends StatelessWidget {
  final String? selectedFileName;
  final void Function(Uint8List bytes, String filename) onSelected;

  const ArtifactSourcePicker({
    super.key,
    required this.selectedFileName,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return PlatformFileSelectionButton(
      key: const ValueKey('extension-source-picker'),
      allowedExtensions: const ['zip'],
      withData: true,
      icon: Icons.folder_zip_outlined,
      label: selectedFileName ?? 'Choose source archive',
      onSelected: (file) {
        final bytes = file.bytes;
        if (bytes != null) onSelected(bytes, file.name);
      },
    );
  }
}

class _RuntimeSummary extends StatelessWidget {
  final ExtensionSlot slot;
  final bool compact;

  const _RuntimeSummary({required this.slot, required this.compact});

  @override
  Widget build(BuildContext context) {
    final timeout = slot.resourceLimits['timeout_seconds'];
    final memory = slot.resourceLimits['memory_mb'];
    return Row(
      children: [
        const Icon(Icons.code, size: AppSpacing.iconSm),
        const SizedBox(width: AppSpacing.xs),
        Expanded(
          child: Text(
            compact
                ? 'Python 3.11'
                : 'Runtime: Python 3.11 (platform selected) · '
                      '${timeout}s · $memory MiB',
          ),
        ),
      ],
    );
  }
}

class _DependencySummary extends StatelessWidget {
  final UserFunctionValidationResult? validation;

  const _DependencySummary({required this.validation});

  @override
  Widget build(BuildContext context) {
    final count = validation?.dependencies.length;
    return Row(
      children: [
        const Icon(Icons.inventory_2_outlined, size: AppSpacing.iconSm),
        const SizedBox(width: AppSpacing.xs),
        Expanded(
          child: Text(
            count == null
                ? 'Dependencies: pending validation'
                : '$count pinned / $count verified dependencies',
          ),
        ),
      ],
    );
  }
}

class DynamicConfigurationForm extends StatelessWidget {
  final ExtensionSlot slot;
  final Map<String, dynamic> values;
  final void Function(String field, Object? value) onChanged;

  const DynamicConfigurationForm({
    super.key,
    required this.slot,
    required this.values,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Configuration · ${slot.configurationFields.where((field) => field.required).length} required',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: AppSpacing.sm),
        for (final field in slot.configurationFields)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: _field(field),
          ),
      ],
    );
  }

  Widget _field(ExtensionConfigurationField field) {
    if (field.type == 'boolean') {
      return SwitchListTile(
        key: ValueKey('extension-field-${field.name}'),
        contentPadding: EdgeInsets.zero,
        title: Text(field.title),
        value: values[field.name] == true,
        onChanged: (value) => onChanged(field.name, value),
      );
    }
    if (field.allowedValues.isNotEmpty) {
      return DropdownButtonFormField<Object>(
        key: ValueKey('extension-field-${field.name}'),
        initialValue: values[field.name],
        decoration: InputDecoration(labelText: field.title),
        items: [
          for (final value in field.allowedValues)
            DropdownMenuItem(value: value, child: Text(value.toString())),
        ],
        onChanged: (value) => onChanged(field.name, value),
      );
    }
    return TextFormField(
      key: ValueKey('extension-field-${field.name}'),
      initialValue: values[field.name]?.toString(),
      autovalidateMode: AutovalidateMode.onUserInteraction,
      keyboardType: {'integer', 'number'}.contains(field.type)
          ? const TextInputType.numberWithOptions(decimal: true, signed: true)
          : TextInputType.text,
      decoration: InputDecoration(
        labelText: field.title,
        helperText: field.required ? 'Required non-secret value' : 'Optional',
      ),
      validator: (value) => _validateField(field, value),
      onChanged: (value) {
        final parsed = switch (field.type) {
          'integer' => int.tryParse(value),
          'number' => num.tryParse(value),
          _ => value,
        };
        onChanged(field.name, parsed);
      },
    );
  }

  String? _validateField(ExtensionConfigurationField field, String? value) {
    if (field.required && (value == null || value.trim().isEmpty)) {
      return '${field.title} is required';
    }
    if (value == null || value.isEmpty) return null;
    if ({'integer', 'number'}.contains(field.type)) {
      final number = field.type == 'integer'
          ? int.tryParse(value)
          : num.tryParse(value);
      if (number == null) return 'Enter a valid ${field.type}';
      if (field.minimum != null && number < field.minimum!) {
        return 'Minimum: ${field.minimum}';
      }
      if (field.maximum != null && number > field.maximum!) {
        return 'Maximum: ${field.maximum}';
      }
    }
    if (field.minLength != null && value.length < field.minLength!) {
      return 'Minimum length: ${field.minLength}';
    }
    if (field.maxLength != null && value.length > field.maxLength!) {
      return 'Maximum length: ${field.maxLength}';
    }
    if (field.pattern != null) {
      try {
        if (!RegExp(field.pattern!).hasMatch(value)) {
          return 'Enter a value matching the required format';
        }
      } on FormatException {
        return 'The field contract has an invalid format rule';
      }
    }
    return null;
  }
}

class ValidationDetails extends StatelessWidget {
  final UserFunctionValidationResult? validation;
  final TwinUserFunction? userFunction;

  const ValidationDetails({
    super.key,
    required this.validation,
    required this.userFunction,
  });

  @override
  Widget build(BuildContext context) {
    return ExpansionTile(
      key: const ValueKey('extension-validation-details'),
      tilePadding: EdgeInsets.zero,
      title: const Text('Validation details'),
      subtitle: Text(
        validation == null
            ? 'No validation evidence yet'
            : '${validation!.checks.length} checks passed',
      ),
      children: [
        if (validation != null)
          for (final check in validation!.checks)
            ListTile(
              dense: true,
              leading: const Icon(Icons.check, size: AppSpacing.iconSm),
              title: Text(check.replaceAll('_', ' ')),
            ),
        if (userFunction != null)
          ListTile(
            dense: true,
            leading: const Icon(Icons.save_outlined, size: AppSpacing.iconSm),
            title: const Text('Current Twin function'),
            subtitle: Text(userFunction!.artifactDigest),
          ),
      ],
    );
  }
}

class _AsyncActionButton extends StatelessWidget {
  final String label;
  final bool isLoading;
  final VoidCallback? onPressed;

  const _AsyncActionButton({
    super.key,
    required this.label,
    required this.isLoading,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return FilledButton.icon(
      onPressed: isLoading ? null : onPressed,
      icon: isLoading
          ? const SizedBox.square(
              dimension: AppSpacing.md,
              child: CircularProgressIndicator(strokeWidth: AppSpacing.xxs),
            )
          : const Icon(Icons.save_outlined),
      label: Text(isLoading ? 'Saving' : label),
    );
  }
}
