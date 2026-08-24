import 'dart:convert';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../bloc/cloud_bootstrap/cloud_bootstrap.dart';
import '../../models/cloud_bootstrap.dart';
import '../../models/cloud_connection.dart';
import '../../theme/spacing.dart';
import 'provider_payload_form.dart';

class CloudBootstrapFlow extends StatefulWidget {
  final CloudProvider provider;
  final CloudBootstrapEntryPoint entryPoint;
  final ValueChanged<CloudBootstrapConnectionSummary> onConnectionReady;
  final VoidCallback onClosed;

  const CloudBootstrapFlow({
    super.key,
    required this.provider,
    required this.entryPoint,
    required this.onConnectionReady,
    required this.onClosed,
  });

  @override
  State<CloudBootstrapFlow> createState() => _CloudBootstrapFlowState();
}

class _CloudBootstrapFlowState extends State<CloudBootstrapFlow> {
  String? _reportedConnectionId;

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<CloudBootstrapBloc, CloudBootstrapState>(
      listenWhen: (previous, current) =>
          previous.completedConnection?.id != current.completedConnection?.id,
      listener: (context, state) {
        final connection = state.completedConnection;
        if (connection != null && connection.id != _reportedConnectionId) {
          _reportedConnectionId = connection.id;
        }
      },
      builder: (context, state) => PopScope(
        canPop: !state.commandInProgress,
        child: AlertDialog(
          title: Text('Set up ${widget.provider.label} deployment access'),
          content: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppSpacing.maxContentWidthMedium,
              maxHeight: AppSpacing.maxContentWidthMedium,
            ),
            child: SizedBox(
              width:
                  MediaQuery.sizeOf(context).width <
                      AppSpacing.maxContentWidthMedium
                  ? double.maxFinite
                  : AppSpacing.dialogContentMaxWidth,
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    _BootstrapProgress(
                      phase: state.phase,
                      provider: state.provider,
                      sessionState: state.session?.state,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    if (state.safeError != null) ...[
                      _BootstrapMessage(
                        icon: Icons.error_outline,
                        message: state.safeError!,
                        isError: true,
                      ),
                      const SizedBox(height: AppSpacing.md),
                    ],
                    if (state.session?.finding != null &&
                        state.phase != CloudBootstrapPhase.result) ...[
                      _BootstrapFindingMessage(
                        finding: state.session!.finding!,
                      ),
                      const SizedBox(height: AppSpacing.md),
                    ],
                    _body(context, state),
                  ],
                ),
              ),
            ),
          ),
          actions: _actions(context, state),
        ),
      ),
    );
  }

  Widget _body(BuildContext context, CloudBootstrapState state) {
    return switch (state.phase) {
      CloudBootstrapPhase.idle || CloudBootstrapPhase.loading => const Center(
        child: Padding(
          padding: EdgeInsets.all(AppSpacing.xl),
          child: CircularProgressIndicator(),
        ),
      ),
      CloudBootstrapPhase.target => _BootstrapTargetForm(
        provider: widget.provider,
        initialTarget: state.target,
        onSubmitted: (target) => context.read<CloudBootstrapBloc>().add(
          CloudBootstrapGuideRequested(target),
        ),
      ),
      CloudBootstrapPhase.guide => _BootstrapGuideStep(guide: state.guide!),
      CloudBootstrapPhase.authority => _BootstrapAuthorityForm(
        key: ValueKey('${state.session?.id}:${state.session?.revision}'),
        guide: state.guide!,
        session: state.session!,
        onSubmitted: (request) => context.read<CloudBootstrapBloc>().add(
          CloudBootstrapExecuteSubmitted(request),
        ),
      ),
      CloudBootstrapPhase.command => const _BootstrapMessage(
        icon: Icons.hourglass_top,
        message:
            'The request is running. Administrator authority remains request-only and is not shown again.',
      ),
      CloudBootstrapPhase.result => _BootstrapResultStep(
        session: state.session,
        requiresRecheck: state.requiresRecheck,
      ),
    };
  }

  List<Widget> _actions(BuildContext context, CloudBootstrapState state) {
    final bloc = context.read<CloudBootstrapBloc>();
    final session = state.session;
    return [
      if (!state.commandInProgress)
        TextButton(
          onPressed: () {
            bloc.add(const CloudBootstrapClosed());
            widget.onClosed();
          },
          child: const Text('Close'),
        ),
      if (state.phase == CloudBootstrapPhase.guide)
        FilledButton(
          onPressed:
              state.guide != null &&
                  state.guide!.executionMode !=
                      CloudBootstrapExecutionMode.disabled &&
                  !state.guide!.knownBlockers.any((item) => item.blocking)
              ? () => bloc.add(
                  CloudBootstrapSessionStarted(
                    'twin2mc-${widget.provider.apiValue}-deployer',
                  ),
                )
              : null,
          child: const Text('I completed these steps'),
        ),
      if (state.phase == CloudBootstrapPhase.loading &&
          state.safeError != null &&
          state.target != null)
        FilledButton.icon(
          onPressed: () =>
              bloc.add(CloudBootstrapGuideRequested(state.target!)),
          icon: const Icon(Icons.refresh),
          label: const Text('Retry guide'),
        ),
      if (state.requiresRecheck && session != null)
        FilledButton.icon(
          onPressed: state.commandInProgress
              ? null
              : () => bloc.add(const CloudBootstrapSessionRechecked()),
          icon: const Icon(Icons.refresh),
          label: const Text('Check stored result'),
        ),
      if (session?.commandPermissions.contains('cancel') == true)
        OutlinedButton(
          onPressed: state.commandInProgress
              ? null
              : () => bloc.add(const CloudBootstrapCancelled()),
          child: const Text('Cancel setup'),
        ),
      if (session?.commandPermissions.contains(
            'acknowledge_manual_revocation',
          ) ==
          true)
        FilledButton(
          onPressed: state.commandInProgress
              ? null
              : () => bloc.add(
                  const CloudBootstrapManualRevocationAcknowledged(),
                ),
          child: const Text('I revoked the temporary credential'),
        ),
      if (session?.commandPermissions.contains('start_new') == true)
        FilledButton(
          onPressed: state.commandInProgress
              ? null
              : () => bloc.add(const CloudBootstrapStartNewRequested()),
          child: const Text('Start new setup'),
        ),
      if (state.completedConnection != null)
        FilledButton(
          onPressed: () => widget.onConnectionReady(state.completedConnection!),
          child: const Text('Use bounded access'),
        ),
    ];
  }
}

