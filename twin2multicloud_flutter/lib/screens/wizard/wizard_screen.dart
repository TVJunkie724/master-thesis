import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:dio/dio.dart';
import 'step1_configuration.dart';
import 'step2_optimizer.dart';
import 'step3_deployer.dart';
import '../../providers/twins_provider.dart';
import '../../providers/theme_provider.dart';
import '../../models/wizard_cache.dart';

class WizardScreen extends ConsumerStatefulWidget {
  final String? twinId; // null for new, set for edit
  
  const WizardScreen({super.key, this.twinId});
  
  @override
  ConsumerState<WizardScreen> createState() => _WizardScreenState();
}

class _WizardScreenState extends ConsumerState<WizardScreen> {
  int _currentStep = 0;
  int _highestStepReached = 0; // Tracks maximum step visited for navigation
  String? _activeTwinId;
  bool _isLoading = false;
  bool _isSaving = false;
  String? _nameError; // Error message for duplicate name
  
  // In-memory cache for all wizard data
  final WizardCache _cache = WizardCache();
  
  @override
  void initState() {
    super.initState();
    _activeTwinId = widget.twinId;
    if (_activeTwinId != null) {
      _loadExistingTwinData();
    }
  }

  /// Load existing twin data from database into cache (for editing)
  Future<void> _loadExistingTwinData() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      
      // Fetch twin details and config in parallel
      final results = await Future.wait([
        api.getTwin(_activeTwinId!),
        api.getTwinConfig(_activeTwinId!),
      ]);
      
      final twin = results[0];
      final config = results[1];
      final state = twin['state'];
      
