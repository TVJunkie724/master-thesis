import 'dart:async';
import 'package:flutter/material.dart';
import '../../models/calc_params.dart';
import '../../models/calc_result.dart';
import '../../models/wizard_cache.dart';
import '../../services/api_service.dart';
import '../../services/sse_service.dart';
import '../../widgets/data_freshness_card.dart';
import '../../widgets/calc_form/calc_form.dart';
import '../../widgets/results/layer_cost_card.dart';
import '../../widgets/results/optimization_warning.dart';

/// Step 2: Optimizer - Cost calculation and optimization
/// 
/// This step allows users to configure calculation parameters and
/// view cost optimization results across AWS, Azure, and GCP.
class Step2Optimizer extends StatefulWidget {
  final String? twinId;  // May be null if twin not yet created
  final WizardCache cache;
  final VoidCallback onCacheChanged;

  const Step2Optimizer({
    super.key,
    required this.twinId,
    required this.cache,
    required this.onCacheChanged,
  });

  @override
  State<Step2Optimizer> createState() => _Step2OptimizerState();
}

class _Step2OptimizerState extends State<Step2Optimizer> {
  final ApiService _apiService = ApiService();
  
  CalcParams? _params;
  bool _isCalculating = false;
  Map<String, dynamic>? _pricingStatus;
  bool _loadingStatus = true;
  
  // Loading state for optimizer config
  bool _loadingConfig = true;
  
  // SSE Refresh State
  bool _isRefreshing = false;
  String? _refreshingProvider;
  List<String> _refreshLogs = [];
  StreamSubscription? _sseSubscription;

  // Dirty State - tracks if inputs changed since last calculation
  // When true: Calculate button enabled, results greyed out
  // When false: Calculate button disabled (if results exist), results at full opacity
  bool _isDirty = true;  // Start dirty so first calculation is allowed

  // Provider Colors
  static const Color awsColor = Colors.orange;
  static const Color azureColor = Colors.blue;
  static const Color gcpColor = Colors.green;

  /// Get result from cache
  CalcResult? get _result => widget.cache.calcResult;

  @override
  void initState() {
    super.initState();
    _loadPricingStatus();
    
    // Debug: trace cache state on init
    debugPrint('[Step2Init] calcParams=${widget.cache.calcParams != null}, calcResult=${widget.cache.calcResult != null}, calcResultRaw=${widget.cache.calcResultRaw != null}');
    
    // Register calculate callback for header button
    widget.cache.onCalculateRequested = _calculate;
    
    // Load from cache first, then from DB if needed
    if (widget.cache.calcParams != null) {
      _params = widget.cache.calcParams;
      _loadingConfig = false;
      // If results already exist in cache, start with clean state
      if (widget.cache.calcResult != null) {
        _isDirty = false;
        widget.cache.isCalcDirty = false;
        debugPrint('[Step2Init] Using cached results, _isDirty=false');
      } else {
        debugPrint('[Step2Init] Params exist but NO results in cache!');
      }
    } else if (widget.twinId != null) {
      debugPrint('[Step2Init] No params in cache, loading from DB...');
      _loadOptimizerConfig();
    } else {
      // New twin, no config to load
      _loadingConfig = false;
      debugPrint('[Step2Init] New twin, no config to load');
    }
  }

  @override
  void dispose() {
    _sseSubscription?.cancel();
    widget.cache.onCalculateRequested = null;  // Unregister callback
    super.dispose();
  }

  /// Load saved optimizer config from backend (only if twinId exists)
  Future<void> _loadOptimizerConfig() async {
    if (widget.twinId == null) {
      setState(() => _loadingConfig = false);
      return;
    }
    
    try {
      final config = await _apiService.getOptimizerConfig(widget.twinId!);
      debugPrint('[LoadConfig] API response keys: ${config.keys}');
      debugPrint('[LoadConfig] params=${config['params'] != null}, result=${config['result'] != null}');
      if (config['params'] != null) {
        _params = CalcParams.fromJson(config['params']);
        widget.cache.calcParams = _params;
        debugPrint('[LoadConfig] Loaded params successfully');
      }
      if (config['result'] != null) {
        // Load result into cache
        widget.cache.calcResult = CalcResult.fromJson({'result': config['result']});
        widget.cache.calcResultRaw = {'result': config['result']};
        debugPrint('[LoadConfig] Loaded result successfully');
      } else {
        debugPrint('[LoadConfig] No result in API response');
      }
    } catch (e) {
      debugPrint('Failed to load optimizer config: $e');
    } finally {
      if (mounted) {
        setState(() {
          _loadingConfig = false;
          // If we loaded results, start with clean state
          if (widget.cache.calcResult != null) {
            _isDirty = false;
          }
        });
      }
    }
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

  /// Shows confirmation dialog before starting pricing refresh
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

    if (confirmed == true) {
      await _startStreamingRefresh(provider);
    }
  }

