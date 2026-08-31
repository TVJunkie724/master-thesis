import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../theme/spacing.dart';
import '../../utils/api_error_handler.dart';
import 'cloud_connection_strings.dart';

typedef CloudCredentialFilePicker =
    Future<PlatformFile?> Function(CloudProvider provider);

/// Captures non-secret metadata and one transient provider credential file.
class CloudConnectionImportDialog extends StatefulWidget {
  final CloudProvider provider;
  final CloudCredentialFilePicker? pickFile;

  const CloudConnectionImportDialog({
    super.key,
    required this.provider,
    this.pickFile,
  });

  @override
  State<CloudConnectionImportDialog> createState() =>
      _CloudConnectionImportDialogState();
}

class _CloudConnectionImportDialogState
    extends State<CloudConnectionImportDialog> {
  final _formKey = GlobalKey<FormState>();
  final _displayName = TextEditingController();
  late final TextEditingController _region;
  final _targetScopeId = TextEditingController();
  final _accountId = TextEditingController();
  final _ssoRegion = TextEditingController();
  final _regionIotHub = TextEditingController();
  final _regionDigitalTwin = TextEditingController();
  final _preparationClientId = TextEditingController();
  final _preparationClientSecret = TextEditingController();
  String? _filename;
  Uint8List? _bytes;
  String? _fileError;

  @override
  void initState() {
    super.initState();
    _region = TextEditingController(text: _defaultRegion(widget.provider));
  }

  @override
  void dispose() {
    _bytes = null;
    _displayName.dispose();
    _region.dispose();
    _targetScopeId.dispose();
    _accountId.dispose();
    _ssoRegion.dispose();
    _regionIotHub.dispose();
    _regionDigitalTwin.dispose();
    _preparationClientId.clear();
    _preparationClientId.dispose();
    _preparationClientSecret.clear();
    _preparationClientSecret.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final expected = widget.provider == CloudProvider.aws ? 'CSV' : 'JSON';
    return AlertDialog(
      title: Text('Import ${widget.provider.label} administrator'),
      content: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppSpacing.dialogContentMaxWidth,
        ),
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _requiredField(_displayName, 'Display name'),
                const SizedBox(height: AppSpacing.md),
                _requiredField(_region, 'Primary region'),
                if (widget.provider != CloudProvider.aws) ...[
                  const SizedBox(height: AppSpacing.md),
                  _requiredField(
                    _targetScopeId,
                    widget.provider == CloudProvider.azure
                        ? 'Subscription ID'
                        : 'Project ID',
                  ),
                ],
                if (widget.provider == CloudProvider.aws) ...[
                  const SizedBox(height: AppSpacing.md),
                  _optionalField(_accountId, 'Account ID (optional)'),
                  const SizedBox(height: AppSpacing.md),
                  _optionalField(
                    _ssoRegion,
                    'IAM Identity Center region (optional)',
                  ),
                ],
                if (widget.provider == CloudProvider.azure) ...[
                  const SizedBox(height: AppSpacing.md),
                  _optionalField(_regionIotHub, 'IoT Hub region (optional)'),
                  const SizedBox(height: AppSpacing.md),
                  _optionalField(
                    _regionDigitalTwin,
                    'Digital Twins region (optional)',
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  Text(
                    CloudConnectionStrings.preparationPrincipal,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    CloudConnectionStrings.preparationPrincipalHelp,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  _requiredField(
                    _preparationClientId,
                    CloudConnectionStrings.preparationClientId,
                  ),
                  const SizedBox(height: AppSpacing.md),
                  _requiredField(
                    _preparationClientSecret,
                    CloudConnectionStrings.preparationClientSecret,
                    obscureText: true,
                  ),
                ],
                const SizedBox(height: AppSpacing.lg),
                OutlinedButton.icon(
                  key: const Key('select-cloud-credential-file'),
                  onPressed: _selectFile,
                  icon: const Icon(Icons.upload_file_outlined),
                  label: Text(
                    _filename == null
                        ? 'Select $expected credential file'
                        : _filename!,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'The file is sent directly for server-side allowlist and credential validation. Its contents are never previewed.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                if (_fileError != null) ...[
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    _fileError!,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('import-cloud-credential'),
          onPressed: _submit,
          child: const Text('Import'),
        ),
      ],
    );
  }

  TextFormField _requiredField(
    TextEditingController controller,
    String label, {
    bool obscureText = false,
  }) => TextFormField(
    controller: controller,
    obscureText: obscureText,
    autocorrect: false,
    enableSuggestions: false,
    decoration: InputDecoration(
      labelText: label,
      border: const OutlineInputBorder(),
    ),
    validator: (value) =>
        value == null || value.trim().isEmpty ? '$label is required.' : null,
  );

  TextFormField _optionalField(
    TextEditingController controller,
    String label,
  ) => TextFormField(
    controller: controller,
    decoration: InputDecoration(
      labelText: label,
      border: const OutlineInputBorder(),
    ),
  );

  Future<void> _selectFile() async {
    try {
      final file = widget.pickFile == null
          ? await _pickProviderFile(widget.provider)
          : await widget.pickFile!(widget.provider);
      if (file == null || !mounted) return;
      if (file.bytes == null) {
        setState(() => _fileError = 'The selected file could not be read.');
        return;
      }
      final extension = widget.provider == CloudProvider.aws ? '.csv' : '.json';
      if (!file.name.toLowerCase().endsWith(extension)) {
        setState(() {
          _filename = null;
          _bytes = null;
          _fileError = '${widget.provider.label} requires a $extension file.';
        });
        return;
      }
      setState(() {
        _filename = file.name;
        _bytes = Uint8List.fromList(file.bytes!);
        _fileError = null;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _filename = null;
        _bytes = null;
        _fileError = ApiErrorHandler.extractMessage(error);
      });
    }
  }

  void _submit() {
    if (_formKey.currentState?.validate() != true) return;
    if (_filename == null || _bytes == null) {
      setState(() => _fileError = 'Select a provider credential file.');
      return;
    }
    try {
      final request = CloudConnectionImportRequest(
        provider: widget.provider,
        displayName: _displayName.text,
        region: _region.text,
        targetScopeId: widget.provider == CloudProvider.aws
            ? null
            : _targetScopeId.text,
        accountId: _optional(_accountId.text),
        ssoRegion: _optional(_ssoRegion.text),
        regionIotHub: _optional(_regionIotHub.text),
        regionDigitalTwin: _optional(_regionDigitalTwin.text),
        preparationClientId: _optional(_preparationClientId.text),
        preparationClientSecret: _optional(_preparationClientSecret.text),
        filename: _filename!,
        bytes: _bytes!,
      );
      _bytes = null;
      _preparationClientSecret.clear();
      Navigator.of(context).pop(request);
    } catch (error) {
      setState(() => _fileError = ApiErrorHandler.extractMessage(error));
    }
  }
}

Future<PlatformFile?> _pickProviderFile(CloudProvider provider) async {
  final extension = provider == CloudProvider.aws ? 'csv' : 'json';
  final result = await FilePicker.pickFiles(
    type: FileType.custom,
    allowedExtensions: [extension],
    withData: true,
  );
  return result == null || result.files.isEmpty ? null : result.files.single;
}

String _defaultRegion(CloudProvider provider) => switch (provider) {
  CloudProvider.aws => 'eu-central-1',
  CloudProvider.azure => 'westeurope',
  CloudProvider.gcp => 'europe-west1',
};

String? _optional(String value) {
  final normalized = value.trim();
  return normalized.isEmpty ? null : normalized;
}
