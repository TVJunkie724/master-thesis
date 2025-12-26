import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'step1_configuration.dart';
import '../../providers/twins_provider.dart';

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
  
  @override
  void initState() {
    super.initState();
    _activeTwinId = widget.twinId;
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
        title: Text(_activeTwinId == null ? 'Create Digital Twin' : 'Edit Digital Twin'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.go('/dashboard'),
        ),
      ),
      body: Column(
        children: [
          _buildStepIndicator(),
          const Divider(height: 1),
          Expanded(child: _buildStepContent()),
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
        return const Center(child: Text('Step 2: Optimizer (Sprint 3)'));
      case 2:
        return const Center(child: Text('Step 3: Deployer (Sprint 4)'));
      default:
        return const SizedBox();
    }
  }
}
