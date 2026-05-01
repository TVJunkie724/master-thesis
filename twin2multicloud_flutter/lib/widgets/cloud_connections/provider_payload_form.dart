import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../models/cloud_connection.dart';
import '../../theme/spacing.dart';
import '../../utils/file_reader.dart';

class ProviderPayloadForm extends StatefulWidget {
  final CloudProvider provider;
  final void Function(Map<String, dynamic> credentials) onChanged;

  const ProviderPayloadForm({
    super.key,
    required this.provider,
    required this.onChanged,
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
    var valid = true;
    for (final field in _fields.where((field) => field.required)) {
      final value = _controllers[field.name]?.text.trim() ?? '';
      if (value.isEmpty) {
        valid = false;
      }
    }
    if (widget.provider == CloudProvider.gcp &&
        (_gcpServiceAccountJson == null || _gcpServiceAccountJson!.isEmpty)) {
      valid = false;
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
    if (widget.provider == CloudProvider.gcp) {
      values['service_account_json'] = _gcpServiceAccountJson;
      values['project_id'] = values['project_id'] ?? _gcpProjectId;
    }
    return values;
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
            decoration: InputDecoration(
              labelText: field.label,
              border: const OutlineInputBorder(),
            ),
            onChanged: (_) => widget.onChanged(credentials()),
          ),
          const SizedBox(height: AppSpacing.md),
        ],
        if (widget.provider == CloudProvider.gcp) ...[
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
    widget.onChanged(credentials());
  }

  List<_PayloadField> get _fields {
    return switch (widget.provider) {
      CloudProvider.aws => const [
        _PayloadField('access_key_id', 'Access Key ID'),
        _PayloadField('secret_access_key', 'Secret Access Key', secret: true),
        _PayloadField('region', 'Region', initial: 'eu-central-1'),
        _PayloadField('sso_region', 'SSO Region', required: false),
        _PayloadField(
          'session_token',
          'Session Token',
          required: false,
          secret: true,
        ),
      ],
      CloudProvider.azure => const [
        _PayloadField('subscription_id', 'Subscription ID'),
        _PayloadField('client_id', 'Client ID'),
        _PayloadField('client_secret', 'Client Secret', secret: true),
        _PayloadField('tenant_id', 'Tenant ID'),
        _PayloadField('region', 'Region', initial: 'westeurope'),
        _PayloadField('region_iothub', 'IoT Hub Region', required: false),
        _PayloadField(
          'region_digital_twin',
          'Digital Twin Region',
          required: false,
        ),
      ],
      CloudProvider.gcp => const [
        _PayloadField('project_id', 'Project ID', required: false),
        _PayloadField('billing_account', 'Billing Account', required: false),
        _PayloadField('region', 'Region', initial: 'europe-west1'),
      ],
    };
  }
}

class _PayloadField {
  final String name;
  final String label;
  final bool required;
  final bool secret;
  final String? initial;

  const _PayloadField(
    this.name,
    this.label, {
    this.required = true,
    this.secret = false,
    this.initial,
  });
}
