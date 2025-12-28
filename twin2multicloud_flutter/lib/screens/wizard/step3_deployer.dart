import 'package:flutter/material.dart';
import '../../models/wizard_cache.dart';
import '../../models/calc_result.dart';
import '../../theme/colors.dart';

/// Step 3: Deployer Configuration
/// 
/// Displays the architecture view (left) and file editor placeholders (right).
/// Architecture view shows a real flowchart with individual component boxes.
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
  static const Color systemColor = Color(0xFF78909C); // Blue-grey for system components
  static const Color glueColor = Color(0xFF78909C); // Same grey for glue (system-managed)

  CalcResult? get _result => widget.cache.calcResult;
  
  Map<String, String> get _layerProviders {
    final result = <String, String>{};
    if (_result == null) return result;
    
    for (final segment in _result!.cheapestPath) {
      final parts = segment.split('_');
      if (parts.isEmpty) continue;
      final layer = parts[0].toUpperCase();
      if (layer == 'L3' && parts.length >= 3) {
        result['${layer}_${parts[1]}'] = parts[2].toUpperCase();
      } else if (parts.length >= 2) {
        result[layer] = parts[1].toUpperCase();
      }
    }
    return result;
  }

  bool _hasCrossCloudBoundary(String layer1, String layer2) {
    final providers = _layerProviders;
    final p1 = providers[layer1];
    final p2 = providers[layer2];
    return p1 != null && p2 != null && p1 != p2;
  }

  Color _getProviderColor(String? provider) {
    if (provider == null) return systemColor;
    return AppColors.getProviderColor(provider);
  }
  
  String _getProviderLabel(String? provider) {
    if (provider == null) return 'N/A';
    switch (provider.toUpperCase()) {
      case 'AWS': return 'AWS';
      case 'AZURE': return 'Azure';
      case 'GCP': return 'GCP';
      default: return provider;
    }
  }

  String _getL1Service(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'IoT Core', 'AZURE' => 'IoT Hub', 'GCP' => 'Pub/Sub', _ => 'IoT' };
  String _getL3HotService(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'DynamoDB', 'AZURE' => 'Cosmos DB', 'GCP' => 'Firestore', _ => 'Hot DB' };
  String _getL3ColdService(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'S3 IA', 'AZURE' => 'Blob Cool', 'GCP' => 'Nearline', _ => 'Cold' };
  String _getL3ArchiveService(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'Glacier', 'AZURE' => 'Archive', 'GCP' => 'Coldline', _ => 'Archive' };
  String _getL4Service(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'TwinMaker', 'AZURE' => 'ADT', _ => 'Twin' };
  String _getL5Service(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'Managed Grafana', 'AZURE' => 'Managed Grafana', _ => 'Grafana' };

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
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      flex: 1,
                      child: SingleChildScrollView(
                        padding: const EdgeInsets.all(16),
                        child: _buildArchitectureView(),
                      ),
                    ),
                    const VerticalDivider(width: 1),
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

  Widget _buildArchitectureView() {
    final layers = _layerProviders;
    
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 320),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            // Header
            Text('Data Flow', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 4),
            Text('Component architecture', style: TextStyle(fontSize: 12, color: Colors.grey.shade500)),
            const SizedBox(height: 20),
            
            // IoT Devices (source)
            _buildSourceBox('IoT Devices', Icons.sensors),
            _buildArrow(),
            
            // L1 Layer Card
            _buildLayerCard('L1', 'Data Acquisition', layers['L1'], [
              _buildComponentBox(_getL1Service(layers['L1']), layers['L1'], Icons.router),
              _buildArrow(small: true),
              _buildComponentBox('Dispatcher', layers['L1'], Icons.call_split),
              // Connector glue is deployed in L1 when sending to another cloud
              if (_hasCrossCloudBoundary('L1', 'L2')) ...[
                _buildArrow(small: true),
                _buildGlueComponentBox('Connector', layers['L1']),
              ],
            ]),
            _buildArrow(),
            
            // L2 Layer Card (EDITABLE)
            _buildLayerCard('L2', 'Processing', layers['L2'], [
              // Ingestion glue is deployed in L2 when receiving from another cloud
              if (_hasCrossCloudBoundary('L1', 'L2')) ...[
                _buildGlueComponentBox('Ingestion', layers['L2']),
                _buildArrow(small: true),
              ],
              _buildComponentBox('Persister', layers['L2'], Icons.save),
              _buildArrow(small: true),
              _buildComponentBox('Processor Wrapper', layers['L2'], Icons.hub),
              _buildArrow(small: true),
              _buildEditableComponentBox('User Processors', Icons.code),
              // Hot Writer glue is deployed in L2 when sending to another cloud for L3
              if (_hasCrossCloudBoundary('L2', 'L3_hot')) ...[
                _buildArrow(small: true),
                _buildGlueComponentBox('Hot Writer', layers['L2']),
              ],
            ], isEditable: true),
            _buildArrow(),
            
            // L3 Layer Card (Storage)
            _buildLayerCard('L3', 'Storage', null, [
              // Hot Reader glue deployed in L3 hot provider when L4 is different
              if (_hasCrossCloudBoundary('L2', 'L3_hot')) ...[
                _buildGlueComponentBox('Hot Receiver', layers['L3_hot']),
                _buildArrow(small: true),
              ],
              _buildStorageBox('Hot', _getL3HotService(layers['L3_hot']), layers['L3_hot']),
              _buildArrow(small: true),
              if (_hasCrossCloudBoundary('L3_hot', 'L3_cool')) ...[
                _buildGlueComponentBox('Cold Writer', layers['L3_hot']),
                _buildArrow(small: true),
                _buildGlueComponentBox('Cold Receiver', layers['L3_cool']),
                _buildArrow(small: true),
              ],
              _buildStorageBox('Cool', _getL3ColdService(layers['L3_cool']), layers['L3_cool']),
              _buildArrow(small: true),
              if (_hasCrossCloudBoundary('L3_cool', 'L3_archive')) ...[
                _buildGlueComponentBox('Archive Writer', layers['L3_cool']),
                _buildArrow(small: true),
                _buildGlueComponentBox('Archive Receiver', layers['L3_archive']),
                _buildArrow(small: true),
              ],
              _buildStorageBox('Archive', _getL3ArchiveService(layers['L3_archive']), layers['L3_archive']),
            ], isStorage: true),
            _buildArrow(),
            
            // L4 Layer Card
            _buildLayerCard('L4', 'Twin Management', layers['L4'], [
              _buildComponentBox(_getL4Service(layers['L4']), layers['L4'], Icons.hub),
              _buildArrow(small: true),
              _buildComponentBox('State Sync', layers['L4'], Icons.sync),
            ]),
            _buildArrow(),
            
            // L5 Layer Card
            _buildLayerCard('L5', 'Visualization', layers['L5'], [
              _buildComponentBox(_getL5Service(layers['L5']), layers['L5'], Icons.dashboard),
            ]),
            
            const SizedBox(height: 20),
            _buildLegend(),
          ],
        ),
      ),
    );
  }

  /// Source node (IoT devices)
  Widget _buildSourceBox(String name, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.grey.shade200,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade400),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: Colors.grey.shade700),
          const SizedBox(width: 10),
          Text(name, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.grey.shade800)),
        ],
      ),
    );
  }

  /// Layer card container with components inside
  Widget _buildLayerCard(String layer, String title, String? provider, List<Widget> components, {bool isEditable = false, bool isStorage = false}) {
    // Layer card always uses provider color (or neutral grey for storage since it spans providers)
    final color = isStorage ? systemColor : _getProviderColor(provider);
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withAlpha(12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withAlpha(100), width: 1),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          // Layer header
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(layer, style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(width: 10),
              Text(title, style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: color)),
              if (isEditable) ...[
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                  decoration: BoxDecoration(color: editableColor, borderRadius: BorderRadius.circular(3)),
                  child: const Text('EDIT', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
                ),
              ],
              if (provider != null && !isStorage) ...[
                const SizedBox(width: 10),
                _buildProviderChip(provider),
              ],
            ],
          ),
          const SizedBox(height: 12),
          // Components flow (centered)
          ...components,
        ],
      ),
    );
  }

  /// Individual component box (grey, system-managed)
  Widget _buildComponentBox(String name, String? provider, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: systemColor.withAlpha(120)),
        boxShadow: [BoxShadow(color: Colors.black.withAlpha(15), blurRadius: 3, offset: const Offset(0, 1))],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: systemColor),
          const SizedBox(width: 10),
          Text(name, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Colors.grey.shade800)),
        ],
      ),
    );
  }

  /// Editable component box (dark pink, highlighted)
  Widget _buildEditableComponentBox(String name, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: editableColor.withAlpha(25),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: editableColor, width: 2),
        boxShadow: [BoxShadow(color: editableColor.withAlpha(30), blurRadius: 6, offset: const Offset(0, 2))],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 20, color: editableColor),
          const SizedBox(width: 12),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: editableColor)),
              Text('Upload code', style: TextStyle(fontSize: 11, color: editableColor.withAlpha(180))),
            ],
          ),
        ],
      ),
    );
  }

  /// Glue component box (grey, labeled as GLUE)
  Widget _buildGlueComponentBox(String name, String? provider) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: glueColor.withAlpha(20),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: glueColor, style: BorderStyle.solid),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.swap_horiz, size: 16, color: glueColor),
          const SizedBox(width: 8),
          Text(name, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: Colors.grey.shade700)),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
            decoration: BoxDecoration(color: glueColor, borderRadius: BorderRadius.circular(3)),
            child: const Text('GLUE', style: TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  /// Storage tier box with provider chip
  Widget _buildStorageBox(String tier, String service, String? provider) {
    final color = _getProviderColor(provider);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withAlpha(120)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$tier:', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.grey.shade700)),
          const SizedBox(width: 8),
          Text(service, style: TextStyle(fontSize: 13, color: Colors.grey.shade800)),
          const SizedBox(width: 10),
          _buildProviderChip(provider),
        ],
      ),
    );
  }

  Widget _buildProviderChip(String? provider) {
    final color = _getProviderColor(provider);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(10)),
      child: Text(_getProviderLabel(provider), style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
    );
  }

  /// Arrow between components
  Widget _buildArrow({bool small = false}) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: small ? 4 : 6),
      child: Icon(Icons.arrow_downward, color: Colors.grey.shade400, size: small ? 16 : 20),
    );
  }

  Widget _buildLegend() {
    return Wrap(
      spacing: 12,
      runSpacing: 6,
      alignment: WrapAlignment.center,
      children: [
        _buildLegendItem('AWS', AppColors.aws),
        _buildLegendItem('Azure', AppColors.azure),
        _buildLegendItem('GCP', AppColors.gcp),
        _buildLegendItem('Editable', editableColor),
        _buildLegendItem('Glue', glueColor),
      ],
    );
  }

  Widget _buildLegendItem(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 12, height: 12, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3))),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
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
