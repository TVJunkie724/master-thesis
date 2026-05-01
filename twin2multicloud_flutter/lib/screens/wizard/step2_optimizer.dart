import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../bloc/wizard/wizard.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../providers/twins_provider.dart';
import '../../utils/api_error_handler.dart';
import '../../widgets/data_freshness_card.dart';
import '../../widgets/calc_form/calc_form.dart';
import '../../widgets/results/layer_cost_card.dart';
import '../../widgets/results/optimization_warning.dart';
import '../../widgets/results/cheapest_path_visualization.dart';
import '../../services/api_service.dart';
import '../../services/sse_service.dart';

/// Step 2: Optimizer - BLoC version
///
/// Manages calculation parameters and displays optimization results.
class Step2Optimizer extends ConsumerStatefulWidget {
  const Step2Optimizer({super.key});

  @override
  ConsumerState<Step2Optimizer> createState() => _Step2OptimizerState();
}

class _Step2OptimizerState extends ConsumerState<Step2Optimizer> {
  final ApiService _apiService = ApiService();

  // Local state for pricing/refresh (not in BLoC yet)
  Map<String, dynamic>? _pricingStatus;
  bool _loadingStatus = true;
  bool _loadingConfig = true;

  // SSE Refresh State
  bool _isRefreshing = false;
  String? _refreshingProvider;
  List<String> _refreshLogs = [];
  StreamSubscription? _sseSubscription;

  // Scroll keys for navigation
  final _resultsKey = GlobalKey();

  // Provider Colors (gcpColor used for results header)
  static const Color gcpColor = Colors.green;