class _BootstrapProgress extends StatelessWidget {
  final CloudBootstrapPhase phase;
  final CloudProvider provider;
  final CloudBootstrapSessionState? sessionState;

  const _BootstrapProgress({
    required this.phase,
    required this.provider,
    required this.sessionState,
  });

  @override
  Widget build(BuildContext context) {
    final step = switch (phase) {
      CloudBootstrapPhase.idle ||
      CloudBootstrapPhase.loading ||
      CloudBootstrapPhase.target => 1,
      CloudBootstrapPhase.guide => 2,
      CloudBootstrapPhase.authority || CloudBootstrapPhase.command => 3,
      CloudBootstrapPhase.result => 4,
    };
    return Semantics(
      liveRegion: true,
      label:
          '${provider.label} cloud access setup step $step of 4${sessionState == null ? '' : ', ${sessionState!.name}'}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Step $step of 4',
            style: Theme.of(context).textTheme.labelLarge,
          ),
          const SizedBox(height: AppSpacing.sm),
          LinearProgressIndicator(value: step / 4),
        ],
      ),
    );
  }
}

class _BootstrapTargetForm extends StatefulWidget {
  final CloudProvider provider;
  final CloudBootstrapTarget? initialTarget;
  final ValueChanged<CloudBootstrapTarget> onSubmitted;

