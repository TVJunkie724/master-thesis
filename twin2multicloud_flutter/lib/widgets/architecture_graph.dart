import 'package:flutter/material.dart';
import '../models/calc_result.dart';
import '../models/calc_params.dart';
import '../theme/colors.dart';

/// Hybrid architecture view with layer boxes and graphview for L2 branching.
/// 
/// Uses Column/Row for structured layer boxes (L1-L5) but graphview 
/// for the complex branching inside L2.
class ArchitectureGraph extends StatefulWidget {
  final CalcResult? calcResult;
  final CalcParams? calcParams;

  const ArchitectureGraph({
    super.key,
    required this.calcResult,
    required this.calcParams,
  });

  @override
  State<ArchitectureGraph> createState() => _ArchitectureGraphState();
}

class _ArchitectureGraphState extends State<ArchitectureGraph> {
  // Colors
  static const Color editableColor = Color(0xFFD81B60);
  static const Color systemColor = Color(0xFF78909C);
  static const Color glueColor = Color(0xFF78909C);

  Map<String, String> get _layerProviders {
    final result = <String, String>{};
    if (widget.calcResult == null) return result;
    
    for (final segment in widget.calcResult!.cheapestPath) {
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

  @override
  Widget build(BuildContext context) {
    if (widget.calcResult == null) {
      return const Center(child: Text('No optimization result'));
    }

    final layers = _layerProviders;

    return SingleChildScrollView(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 500),
          child: Column(
            children: [
              Text('Data Flow', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text('Component architecture', style: TextStyle(fontSize: 12, color: Colors.grey.shade500)),
              const SizedBox(height: 20),
              
              // L1 - Data Acquisition (includes IoT Devices)
              _buildLayerCard('L1', 'Data Acquisition', layers['L1'], [
                _buildEditableSourceBox('IoT Devices', Icons.sensors),
                _buildArrow(small: true),
                _buildComponentBox(_getL1Service(layers['L1']), layers['L1'], Icons.router),
                _buildArrow(small: true),
                _buildComponentBox('Dispatcher', layers['L1'], Icons.call_split),
                if (_hasCrossCloudBoundary('L1', 'L2')) ...[
                  _buildArrow(small: true),
                  _buildGlueComponentBox('Connector', layers['L1']),
                ],
              ]),
              _buildArrow(),
              
              // L2 - Processing (with graphview for branching)
              _buildL2LayerWithGraphview(layers),
              _buildArrow(),
              
              // L3 - Storage
              _buildL3StorageLayer(layers),
              _buildArrow(),
              
              // L4 - Twin (editable - user uploads 3D scene files)
              _buildLayerCard('L4', 'Digital Twin', layers['L4'], [
                _buildEditableComponentBox(_getL4Service(layers['L4']), Icons.hub),
              ], isEditable: true),
              _buildArrow(),
              
              // L5 - Visualization (editable - user configures dashboards)
              _buildLayerCard('L5', 'Visualization', layers['L5'], [
                _buildEditableComponentBox('Grafana', Icons.dashboard),
              ], isEditable: true),
              
              const SizedBox(height: 16),
              _buildLegend(),
            ],
          ),
        ),
      ),
    );
  }

