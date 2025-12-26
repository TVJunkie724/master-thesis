import 'package:flutter/material.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../services/api_service.dart';
import '../../widgets/data_freshness_card.dart';
import '../../widgets/calc_form/calc_form.dart';
import '../../widgets/results/layer_cost_card.dart';
import '../../widgets/results/optimization_warning.dart';
import '../../widgets/results/service_breakdown.dart';

/// Step 2: Optimizer - Cost calculation and optimization
/// 
/// This step allows users to configure calculation parameters and
/// view cost optimization results across AWS, Azure, and GCP.
class Step2Optimizer extends StatefulWidget {
  final String twinId;
  final VoidCallback onNext;
  final VoidCallback onBack;

  const Step2Optimizer({
    super.key,
    required this.twinId,
    required this.onNext,
    required this.onBack,
  });

  @override
  State<Step2Optimizer> createState() => _Step2OptimizerState();
}

class _Step2OptimizerState extends State<Step2Optimizer> {
  final ApiService _apiService = ApiService();
  
  CalcParams? _params;
  CalcResult? _result;
  bool _isCalculating = false;
  Map<String, dynamic>? _pricingStatus;
  bool _loadingStatus = true;

  @override
  void initState() {
    super.initState();
    _loadPricingStatus();
  }

  Future<void> _loadPricingStatus() async {
    try {
      final status = await _apiService.getPricingStatus();
      setState(() {
        _pricingStatus = status;
        _loadingStatus = false;
      });
    } catch (e) {
      setState(() => _loadingStatus = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load pricing status: $e')),
        );
      }
    }
  }

  Future<void> _refreshPricing(String provider) async {
    try {
      await _apiService.refreshPricing(provider, widget.twinId);
      await _loadPricingStatus();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$provider pricing refreshed successfully')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to refresh $provider pricing: $e')),
        );
      }
    }
  }

  Future<void> _calculate() async {
    if (_params == null) return;
    
    // Validate storage durations
    if (!_params!.isStorageDurationValid) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Storage durations must be: Hot ≤ Cool ≤ Archive'),
          backgroundColor: Colors.red,
        ),
      );
      return;
    }
    
    setState(() => _isCalculating = true);

    try {
      final response = await _apiService.calculateCosts(_params!.toJson());
      setState(() => _result = CalcResult.fromJson(response));
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Calculation failed: $e')),
        );
      }
    } finally {
      setState(() => _isCalculating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 900),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // ============================================================
              // SECTION 1: DATA FRESHNESS
              // ============================================================
              Row(
                children: [
                  Icon(Icons.cloud_sync, 
                    size: 28, 
                    color: Theme.of(context).primaryColor,
                  ),
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
              
              // Data Freshness Cards
              _buildDataFreshnessCards(),

              const SizedBox(height: 32),
              const Divider(),
              const SizedBox(height: 32),
              
              // ============================================================
              // SECTION 2: CALCULATION INPUTS
              // ============================================================
              Row(
                children: [
                  Icon(Icons.tune, 
                    size: 28, 
                    color: Theme.of(context).primaryColor,
                  ),
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

              // Calculation Form
              CalcForm(
                onChanged: (params) => setState(() => _params = params),
              ),

              const SizedBox(height: 32),

              // Calculate Button
              Center(
                child: SizedBox(
                  width: 220,
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: _params != null && !_isCalculating ? _calculate : null,
                    icon: _isCalculating
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.calculate),
                    label: Text(_isCalculating ? 'Calculating...' : 'Calculate Cost'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Theme.of(context).primaryColor,
                      foregroundColor: Colors.white,
                      textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
              ),

              // Results Section
              if (_result != null) ...[
                const SizedBox(height: 48),
                const Divider(),
                const SizedBox(height: 24),
                _buildResultsSection(),
              ],

              const SizedBox(height: 32),

              // Navigation
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  OutlinedButton.icon(
                    onPressed: widget.onBack,
                    icon: const Icon(Icons.arrow_back),
                    label: const Text('Back'),
                  ),
                  ElevatedButton.icon(
                    onPressed: _result != null ? widget.onNext : null,
                    icon: const Icon(Icons.arrow_forward),
                    label: const Text('Next Step'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
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
            onRefresh: () => _refreshPricing('aws'),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: DataFreshnessCard(
            provider: 'azure',
            status: _pricingStatus?['azure'],
            onRefresh: () => _refreshPricing('azure'),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: DataFreshnessCard(
            provider: 'gcp',
            status: _pricingStatus?['gcp'],
            onRefresh: () => _refreshPricing('gcp'),
          ),
        ),
      ],
    );
  }

  Widget _buildResultsSection() {
    final result = _result!;
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Results Header
        Row(
          children: [
            const Icon(Icons.analytics, size: 24, color: Colors.green),
            const SizedBox(width: 8),
            Text(
              'Optimization Results',
              style: Theme.of(context).textTheme.titleLarge,
            ),
          ],
        ),
        const SizedBox(height: 16),

        // Cheapest Path Badges
        _buildCheapestPath(result.cheapestPath),
        const SizedBox(height: 24),

        // Optimization Warnings (if any)
        if (result.l1OptimizationOverride != null)
          OptimizationWarning(
            layer: 'L1',
            optimizationOverride: result.l1OptimizationOverride!,
          ),
        if (result.l2OptimizationOverride != null)
          OptimizationWarning(
            layer: 'L2',
            optimizationOverride: result.l2OptimizationOverride!,
          ),
        if (result.l3OptimizationOverride != null)
          OptimizationWarning(
            layer: 'L3',
            optimizationOverride: result.l3OptimizationOverride!,
          ),
        if (result.l4OptimizationOverride != null)
          OptimizationWarning(
            layer: 'L4',
            optimizationOverride: result.l4OptimizationOverride!,
          ),

        const SizedBox(height: 24),

        // Layer Cost Cards
        Text(
          'Cost Breakdown by Layer',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 16),
        
        Wrap(
          spacing: 16,
          runSpacing: 16,
          children: [
            SizedBox(
              width: 300,
              child: LayerCostCard(
                layer: 'L1 - IoT Ingestion',
                awsCost: result.awsCosts.l1?.cost,
                azureCost: result.azureCosts.l1?.cost,
                gcpCost: result.gcpCosts.l1?.cost,
                cheapestPath: result.cheapestPath,
              ),
            ),
            SizedBox(
              width: 300,
              child: LayerCostCard(
                layer: 'L2 - Processing',
                awsCost: result.awsCosts.l2?.cost,
                azureCost: result.azureCosts.l2?.cost,
                gcpCost: result.gcpCosts.l2?.cost,
                cheapestPath: result.cheapestPath,
              ),
            ),
            SizedBox(
              width: 300,
              child: LayerCostCard(
                layer: 'L3 - Hot Storage',
                awsCost: result.awsCosts.l3Hot?.cost,
                azureCost: result.azureCosts.l3Hot?.cost,
                gcpCost: result.gcpCosts.l3Hot?.cost,
                cheapestPath: result.cheapestPath,
              ),
            ),
            SizedBox(
              width: 300,
              child: LayerCostCard(
                layer: 'L4 - Twin Management',
                awsCost: result.awsCosts.l4?.cost,
                azureCost: result.azureCosts.l4?.cost,
                gcpCost: result.gcpCosts.l4?.cost,
                cheapestPath: result.cheapestPath,
              ),
            ),
            SizedBox(
              width: 300,
              child: LayerCostCard(
                layer: 'L5 - Visualization',
                awsCost: result.awsCosts.l5?.cost,
                azureCost: result.azureCosts.l5?.cost,
                gcpCost: result.gcpCosts.l5?.cost,
                cheapestPath: result.cheapestPath,
              ),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // Service Breakdown
        Text(
          'Service Breakdown',
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 16),
        ServiceBreakdown(result: result),

        const SizedBox(height: 24),

        // Total Cost
        _buildTotalCost(result),
      ],
    );
  }

  Widget _buildCheapestPath(List<String> path) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: path.map((segment) {
        final parts = segment.split('_');
        final layer = parts.isNotEmpty ? parts[0] : '';
        final provider = parts.length > 1 ? parts[1] : '';
        
        Color chipColor;
        switch (provider.toUpperCase()) {
          case 'AWS':
            chipColor = Colors.orange;
            break;
          case 'AZURE':
            chipColor = Colors.blue;
            break;
          case 'GCP':
            chipColor = Colors.red;
            break;
          default:
            chipColor = Colors.grey;
        }
        
        return Chip(
          label: Text(
            '$layer: $provider',
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
          ),
          backgroundColor: chipColor,
        );
      }).toList(),
    );
  }

  Widget _buildTotalCost(CalcResult result) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.green.withAlpha(38),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.green.shade600),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            'Total Monthly Cost (Optimal Path)',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          Text(
            '\$${result.totalCost.toStringAsFixed(2)}/month',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              color: Colors.green.shade400,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }
}