  const _BootstrapTargetForm({
    required this.provider,
    this.initialTarget,
    required this.onSubmitted,
  });

  @override
  State<_BootstrapTargetForm> createState() => _BootstrapTargetFormState();
}

class _BootstrapTargetFormState extends State<_BootstrapTargetForm> {
  final _formKey = GlobalKey<FormState>();
  final _values = <String, TextEditingController>{};

  @override
  void initState() {
    super.initState();
    final defaults = switch (widget.provider) {
      CloudProvider.aws => {
        'account_id': '',
        'region': 'eu-central-1',
        'session_expires_at': '',
      },
      CloudProvider.azure => {
        'tenant_id': '',
        'subscription_id': '',
        'region': 'westeurope',
        'bootstrap_credential_key_id': '',
      },
      CloudProvider.gcp => {'project_id': '', 'region': 'europe-west1'},
    };
    for (final entry in defaults.entries) {
      final initial = widget.initialTarget?.values[entry.key]?.toString();
      _values[entry.key] = TextEditingController(text: initial ?? entry.value);
    }
  }

  @override
  void dispose() {
    for (final controller in _values.values) {
      controller.clear();
      controller.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Cloud target', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: AppSpacing.sm),
          const Text(
            'Choose the existing billable account, subscription, or project. This does not create a commercial cloud account.',
          ),
          const SizedBox(height: AppSpacing.md),
          if (widget.provider == CloudProvider.gcp) ...[
            const _BootstrapMessage(
              icon: Icons.account_tree_outlined,
              message:
                  'GCP setup currently supports one existing billing-enabled project. Organization/project creation remains outside the first supervised PoC gate.',
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          for (final field in _visibleFields) ...[
            TextFormField(
              controller: _values[field.$1],
              decoration: InputDecoration(
                labelText: field.$2,
                border: const OutlineInputBorder(),
              ),
              validator: (value) {
                final normalized = value?.trim() ?? '';
                if (field.$3 && normalized.isEmpty) {
                  return '${field.$2} is required.';
                }
                if (normalized.isEmpty) return null;
                if (field.$1 == 'account_id' &&
                    !RegExp(r'^\d{12}$').hasMatch(normalized)) {
                  return 'Enter the twelve-digit AWS account ID.';
                }
                if (field.$1 == 'session_expires_at') {
                  final expiry = DateTime.tryParse(normalized);
                  if (expiry == null ||
                      !expiry.toUtc().isAfter(DateTime.now().toUtc())) {
                    return 'Enter a future ISO-8601 expiry.';
                  }
                }
                if (field.$1 == 'project_id' &&
                    !RegExp(
                      r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$',
                    ).hasMatch(normalized)) {
                  return 'Enter a valid GCP project ID.';
                }
                return null;
              },
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          FilledButton(
            onPressed: _submit,
            child: const Text('Load provider guide'),
          ),
        ],
      ),
    );
  }

  List<(String, String, bool)> get _visibleFields => switch (widget.provider) {
    CloudProvider.aws => const [
      ('account_id', 'AWS account ID', true),
      ('region', 'Region', true),
      ('session_expires_at', 'STS session expiry (ISO 8601, optional)', false),
    ],
    CloudProvider.azure => const [
      ('tenant_id', 'Tenant ID', true),
      ('subscription_id', 'Subscription ID', true),
      ('region', 'Region', true),
      (
        'bootstrap_credential_key_id',
        'Temporary credential key ID (for automatic cleanup)',
        false,
      ),
    ],
    CloudProvider.gcp => const [
      ('project_id', 'Project ID', true),
      ('region', 'Region', true),
    ],
  };

  void _submit() {
    if (_formKey.currentState?.validate() != true) return;
    try {
      String value(String key) => _values[key]!.text.trim();
      final target = switch (widget.provider) {
        CloudProvider.aws => CloudBootstrapTarget.aws(
          accountId: value('account_id'),
          region: value('region'),
          sessionExpiresAt: value('session_expires_at').isEmpty
              ? null
              : DateTime.parse(value('session_expires_at')),
        ),
        CloudProvider.azure => CloudBootstrapTarget.azure(
          tenantId: value('tenant_id'),
          subscriptionId: value('subscription_id'),
          region: value('region'),
          bootstrapCredentialKeyId: value('bootstrap_credential_key_id'),
        ),
        CloudProvider.gcp => CloudBootstrapTarget.gcpExistingProject(
          projectId: value('project_id'),
          region: value('region'),
        ),
      };
      widget.onSubmitted(target);
    } on ArgumentError {
      _formKey.currentState?.validate();
    }
  }
}

class _BootstrapGuideStep extends StatelessWidget {
  final CloudBootstrapGuide guide;

  const _BootstrapGuideStep({required this.guide});

  @override
  Widget build(BuildContext context) {
    final disabled =
        guide.executionMode == CloudBootstrapExecutionMode.disabled;
    final blocked = guide.knownBlockers.any((item) => item.blocking);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _BootstrapMessage(
          icon: disabled || blocked
              ? Icons.block
              : guide.executionMode ==
                    CloudBootstrapExecutionMode.supervisedLive
              ? Icons.cloud_sync_outlined
              : Icons.science_outlined,
          message: guide.executionMode.label,
          isError: disabled || blocked,
        ),
        const SizedBox(height: AppSpacing.md),
        Text(
          'Manual prerequisites',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: AppSpacing.sm),
        for (final step in guide.preparationSteps)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    step.title,
                    style: Theme.of(context).textTheme.titleSmall,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(step.description),
                  const SizedBox(height: AppSpacing.xs),
                  Text('Expected: ${step.expectedOutcome}'),
                  TextButton.icon(
                    onPressed: () => launchUrl(
                      step.officialUrl,
                      mode: LaunchMode.externalApplication,
                    ),
                    icon: const Icon(Icons.open_in_new),
                    label: Text('Open ${guide.provider.label} instructions'),
                  ),
                ],
              ),
            ),
          ),
        const SizedBox(height: AppSpacing.sm),
        Text('Target: ${guide.target.summary}'),
        const SizedBox(height: AppSpacing.md),
        _BootstrapPackSummary(
          title: 'Temporary bootstrap authority',
          pack: guide.bootstrapAuthorityPack,
        ),
        const SizedBox(height: AppSpacing.sm),
        _BootstrapPackSummary(
          title: 'Generated deployment access',
          pack: guide.generatedDeploymentPack,
        ),
        if (guide.apiBaseline case final baseline?) ...[
          const SizedBox(height: AppSpacing.sm),
          _BootstrapApiBaselineSummary(baseline: baseline),
        ],
        if (guide.knownBlockers.isNotEmpty) ...[
          const SizedBox(height: AppSpacing.md),
          Text(
            'Known prerequisites',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          const SizedBox(height: AppSpacing.sm),
          for (final finding in guide.knownBlockers)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: _BootstrapFindingMessage(finding: finding),
            ),
        ],
      ],
    );
  }
}