      if (mounted) {
        setState(() {
          // Populate cache from database
          _cache.twinName = twin['name'];
          _cache.debugMode = config['debug_mode'] ?? false;
          
          // Parse AWS - mark as valid AND inherited if configured
          if (config['aws_configured'] == true) {
            _cache.awsCredentials = {
              'region': config['aws_region']?.toString() ?? 'eu-central-1',
              'sso_region': config['aws_sso_region']?.toString() ?? '',
              'access_key_id': '', // Secrets hidden by backend
              'secret_access_key': '',
              'session_token': '',
            };
            _cache.markAwsInherited(); // Mark as inherited from DB
          }
          
          // Parse Azure - mark as valid AND inherited if configured
          if (config['azure_configured'] == true) {
            _cache.azureCredentials = {
              'region': config['azure_region']?.toString() ?? '',
              'subscription_id': '',
              'client_id': '',
              'client_secret': '',
              'tenant_id': '',
            };
            _cache.markAzureInherited(); // Mark as inherited from DB
          }
          
          // Parse GCP - mark as valid AND inherited if configured
          if (config['gcp_configured'] == true) {
            _cache.gcpCredentials = {
              'project_id': config['gcp_project_id']?.toString() ?? '',
              'region': config['gcp_region']?.toString() ?? '',
              'billing_account': '',
            };
            _cache.markGcpInherited(); // Mark as inherited from DB
          }
          
          // Determine starting step based on state
          if (state == 'deployed' || state == 'configured') {
            _currentStep = 2; // Deployer
            _highestStepReached = 2;
          } else if (_cache.canProceedToStep2) {
            _currentStep = 1; // Optimizer
            _highestStepReached = 1;
          } else {
            _currentStep = 0; // Configuration
            _highestStepReached = 0;
          }
        });
      }
    } catch (e) {
      debugPrint('Error loading twin data: $e');
      if (mounted) setState(() => _currentStep = 0);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  /// Save all cached data to database
  Future<bool> _saveDraftToDatabase() async {
    if (_cache.twinName?.isEmpty ?? true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Please enter a name for your Digital Twin'),
          backgroundColor: Colors.red,
        ),
      );
      return false;
    }
    
    setState(() => _isSaving = true);
    
    try {
      final api = ref.read(apiServiceProvider);
      
      // Step 1: Create twin if it doesn't exist, or update name if changed
      if (_activeTwinId == null) {
        final result = await api.createTwin(_cache.twinName!);
        _activeTwinId = result['id'];
      } else {
        // Update twin name if it has changed
        await api.updateTwin(_activeTwinId!, name: _cache.twinName);
      }
      
      // Step 2: Save Step 1 config (credentials)
      // IMPORTANT: Only send credentials if they were NEWLY ENTERED
      // Inherited credentials are already encrypted in DB - don't overwrite with empty values
      final configData = <String, dynamic>{'debug_mode': _cache.debugMode};
      
      // AWS credentials - only if newly entered
      if (_cache.hasNewAwsCredentials && 
          _cache.awsCredentials['access_key_id']?.isNotEmpty == true) {
        final awsConfig = {
          'access_key_id': _cache.awsCredentials['access_key_id'],
          'secret_access_key': _cache.awsCredentials['secret_access_key'],
          'region': _cache.awsCredentials['region'] ?? 'eu-central-1',
          'sso_region': _cache.awsCredentials['sso_region'],
        };
        if (_cache.awsCredentials['session_token']?.isNotEmpty == true) {
          awsConfig['session_token'] = _cache.awsCredentials['session_token']!;
        }
        configData['aws'] = awsConfig;
      }
      
      // Azure credentials - only if newly entered
      if (_cache.hasNewAzureCredentials &&
          _cache.azureCredentials['subscription_id']?.isNotEmpty == true) {
        configData['azure'] = {
          'subscription_id': _cache.azureCredentials['subscription_id'],
          'client_id': _cache.azureCredentials['client_id'],
          'client_secret': _cache.azureCredentials['client_secret'],
          'tenant_id': _cache.azureCredentials['tenant_id'],
          'region': _cache.azureCredentials['region'] ?? '',
        };
      }
      
      // GCP credentials - only if newly entered
      if (_cache.hasNewGcpCredentials && (
          _cache.gcpCredentials['project_id']?.isNotEmpty == true || 
          _cache.gcpCredentials['billing_account']?.isNotEmpty == true ||
          _cache.gcpServiceAccountJson != null)) {
        configData['gcp'] = {
          'project_id': _cache.gcpCredentials['project_id'],
          'billing_account': _cache.gcpCredentials['billing_account'],
          'region': _cache.gcpCredentials['region'] ?? '',
          'service_account_json': _cache.gcpServiceAccountJson,
        };
      }
      
      await api.updateTwinConfig(_activeTwinId!, configData);
      
      // Step 3: Save Step 2 optimizer data (if exists)
      if (_cache.calcResult != null && _cache.calcResultRaw != null) {
        await api.saveOptimizerResult(
          _activeTwinId!,
          params: _cache.calcParams?.toJson() ?? {},
          result: _cache.calcResultRaw!['result'],
          cheapestPath: _parseCheapestPath(_cache.calcResult!.cheapestPath),
          pricingSnapshots: _cache.pricingSnapshots ?? {},
          pricingTimestamps: _cache.pricingTimestamps ?? {},
        );
      }
      
      // Mark cache as clean after successful save
      _cache.markClean();
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Draft saved!')),
        );
      }
      
      return true;
    } on DioException catch (e) {
      debugPrint('Failed to save draft: $e');
      if (mounted) {
        // Handle 409 Conflict (duplicate name)
        if (e.response?.statusCode == 409) {
          final detail = e.response?.data['detail'] ?? 'A twin with this name already exists';
          setState(() => _nameError = detail);
          await showDialog(
            context: context,
            builder: (ctx) => AlertDialog(
              icon: Icon(Icons.error_outline, color: Colors.red.shade400, size: 48),
              title: const Text('Duplicate Name'),
              content: Text(detail),
              actions: [
                FilledButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('OK'),
                ),
              ],
            ),
          );
        } else {
          // Other errors - show snackbar
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Failed to save: ${e.message}'),
              backgroundColor: Colors.red,
            ),
          );
        }
      }
      return false;
    } catch (e) {
      debugPrint('Failed to save draft: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
      return false;
    } finally {
      if (mounted) setState(() => _isSaving = false);
    }
  }
  
  /// Parse cheapest path array to dict format for API
  Map<String, String?> _parseCheapestPath(List<String> path) {
    final result = <String, String?>{
      'l1': null, 'l2': null, 'l3_hot': null, 
      'l3_cool': null, 'l3_archive': null, 'l4': null, 'l5': null,
    };
    for (final segment in path) {
      final parts = segment.split('_');
      if (parts.isEmpty) continue;
      
      final layer = parts[0].toUpperCase();
      
      if (layer == 'L3' && parts.length >= 3) {
        final tier = parts[1].toLowerCase();
        result['l3_$tier'] = parts[2].toUpperCase();
      } else if (parts.length >= 2) {
        result[layer.toLowerCase()] = parts[1].toUpperCase();
      }
    }
    return result;
  }

  Future<void> _showExitConfirmation(BuildContext context) async {
    // If no unsaved changes, just exit
    if (!_cache.hasUnsavedChanges) {
      _cache.clear();
      ref.invalidate(twinsProvider); // Refresh twins list on dashboard
      context.go('/dashboard');
      return;
    }
    
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Leave Wizard?'),
        content: const Text(
          'You have unsaved changes. What would you like to do?'
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, 'cancel'),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, 'discard'),
            child: const Text('Discard Changes'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, 'save'),
            child: const Text('Save Draft'),
          ),
        ],
      ),
    );

    if (!context.mounted) return;

    switch (result) {
      case 'discard':
        _cache.clear();
        ref.invalidate(twinsProvider); // Refresh twins list on dashboard
        context.go('/dashboard');
        break;
      case 'save':
        final saved = await _saveDraftToDatabase();
        if (saved && context.mounted) {
          _cache.clear();
          ref.invalidate(twinsProvider); // Refresh twins list on dashboard
          context.go('/dashboard');
        }
        break;
      case 'cancel':
      default:
        // Do nothing, stay on page
        break;
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Twin2MultiCloud'),
        automaticallyImplyLeading: false,
        backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
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
          const CircleAvatar(child: Icon(Icons.person)),
          const SizedBox(width: 16),
        ],
      ),
      body: Column(
        children: [
          // Screen-specific header with title and close button
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
            child: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => _showExitConfirmation(context),
                  tooltip: 'Close',
                ),
                const SizedBox(width: 8),
                Text(
                  _activeTwinId == null ? 'Create Digital Twin' : 'Edit Digital Twin',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
              ],
            ),
          ),
          _buildStepIndicator(),
          const Divider(height: 1),
          Expanded(
            child: _isLoading 
              ? const Center(child: CircularProgressIndicator())
              : _buildStepContent(),
          ),
        ],
      ),
    );
  }
  
  Widget _buildStepIndicator() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          _buildStep(0, 'Configuration', Icons.settings),
          _buildConnector(0),
          _buildStep(1, 'Optimizer', Icons.analytics),
          _buildConnector(1),
          _buildStep(2, 'Deployer', Icons.cloud_upload),
        ],
      ),
    );
  }
  
  Widget _buildStep(int index, String label, IconData icon) {
    final isActive = _currentStep == index;
    final isCompleted = _highestStepReached > index;
    
    return InkWell(
      onTap: () {
        // Only allow navigation to previously reached steps or the current step
        if (index <= _highestStepReached) {
          setState(() => _currentStep = index);
        }
      },
      borderRadius: BorderRadius.circular(20),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Column(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isCompleted 
                  ? Colors.green 
                  : isActive 
                    ? Theme.of(context).colorScheme.primary 
                    : (index <= _highestStepReached)
                      ? Theme.of(context).colorScheme.primary.withAlpha(150)
                      : Colors.grey.shade300,
              ),
              child: Icon(
                isCompleted ? Icons.check : icon,
                color: Colors.white,
                size: 20,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 12,
                fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
                color: index <= _highestStepReached 
                  ? null 
                  : Colors.grey.shade500,
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildConnector(int afterIndex) {
    final isActive = _highestStepReached > afterIndex;
    return Container(
      width: 60,
      height: 2,
      margin: const EdgeInsets.only(bottom: 20),
      color: isActive ? Colors.green : Colors.grey.shade300,
    );
  }
  
  Widget _buildStepContent() {
    switch (_currentStep) {
      case 0:
        return Step1Configuration(
          twinId: _activeTwinId,
          cache: _cache,
          isSaving: _isSaving,
          nameError: _nameError,
          onNext: () => setState(() {
            _currentStep = 1;
            if (_highestStepReached < 1) _highestStepReached = 1;
          }),
          onBack: () => _showExitConfirmation(context),
          onSaveDraft: _saveDraftToDatabase,
          onCacheChanged: () => setState(() {}),  // Trigger rebuild to update UI
          onNameErrorClear: () => setState(() => _nameError = null),
        );
      case 1:
        return Step2Optimizer(
          twinId: _activeTwinId,
          cache: _cache,
          isSaving: _isSaving,
          onNext: () => setState(() {
            _currentStep = 2;
            if (_highestStepReached < 2) _highestStepReached = 2;
          }),
          onBack: () => setState(() => _currentStep = 0),
          onSaveDraft: _saveDraftToDatabase,
          onCacheChanged: () => setState(() {}),
        );
      case 2:
        return Step3Deployer(
          twinId: _activeTwinId,
          cache: _cache,
          isSaving: _isSaving,
          onBack: () => setState(() => _currentStep = 1),
          onSaveDraft: _saveDraftToDatabase,
          onCacheChanged: () => setState(() {}),
          onFinish: () async {
            // Save and navigate to dashboard on finish
            final saved = await _saveDraftToDatabase();
            if (saved && mounted) {
              _cache.step3Complete = true;
              _cache.clear();
              ref.invalidate(twinsProvider);
              context.go('/dashboard');
            }
          },
        );
      default:
        return const SizedBox();
    }
  }
}