  @override
  void initState() {
    super.initState();
    _loadPricingStatus();

    // If we have calcParams in BLoC state, skip loading
    final state = context.read<WizardBloc>().state;
    if (state.calcParams != null) {
      _loadingConfig = false;
    } else if (state.twinId != null) {
      _loadOptimizerConfig();
    } else {
      _loadingConfig = false;
    }

    // Auto-scroll to results if they're already present (edit mode resume)
    if (state.calcResult != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        Future.delayed(const Duration(milliseconds: 100), () {
          if (_resultsKey.currentContext != null && mounted) {
            Scrollable.ensureVisible(
              _resultsKey.currentContext!,
              duration: const Duration(milliseconds: 500),
              curve: Curves.easeInOut,
            );
          }
        });
      });
    }
  }

  @override
  void dispose() {
    _sseSubscription?.cancel();
    super.dispose();
  }

  Future<void> _loadPricingStatus() async {
    try {
      final status = await _apiService.getPricingStatus();
      if (mounted) {
        setState(() {
          _pricingStatus = status;
          _loadingStatus = false;
        });
      }
    } catch (e) {
      debugPrint('Failed to load pricing status: $e');
      if (mounted) setState(() => _loadingStatus = false);
    }
  }

  Future<void> _loadOptimizerConfig() async {
    final state = context.read<WizardBloc>().state;
    if (state.twinId == null) {
      setState(() => _loadingConfig = false);
      return;
    }

    try {
      final api = ref.read(apiServiceProvider);
      final config = await api.getOptimizerConfig(state.twinId!);

      if (config['params'] != null && mounted) {
        final params = CalcParams.fromJson(config['params']);
        context.read<WizardBloc>().add(WizardCalcParamsChanged(params));
      }

      if (mounted) setState(() => _loadingConfig = false);
    } catch (e) {
      debugPrint('Failed to load optimizer config: $e');
      if (mounted) setState(() => _loadingConfig = false);
    }
  }

  void _onCalcParamsChanged(CalcParams params) {
    context.read<WizardBloc>().add(WizardCalcParamsChanged(params));
  }

  Future<void> _confirmRefresh(String provider) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Refresh ${provider.toUpperCase()} Pricing?'),
        content: const Text(
          'Fetching cloud pricing data may take 30-60 seconds.\n\n'
          'You will see real-time progress in the log window below.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Refresh'),
          ),
        ],
      ),
    );

    if (confirmed == true && mounted) {
      _startStreamingRefresh(provider);
    }
  }

  Future<void> _startStreamingRefresh(String provider) async {
    setState(() {
      _isRefreshing = true;
      _refreshingProvider = provider;
      _refreshLogs = [];
    });

    final authToken = await _apiService.getAuthToken();
    final sseService = SseService(
      baseUrl: ApiService.baseUrl,
      authToken: authToken,
    );

    if (!mounted) return;
    final state = context.read<WizardBloc>().state;
    _sseSubscription = sseService
        .streamRefreshPricing(provider, state.twinId ?? '')
        .listen(
          (event) {
            if (!mounted) return;
            setState(() {
              _refreshLogs.add('${_formatTime()} ${event.message}');
            });

            if (event.isComplete) {
              _loadPricingStatus();
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      '${provider.toUpperCase()} pricing refreshed successfully',
                    ),
                  ),
                );
              }
            } else if (event.isError) {
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: Text(
                      'Failed to refresh ${provider.toUpperCase()} pricing',
                    ),
                  ),
                );
              }
            }
          },
          onDone: () {
            if (mounted) setState(() => _isRefreshing = false);
          },
          onError: (e) {
            if (!mounted) return;
            setState(() {
              _refreshLogs.add(
                '${_formatTime()} ❌ Connection error: ${ApiErrorHandler.extractMessage(e)}',
              );
              _isRefreshing = false;
            });
          },
        );
  }

  String _formatTime() => TimeOfDay.now().format(context);

  @override
  Widget build(BuildContext context) {
    return BlocListener<WizardBloc, WizardState>(
      // Scroll to results when any calculation completes (not just first)
      listenWhen: (prev, curr) =>
          prev.isCalculating && !curr.isCalculating && curr.calcResult != null,
      listener: (context, state) {
        // Scroll to results when calculation completes
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (_resultsKey.currentContext != null) {
            Scrollable.ensureVisible(
              _resultsKey.currentContext!,
              duration: const Duration(milliseconds: 500),
              curve: Curves.easeInOut,
            );
          }
        });
      },
      child: BlocBuilder<WizardBloc, WizardState>(
        builder: (context, state) {
          return SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1000),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Section 1: Data Freshness
                    _buildPricingStatusSection(context),

                    if (_isRefreshing || _refreshLogs.isNotEmpty)
                      _buildLogWindow(),

                    const SizedBox(height: 32),
                    const Divider(),
                    const SizedBox(height: 32),

                    // Note: Step 3 invalidation warning now shown in header alert via warningMessage
                    // Section 2: Calculation Inputs
                    _buildCalculationSection(context, state),

                    // Section 3: Results (if available)
                    if (state.calcResult != null) ...[
                      const SizedBox(height: 64),
                      Container(
                        key: _resultsKey,
                        child: _buildResultsSection(context, state),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildPricingStatusSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              Icons.cloud_sync,
              size: 28,
              color: Theme.of(context).primaryColor,
            ),
            const SizedBox(width: 12),
            Text(
              'Pricing Data Status',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'Ensure pricing data is up-to-date before calculating costs. Click refresh to update.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 20),
        _buildDataFreshnessCards(),
      ],
    );
  }

  Widget _buildDataFreshnessCards() {
    if (_loadingStatus) {
      return const Center(child: CircularProgressIndicator());
    }

    // Wrap in BlocBuilder to react to state changes (e.g., draft saved → twinId available)
    return BlocBuilder<WizardBloc, WizardState>(
      buildWhen: (prev, curr) =>
          prev.twinId != curr.twinId ||
          prev.aws.isValid != curr.aws.isValid ||
          prev.aws.source != curr.aws.source ||
          prev.gcp.isValid != curr.gcp.isValid ||
          prev.gcp.source != curr.gcp.source ||
          prev.hasUnsavedChanges != curr.hasUnsavedChanges,
      builder: (context, state) {
        final hasSavedDraft = state.twinId != null;

        // Helper: credentials are "saved" if inherited from DB OR no unsaved changes
        bool isCredentialSaved(ProviderCredentials cred) {
          if (!cred.isValid) return false;
          return cred.source == CredentialSource.inherited ||
              !state.hasUnsavedChanges;
        }

        // Determine enabled state for each provider:
        // - Azure: Always enabled (uses public API, no credentials needed)
        // - AWS/GCP: Enabled only if draft saved AND credentials are SAVED (not just validated)
        final awsEnabled = hasSavedDraft && isCredentialSaved(state.aws);
        final gcpEnabled = hasSavedDraft && isCredentialSaved(state.gcp);

        // Build disabled reason messages
        String? awsDisabledReason;
        if (!hasSavedDraft) {
          awsDisabledReason = 'Save draft to enable refresh';
        } else if (!state.aws.isValid) {
          awsDisabledReason = 'Configure AWS credentials in Step 1';
        } else if (!isCredentialSaved(state.aws)) {
          awsDisabledReason = 'Save credentials to enable refresh';
        }

        String? gcpDisabledReason;
        if (!hasSavedDraft) {
          gcpDisabledReason = 'Save draft to enable refresh';
        } else if (!state.gcp.isValid) {
          gcpDisabledReason = 'Configure GCP credentials in Step 1';
        } else if (!isCredentialSaved(state.gcp)) {
          gcpDisabledReason = 'Save credentials to enable refresh';
        }

        return Row(
          children: [
            Expanded(
              child: DataFreshnessCard(
                provider: 'aws',
                status: _pricingStatus?['aws'],
                onRefresh: () => _confirmRefresh('aws'),
                enabled: awsEnabled,
                disabledReason: awsDisabledReason,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: DataFreshnessCard(
                provider: 'azure',
                status: _pricingStatus?['azure'],
                onRefresh: () => _confirmRefresh('azure'),
                enabled: true, // Azure always enabled (public API)
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: DataFreshnessCard(
                provider: 'gcp',
                status: _pricingStatus?['gcp'],
                onRefresh: () => _confirmRefresh('gcp'),
                enabled: gcpEnabled,
                disabledReason: gcpDisabledReason,
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildLogWindow() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 16),
        Row(
          children: [
            Icon(Icons.terminal, color: Colors.grey[700]),
            const SizedBox(width: 8),
            Text(
              'Refresh Log${_refreshingProvider != null ? " (${_refreshingProvider!.toUpperCase()})" : ""}',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: Colors.grey[700],
              ),
            ),
            const Spacer(),
            if (!_isRefreshing)
              TextButton(
                onPressed: () => setState(() => _refreshLogs.clear()),
                child: const Text('Clear'),
              ),
          ],
        ),
        const SizedBox(height: 8),
        Container(
          height: 150,
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.grey[900],
            borderRadius: BorderRadius.circular(8),
          ),
          child: ListView.builder(
            itemCount: _refreshLogs.length + (_isRefreshing ? 1 : 0),
            itemBuilder: (context, index) {
              if (index < _refreshLogs.length) {
                return Text(
                  _refreshLogs[index],
                  style: const TextStyle(
                    fontFamily: 'monospace',
                    fontSize: 12,
                    color: Colors.green,
                  ),
                );
              } else {
                return const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: LinearProgressIndicator(),
                );
              }
            },
          ),
        ),
      ],
    );
  }

  Widget _buildCalculationSection(BuildContext context, WizardState state) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.tune, size: 28, color: Theme.of(context).primaryColor),
            const SizedBox(width: 12),
            Text(
              'Calculation Inputs',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          'Configure your digital twin workload parameters to calculate optimized costs.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 24),

        if (_loadingConfig)
          const Center(child: CircularProgressIndicator())
        else
          CalcForm(
            initialParams: state.calcParams,
            onChanged: _onCalcParamsChanged,
            onValidChanged: (isValid) {
              context.read<WizardBloc>().add(
                WizardCalcFormValidChanged(isValid),
              );
            },
          ),
      ],
    );
  }

  Widget _buildResultsSection(BuildContext context, WizardState state) {
    final result = state.calcResult!;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Header
        Row(
          children: [
            const Icon(Icons.analytics, size: 32, color: gcpColor),
            const SizedBox(width: 12),
            Text(
              'Optimization Results',
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 8),
        const Divider(thickness: 2),
        const SizedBox(height: 24),

        // Total Cost Banner
        _buildTotalCost(result),

        // Note: Unconfigured provider warning is now shown in the wizard header
        const SizedBox(height: 32),

        // Cheapest Path
        Text(
          'Cheapest Path',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: Colors.grey.shade700,
          ),
        ),
        const SizedBox(height: 16),
        Center(child: CheapestPathVisualization(path: result.cheapestPath)),
        const SizedBox(height: 32),

        // Optimization Warnings (if any)
        if (result.l1OptimizationOverride != null) ...[
          OptimizationWarning(
            layer: 'L1',
            optimizationOverride: result.l1OptimizationOverride!,
          ),
          const SizedBox(height: 8),
        ],
        if (result.l2OptimizationOverride != null) ...[
          OptimizationWarning(
            layer: 'L2',
            optimizationOverride: result.l2OptimizationOverride!,
          ),
          const SizedBox(height: 8),
        ],
        if (result.l3OptimizationOverride != null) ...[
          OptimizationWarning(
            layer: 'L3',
            optimizationOverride: result.l3OptimizationOverride!,
          ),
          const SizedBox(height: 8),
        ],
        if (result.l4OptimizationOverride != null) ...[
          OptimizationWarning(
            layer: 'L4',
            optimizationOverride: result.l4OptimizationOverride!,
          ),
          const SizedBox(height: 8),
        ],
        const SizedBox(height: 24),

        // Layer Cost Cards
        Text(
          'Cost Breakdown by Layer',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.bold,
            color: Colors.grey.shade700,
          ),
        ),
        const SizedBox(height: 16),

        Center(
          child: Wrap(
            alignment: WrapAlignment.center,
            spacing: 16,
            runSpacing: 24,
            children: [
              SizedBox(
                width: 300,
                child: LayerCostCard(
                  layer: 'L1 - IoT Ingestion',
                  awsLayer: result.awsCosts.l1,
                  azureLayer: result.azureCosts.l1,
                  gcpLayer: result.gcpCosts.l1,
                  cheapestPath: result.cheapestPath,
                ),
              ),
              SizedBox(
                width: 300,
                child: LayerCostCard(
                  layer: 'L2 - Processing',
                  awsLayer: result.awsCosts.l2,
                  azureLayer: result.azureCosts.l2,
                  gcpLayer: result.gcpCosts.l2,
                  cheapestPath: result.cheapestPath,
                ),
              ),
              SizedBox(
                width: 300,
                child: LayerCostCard(
                  layer: 'L3 - Hot Storage',
                  awsLayer: result.awsCosts.l3Hot,
                  azureLayer: result.azureCosts.l3Hot,
                  gcpLayer: result.gcpCosts.l3Hot,
                  cheapestPath: result.cheapestPath,
                ),
              ),
              SizedBox(
                width: 300,
                child: LayerCostCard(
                  layer: 'L3 - Cool Storage',
                  awsLayer: result.awsCosts.l3Cool,
                  azureLayer: result.azureCosts.l3Cool,
                  gcpLayer: result.gcpCosts.l3Cool,
                  cheapestPath: result.cheapestPath,
                ),
              ),
              SizedBox(
                width: 300,
                child: LayerCostCard(
                  layer: 'L3 - Archive Storage',
                  awsLayer: result.awsCosts.l3Archive,
                  azureLayer: result.azureCosts.l3Archive,
                  gcpLayer: result.gcpCosts.l3Archive,
                  cheapestPath: result.cheapestPath,
                ),
              ),
              SizedBox(
                width: 300,
                child: LayerCostCard(
                  layer: 'L4 - Twin Management',
                  awsLayer: result.awsCosts.l4,
                  azureLayer: result.azureCosts.l4,
                  gcpLayer: result.gcpCosts.l4,
                  cheapestPath: result.cheapestPath,
                  hideGcp: true,
                ),
              ),
              SizedBox(
                width: 300,
                child: LayerCostCard(
                  layer: 'L5 - Visualization',
                  awsLayer: result.awsCosts.l5,
                  azureLayer: result.azureCosts.l5,
                  gcpLayer: result.gcpCosts.l5,
                  cheapestPath: result.cheapestPath,
                  hideGcp: true,
                ),
              ),
            ],
          ),
        ),

        const SizedBox(height: 32),
        Center(
          child: Text(
            'Prices are estimates based on public pricing APIs and may vary.',
            style: TextStyle(
              color: Colors.grey.shade500,
              fontStyle: FontStyle.italic,
            ),
          ),
        ),
        const SizedBox(height: 32),
      ],
    );
  }

  Widget _buildTotalCost(CalcResult result) {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.green.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.green.shade300, width: 2),
      ),
      child: Column(
        children: [
          Text(
            'TOTAL OPTIMIZED MONTHLY COST',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
              fontWeight: FontWeight.bold,
              color: Colors.green.shade800,
              letterSpacing: 1.1,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '\$${result.totalCost.toStringAsFixed(2)}',
            style: Theme.of(context).textTheme.displaySmall?.copyWith(
              color: Colors.green.shade700,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Includes cloud infrastructure, transaction, and data transfer costs',
            style: TextStyle(fontSize: 12, color: Colors.green.shade800),
          ),
        ],
      ),
    );
  }
}