class _BootstrapApiBaselineSummary extends StatelessWidget {
  final CloudBootstrapApiBaseline baseline;

  const _BootstrapApiBaselineSummary({required this.baseline});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ExpansionTile(
        key: const ValueKey('gcp-phase8-api-baseline'),
        leading: const Icon(Icons.api_outlined),
        title: const Text('Phase 8 API setup'),
        subtitle: Text(
          '${baseline.services.length} reviewed APIs · enabled once and retained',
        ),
        childrenPadding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          0,
          AppSpacing.md,
          AppSpacing.md,
        ),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(baseline.mutationSummary),
          const SizedBox(height: AppSpacing.sm),
          for (final service in baseline.services) Text('• $service'),
          const SizedBox(height: AppSpacing.sm),
          for (final limitation in baseline.limitations)
            Text('Limit: $limitation'),
          TextButton.icon(
            onPressed: () => launchUrl(
              baseline.artifactUrl,
              mode: LaunchMode.externalApplication,
            ),
            icon: const Icon(Icons.open_in_new),
            label: const Text('Open reviewed API baseline'),
          ),
        ],
      ),
    );
  }
}

class _BootstrapPackSummary extends StatelessWidget {
  final String title;
  final CloudBootstrapPackReference pack;

  const _BootstrapPackSummary({required this.title, required this.pack});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      container: true,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.labelLarge),
          Text('${pack.id} · ${pack.version}'),
          if (pack.scopeSummary != null) Text(pack.scopeSummary!),
          for (final limitation in pack.limitations) Text('Limit: $limitation'),
          if (pack.artifactUrl != null)
            TextButton.icon(
              onPressed: () => launchUrl(
                pack.artifactUrl!,
                mode: LaunchMode.externalApplication,
              ),
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open reviewed permission artifact'),
            ),
        ],
      ),
    );
  }
}