  /// Starts SSE-based pricing refresh with real-time log streaming
  Future<void> _startStreamingRefresh(String provider) async {
    setState(() {
      _isRefreshing = true;
      _refreshingProvider = provider;
      _refreshLogs = [];
    });

    final authToken = await _apiService.getAuthToken();
    final sseService = SseService(
      baseUrl: ApiService.baseUrl,  // Use same baseUrl as ApiService
      authToken: authToken,
    );

    _sseSubscription = sseService
        .streamRefreshPricing(provider, widget.twinId ?? '')
        .listen(
      (event) {
        if (!mounted) return;  // Check mounted before setState
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

  // Keep legacy method for compatibility (redirects to confirmation)
  Future<void> _refreshPricing(String provider) => _confirmRefresh(provider);

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
    widget.cache.isCalculating = true;
    widget.onCacheChanged();

    try {
      final response = await _apiService.calculateCosts(_params!.toJson());
      final result = CalcResult.fromJson(response);
      
      // Store in cache (not DB - only on Save Draft)
      widget.cache.calcParams = _params;
      widget.cache.calcResult = result;
      widget.cache.calcResultRaw = response;
      
      // Fetch pricing snapshots and store in cache
      await _cachePricingSnapshots();
      
      widget.cache.markDirty();
      
      setState(() {
        _isDirty = false;  // Results now match inputs - disable button
      });
      widget.cache.isCalcDirty = false;
      widget.onCacheChanged();
      
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Calculation failed: $e')),
        );
      }
    } finally {
      setState(() => _isCalculating = false);
      widget.cache.isCalculating = false;
      widget.onCacheChanged();
    }
  }
  
  /// Fetch pricing snapshots and store in cache (for later persistence)
  Future<void> _cachePricingSnapshots() async {
    final pricingSnapshots = <String, dynamic>{};
    final pricingTimestamps = <String, String?>{};
    
    final providers = ['aws', 'azure', 'gcp'];
    final exports = await Future.wait(
      providers.map((p) => _apiService.exportPricing(p).catchError((e) {
        debugPrint('Failed to export $p pricing: $e');
        return <String, dynamic>{};
      })),
    );
    
    for (var i = 0; i < providers.length; i++) {
      if (exports[i].isNotEmpty) {
        pricingSnapshots[providers[i]] = exports[i]['pricing'];
        pricingTimestamps[providers[i]] = exports[i]['updated_at'];
      }
    }
    
    widget.cache.pricingSnapshots = pricingSnapshots;
    widget.cache.pricingTimestamps = pricingTimestamps;
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1000), // Increased width slightly
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

              // Log Window (appears during/after refresh)
              if (_isRefreshing || _refreshLogs.isNotEmpty)
                _buildLogWindow(),

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
              if (_loadingConfig)
                const Center(child: CircularProgressIndicator())
              else
                CalcForm(
                  initialParams: _params ?? widget.cache.calcParams,
                  onChanged: (params) {
                    // Check if params actually changed (not just initial load)
                    final cachedParams = widget.cache.calcParams;
                    final paramsChanged = cachedParams == null || 
                        params.toJson().toString() != cachedParams.toJson().toString();
                    
                    setState(() {
                      _params = params;
                      if (paramsChanged) {
                        _isDirty = true;  // Inputs changed - results are now invalid
                      }
                    });
                    
                    // Sync params to cache
                    widget.cache.calcParams = params;
                    
                    // Only clear results if params actually changed (not on initial form load)
                    if (paramsChanged && widget.cache.calcResult != null) {
                      debugPrint('[CalcForm] Params changed, clearing stale results');
                      widget.cache.isCalcDirty = true;  // Sync dirty state for header button
                      widget.cache.calcResult = null;
                      widget.cache.calcResultRaw = null;
                      widget.cache.markDirty();
                      widget.onCacheChanged();
                    }
                  },
                ),

              const SizedBox(height: 24),

