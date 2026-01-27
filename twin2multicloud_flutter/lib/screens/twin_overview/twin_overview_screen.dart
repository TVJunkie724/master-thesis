// lib/screens/twin_overview/twin_overview_screen.dart
// Overview page for configured Digital Twins (Phase 2 implementation)

import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../bloc/twin_overview/twin_overview_bloc.dart';
import '../../bloc/twin_overview/twin_overview_event.dart';
import '../../bloc/twin_overview/twin_overview_state.dart';
import '../../providers/twins_provider.dart';
import '../../providers/theme_provider.dart';
import '../../utils/twin_state_utils.dart';
import '../../widgets/branded_app_bar.dart';
import '../../widgets/code_viewer_dialog.dart';
import '../../widgets/deployment_terminal.dart';
import '../../widgets/terraform_outputs_card.dart';
import '../../widgets/results/cheapest_path_visualization.dart';

/// Twin Overview Screen - Entry point with BlocProvider
class TwinOverviewScreen extends ConsumerWidget {
  final String twinId;

  const TwinOverviewScreen({super.key, required this.twinId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.read(apiServiceProvider);

    return BlocProvider(
      create: (context) =>
          TwinOverviewBloc(api: api)..add(TwinOverviewLoad(twinId)),
      child: TwinOverviewView(twinId: twinId),
    );
  }
}

/// Main view consuming BLoC state
class TwinOverviewView extends ConsumerWidget {
  final String twinId;

  const TwinOverviewView({super.key, required this.twinId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return BlocListener<TwinOverviewBloc, TwinOverviewState>(
      listenWhen: (prev, curr) =>
          curr is TwinOverviewLoaded && curr.successMessage == 'deleted',
      listener: (context, state) {
        // Navigate back to dashboard after successful delete
        context.go('/dashboard');
      },
      child: BlocBuilder<TwinOverviewBloc, TwinOverviewState>(
        builder: (context, state) {
          return Scaffold(
            appBar: _buildAppBar(context, ref),
            body: Column(
              children: [
                // Header section with back button and twin name
                _buildHeader(context, state),
                // Alert banners for messages
                _buildAlertBanners(context, state),
                // Main content
                Expanded(child: _buildBody(context, state)),
              ],
            ),
          );
        },
      ),
    );
  }

  PreferredSizeWidget _buildAppBar(BuildContext context, WidgetRef ref) {
    return BrandedAppBar(
      title: 'Twin2MultiCloud',
      actions: [
        IconButton(
          icon: Icon(
            ref.watch(themeProvider) == ThemeMode.dark
                ? Icons.light_mode
                : Icons.dark_mode,
          ),
          onPressed: () => ref.read(themeProvider.notifier).toggle(),
          tooltip: 'Toggle theme',
        ),
        const SizedBox(width: 8),
      ],
    );
  }

  Widget _buildHeader(BuildContext context, TwinOverviewState state) {
    final projectName = state is TwinOverviewLoaded
        ? state.projectName
        : 'Loading...';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
      decoration: BoxDecoration(
        color: Theme.of(
          context,
        ).colorScheme.surfaceContainerHighest.withOpacity(0.3),
        border: Border(
          bottom: BorderSide(
            color: Theme.of(context).dividerColor.withOpacity(0.5),
          ),
        ),
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1200),
          child: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: () => context.go('/dashboard'),
                tooltip: 'Back to Dashboard',
              ),
              const SizedBox(width: 8),
              Text(
                projectName,
                style: Theme.of(context).textTheme.headlineSmall,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAlertBanners(BuildContext context, TwinOverviewState state) {
    if (state is! TwinOverviewLoaded) return const SizedBox.shrink();

    if (state.errorMessage != null) {
      return _buildBanner(
        context,
        message: state.errorMessage!,
        color: Colors.red,
        icon: Icons.error,
        onDismiss: () => context.read<TwinOverviewBloc>().add(
          const TwinOverviewClearMessages(),
        ),
      );
    } else if (state.successMessage != null &&
        state.successMessage != 'deleted') {
      return _buildBanner(
        context,
        message: state.successMessage!,
        color: Colors.green,
        icon: Icons.check_circle,
        onDismiss: () => context.read<TwinOverviewBloc>().add(
          const TwinOverviewClearMessages(),
        ),
      );
    } else if (state.infoMessage != null) {
      return _buildBanner(
        context,
        message: state.infoMessage!,
        color: Colors.blue,
        icon: Icons.info,
        onDismiss: () => context.read<TwinOverviewBloc>().add(
          const TwinOverviewClearMessages(),
        ),
      );
    }
    return const SizedBox.shrink();
  }

  Widget _buildBanner(
    BuildContext context, {
    required String message,
    required MaterialColor color,
    required IconData icon,
    required VoidCallback onDismiss,
  }) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
      decoration: BoxDecoration(
        color: color.shade50,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.08),
            blurRadius: 6,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1200),
          child: Row(
            children: [
              Icon(icon, color: color.shade700),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  message,
                  style: TextStyle(
                    color: color.shade700,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
              IconButton(
                icon: Icon(Icons.close, color: color.shade700, size: 20),
                onPressed: onDismiss,
                tooltip: 'Dismiss',
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBody(BuildContext context, TwinOverviewState state) {
    if (state is TwinOverviewLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Loading twin configuration...'),
          ],
        ),
      );
    }

    if (state is TwinOverviewError) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.error_outline, size: 64, color: Colors.red[400]),
            const SizedBox(height: 16),
            Text(
              'Failed to load twin',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              state.message,
              textAlign: TextAlign.center,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(color: Colors.grey[600]),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () => context.read<TwinOverviewBloc>().add(
                TwinOverviewLoad(twinId),
              ),
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      );
    }

    if (state is TwinOverviewLoaded) {
      return _buildLoadedContent(context, state);
    }

    // Initial state
    return const Center(child: CircularProgressIndicator());
  }