class _BootstrapFindingMessage extends StatelessWidget {
  final CloudBootstrapFinding finding;

  const _BootstrapFindingMessage({required this.finding});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _BootstrapMessage(
          icon: Icons.warning_amber,
          message: '${finding.title}\n${finding.message}\n${finding.action}',
          isError: finding.blocking,
        ),
        if (finding.remediationUrl != null)
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: () => launchUrl(
                finding.remediationUrl!,
                mode: LaunchMode.externalApplication,
              ),
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open remediation instructions'),
            ),
          ),
      ],
    );
  }
}

class _BootstrapAuthorityForm extends StatefulWidget {
  final CloudBootstrapGuide guide;
  final CloudBootstrapSession session;
  final ValueChanged<CloudBootstrapExecuteRequest> onSubmitted;

  const _BootstrapAuthorityForm({
    super.key,
    required this.guide,
    required this.session,
    required this.onSubmitted,
  });

  @override
  State<_BootstrapAuthorityForm> createState() =>
      _BootstrapAuthorityFormState();
}

class _BootstrapAuthorityFormState extends State<_BootstrapAuthorityForm> {
  final _formKey = GlobalKey<FormState>();
  final _payloadKey = GlobalKey<ProviderPayloadFormState>();
  CloudBootstrapCredentialOrigin _origin =
      CloudBootstrapCredentialOrigin.dedicatedDisposable;

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            'Administrator/bootstrap authority',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.sm),
          const Text(
            'Used for this request only. Values cannot be restored after submission.',
          ),
          const SizedBox(height: AppSpacing.md),
          ProviderPayloadForm(
            key: _payloadKey,
            provider: widget.guide.provider,
            fields: widget.guide.credentialFields
                .map(
                  (field) => ProviderPayloadField(
                    field.id,
                    field.label,
                    required: field.required,
                    secret:
                        field.inputType == 'secret' ||
                        field.inputType == 'json',
                    json: field.inputType == 'json',
                    minimumLength: _minimumLength(field.id),
                  ),
                )
                .toList(growable: false),
          ),
          RadioGroup<CloudBootstrapCredentialOrigin>(
            groupValue: _origin,
            onChanged: (value) => setState(() {
              if (value != null) _origin = value;
            }),
            child: const Column(
              children: [
                RadioListTile(
                  value: CloudBootstrapCredentialOrigin.dedicatedDisposable,
                  title: Text('Dedicated temporary credential'),
                  subtitle: Text('Delete or revoke it after bootstrap.'),
                ),
                RadioListTile(
                  value: CloudBootstrapCredentialOrigin.existingUserOwned,
                  title: Text('Existing user-owned credential'),
                  subtitle: Text('The application will not revoke it.'),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          FilledButton.icon(
            onPressed: _submit,
            icon: const Icon(Icons.lock_outline),
            label: const Text('Create bounded access'),
          ),
        ],
      ),
    );
  }

  void _submit() {
    if (_formKey.currentState?.validate() != true ||
        _payloadKey.currentState?.validate() != true) {
      return;
    }
    final values = _payloadKey.currentState!.takeCredentials();
    Map<String, dynamic>? credential;
    try {
      credential = switch (widget.guide.provider) {
        CloudProvider.aws => {'provider': 'aws', ...values},
        CloudProvider.azure => {'provider': 'azure', ...values},
        CloudProvider.gcp => {
          ...Map<String, dynamic>.from(
            jsonDecode(values['service_account_json']!.toString()) as Map,
          ),
          'provider': 'gcp',
        },
      };
      final request = CloudBootstrapExecuteRequest(
        expectedRevision: widget.session.revision,
        idempotencyKey: _idempotencyKey(),
        credentialOrigin: _origin,
        credential: credential,
      );
      credential = null;
      values.clear();
      widget.onSubmitted(request);
    } finally {
      values.clear();
      credential?.clear();
    }
  }

  int? _minimumLength(String fieldId) => switch (fieldId) {
    'access_key_id' || 'secret_access_key' || 'session_token' => 16,
    'client_secret' => 8,
    _ => null,
  };

  String _idempotencyKey() {
    final random = Random.secure();
    final suffix = List.generate(
      24,
      (_) => random.nextInt(16).toRadixString(16),
    ).join();
    return 'execute-${DateTime.now().microsecondsSinceEpoch}-$suffix';
  }
}

