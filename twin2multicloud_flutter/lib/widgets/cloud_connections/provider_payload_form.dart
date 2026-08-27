import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../theme/spacing.dart';
import '../../utils/file_reader.dart';

class ProviderPayloadForm extends StatefulWidget {
  final CloudProvider provider;
  final void Function(Map<String, dynamic> credentials)? onChanged;
  final List<ProviderPayloadField>? fields;

  const ProviderPayloadForm({
    super.key,
    required this.provider,
    this.onChanged,
    this.fields,
  });

  @override
  State<ProviderPayloadForm> createState() => ProviderPayloadFormState();
}

class ProviderPayloadFormState extends State<ProviderPayloadForm> {
  final _controllers = <String, TextEditingController>{};
  String? _gcpFileName;
  String? _gcpServiceAccountJson;
  String? _gcpProjectId;

  @override
  void initState() {
    super.initState();
    for (final field in _fields) {
      _controllers[field.name] = TextEditingController(text: field.initial);
    }
  }

  @override
  void dispose() {
    for (final controller in _controllers.values) {
      controller.clear();
      controller.dispose();
    }
    super.dispose();
  }

  bool validate() {
    final valid = _fields.every(
      (field) =>
          _validationMessage(
            field,
            _controllers[field.name]?.text.trim() ?? '',
          ) ==
          null,
    );
    if (widget.provider == CloudProvider.gcp &&
        widget.fields == null &&
        (_gcpServiceAccountJson == null || _gcpServiceAccountJson!.isEmpty)) {
      return false;
    }
    return valid;
  }

  Map<String, dynamic> credentials() {
    final values = <String, dynamic>{};
    for (final entry in _controllers.entries) {
      final value = entry.value.text.trim();
      if (value.isNotEmpty) {
        values[entry.key] = value;
      }
    }
    if (widget.provider == CloudProvider.gcp && widget.fields == null) {
      values['service_account_json'] = _gcpServiceAccountJson;
      values['project_id'] = values['project_id'] ?? _gcpProjectId;
    }
    return values;
  }

  Map<String, dynamic> takeCredentials() {
    final values = credentials();
    clear();
    return values;
  }

  void clear() {
    for (final controller in _controllers.values) {
      controller.clear();
    }
    _gcpFileName = null;
    _gcpServiceAccountJson = null;
    _gcpProjectId = null;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final field in _fields) ...[
          TextFormField(
            controller: _controllers[field.name],
            obscureText: field.secret,
            minLines: field.json && !field.secret ? 5 : 1,
            maxLines: field.json && !field.secret ? 10 : 1,
            autocorrect: false,
            enableSuggestions: false,
            decoration: InputDecoration(
              labelText: field.label,
              border: const OutlineInputBorder(),
            ),
            validator: (value) =>
                _validationMessage(field, value?.trim() ?? ''),
            onChanged: widget.onChanged == null
                ? null
                : (_) => widget.onChanged!(credentials()),
          ),
          const SizedBox(height: AppSpacing.md),
        ],
        if (widget.provider == CloudProvider.gcp && widget.fields == null) ...[
          OutlinedButton.icon(
            icon: const Icon(Icons.upload_file),
            label: Text(_gcpFileName ?? 'Upload service account JSON'),
            onPressed: _pickGcpJson,
          ),
          if (_gcpProjectId != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Project ID: $_gcpProjectId',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ],
    );
  }

  Future<void> _pickGcpJson() async {
    final result = await FilePicker.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['json'],
      withData: true,
    );
    if (result == null || result.files.isEmpty) {
      return;
    }

    final file = result.files.single;
    final content = await readPickedFile(file);
    String? projectId;
    try {
      final decoded = jsonDecode(content);
      if (decoded is Map && decoded['project_id'] != null) {
        projectId = decoded['project_id'].toString();
      }
    } catch (_) {
      projectId = null;
    }

    setState(() {
      _gcpFileName = file.name;
      _gcpServiceAccountJson = content;
      _gcpProjectId = projectId;
    });
    widget.onChanged?.call(credentials());
  }

  String? _validationMessage(ProviderPayloadField field, String value) {
    if (field.required && value.isEmpty) {
      return '${field.label} is required.';
    }
    if (value.isEmpty) return null;
    if (field.minimumLength != null && value.length < field.minimumLength!) {
      return '${field.label} is too short.';
    }
    if (field.json) {
      try {
        final decoded = jsonDecode(value);
        if (decoded is! Map<String, dynamic>) {
          return 'Enter a JSON object.';
        }
        const requiredServiceAccountFields = {
          'type',
          'project_id',
          'private_key_id',
          'private_key',
          'client_email',
          'client_id',
        };
        if (requiredServiceAccountFields
                .difference(decoded.keys.toSet())
                .isNotEmpty ||
            decoded['type'] != 'service_account') {
          return 'Enter a complete service-account JSON document.';
        }
      } catch (_) {
        return 'Enter valid service-account JSON.';
      }
    }
    return null;
  }

  List<ProviderPayloadField> get _fields {
    final configured = widget.fields;
    if (configured != null) return configured;
    return switch (widget.provider) {
      CloudProvider.aws => const [
        ProviderPayloadField('access_key_id', 'Access Key ID'),
        ProviderPayloadField(
          'secret_access_key',
          'Secret Access Key',
          secret: true,
        ),
        ProviderPayloadField('region', 'Region', initial: 'eu-central-1'),
        ProviderPayloadField('sso_region', 'SSO Region', required: false),
        ProviderPayloadField(
          'session_token',
          'Session Token',
          required: false,
          secret: true,
        ),
      ],
      CloudProvider.azure => const [
        ProviderPayloadField('subscription_id', 'Subscription ID'),
        ProviderPayloadField('client_id', 'Client ID'),
        ProviderPayloadField('client_secret', 'Client Secret', secret: true),
        ProviderPayloadField('tenant_id', 'Tenant ID'),
        ProviderPayloadField('region', 'Region', initial: 'westeurope'),
        ProviderPayloadField(
          'region_iothub',
          'IoT Hub Region',
          required: false,
        ),
        ProviderPayloadField(
          'region_digital_twin',
          'Digital Twin Region',
          required: false,
        ),
      ],
      CloudProvider.gcp => const [
        ProviderPayloadField('project_id', 'Existing project ID'),
        ProviderPayloadField('region', 'Region', initial: 'europe-west1'),
      ],
    };
  }
}

class ProviderPayloadField {
  final String name;
  final String label;
  final bool required;
  final bool secret;
  final bool json;
  final int? minimumLength;
  final String? initial;

  const ProviderPayloadField(
    this.name,
    this.label, {
    this.required = true,
    this.secret = false,
    this.json = false,
    this.minimumLength,
    this.initial,
  });
}
