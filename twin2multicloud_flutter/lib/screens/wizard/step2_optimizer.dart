import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../bloc/wizard/wizard.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../providers/twins_provider.dart';
import '../../widgets/data_freshness_card.dart';
import '../../widgets/calc_form/calc_form.dart';
import '../../widgets/results/layer_cost_card.dart';
import '../../widgets/results/optimization_warning.dart';
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

  // Provider Colors
  static const Color awsColor = Colors.orange;
  static const Color azureColor = Colors.blue;
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
  }

  @override
  void dispose() {
    _sseSubscription?.cancel();
    super.dispose();
  }

  Future<void> _loadPricingStatus() async {
    try {
      final status = await _apiService.getPricingStatus();
      if (mounted) setState(() {
        _pricingStatus = status;
        _loadingStatus = false;
      });
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
          'You will see real-time progress in the log window below.'
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Refresh')),
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
              SnackBar(content: Text('${provider.toUpperCase()} pricing refreshed successfully')),
            );
          }
        } else if (event.isError) {
          if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Failed to refresh ${provider.toUpperCase()} pricing')),
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
          _refreshLogs.add('${_formatTime()} ❌ Connection error: $e');
          _isRefreshing = false;
        });
      },
    );
  }

  String _formatTime() => TimeOfDay.now().format(context);

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<WizardBloc, WizardState>(
      builder: (context, state) {
        return Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1000),
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
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
                  
                  // Section 2: Calculation Inputs
                  _buildCalculationSection(context, state),
                  
                  // Section 3: Results (if available)
                  if (state.calcResult != null) ...[
                    const SizedBox(height: 64),
                    _buildResultsSection(context, state),
                  ],
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildPricingStatusSection(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.cloud_sync, size: 28, color: Theme.of(context).primaryColor),
            const SizedBox(width: 12),
            Text(
              'Pricing Data Status',
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
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
    
    return Row(
      children: [
        Expanded(
          child: DataFreshnessCard(
            provider: 'aws',
            status: _pricingStatus?['aws'],
            onRefresh: () => _confirmRefresh('aws'),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: DataFreshnessCard(
            provider: 'azure',
            status: _pricingStatus?['azure'],
            onRefresh: () => _confirmRefresh('azure'),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: DataFreshnessCard(
            provider: 'gcp',
            status: _pricingStatus?['gcp'],
            onRefresh: () => _confirmRefresh('gcp'),
          ),
        ),
      ],
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
              style: TextStyle(fontWeight: FontWeight.bold, color: Colors.grey[700]),
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
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 12, color: Colors.green),
                );
              } else {
                return const Padding(padding: EdgeInsets.only(top: 8), child: LinearProgressIndicator());
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
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
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
              style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
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
        Center(child: _buildCheapestPath(result.cheapestPath)),
        const SizedBox(height: 32),

        // Optimization Warnings (if any)
        if (result.l1OptimizationOverride != null) ...[
          OptimizationWarning(layer: 'L1', optimizationOverride: result.l1OptimizationOverride!),
          const SizedBox(height: 8),
        ],
        if (result.l2OptimizationOverride != null) ...[
          OptimizationWarning(layer: 'L2', optimizationOverride: result.l2OptimizationOverride!),
          const SizedBox(height: 8),
        ],
        if (result.l3OptimizationOverride != null) ...[
          OptimizationWarning(layer: 'L3', optimizationOverride: result.l3OptimizationOverride!),
          const SizedBox(height: 8),
        ],
        if (result.l4OptimizationOverride != null) ...[
          OptimizationWarning(layer: 'L4', optimizationOverride: result.l4OptimizationOverride!),
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
            style: TextStyle(color: Colors.grey.shade500, fontStyle: FontStyle.italic),
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

  Widget _buildCheapestPath(List<String> path) {
    if (path.isEmpty) return const SizedBox();

    return Wrap(
      spacing: 8,
      runSpacing: 16,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        for (int i = 0; i < path.length; i++) ...[
          _buildPathSegment(path[i]),
          if (i < path.length - 1)
            const Icon(Icons.arrow_forward, color: Colors.grey, size: 20),
        ],
      ],
    );
  }

  Widget _buildPathSegment(String segment) {
    final parts = segment.split('_');
    String layer = '';
    String provider = '';
    
    if (segment.startsWith('L3')) {
      if (parts.length >= 3) {
        layer = 'L3 ${parts[1]}';
        provider = parts[2];
      } else {
        layer = parts[0];
        provider = parts.length > 1 ? parts[1] : '?';
      }
    } else {
      layer = parts[0];
      provider = parts.length > 1 ? parts[1] : '?';
    }

    Color bgColor;
    switch (provider.toUpperCase()) {
      case 'AWS':
        bgColor = awsColor;
        break;
      case 'AZURE':
        bgColor = azureColor;
        break;
      case 'GCP':
        bgColor = gcpColor;
        break;
      default:
        bgColor = Colors.grey;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: bgColor.withAlpha(100),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Text(
        '$layer $provider'.toUpperCase(),
        style: const TextStyle(
          color: Colors.white, 
          fontWeight: FontWeight.bold,
          fontSize: 12,
        ),
      ),
    );
  }
}