  /// L2 Processing layer with branching from Persister
  Widget _buildL2LayerWithGraphview(Map<String, String> layers) {
    final provider = layers['L2'];
    final color = _getProviderColor(provider);
    final hasEventBranch = widget.calcParams?.useEventChecking == true;
    final hasFeedback = widget.calcParams?.returnFeedbackToDevice == true;
    final hasWorkflow = widget.calcParams?.triggerNotificationWorkflow == true;
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withAlpha(12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withAlpha(100), width: 1),
      ),
      child: Column(
        children: [
          // Layer header
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4)),
                child: const Text('L2', style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(width: 10),
              Text('Processing', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: color)),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                decoration: BoxDecoration(color: editableColor, borderRadius: BorderRadius.circular(3)),
                child: const Text('EDIT', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
              ),
              const SizedBox(width: 10),
              _buildProviderChip(provider),
            ],
          ),
          const SizedBox(height: 12),
          
          // Ingestion glue when receiving from another cloud
          if (_hasCrossCloudBoundary('L1', 'L2')) ...[
            _buildGlueComponentBox('Ingestion', provider),
            _buildArrow(small: true),
          ],
          
          // Linear flow: Processor Wrapper → User Processors → Persister
          _buildComponentBox('Processor Wrapper', provider, Icons.hub),
          _buildArrow(small: true),
          _buildEditableComponentBox('User Processors', Icons.code),
          _buildArrow(small: true),
          _buildComponentBox('Persister', provider, Icons.save),
          
          // === BRANCHING FROM PERSISTER: Split View ===
          if (hasEventBranch) ...[
            // Two arrows showing the split
            const SizedBox(height: 4),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.arrow_downward, size: 16, color: Colors.grey.shade500),
                const SizedBox(width: 60),
                Icon(Icons.arrow_downward, size: 16, color: Colors.grey.shade500),
              ],
            ),
            const SizedBox(height: 8),
            IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // LEFT SIDE: Arrows continuing to L3
                  Expanded(
                    flex: 1,
                    child: Column(
                      children: [
                        if (_hasCrossCloudBoundary('L2', 'L3_hot')) ...[
                          _buildGlueComponentBox('Hot Writer', provider),
                          _buildArrow(small: true),
                        ],
                        // Continuation line - expands to fill height
                        Expanded(
                          child: Container(
                            width: 2,
                            color: Colors.grey.shade400,
                          ),
                        ),
                        Icon(Icons.arrow_downward, size: 16, color: Colors.grey.shade500),
                        const SizedBox(height: 4),
                        Text('to L3', style: TextStyle(fontSize: 10, color: Colors.grey.shade600, fontWeight: FontWeight.w500)),
                      ],
                    ),
                  ),
                  const SizedBox(width: 12),
                  // RIGHT SIDE: Event Branch block
                  Expanded(
                    flex: 1,
                    child: Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        border: Border.all(color: editableColor.withAlpha(100)),
                        borderRadius: BorderRadius.circular(8),
                        color: editableColor.withAlpha(8),
                      ),
                      child: Column(
                        children: [
                          Text('Event Branch', style: TextStyle(fontSize: 10, color: editableColor, fontWeight: FontWeight.w500)),
                          const SizedBox(height: 8),
                          _buildEditableComponentBox('Event Checker', Icons.notification_important),
                          
                          // Branching arrows from Event Checker (grey)
                          if (hasFeedback || hasWorkflow) ...[
                            const SizedBox(height: 8),
                            Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                if (hasFeedback) Icon(Icons.arrow_downward, size: 14, color: Colors.grey.shade500),
                                if (hasFeedback && hasWorkflow) const SizedBox(width: 40),
                                if (hasWorkflow) Icon(Icons.arrow_downward, size: 14, color: Colors.grey.shade500),
                              ],
                            ),
                            const SizedBox(height: 6),
                            
                            // Feedback and Workflow on same row with CrossAxisAlignment.start
                            Row(
                              mainAxisSize: MainAxisSize.min,
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (hasFeedback) ...[
                                  Column(
                                    children: [
                                      _buildEditableComponentBoxSmall('Feedback', Icons.replay),
                                      const SizedBox(height: 4),
                                      Row(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Icon(Icons.arrow_upward, size: 14, color: Colors.orange),
                                          const SizedBox(width: 4),
                                          Text('IoT Device', style: TextStyle(fontSize: 10, color: Colors.orange, fontWeight: FontWeight.w500)),
                                        ],
                                      ),
                                    ],
                                  ),
                                ],
                                if (hasFeedback && hasWorkflow) const SizedBox(width: 16),
                                if (hasWorkflow) ...[
                                  Column(
                                    children: [
                                      _buildEditableComponentBoxSmall('Workflow', Icons.account_tree),
                                      _buildArrow(small: true),
                                      _buildEditableComponentBoxSmall('Event Actions', Icons.flash_on),
                                    ],
                                  ),
                                ],
                              ],
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ] else ...[
            // No branching - show Hot Writer directly if needed
            if (_hasCrossCloudBoundary('L2', 'L3_hot')) ...[
              _buildArrow(small: true),
              _buildGlueComponentBox('Hot Writer', provider),
            ],
          ],
        ],
      ),
    );
  }

  /// L3 Storage layer: Left column (Hot Writer → Hot → Cool → Archive), Right: Hot Reader
  Widget _buildL3StorageLayer(Map<String, String> layers) {
    final hasCrossFromL2 = _hasCrossCloudBoundary('L2', 'L3_hot');
    final hasCrossToL4 = _hasCrossCloudBoundary('L3_hot', 'L4');
    
    return _buildLayerCard('L3', 'Storage', null, [
      Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // LEFT: Storage stack (Hot Writer → Hot → Cool → Archive)
          Column(
            children: [
              if (hasCrossFromL2) ...[
                _buildGlueComponentBox('Hot Writer', layers['L3_hot']),
                _buildArrow(small: true),
              ],
              _buildStorageBox('Hot', _getL3HotService(layers['L3_hot']), layers['L3_hot']),
              _buildArrow(small: true),
              _buildStorageBox('Cool', _getL3CoolService(layers['L3_cool']), layers['L3_cool']),
              _buildArrow(small: true),
              _buildStorageBox('Archive', _getL3ArchiveService(layers['L3_archive']), layers['L3_archive']),
            ],
          ),
          // RIGHT: Hot Reader branch (aligned with Hot Storage)
          if (hasCrossToL4) ...[
            const SizedBox(width: 12),
            Column(
              children: [
                // Spacer to align with Hot Storage position
                if (hasCrossFromL2) const SizedBox(height: 60), // Height of Hot Writer + arrow
                Row(
                  children: [
                    Icon(Icons.arrow_forward, size: 16, color: Colors.grey.shade500),
                    const SizedBox(width: 8),
                    Column(
                      children: [
                        _buildGlueComponentBox('Hot Reader', layers['L3_hot']),
                        const SizedBox(height: 4),
                        Text('to L4/L5', style: TextStyle(fontSize: 10, color: Colors.grey.shade600)),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ],
        ],
      ),
    ], isStorage: true);
  }


  // ===== UI BUILDING BLOCKS =====

  Widget _buildEditableSourceBox(String name, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
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
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: editableColor)),
              Text('Upload payload', style: TextStyle(fontSize: 10, color: editableColor.withAlpha(180))),
            ],
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
            decoration: BoxDecoration(color: editableColor, borderRadius: BorderRadius.circular(3)),
            child: const Text('EDIT', style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildArrow({bool small = false}) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: small ? 4 : 8),
      child: Icon(Icons.arrow_downward, size: small ? 18 : 24, color: Colors.grey.shade500),
    );
  }

  Widget _buildLayerCard(String layer, String title, String? provider, List<Widget> components, {bool isEditable = false, bool isStorage = false}) {
    final color = isStorage ? systemColor : _getProviderColor(provider);
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withAlpha(12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withAlpha(100), width: 1),
      ),
      child: Column(
        children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4)),
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
              if (provider != null) ...[
                const SizedBox(width: 10),
                _buildProviderChip(provider),
              ],
            ],
          ),
          const SizedBox(height: 12),
          ...components,
        ],
      ),
    );
  }

  Widget _buildComponentBox(String name, String? provider, IconData icon) {
    final color = _getProviderColor(provider);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withAlpha(120)),
        boxShadow: [BoxShadow(color: Colors.black.withAlpha(10), blurRadius: 2, offset: const Offset(0, 1))],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 10),
          Text(name, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Colors.grey.shade800)),
        ],
      ),
    );
  }

  Widget _buildEditableComponentBox(String name, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: editableColor.withAlpha(25),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: editableColor, width: 2),
        boxShadow: [BoxShadow(color: editableColor.withAlpha(30), blurRadius: 6, offset: const Offset(0, 2))],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: editableColor),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: editableColor)),
              Text('Upload code', style: TextStyle(fontSize: 10, color: editableColor.withAlpha(180))),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildEditableComponentBoxSmall(String name, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: editableColor.withAlpha(25),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: editableColor, width: 1.5),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: editableColor),
          const SizedBox(width: 6),
          Flexible(child: Text(name, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: editableColor), overflow: TextOverflow.ellipsis)),
        ],
      ),
    );
  }

  Widget _buildGlueComponentBox(String name, String? provider) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: glueColor.withAlpha(20),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: glueColor),
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

  Widget _buildStorageBox(String tier, String service, String? provider) {
    final color = _getProviderColor(provider);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withAlpha(120)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.storage, size: 14, color: color),
          const SizedBox(width: 6),
          Text('$tier:', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.grey.shade700)),
          const SizedBox(width: 4),
          Text(service, style: TextStyle(fontSize: 12, color: Colors.grey.shade800)),
          const SizedBox(width: 6),
          _buildProviderChip(provider),
        ],
      ),
    );
  }

  Widget _buildProviderChip(String? provider) {
    final color = _getProviderColor(provider);
    final label = provider?.toUpperCase() ?? 'N/A';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(8)),
      child: Text(label, style: const TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold)),
    );
  }

  Widget _buildLegend() {
    return Wrap(
      spacing: 12,
      runSpacing: 6,
      alignment: WrapAlignment.center,
      children: [
        _legendItem('AWS', AppColors.aws),
        _legendItem('Azure', AppColors.azure),
        _legendItem('GCP', AppColors.gcp),
        _legendItem('Editable', editableColor),
        _legendItem('Glue', glueColor),
      ],
    );
  }

  Widget _legendItem(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 12, height: 12, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3))),
        const SizedBox(width: 4),
        Text(label, style: const TextStyle(fontSize: 11)),
      ],
    );
  }

  // Service name helpers
  String _getL1Service(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'IoT Core', 'AZURE' => 'IoT Hub', 'GCP' => 'Pub/Sub', _ => 'IoT' };
  String _getL3HotService(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'DynamoDB', 'AZURE' => 'Cosmos DB', 'GCP' => 'Firestore', _ => 'Hot' };
  String _getL3CoolService(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'S3 IA', 'AZURE' => 'Blob Cool', 'GCP' => 'Nearline', _ => 'Cool' };
  String _getL3ArchiveService(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'Glacier', 'AZURE' => 'Archive', 'GCP' => 'Coldline', _ => 'Archive' };
  String _getL4Service(String? p) => switch (p?.toUpperCase()) { 'AWS' => 'TwinMaker', 'AZURE' => 'ADT', _ => 'Twin' };
}
