import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../bloc/wizard/wizard.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../providers/twins_provider.dart';
import '../../widgets/calc_form/calc_form.dart';
import '../../widgets/results/calculation_trace_summary.dart';
import '../../widgets/results/layer_cost_card.dart';
import '../../widgets/results/optimization_warning.dart';
import '../../widgets/results/cheapest_path_visualization.dart';

/// Step 2: Optimizer - BLoC version
///
/// Manages calculation parameters and displays optimization results.
class Step2Optimizer extends ConsumerStatefulWidget {
  const Step2Optimizer({super.key});

  @override
  ConsumerState<Step2Optimizer> createState() => _Step2OptimizerState();
}

class _Step2OptimizerState extends ConsumerState<Step2Optimizer> {
  bool _loadingConfig = true;

  // Scroll keys for navigation
  final _resultsKey = GlobalKey();

  // Provider Colors (gcpColor used for results header)
  static const Color gcpColor = Colors.green;

  @override
  void initState() {
    super.initState();

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
                    _buildPricingReviewNotice(context),
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

  Widget _buildPricingReviewNotice(BuildContext context) {
    return Card(
      elevation: 1,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              Icons.price_check,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Pricing review is managed from the dashboard',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Use Dashboard > Pricing Review to refresh provider pricing. '
                    'This step focuses on workload inputs and calculation results for the current twin.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
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
        const SizedBox(height: 16),
        CalculationTraceSummary(result: result),

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
