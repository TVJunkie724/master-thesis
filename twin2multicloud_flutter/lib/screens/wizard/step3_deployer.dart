import 'package:flutter/material.dart';
import '../../models/wizard_cache.dart';
import '../../models/calc_result.dart';
import '../../widgets/architecture_graph.dart';

/// Step 3: Deployer Configuration
/// 
/// Displays the architecture view (left) and file editor placeholders (right).
/// Architecture view uses graphview for proper flowchart visualization.
class Step3Deployer extends StatefulWidget {
  final String? twinId;
  final WizardCache cache;
  final bool isSaving;
  final VoidCallback onBack;
  final Future<bool> Function() onSaveDraft;
  final VoidCallback onCacheChanged;
  final VoidCallback onFinish;

  const Step3Deployer({
    super.key,
    required this.twinId,
    required this.cache,
    required this.isSaving,
    required this.onBack,
    required this.onSaveDraft,
    required this.onCacheChanged,
    required this.onFinish,
  });

  @override
  State<Step3Deployer> createState() => _Step3DeployerState();
}

class _Step3DeployerState extends State<Step3Deployer> {
  // Colors
  static const Color editableColor = Color(0xFFD81B60); // Dark pink for editable

  CalcResult? get _result => widget.cache.calcResult;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: _buildNavigationButtons(),
        ),
        const Divider(height: 1),
        Expanded(
          child: _result == null
              ? _buildNoResultMessage()
              : Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    // Architecture View (graphview flowchart)
                    Expanded(
                      flex: 1,
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: ArchitectureGraph(
                          calcResult: widget.cache.calcResult,
                          calcParams: widget.cache.calcParams,
                        ),
                      ),
                    ),
                    const VerticalDivider(width: 1),
                    // File Editors
                    Expanded(
                      flex: 2,
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.all(24),
                        child: _buildFileEditors(),
                      ),
                    ),
                  ],
                ),
        ),
      ],
    );
  }

  Widget _buildNoResultMessage() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.warning_amber_rounded, size: 64, color: Colors.orange.shade400),
          const SizedBox(height: 16),
          Text('No Optimization Result', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('Please complete Step 2 (Optimizer) first.', style: TextStyle(color: Colors.grey.shade600)),
          const SizedBox(height: 24),
          OutlinedButton.icon(onPressed: widget.onBack, icon: const Icon(Icons.arrow_back), label: const Text('Back')),
        ],
      ),
    );
  }

  Widget _buildFileEditors() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.edit_document, size: 24, color: Theme.of(context).primaryColor),
            const SizedBox(width: 12),
            Text('Configuration', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
          ],
        ),
        const SizedBox(height: 8),
        Text('Upload custom code and configuration files', style: TextStyle(fontSize: 13, color: Colors.grey.shade600)),
        const SizedBox(height: 24),
        _buildFilePlaceholder('processors/', 'User processor functions (L2)', Icons.code, isHighlighted: true),
        const SizedBox(height: 16),
        _buildFilePlaceholder('config_grafana.json', 'Grafana dashboard config', Icons.dashboard),
        const SizedBox(height: 16),
        _buildFilePlaceholder('payloads.json', 'Device payload schemas', Icons.data_object),
        const SizedBox(height: 28),
        Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.blue.shade50,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: Colors.blue.shade200),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.info_outline, color: Colors.blue.shade700, size: 20),
              const SizedBox(width: 12),
              Expanded(child: Text('File editors coming soon. Click "Finish Configuration" to proceed.', style: TextStyle(color: Colors.blue.shade800, fontSize: 13))),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildFilePlaceholder(String filename, String description, IconData icon, {bool isHighlighted = false}) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isHighlighted ? editableColor.withAlpha(12) : Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: isHighlighted ? editableColor.withAlpha(120) : Colors.grey.shade300),
      ),
      child: Row(
        children: [
          Icon(icon, color: isHighlighted ? editableColor : Colors.grey.shade600, size: 22),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(filename, style: TextStyle(fontWeight: FontWeight.w600, fontFamily: 'monospace', fontSize: 14, color: isHighlighted ? editableColor : null)),
                const SizedBox(height: 2),
                Text(description, style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(color: Colors.grey.shade200, borderRadius: BorderRadius.circular(4)),
            child: Text('Soon', style: TextStyle(color: Colors.grey.shade600, fontSize: 11)),
          ),
        ],
      ),
    );
  }

  Widget _buildNavigationButtons() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        OutlinedButton.icon(onPressed: widget.onBack, icon: const Icon(Icons.arrow_back), label: const Text('Back')),
        Row(
          children: [
            OutlinedButton.icon(
              onPressed: widget.isSaving ? null : () async { await widget.onSaveDraft(); },
              icon: Stack(
                clipBehavior: Clip.none,
                children: [
                  widget.isSaving ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.save),
                  if (widget.cache.hasUnsavedChanges && !widget.isSaving)
                    Positioned(right: -4, top: -4, child: Container(width: 10, height: 10, decoration: const BoxDecoration(color: Colors.orange, shape: BoxShape.circle))),
                ],
              ),
              label: const Text('Save Draft'),
            ),
            const SizedBox(width: 16),
            ElevatedButton.icon(
              onPressed: _result != null ? widget.onFinish : null,
              icon: const Icon(Icons.check_circle),
              label: const Text('Finish Configuration'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
            ),
          ],
        ),
      ],
    );
  }
}
