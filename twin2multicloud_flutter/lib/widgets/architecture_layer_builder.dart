import 'package:flutter/material.dart';
import '../models/calc_result.dart';
import '../models/calc_params.dart';
import '../theme/colors.dart';

/// Utility class that builds individual architecture layer widgets.
/// 
/// Used by both ArchitectureGraph (for full flowchart view) and
/// Step3Deployer (for layer-aligned file editor view).
class ArchitectureLayerBuilder {
  final CalcResult? calcResult;
  final CalcParams? calcParams;
  
  // Colors
  static const Color editableColor = Color(0xFFD81B60);
  static const Color systemColor = Color(0xFF78909C);
  static const Color glueColor = Color(0xFF78909C);

  ArchitectureLayerBuilder({
    required this.calcResult,
    required this.calcParams,
  });

  Map<String, String> get layerProviders {
    final result = <String, String>{};
    if (calcResult == null) return result;
    
    for (final segment in calcResult!.cheapestPath) {
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

  bool hasCrossCloudBoundary(String layer1, String layer2) {
    final providers = layerProviders;
    final p1 = providers[layer1];
    final p2 = providers[layer2];
    return p1 != null && p2 != null && p1 != p2;
  }

  Color getProviderColor(String? provider) {
    if (provider == null) return systemColor;
    return AppColors.getProviderColor(provider);
  }

  // ===== PUBLIC LAYER BUILDERS =====

  /// L1 Data Acquisition layer with IoT Devices
  Widget buildL1Layer(BuildContext context) {
    final layers = layerProviders;
    return _buildLayerCard(context, 'L1', 'Data Acquisition', layers['L1'], [
      _buildEditableSourceBox('IoT Devices', Icons.sensors),
      _buildArrow(small: true),
      _buildComponentBox(context, _getL1Service(layers['L1']), layers['L1'], Icons.router),
      _buildArrow(small: true),
      _buildComponentBox(context, 'Dispatcher', layers['L1'], Icons.call_split),
      if (hasCrossCloudBoundary('L1', 'L2')) ...[
        _buildArrow(small: true),
        _buildGlueComponentBox('Connector', layers['L1']),
      ],
    ]);
  }

  /// L2 Processing layer with branching from Persister
  Widget buildL2Layer(BuildContext context) {
    final layers = layerProviders;
    final provider = layers['L2'];
    final hasEventBranch = calcParams?.useEventChecking ?? false;
    final hasFeedback = calcParams?.returnFeedbackToDevice ?? false;
    final hasWorkflow = calcParams?.triggerNotificationWorkflow ?? false;
    final hasCrossToL3 = hasCrossCloudBoundary('L2', 'L3_hot');
    
    return _buildLayerCard(context, 'L2', 'Processing', provider, [
      // Receiver if cross-cloud from L1
      if (hasCrossCloudBoundary('L1', 'L2')) ...[
        _buildGlueComponentBox('Receiver', provider),
        _buildArrow(small: true),
      ],
      
      // Processor Wrapper
      _buildComponentBox(context, 'Processor Wrapper', provider, Icons.settings),
      _buildArrow(small: true),
      
      // User Processors (editable)
      _buildEditableComponentBox('User Processors', Icons.code),
      _buildArrow(small: true),
      
      // Persister
      _buildComponentBox(context, 'Persister', provider, Icons.save),
      
      // === BRANCHING FROM PERSISTER ===
      if (hasEventBranch) ...[
        // Two arrows showing the split
        const SizedBox(height: 4),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.arrow_downward, size: 16, color: Colors.grey.shade500),
            const SizedBox(width: 80),
            Icon(Icons.arrow_downward, size: 16, color: Colors.grey.shade500),
          ],
        ),
        const SizedBox(height: 8),
        // Split view: Left = to L3, Right = Event Branch
        IntrinsicHeight(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              // LEFT SIDE: Connector if cross-cloud, then line to L3
              Column(
                children: [
                  if (hasCrossToL3) ...[
                    _buildGlueComponentBoxCompact('Connector', provider),
                    _buildArrow(small: true),
                  ],
                  // Continuation line
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
              const SizedBox(width: 8),
              // RIGHT SIDE: Event Branch block
              _buildEventBranchBox(context, provider, hasFeedback, hasWorkflow),
            ],
          ),
        ),
      ] else ...[
        // No branching - show Connector directly if needed
        if (hasCrossToL3) ...[
          _buildArrow(small: true),
          _buildGlueComponentBox('Connector', provider),
        ],
      ],
    ], isEditable: true);
  }

  Widget _buildEventBranchBox(BuildContext context, String? provider, bool hasFeedback, bool hasWorkflow) {
    return Container(
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
          
          // Branching arrows from Event Checker
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
            
            // Feedback and Workflow on same row
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
    );
  }

  /// L3 Storage layer
  Widget buildL3Layer(BuildContext context) {
    final layers = layerProviders;
    final hasCrossFromL2 = hasCrossCloudBoundary('L2', 'L3_hot');
    final hasCrossToL4 = hasCrossCloudBoundary('L3_hot', 'L4');
    
    return _buildLayerCard(context, 'L3', 'Storage', null, [
      Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // LEFT: Storage stack
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
          // RIGHT: Hot Reader branch
          if (hasCrossToL4) ...[
            const SizedBox(width: 12),
            Column(
              children: [
                if (hasCrossFromL2) const SizedBox(height: 60),
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

  /// L4 Digital Twin layer
  Widget buildL4Layer(BuildContext context) {
    final layers = layerProviders;
    return _buildLayerCard(context, 'L4', 'Digital Twin', layers['L4'], [
      _buildEditableComponentBox(_getL4Service(layers['L4']), Icons.hub),
    ], isEditable: true);
  }

  /// L5 Visualization layer
  Widget buildL5Layer(BuildContext context) {
    final layers = layerProviders;
    return _buildLayerCard(context, 'L5', 'Visualization', layers['L5'], [
      _buildEditableComponentBox('Grafana', Icons.dashboard),
    ], isEditable: true);
  }

  /// Arrow between layers
  Widget buildArrow({bool small = false}) => _buildArrow(small: small);

  /// Legend
  Widget buildLegend() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Legend', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.grey.shade700)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 16,
            runSpacing: 8,
            children: [
              _legendItem('AWS', AppColors.aws),
              _legendItem('Azure', AppColors.azure),
              _legendItem('GCP', AppColors.gcp),
              _legendItem('Editable', editableColor),
              _legendItem('System', systemColor),
            ],
          ),
        ],
      ),
    );
  }

  // ===== PRIVATE HELPER METHODS =====

  Widget _buildArrow({bool small = false}) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: small ? 4 : 8),
      child: Icon(Icons.arrow_downward, size: small ? 18 : 24, color: Colors.grey.shade500),
    );
  }

  Widget _buildLayerCard(BuildContext context, String layer, String title, String? provider, List<Widget> components, {bool isEditable = false, bool isStorage = false}) {
    final color = isStorage ? systemColor : getProviderColor(provider);
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withAlpha(12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withAlpha(60), width: 1.5),
      ),
      child: Column(
        children: [
          // Layer header: title left, provider right
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // Left: Layer badge + title
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4)),
                    child: Text(layer, style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.bold)),
                  ),
                  const SizedBox(width: 10),
                  Text(title, style: TextStyle(fontWeight: FontWeight.w600, color: color, fontSize: 14)),
                ],
              ),
              // Right: Provider chip
              if (!isStorage && provider != null) _buildProviderChip(provider),
            ],
          ),
          const SizedBox(height: 14),
          // Components
          ...components,
        ],
      ),
    );
  }

  /// System component box - grey style for non-editable components (Dispatcher, IoT Core, etc.)
  Widget _buildComponentBox(BuildContext context, String name, String? provider, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: systemColor.withAlpha(15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: systemColor.withAlpha(80)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: systemColor),
          const SizedBox(width: 8),
          Text(name, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: systemColor)),
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
          Text(name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: editableColor)),
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

  Widget _buildEditableComponentBoxSmall(String name, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: editableColor.withAlpha(20),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: editableColor.withAlpha(150)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: editableColor),
          const SizedBox(width: 6),
          Text(name, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: editableColor)),
        ],
      ),
    );
  }

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

  Widget _buildGlueComponentBox(String name, String? provider) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: glueColor.withAlpha(20),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: glueColor.withAlpha(100)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.swap_horiz, size: 14, color: glueColor),
          const SizedBox(width: 6),
          Text(name, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: glueColor)),
        ],
      ),
    );
  }

  /// Compact glue box for tight layouts
  Widget _buildGlueComponentBoxCompact(String name, String? provider) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        color: glueColor.withAlpha(20),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: glueColor.withAlpha(100)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.swap_horiz, size: 12, color: glueColor),
          const SizedBox(width: 4),
          Text(name, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w500, color: glueColor)),
        ],
      ),
    );
  }

  Widget _buildStorageBox(String tier, String service, String? provider) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: systemColor.withAlpha(15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: systemColor.withAlpha(80)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.dns, size: 14, color: systemColor),
          const SizedBox(width: 8),
          Text('$tier: $service', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w500, color: systemColor)),
          const SizedBox(width: 8),
          _buildProviderChipSmall(provider),
        ],
      ),
    );
  }

  Widget _buildProviderChip(String? provider) {
    if (provider == null) return const SizedBox.shrink();
    final color = getProviderColor(provider);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(4)),
      child: Text(provider.toUpperCase(), style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
    );
  }

  Widget _buildProviderChipSmall(String? provider) {
    if (provider == null) return const SizedBox.shrink();
    final color = getProviderColor(provider);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
      decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(3)),
      child: Text(provider.toUpperCase(), style: const TextStyle(color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold)),
    );
  }

  Widget _legendItem(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 10, height: 10, decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(2))),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(fontSize: 10, color: Colors.grey.shade600)),
      ],
    );
  }

  // Service name helpers
  String _getL1Service(String? p) => p == 'AWS' ? 'IoT Core' : p == 'AZURE' ? 'IoT Hub' : p == 'GCP' ? 'Pub/Sub' : 'IoT Hub';
  String _getL3HotService(String? p) => p == 'AWS' ? 'DynamoDB' : p == 'AZURE' ? 'CosmosDB' : p == 'GCP' ? 'Firestore' : 'Hot Storage';
  String _getL3CoolService(String? p) => p == 'AWS' ? 'S3 IA' : p == 'AZURE' ? 'Cool Blob' : p == 'GCP' ? 'Nearline' : 'Cool Storage';
  String _getL3ArchiveService(String? p) => p == 'AWS' ? 'Glacier' : p == 'AZURE' ? 'Archive' : p == 'GCP' ? 'Coldline' : 'Archive';
  String _getL4Service(String? p) => p == 'AWS' ? 'IoT TwinMaker' : p == 'AZURE' ? 'Digital Twins' : p == 'GCP' ? 'Supply Chain' : 'Digital Twin';
}