class _BootstrapResultStep extends StatelessWidget {
  final CloudBootstrapSession? session;
  final bool requiresRecheck;

  const _BootstrapResultStep({
    required this.session,
    required this.requiresRecheck,
  });

  @override
  Widget build(BuildContext context) {
    final current = session;
    if (current == null) {
      return const _BootstrapMessage(
        icon: Icons.help_outline,
        message:
            'No safe session result is available. Check the stored result.',
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (requiresRecheck)
          const _BootstrapMessage(
            icon: Icons.sync_problem,
            message:
                'The command result is uncertain. The request will not be submitted again automatically.',
          ),
        if (current.finding != null) ...[
          _BootstrapFindingMessage(finding: current.finding!),
          const SizedBox(height: AppSpacing.md),
        ],
        if (current.connection != null) ...[
          Text(
            'Bounded deployment access created',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.sm),
          Text('Identity: ${current.connection!.displayName}'),
          Text('Target: ${current.target.summary}'),
          Text('Permission pack: ${current.connection!.permissionSetVersion}'),
          Text('Validation: ${current.connection!.validationStatus}'),
          const SizedBox(height: AppSpacing.md),
        ],
        Text(
          'Bootstrap authority: ${current.disposalStatus ?? 'not retained'}',
        ),
        if (current.safeCredentialIdentifier != null)
          Text('Credential identifier: ${current.safeCredentialIdentifier}'),
        if (current.credentialExpiresAt != null)
          Text('Provider expiry: ${current.credentialExpiresAt!.toLocal()}'),
        if (current.state ==
            CloudBootstrapSessionState.manualRevocationRequired) ...[
          const SizedBox(height: AppSpacing.md),
          const _BootstrapMessage(
            icon: Icons.delete_outline,
            message:
                'Delete the displayed temporary provider credential, then acknowledge the cleanup. The application has released its local copy but does not claim provider revocation.',
          ),
        ],
      ],
    );
  }
}

class _BootstrapMessage extends StatelessWidget {
  final IconData icon;
  final String message;
  final bool isError;

  const _BootstrapMessage({
    required this.icon,
    required this.message,
    this.isError = false,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      color: isError ? scheme.errorContainer : scheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: isError ? scheme.onErrorContainer : null),
            const SizedBox(width: AppSpacing.sm),
            Expanded(
              child: Text(
                message,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: isError ? scheme.onErrorContainer : null,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