              // Results Section - only shown when results exist and are current
              if (_result != null) ...[
                const SizedBox(height: 64),
                
                // Header with Total Cost Summary on the right
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
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
                  ],
                ),
                
                const SizedBox(height: 8),
                const Divider(thickness: 2),
                const SizedBox(height: 24),
                
                // Total Cost Banner
                _buildTotalCost(_result!),
                
                // Warning for unconfigured providers
                if (_getUnconfiguredProviders().isNotEmpty) ...[
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.orange.shade50,
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.orange.shade300),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.warning_amber_rounded, color: Colors.orange.shade700, size: 28),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Unconfigured Provider(s) in Optimal Path',
                                style: TextStyle(
                                  fontWeight: FontWeight.bold,
                                  color: Colors.orange.shade800,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'The optimal path includes ${_getUnconfiguredProviders().join(", ")} which are not configured. '
                                'Return to Step 1 to add credentials before deploying.',
                                style: TextStyle(color: Colors.orange.shade900, fontSize: 13),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                
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
                Center(child: _buildCheapestPath(_result!.cheapestPath)),
                const SizedBox(height: 32),

                // Optimization Warnings (if any)
                if (_result!.l1OptimizationOverride != null) ...[
                  OptimizationWarning(layer: 'L1', optimizationOverride: _result!.l1OptimizationOverride!),
                  const SizedBox(height: 8),
                ],
                if (_result!.l2OptimizationOverride != null) ...[
                  OptimizationWarning(layer: 'L2', optimizationOverride: _result!.l2OptimizationOverride!),
                  const SizedBox(height: 8),
                ],
                if (_result!.l3OptimizationOverride != null) ...[
                  OptimizationWarning(layer: 'L3', optimizationOverride: _result!.l3OptimizationOverride!),
                  const SizedBox(height: 8),
                ],
                 if (_result!.l4OptimizationOverride != null) ...[
                  OptimizationWarning(layer: 'L4', optimizationOverride: _result!.l4OptimizationOverride!),
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
                        awsLayer: _result!.awsCosts.l1,
                        azureLayer: _result!.azureCosts.l1,
                        gcpLayer: _result!.gcpCosts.l1,
                        cheapestPath: _result!.cheapestPath,
                      ),
                    ),
                    SizedBox(
                      width: 300,
                      child: LayerCostCard(
                        layer: 'L2 - Processing',
                        awsLayer: _result!.awsCosts.l2,
                        azureLayer: _result!.azureCosts.l2,
                        gcpLayer: _result!.gcpCosts.l2,
                        cheapestPath: _result!.cheapestPath,
                      ),
                    ),
                    SizedBox(
                      width: 300,
                      child: LayerCostCard(
                        layer: 'L3 - Hot Storage',
                        awsLayer: _result!.awsCosts.l3Hot,
                        azureLayer: _result!.azureCosts.l3Hot,
                        gcpLayer: _result!.gcpCosts.l3Hot,
                        cheapestPath: _result!.cheapestPath,
                      ),
                    ),
                    SizedBox(
                      width: 300,
                      child: LayerCostCard(
                        layer: 'L3 - Cool Storage',
                        awsLayer: _result!.awsCosts.l3Cool,
                        azureLayer: _result!.azureCosts.l3Cool,
                        gcpLayer: _result!.gcpCosts.l3Cool,
                        cheapestPath: _result!.cheapestPath,
                      ),
                    ),
                    SizedBox(
                      width: 300,
                      child: LayerCostCard(
                        layer: 'L3 - Archive Storage',
                        awsLayer: _result!.awsCosts.l3Archive,
                        azureLayer: _result!.azureCosts.l3Archive,
                        gcpLayer: _result!.gcpCosts.l3Archive,
                        cheapestPath: _result!.cheapestPath,
                      ),
                    ),
                    SizedBox(
                      width: 300,
                      child: LayerCostCard(
                        layer: 'L4 - Twin Management',
                        awsLayer: _result!.awsCosts.l4,
                        azureLayer: _result!.azureCosts.l4,
                        gcpLayer: _result!.gcpCosts.l4,
                        cheapestPath: _result!.cheapestPath,
                        hideGcp: true, // GCP self-hosted L4 not implemented
                      ),
                    ),
                    SizedBox(
                      width: 300,
                      child: LayerCostCard(
                        layer: 'L5 - Visualization',
                        awsLayer: _result!.awsCosts.l5,
                        azureLayer: _result!.azureCosts.l5,
                        gcpLayer: _result!.gcpCosts.l5,
                        cheapestPath: _result!.cheapestPath,
                        hideGcp: true, // GCP self-hosted L5 not implemented
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
              ],

              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  /// Find providers in cheapest path that are not configured
  Set<String> _getUnconfiguredProviders() {
    if (_result == null) return {};
    final resultProviders = <String>{};
    for (final segment in _result!.cheapestPath) {
      final parts = segment.split('_');
      // L3_hot_GCP -> GCP, L1_AWS -> AWS
      if (parts.length >= 3 && segment.startsWith('L3')) {
        resultProviders.add(parts[2].toUpperCase());
      } else if (parts.length >= 2) {
        resultProviders.add(parts[1].toUpperCase());
      }
    }
    return resultProviders.difference(widget.cache.configuredProviders);
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

  /// Terminal-style log window for SSE refresh messages
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
    
    // Parse segment
    if (segment.startsWith('L3')) {
      // e.g. L3_hot_GCP, L3_cool_Azure
      if (parts.length >= 3) {
        layer = 'L3 ${parts[1]}'; // L3 hot
        provider = parts[2];      // GCP
      } else {
        layer = parts[0];
        provider = parts.length > 1 ? parts[1] : '?';
      }
    } else {
      // e.g. L1_AWS
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