  Widget _buildLoadedContent(BuildContext context, TwinOverviewLoaded state) {
    final theme = Theme.of(context);

    return SingleChildScrollView(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1200),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Dual Name Header
                _buildDualNameHeader(context, state),
                const SizedBox(height: 24),

                // Command Center (always visible)
                _buildCommandCenter(context, state),
                const SizedBox(height: 32),

                // Configuration Review sections
                Text(
                  'CONFIGURATION REVIEW',
                  style: theme.textTheme.labelLarge?.copyWith(
                    color: Colors.grey[600],
                    letterSpacing: 1.2,
                  ),
                ),
                const Divider(),
                const SizedBox(height: 16),

                // Provider Architecture (expanded by default)
                _buildProviderArchitectureSection(context, state),
                const SizedBox(height: 16),

                // Optimization Summary with calculation date
                _buildOptimizationSummarySection(context, state),
                const SizedBox(height: 16),

                // Pricing Data with fetch timestamps
                _buildPricingDataSection(context, state),
                const SizedBox(height: 16),

                // Configuration Files (collapsed by default)
                _buildConfigurationFilesSection(context, state),
                const SizedBox(height: 16),

                // User Functions (collapsed by default)
                _buildUserFunctionsSection(context, state),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildProviderArchitectureSection(
    BuildContext context,
    TwinOverviewLoaded state,
  ) {
    final result = state.optimizerResult;

    // Extract cheapest path from optimizer result (camelCase key, List format)
    List<String> cheapestPath = [];
    if (result != null && result['cheapestPath'] != null) {
      cheapestPath = List<String>.from(result['cheapestPath'] as List);
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.architecture),
                const SizedBox(width: 12),
                Text(
                  'Provider Architecture',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Center(child: CheapestPathVisualization(path: cheapestPath)),
          ],
        ),
      ),
    );
  }

  Widget _buildOptimizationSummarySection(
    BuildContext context,
    TwinOverviewLoaded state,
  ) {
    final theme = Theme.of(context);
    final result = state.optimizerResult;
    final params = state.optimizerParams;

    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.analytics),
        title: const Text('Optimization Summary'),
        initiallyExpanded: true,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: result == null
                ? Text(
                    'No optimization result available',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: Colors.grey[600],
                    ),
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Cost estimate
                      Row(
                        children: [
                          Icon(Icons.attach_money, color: Colors.green[700]),
                          const SizedBox(width: 8),
                          Text(
                            'Estimated Cost: ',
                            style: theme.textTheme.titleMedium,
                          ),
                          Text(
                            '\$${(result['totalCost'] ?? 0).toStringAsFixed(2)}/month',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.bold,
                              color: Colors.green[700],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Calculation parameters
                      if (params != null) ...[
                        _buildParamRow(
                          'Devices',
                          '${params['numberOfDevices'] ?? 'N/A'}',
                        ),
                        _buildParamRow(
                          'Messages/hour',
                          _formatMessagesPerHour(params),
                        ),
                        _buildParamRow('Retention', _formatRetention(params)),
                        const SizedBox(height: 12),
                      ],

                      // Calculation date
                      if (state.calculatedAt != null)
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.blue[50],
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.schedule,
                                size: 16,
                                color: Colors.blue[700],
                              ),
                              const SizedBox(width: 8),
                              Text(
                                'Calculated: ${_formatTimestamp(state.calculatedAt!)}',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.blue[700],
                                ),
                              ),
                            ],
                          ),
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildParamRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: [
          Text('$label: ', style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  /// Calculate messages per hour from device sending interval
  String _formatMessagesPerHour(Map<String, dynamic> params) {
    final interval = params['deviceSendingIntervalInMinutes'];
    if (interval == null) return 'N/A';
    final messagesPerHour = 60.0 / (interval as num);
    return messagesPerHour.toStringAsFixed(1);
  }

  /// Format retention from storage durations
  String _formatRetention(Map<String, dynamic> params) {
    final hot = params['hotStorageDurationInMonths'] as num? ?? 0;
    final cool = params['coolStorageDurationInMonths'] as num? ?? 0;
    final archive = params['archiveStorageDurationInMonths'] as num? ?? 0;
    final totalMonths = hot + cool + archive;
    if (totalMonths == 0) return 'N/A';
    return '${totalMonths.toStringAsFixed(0)} months';
  }

  Widget _buildPricingDataSection(
    BuildContext context,
    TwinOverviewLoaded state,
  ) {
    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.attach_money),
        title: const Text('Pricing Data'),
        initiallyExpanded: false,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                _buildPricingRow(
                  context,
                  'AWS',
                  const Color(0xFFFF9900),
                  state.pricingAws,
                  state.pricingAwsUpdatedAt,
                ),
                const SizedBox(height: 8),
                _buildPricingRow(
                  context,
                  'Azure',
                  const Color(0xFF0078D4),
                  state.pricingAzure,
                  state.pricingAzureUpdatedAt,
                ),
                const SizedBox(height: 8),
                _buildPricingRow(
                  context,
                  'GCP',
                  const Color(0xFF34A853),
                  state.pricingGcp,
                  state.pricingGcpUpdatedAt,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPricingRow(
    BuildContext context,
    String provider,
    Color color,
    Map<String, dynamic>? pricing,
    String? updatedAt,
  ) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.grey[300]!),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Container(
            width: 4,
            height: 40,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$provider Pricing',
                  style: const TextStyle(fontWeight: FontWeight.w500),
                ),
                Text(
                  updatedAt != null
                      ? 'Fetched: ${_formatTimestamp(updatedAt)}'
                      : 'No pricing data',
                  style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                ),
              ],
            ),
          ),
          if (updatedAt != null) ...[
            IconButton(
              onPressed: pricing != null
                  ? () {
                      final content = _prettyPrintJson(pricing);
                      showCodeViewerDialog(
                        context,
                        title: '$provider Pricing',
                        code: content,
                        filename: '${provider.toLowerCase()}_pricing.json',
                      );
                    }
                  : null,
              icon: const Icon(Icons.visibility_outlined),
              tooltip: 'View',
            ),
            IconButton(
              onPressed: pricing != null
                  ? () async {
                      final content = _prettyPrintJson(pricing);
                      final result = await downloadCodeFile(
                        content: content,
                        filename: '${provider.toLowerCase()}_pricing.json',
                      );
                      if (!context.mounted) return;
                      if (result.success) {
                        context.read<TwinOverviewBloc>().add(
                          TwinOverviewShowMessage(
                            result.message!,
                            MessageType.success,
                          ),
                        );
                      } else if (!result.cancelled && result.error != null) {
                        context.read<TwinOverviewBloc>().add(
                          TwinOverviewShowMessage(
                            result.error!,
                            MessageType.error,
                          ),
                        );
                      }
                    }
                  : null,
              icon: const Icon(Icons.download_outlined),
              tooltip: 'Download',
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildConfigurationFilesSection(
    BuildContext context,
    TwinOverviewLoaded state,
  ) {
    final config = state.deployerConfig;
    // Get L2 provider for state machine naming (provider-specific files)
    final l2Provider =
        state.cheapestPath?['l2']?.toString().toLowerCase() ?? 'aws';
    final stateMachineFilename = _getStateMachineFilename(l2Provider);

    // Get L4 provider for hierarchy and scene config naming
    final l4Provider =
        state.cheapestPath?['l4']?.toString().toLowerCase() ?? 'aws';
    final hierarchyFilename = l4Provider == 'azure'
        ? 'azure_hierarchy.json'
        : 'aws_hierarchy.json';
    final sceneFilename = l4Provider == 'azure'
        ? '3DScenesConfiguration.json'
        : 'scene.json';

    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.code),
        title: const Text('Configuration Files'),
        initiallyExpanded: false,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: config == null
                ? const Text('No configuration files available')
                : Column(
                    children: [
                      if (config['config_events_json'] != null)
                        _buildConfigFileRow(
                          context,
                          'config_events.json',
                          config['config_events_json'] as String,
                        ),
                      if (config['config_iot_devices_json'] != null)
                        _buildConfigFileRow(
                          context,
                          'config_iot_devices.json',
                          config['config_iot_devices_json'] as String,
                        ),
                      if (config['payloads_json'] != null)
                        _buildConfigFileRow(
                          context,
                          'payloads.json',
                          config['payloads_json'] as String,
                        ),
                      if (config['state_machine_content'] != null)
                        _buildConfigFileRow(
                          context,
                          stateMachineFilename,
                          config['state_machine_content'] as String,
                        ),
                      // L4 configuration files (provider-specific naming)
                      if (config['hierarchy_content'] != null)
                        _buildConfigFileRow(
                          context,
                          hierarchyFilename,
                          config['hierarchy_content'] as String,
                        ),
                      if (config['scene_config_content'] != null)
                        _buildConfigFileRow(
                          context,
                          sceneFilename,
                          config['scene_config_content'] as String,
                        ),
                      // L5 user config
                      if (config['user_config_content'] != null)
                        _buildConfigFileRow(
                          context,
                          'config_user.json',
                          config['user_config_content'] as String,
                        ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildConfigFileRow(
    BuildContext context,
    String filename,
    String content,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          const Icon(Icons.insert_drive_file_outlined, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(filename)),
          IconButton(
            onPressed: () => showCodeViewerDialog(
              context,
              title: filename,
              code: content,
              filename: filename,
            ),
            icon: const Icon(Icons.visibility_outlined),
            tooltip: 'View',
          ),
          IconButton(
            onPressed: () async {
              final result = await downloadCodeFile(
                content: content,
                filename: filename,
              );
              if (!context.mounted) return;
              if (result.success) {
                context.read<TwinOverviewBloc>().add(
                  TwinOverviewShowMessage(result.message!, MessageType.success),
                );
              } else if (!result.cancelled && result.error != null) {
                context.read<TwinOverviewBloc>().add(
                  TwinOverviewShowMessage(result.error!, MessageType.error),
                );
              }
            },
            icon: const Icon(Icons.download_outlined),
            tooltip: 'Download',
          ),
        ],
      ),
    );
  }

  Widget _buildUserFunctionsSection(
    BuildContext context,
    TwinOverviewLoaded state,
  ) {
    final config = state.deployerConfig;
    // Get L2 provider for function filename
    final l2Provider =
        state.cheapestPath?['l2']?.toString().toLowerCase() ?? 'aws';

    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.functions),
        title: const Text('User Functions'),
        initiallyExpanded: false,
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: config == null
                ? const Text('No user functions available')
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Processor functions
                      if (config['processor_contents'] != null &&
                          (config['processor_contents'] as Map).isNotEmpty) ...[
                        const Text(
                          'Processors',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        ..._buildFunctionRows(
                          context,
                          config['processor_contents'] as Map<String, dynamic>,
                          'processor',
                          l2Provider,
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Event feedback
                      if (config['event_feedback_content'] != null) ...[
                        const Text(
                          'Event Feedback',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        _buildFunctionRow(
                          context,
                          'event-feedback',
                          config['event_feedback_content'] as String,
                          l2Provider,
                        ),
                        const SizedBox(height: 16),
                      ],

                      // Event actions
                      if (config['event_action_contents'] != null &&
                          (config['event_action_contents'] as Map)
                              .isNotEmpty) ...[
                        const Text(
                          'Event Actions',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 8),
                        ..._buildFunctionRows(
                          context,
                          config['event_action_contents']
                              as Map<String, dynamic>,
                          'event_action',
                          l2Provider,
                        ),
                      ],
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  List<Widget> _buildFunctionRows(
    BuildContext context,
    Map<String, dynamic> functions,
    String prefix,
    String l2Provider,
  ) {
    return functions.entries.map((entry) {
      return _buildFunctionRow(
        context,
        entry.key,
        entry.value as String,
        l2Provider,
      );
    }).toList();
  }

  /// Get function filename based on provider convention.
  /// See ZIP example: AWS=lambda_function.py, GCP=main.py, Azure=function_app.py
  String _getFunctionFilename(String provider) {
    switch (provider.toLowerCase()) {
      case 'gcp':
        return 'main.py';
      case 'azure':
        return 'function_app.py';
      case 'aws':
      default:
        return 'lambda_function.py';
    }
  }

  /// Get state machine filename based on provider convention.
  /// AWS=aws_step_function.json, Azure=azure_logic_app.json, GCP=google_cloud_workflow.yaml
  String _getStateMachineFilename(String provider) {
    switch (provider.toLowerCase()) {
      case 'gcp':
        return 'google_cloud_workflow.yaml';
      case 'azure':
        return 'azure_logic_app.json';
      case 'aws':
      default:
        return 'aws_step_function.json';
    }
  }

  Widget _buildFunctionRow(
    BuildContext context,
    String name,
    String content,
    String l2Provider,
  ) {
    final funcFile = _getFunctionFilename(l2Provider);
    final filename = '$name/$funcFile';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          const Icon(Icons.code, size: 20, color: Colors.blue),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              filename,
              style: const TextStyle(fontFamily: 'monospace'),
            ),
          ),
          IconButton(
            onPressed: () => showCodeViewerDialog(
              context,
              title: filename,
              code: content,
              filename: filename,
            ),
            icon: const Icon(Icons.visibility_outlined),
            tooltip: 'View',
          ),
          IconButton(
            onPressed: () async {
              final result = await downloadCodeFile(
                content: content,
                filename: filename,
              );
              if (!context.mounted) return;
              if (result.success) {
                context.read<TwinOverviewBloc>().add(
                  TwinOverviewShowMessage(result.message!, MessageType.success),
                );
              } else if (!result.cancelled && result.error != null) {
                context.read<TwinOverviewBloc>().add(
                  TwinOverviewShowMessage(result.error!, MessageType.error),
                );
              }
            },
            icon: const Icon(Icons.download_outlined),
            tooltip: 'Download',
          ),
        ],
      ),
    );
  }

  String _prettyPrintJson(Map<String, dynamic> json) {
    // Simple JSON formatting
    try {
      const encoder = JsonEncoder.withIndent('  ');
      return encoder.convert(json);
    } catch (e) {
      return json.toString();
    }
  }

  String _formatTimestamp(String timestamp) {
    try {
      final dt = DateTime.parse(timestamp);
      return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} '
          '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')} UTC';
    } catch (e) {
      return timestamp;
    }
  }

  Widget _buildDualNameHeader(BuildContext context, TwinOverviewLoaded state) {
    final theme = Theme.of(context);

    return Row(
      children: [
        Expanded(
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'PROJECT NAME',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: Colors.grey[600],
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    state.projectName,
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'UI identifier',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: Colors.grey[500],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'CLOUD RESOURCE NAME',
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: Colors.grey[600],
                      letterSpacing: 1,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    state.cloudResourceName ?? 'Not configured',
                    style: theme.textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.bold,
                      fontFamily: 'monospace',
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Used for cloud resources (from config.json)',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: Colors.grey[500],
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildCommandCenter(BuildContext context, TwinOverviewLoaded state) {
    final theme = Theme.of(context);

    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row with state badge and action buttons
            Row(
              children: [
                TwinStateUtils.buildBadge(context, state.twinState),
                const Spacer(),
                // Edit button
                Tooltip(
                  message: state.canEdit
                      ? 'Edit configuration'
                      : 'Destroy cloud resources before editing',
                  child: OutlinedButton.icon(
                    onPressed: state.canEdit
                        ? () => context.go('/wizard/${state.twinId}')
                        : null,
                    icon: const Icon(Icons.edit),
                    label: const Text('Edit'),
                  ),
                ),
                const SizedBox(width: 8),
                // Delete button
                Tooltip(
                  message: state.canDelete
                      ? 'Delete twin'
                      : 'Destroy cloud resources before deleting',
                  child: OutlinedButton.icon(
                    onPressed: state.canDelete
                        ? () => _showDeleteConfirmation(context, state)
                        : null,
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Delete'),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: Colors.red,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              TwinStateUtils.getDescription(state.twinState),
              style: theme.textTheme.bodyMedium?.copyWith(
                color: Colors.grey[600],
              ),
            ),
            const SizedBox(height: 20),

            // Deploy/Destroy buttons
            Row(
              children: [
                Expanded(
                  child: SizedBox(
                    height: 56,
                    child: FilledButton.icon(
                      onPressed: state.canDeploy
                          ? () => _showDeployConfirmation(context, state)
                          : null,
                      icon: state.isDeploying
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.rocket_launch, size: 24),
                      label: Text(
                        state.twinState == 'error' ? 'RETRY DEPLOY' : 'DEPLOY',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      style: FilledButton.styleFrom(
                        backgroundColor: Colors.teal[600],
                        foregroundColor: Colors.white,
                        disabledBackgroundColor: Colors.grey[400],
                        disabledForegroundColor: Colors.grey[700],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: SizedBox(
                    height: 56,
                    child: FilledButton.icon(
                      onPressed: state.canDestroy
                          ? () => _showDestroyConfirmation(context, state)
                          : null,
                      icon: state.isDestroying
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.delete_forever, size: 24),
                      label: Text(
                        state.twinState == 'error' ? 'CLEANUP' : 'DESTROY',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      style: FilledButton.styleFrom(
                        backgroundColor: Colors.red[700],
                        foregroundColor: Colors.white,
                        disabledBackgroundColor: Colors.grey[400],
                        disabledForegroundColor: Colors.grey[700],
                      ),
                    ),
                  ),
                ),
              ],
            ),

            // Error banner (if applicable)
            if (state.twinState == 'error' && state.lastError != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red[50],
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.red[200]!),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error, color: Colors.red[700]),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Deployment Failed',
                            style: theme.textTheme.titleSmall?.copyWith(
                              color: Colors.red[700],
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          Text(
                            state.lastError!,
                            style: theme.textTheme.bodySmall?.copyWith(
                              color: Colors.red[900],
                            ),
                          ),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: () {
                        // TODO: Show full logs
                      },
                      child: const Text('View Logs'),
                    ),
                  ],
                ),
              ),
            ],

            // Terraform Outputs Card (persists independently of terminal)
            if (state.deploymentOutputs != null &&
                state.deploymentOutputs!.isNotEmpty &&
                state.twinState == 'deployed') ...[
              const SizedBox(height: 16),
              TerraformOutputsCard(
                outputs: state.deploymentOutputs!,
                deployedAt: state.outputsTimestamp,
                onCopyFeedback: (message) {
                  context.read<TwinOverviewBloc>().add(
                    TwinOverviewShowMessage(message, MessageType.success),
                  );
                },
              ),
            ],

            // Outputs error banner (not silent)
            if (state.outputsError != null)
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.warning_amber,
                        color: theme.colorScheme.error,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          state.outputsError!,
                          style: TextStyle(
                            color: theme.colorScheme.onErrorContainer,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),

            // Deployment Terminal (appears when showTerminal is true)
            if (state.showTerminal) ...[
              const SizedBox(height: 16),
              Row(
                children: [
                  Icon(
                    Icons.terminal,
                    size: 16,
                    color: theme.colorScheme.primary,
                  ),
                  const SizedBox(width: 8),
                  Text('Deployment Output', style: theme.textTheme.labelLarge),
                  const Spacer(),
                  IconButton(
                    icon: const Icon(Icons.close, size: 18),
                    onPressed: () => context.read<TwinOverviewBloc>().add(
                      const TwinOverviewCloseTerminal(),
                    ),
                    tooltip: 'Close terminal',
                  ),
                ],
              ),
              const SizedBox(height: 8),
              SizedBox(
                height: 300,
                child: DeploymentTerminal(
                  logs: state.terminalLogs,
                  isConnected: state.isDeploying || state.isDestroying,
                  isComplete: !state.isDeploying && !state.isDestroying,
                  isReconnecting: false,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  void _showDeployConfirmation(BuildContext context, TwinOverviewLoaded state) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.rocket_launch, color: Colors.blue),
            SizedBox(width: 8),
            Text('Deploy to Cloud?'),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('This will provision cloud resources for:'),
            const SizedBox(height: 8),
            Text(
              '• ${state.cloudResourceName ?? state.projectName}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Text(
              'Estimated time: 5-15 minutes',
              style: TextStyle(color: Colors.grey[600]),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              context.read<TwinOverviewBloc>().add(TwinOverviewDeploy());
            },
            child: const Text('Deploy Now'),
          ),
        ],
      ),
    );
  }

  void _showDestroyConfirmation(
    BuildContext context,
    TwinOverviewLoaded state,
  ) {
    bool confirmed = false;

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          title: Row(
            children: [
              Icon(Icons.warning_amber, color: Colors.red[700]),
              const SizedBox(width: 8),
              const Text('Destroy Cloud Resources?'),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('This will PERMANENTLY delete:'),
              const SizedBox(height: 8),
              const Text('• All deployed infrastructure'),
              const Text('• IoT device connections'),
              const Text('• Stored data in hot/cold/archive storage'),
              const SizedBox(height: 16),
              CheckboxListTile(
                value: confirmed,
                onChanged: (v) => setState(() => confirmed = v ?? false),
                title: const Text('I understand this action is irreversible'),
                controlAffinity: ListTileControlAffinity.leading,
                contentPadding: EdgeInsets.zero,
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: confirmed
                  ? () {
                      Navigator.of(ctx).pop();
                      context.read<TwinOverviewBloc>().add(
                        TwinOverviewDestroy(),
                      );
                    }
                  : null,
              style: FilledButton.styleFrom(backgroundColor: Colors.red[700]),
              child: const Text('Destroy'),
            ),
          ],
        ),
      ),
    );
  }

  void _showDeleteConfirmation(BuildContext context, TwinOverviewLoaded state) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.delete_forever, color: Colors.red),
            SizedBox(width: 8),
            Text('Delete Twin?'),
          ],
        ),
        content: Text(
          'Are you sure you want to delete "${state.projectName}"? This action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              context.read<TwinOverviewBloc>().add(TwinOverviewDelete());
            },
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}
