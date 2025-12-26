import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'step1_configuration.dart';
import 'step2_optimizer.dart';
import '../../providers/twins_provider.dart';
import '../../providers/theme_provider.dart';

class WizardScreen extends ConsumerStatefulWidget {
  final String? twinId; // null for new, set for edit
  
  const WizardScreen({super.key, this.twinId});
  
  @override
  ConsumerState<WizardScreen> createState() => _WizardScreenState();
}

class _WizardScreenState extends ConsumerState<WizardScreen> {
  int _currentStep = 0;
  String? _activeTwinId;
  bool _isCreatingTwin = false;
  bool _isLoading = false;
  
  @override
  void initState() {
    super.initState();
    _activeTwinId = widget.twinId;
    if (_activeTwinId != null) {
      _loadTwinStatus();
    }
  }

  Future<void> _loadTwinStatus() async {
    setState(() => _isLoading = true);
    try {
      final api = ref.read(apiServiceProvider);
      
      // Fetch twin state and config in parallel
      final results = await Future.wait([
        api.getTwin(_activeTwinId!),
        api.getTwinConfig(_activeTwinId!),
      ]);
      
      final twin = results[0];
      final config = results[1];
      final state = twin['state'];
      
      if (mounted) {
        setState(() {
          if (state == 'deployed') {
            _currentStep = 2; // Deployer
          } else if (state == 'configured') {
            _currentStep = 2; // Deployer (Ready to deploy)
          } else {
            // State is 'draft' (or error/inactive)
            // Check if we have valid credentials to determine if we can skip Step 1
            bool hasCredentials = false;
            
            // Check AWS
            final aws = config['aws'] as Map<String, dynamic>?;
            if (aws != null && aws['access_key_id']?.toString().isNotEmpty == true) {
              hasCredentials = true;
            }
            
            // Check Azure
            final azure = config['azure'] as Map<String, dynamic>?;
            if (!hasCredentials) {
              if (azure != null && azure['subscription_id']?.toString().isNotEmpty == true) {
                hasCredentials = true;
              }
            }
            
            // Check GCP
            final gcp = config['gcp'] as Map<String, dynamic>?;
            if (!hasCredentials) {
              if (gcp != null && gcp['project_id']?.toString().isNotEmpty == true) {
                hasCredentials = true;
              }
            }
            
            if (hasCredentials) {
              _currentStep = 1; // Optimizer (Step 1 completed)
            } else {
              _currentStep = 0; // Configuration
            }
          }
        });
      }
    } catch (e) {
      debugPrint('Error loading twin status: $e');
      // Default to Step 1 on error
      if (mounted) setState(() => _currentStep = 0);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }
  
  Future<String> _createTwinIfNeeded(String name) async {
    if (_activeTwinId != null) return _activeTwinId!;
    
    setState(() => _isCreatingTwin = true);
    try {
      final api = ref.read(apiServiceProvider);
      final result = await api.createTwin(name);
      _activeTwinId = result['id'];
      return _activeTwinId!;
    } finally {
      setState(() => _isCreatingTwin = false);
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
                  onPressed: () => context.go('/dashboard'),
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
    final isCompleted = _currentStep > index;
    
    return Column(
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
          ),
        ),
      ],
    );
  }
  
  Widget _buildConnector(int afterIndex) {
    final isActive = _currentStep > afterIndex;
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
          isCreatingTwin: _isCreatingTwin,
          onCreateTwin: _createTwinIfNeeded,
          onNext: () => setState(() => _currentStep = 1),
          onSaveDraft: () {
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Draft saved!')),
            );
          },
        );
      case 1:
        if (_activeTwinId == null) {
          return const Center(
            child: Text('Please complete Step 1 first to create a twin'),
          );
        }
        return Step2Optimizer(
          twinId: _activeTwinId!,
          onNext: () => setState(() => _currentStep = 2),
          onBack: () => setState(() => _currentStep = 0),
        );
      case 2:
        return const Center(child: Text('Step 3: Deployer (Sprint 4)'));
      default:
        return const SizedBox();
    }
  }
}
