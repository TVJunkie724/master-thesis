// lib/widgets/credentials/credential_input_form.dart
// Extracted credential input form widget

import 'package:flutter/material.dart';

/// Field definition for credential input
class CredentialFieldDef {
  final String key;
  final String label;
  final String hint;
  final bool isRequired;
  final bool isSecret;
  final bool isMultiline;
  final String? helperText;
  final int maxLines;

  const CredentialFieldDef({
    required this.key,
    required this.label,
    required this.hint,
    this.isRequired = true,
    this.isSecret = false,
    this.isMultiline = false,
    this.helperText,
    this.maxLines = 1,
  });
}

/// A form for entering credential fields for a cloud provider.
///
/// Features:
/// - Dynamic field rendering based on field definitions
/// - Secret field masking with toggle
/// - Stored credential hints
/// - Disabled state for inherited credentials
class CredentialInputForm extends StatefulWidget {
  final List<CredentialFieldDef> fields;
  final Map<String, String> values;
  final Map<String, TextEditingController> controllers;
  final bool hasStoredCredentials;
  final bool isDisabled;
  final ValueChanged<Map<String, String>> onChanged;

  const CredentialInputForm({
    super.key,
    required this.fields,
    required this.values,
    required this.controllers,
    required this.onChanged,
    this.hasStoredCredentials = false,
    this.isDisabled = false,
  });

  @override
  State<CredentialInputForm> createState() => _CredentialInputFormState();
}

class _CredentialInputFormState extends State<CredentialInputForm> {
  final Map<String, bool> _obscuredFields = {};

  @override
  void initState() {
    super.initState();
    // Initialize obscured state for secret fields
    for (final field in widget.fields) {
      if (field.isSecret) {
        _obscuredFields[field.key] = true;
      }
    }
  }

  void _onFieldChanged(String key, String value) {
    final updated = Map<String, String>.from(widget.values);
    updated[key] = value;
    widget.onChanged(updated);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (int i = 0; i < widget.fields.length; i++) ...[
          _buildField(widget.fields[i]),
          if (i < widget.fields.length - 1) const SizedBox(height: 16),
        ],
      ],
    );
  }

  Widget _buildField(CredentialFieldDef field) {
    final theme = Theme.of(context);
    final controller = widget.controllers[field.key];
    final currentValue = widget.values[field.key] ?? '';
    final hasValue = currentValue.isNotEmpty;
    final isSecretAndEmpty =
        field.isSecret && !hasValue && widget.hasStoredCredentials;

    return TextField(
      controller: controller,
      enabled: !widget.isDisabled,
      obscureText: field.isSecret && (_obscuredFields[field.key] ?? false),
      maxLines: field.isSecret ? 1 : field.maxLines,
      decoration: InputDecoration(
        labelText: field.label,
        hintText: isSecretAndEmpty ? 'Stored securely' : field.hint,
        hintStyle: isSecretAndEmpty
            ? TextStyle(
                color: theme.colorScheme.primary.withValues(alpha: 0.7),
                fontStyle: FontStyle.italic,
              )
            : null,
        helperText: field.helperText,
        border: const OutlineInputBorder(),
        enabledBorder: OutlineInputBorder(
          borderSide: BorderSide(color: theme.colorScheme.outline),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: BorderSide(color: theme.colorScheme.primary, width: 2),
        ),
        suffixIcon: field.isSecret
            ? IconButton(
                icon: Icon(
                  _obscuredFields[field.key] ?? false
                      ? Icons.visibility_off
                      : Icons.visibility,
                  color: theme.colorScheme.outline,
                ),
                onPressed: widget.isDisabled
                    ? null
                    : () {
                        setState(() {
                          _obscuredFields[field.key] =
                              !(_obscuredFields[field.key] ?? false);
                        });
                      },
                tooltip: _obscuredFields[field.key] ?? false ? 'Show' : 'Hide',
              )
            : null,
        suffixText: field.isRequired ? null : '(optional)',
      ),
      onChanged: (value) => _onFieldChanged(field.key, value),
    );
  }
}
