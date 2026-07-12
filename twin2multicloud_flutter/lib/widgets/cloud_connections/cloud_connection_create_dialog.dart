import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../theme/spacing.dart';
import 'cloud_connection_strings.dart';
import 'provider_payload_form.dart';

class CloudConnectionCreateDialog extends StatefulWidget {
  final CloudProvider provider;
  final CloudConnectionPurpose purpose;

  const CloudConnectionCreateDialog({
    super.key,
    required this.provider,
    this.purpose = CloudConnectionPurpose.deployment,
  });

  @override
  State<CloudConnectionCreateDialog> createState() =>
      _CloudConnectionCreateDialogState();
}

class _CloudConnectionCreateDialogState
    extends State<CloudConnectionCreateDialog> {
  final _displayNameController = TextEditingController();
  final _formKey = GlobalKey<ProviderPayloadFormState>();
  String? _errorText;

  @override
  void dispose() {
    _displayNameController.clear();
    _displayNameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AlertDialog(
      title: Text('New ${widget.provider.label} ${widget.purpose.label}'),
      content: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.maxContentWidthMedium,
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              TextField(
                controller: _displayNameController,
                decoration: const InputDecoration(
                  labelText: 'Display name',
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (_) => _submit(),
              ),
              const SizedBox(height: AppSpacing.md),
              ProviderPayloadForm(
                key: _formKey,
                provider: widget.provider,
                onChanged: (_) {
                  if (_errorText != null) {
                    setState(() => _errorText = null);
                  }
                },
              ),
              if (_errorText != null) ...[
                const SizedBox(height: AppSpacing.md),
                Text(
                  _errorText!,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.error,
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
          child: const Text(CloudConnectionStrings.cancel),
        ),
        FilledButton(
          onPressed: _submit,
          child: const Text(CloudConnectionStrings.create),
        ),
      ],
    );
  }

  void _submit() {
    final displayName = _displayNameController.text.trim();
    final payloadForm = _formKey.currentState;

    if (displayName.isEmpty || payloadForm == null || !payloadForm.validate()) {
      setState(() {
        _errorText =
            'Display name and required credential fields are required.';
      });
      return;
    }

    Navigator.of(context).pop(
      CloudConnectionCreateRequest(
        provider: widget.provider,
        purpose: widget.purpose,
        displayName: displayName,
        credentials: payloadForm.credentials(),
      ),
    );
  }
}
