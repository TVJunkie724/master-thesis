import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../bloc/wizard/wizard.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../theme/colors.dart';
import '../../widgets/calc_form/calc_form.dart';
import '../../widgets/results/calculation_trace_summary.dart';
import '../../widgets/results/layer_cost_card.dart';
import '../../widgets/results/optimization_warning.dart';
import '../../widgets/results/cheapest_path_visualization.dart';
import '../../widgets/pricing/pricing_readiness_summary.dart';
import '../../features/configuration_workspace/domain/configuration_journey.dart';

/// Step 2: Optimizer - BLoC version
///
/// Manages calculation parameters and displays optimization results.
class Step2Optimizer extends StatefulWidget {
  final ConfigurationTaskId? taskId;

  const Step2Optimizer({super.key, this.taskId});

  @override
  State<Step2Optimizer> createState() => _Step2OptimizerState();
}

class _Step2OptimizerState extends State<Step2Optimizer> {
  // Scroll keys for navigation
  final _resultsKey = GlobalKey();

  @override
  void initState() {
    super.initState();

    final state = context.read<WizardBloc>().state;
    _loadPricingHealthIfNeeded();
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
  void didUpdateWidget(covariant Step2Optimizer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.taskId != widget.taskId) {
      _loadPricingHealthIfNeeded();
    }
  }

  void _loadPricingHealthIfNeeded() {
    if (_isWorkloadTask(widget.taskId)) return;
    final bloc = context.read<WizardBloc>();
    final state = bloc.state;
    if (state.pricingHealth != null ||
        state.isPricingHealthLoading ||
        state.pricingHealthError != null) {
      return;
    }
    bloc.add(const WizardPricingHealthLoadRequested());
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
          final workloadTask = _isWorkloadTask(widget.taskId);
          return SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1000),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: workloadTask
                      ? [_buildCalculationSection(context, state)]
                      : _buildArchitectureTask(context, state),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  List<Widget> _buildArchitectureTask(
    BuildContext context,
    WizardState state,
  ) => switch (widget.taskId) {
    ConfigurationTaskId.pricingReadiness => [
      _buildPricingReadiness(context, state),
    ],
    ConfigurationTaskId.calculateAlternatives => [
      _buildPricingReadiness(context, state),
      const SizedBox(height: 32),
      _buildCalculationSummary(context, state),
    ],
    ConfigurationTaskId.compareAndSelect => [
      if (state.calcResult != null)
        Container(key: _resultsKey, child: _buildResultsSection(context, state))
      else
        const Center(child: Text('Calculate an architecture first.')),
    ],
    _ => [
      _buildPricingReadiness(context, state),
      const SizedBox(height: 32),
      _buildCalculationSection(context, state),
      if (state.calcResult != null) ...[
        const SizedBox(height: 64),
        Container(
          key: _resultsKey,
          child: _buildResultsSection(context, state),
        ),
      ],
    ],
  };

  Widget _buildPricingReadiness(BuildContext context, WizardState state) =>
      PricingReadinessSummary(
        health: state.pricingHealth,
        isLoading: state.isPricingHealthLoading,
        error: state.pricingHealthError,
        onRetry: () => context.read<WizardBloc>().add(
          const WizardPricingHealthLoadRequested(),
        ),
      );

  Widget _buildCalculationSummary(BuildContext context, WizardState state) {
    final params = state.calcParams;
    if (params == null) {
      return const Center(
        child: Text(
          'Complete the workload tasks before reviewing the summary.',
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Workload summary',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 16),
        Table(
          columnWidths: const {0: FlexColumnWidth(2), 1: FlexColumnWidth(3)},
          defaultVerticalAlignment: TableCellVerticalAlignment.middle,
          children: [
            _summaryRow('Devices', '${params.numberOfDevices}'),
            _summaryRow(
              'Telemetry interval',
              '${params.deviceSendingIntervalInMinutes} minutes',
            ),
            _summaryRow(
              'Message size',
              '${params.averageSizeOfMessageInKb} KB',
            ),
            _summaryRow(
              'Retention',
              '${params.hotStorageDurationInMonths} / ${params.coolStorageDurationInMonths} / ${params.archiveStorageDurationInMonths} months',
            ),
            _summaryRow(
              'Event processing',
              params.useEventChecking ? 'Enabled' : 'Not required',
            ),
            _summaryRow(
              '3D representation',
              params.needs3DModel ? 'Required' : 'Not required',
            ),
            _summaryRow('Currency', params.currency),
          ],
        ),
      ],
    );
  }

  TableRow _summaryRow(String label, String value) => TableRow(
    children: [
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Text(label),
      ),
      Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
      ),
    ],
  );

  Widget _buildCalculationSection(BuildContext context, WizardState state) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.tune, size: 28, color: Theme.of(context).primaryColor),
            const SizedBox(width: 12),
            Text(
              _taskTitle(widget.taskId),
              style: Theme.of(
                context,
              ).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Text(
          _taskDescription(widget.taskId),
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 24),

        CalcForm(
          section: _calcSectionForTask(widget.taskId),
          initialParams: state.calcParams,
          onChanged: _onCalcParamsChanged,
          onValidChanged: (isValid) {
            context.read<WizardBloc>().add(WizardCalcFormValidChanged(isValid));
          },
        ),
      ],
    );
  }

  CalcFormSection? _calcSectionForTask(ConfigurationTaskId? taskId) =>
      switch (taskId) {
        ConfigurationTaskId.scenarioAndCurrency =>
          CalcFormSection.scenarioAndCurrency,
        ConfigurationTaskId.deviceTraffic => CalcFormSection.deviceTraffic,
        ConfigurationTaskId.processing => CalcFormSection.processing,
        ConfigurationTaskId.retention => CalcFormSection.retention,
        ConfigurationTaskId.twinCapabilities =>
          CalcFormSection.twinCapabilities,
        _ => null,
      };

  bool _isWorkloadTask(ConfigurationTaskId? taskId) => switch (taskId) {
    ConfigurationTaskId.scenarioAndCurrency ||
    ConfigurationTaskId.deviceTraffic ||
    ConfigurationTaskId.processing ||
    ConfigurationTaskId.retention ||
    ConfigurationTaskId.twinCapabilities => true,
    _ => false,
  };

  String _taskTitle(ConfigurationTaskId? taskId) => switch (taskId) {
    ConfigurationTaskId.scenarioAndCurrency => 'Scenario and currency',
    ConfigurationTaskId.deviceTraffic => 'Device traffic',
    ConfigurationTaskId.processing => 'Processing',
    ConfigurationTaskId.retention => 'Retention',
    ConfigurationTaskId.twinCapabilities => 'Twin capabilities',
    _ => 'Calculation inputs',
  };

  String _taskDescription(ConfigurationTaskId? taskId) => switch (taskId) {
    ConfigurationTaskId.scenarioAndCurrency =>
      'Start from a representative scenario and choose the reporting currency.',
    ConfigurationTaskId.deviceTraffic =>
      'Describe connected devices and the telemetry volume they produce.',
    ConfigurationTaskId.processing =>
      'Describe event evaluation, orchestration, and device feedback.',
    ConfigurationTaskId.retention =>
      'Define how long telemetry remains in each storage tier.',
    ConfigurationTaskId.twinCapabilities =>
      'Describe 3D representation and dashboard usage requirements.',
    _ =>
      'Configure your digital twin workload parameters to calculate optimized costs.',
  };

  Widget _buildResultsSection(BuildContext context, WizardState state) {
    final result = state.calcResult!;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Header
        Row(
          children: [
            const Icon(Icons.analytics, size: 32, color: AppColors.gcp),
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
