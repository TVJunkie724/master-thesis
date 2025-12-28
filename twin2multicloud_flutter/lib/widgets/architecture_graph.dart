import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';
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
              
              // IoT Devices (source)
              _buildSourceBox('IoT Devices', Icons.sensors),
              _buildArrow(),
              
              // L1 - Data Acquisition
              _buildLayerCard('L1', 'Data Acquisition', layers['L1'], [
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
              
              // L4 - Twin
              _buildLayerCard('L4', 'Digital Twin', layers['L4'], [
                _buildComponentBox(_getL4Service(layers['L4']), layers['L4'], Icons.hub),
              ]),
              _buildArrow(),
              
              // L5 - Visualization
              _buildLayerCard('L5', 'Visualization', layers['L5'], [
                _buildComponentBox('Grafana', layers['L5'], Icons.dashboard),
              ]),
              
              const SizedBox(height: 16),
              _buildLegend(),
            ],
          ),
        ),
      ),
    );
  }

  /// L2 Processing layer with graphview for internal branching
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
          
          // Processor Wrapper (entry point before branching)
          _buildComponentBox('Processor Wrapper', provider, Icons.hub),
          _buildArrow(small: true),
          
          // === BRANCHING SECTION using graphview ===
          if (hasEventBranch)
            _buildL2BranchingGraph(provider, hasFeedback, hasWorkflow)
          else ...[
            // Simple linear flow
            _buildEditableComponentBox('User Processors', Icons.code),
            _buildArrow(small: true),
            _buildComponentBox('Persister', provider, Icons.save),
          ],
          
          // Hot Writer glue when sending to another cloud
          if (_hasCrossCloudBoundary('L2', 'L3_hot')) ...[
            _buildArrow(small: true),
            _buildGlueComponentBox('Hot Writer', provider),
          ],
        ],
      ),
    );
  }

  /// Use graphview for L2 internal branching
  Widget _buildL2BranchingGraph(String? provider, bool hasFeedback, bool hasWorkflow) {
    final graph = Graph()..isTree = true;
    
    // Nodes
    final userProc = Node.Id('user_processors');
    final persister = Node.Id('persister');
    final eventChecker = Node.Id('event_checker');
    
    // Main flow
    graph.addEdge(userProc, persister, paint: _edgePaint());
    
    // Event flow  
    graph.addEdge(eventChecker, Node.Id('feedback_placeholder'), paint: _edgePaint());
    
    if (hasFeedback) {
      final feedback = Node.Id('feedback');
      graph.addEdge(eventChecker, feedback, paint: _edgePaint());
    }
    
    if (hasWorkflow) {
      final workflow = Node.Id('workflow');
      final eventActions = Node.Id('event_actions');
      graph.addEdge(eventChecker, workflow, paint: _edgePaint());
      graph.addEdge(workflow, eventActions, paint: _edgePaint());
    }
    
    // Simpler approach: use Row with two columns for branching
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // LEFT: Main processing flow
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(8),
              margin: const EdgeInsets.only(right: 4),
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey.shade300),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Column(
                children: [
                  Text('Main Flow', style: TextStyle(fontSize: 10, color: Colors.grey.shade600, fontWeight: FontWeight.w500)),
                  const SizedBox(height: 8),
                  _buildEditableComponentBox('User Processors', Icons.code),
                  _buildArrow(small: true),
                  _buildComponentBox('Persister', provider, Icons.save),
                ],
              ),
            ),
          ),
          // RIGHT: Event checking flow
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(8),
              margin: const EdgeInsets.only(left: 4),
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
                  if (hasFeedback || hasWorkflow) ...[
                    _buildArrow(small: true),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        if (hasFeedback) ...[
                          Flexible(
                            child: Column(
                              children: [
                                _buildEditableComponentBoxSmall('Feedback', Icons.replay),
                                const SizedBox(height: 4),
                                Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    Icon(Icons.arrow_upward, size: 12, color: Colors.orange),
                                    Text(' IoT', style: TextStyle(fontSize: 9, color: Colors.orange)),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ],
                        if (hasFeedback && hasWorkflow) const SizedBox(width: 8),
                        if (hasWorkflow) ...[
                          Flexible(
                            child: Column(
                              children: [
                                _buildEditableComponentBoxSmall('Workflow', Icons.account_tree),
                                _buildArrow(small: true),
                                _buildEditableComponentBoxSmall('Event Actions', Icons.flash_on),
                              ],
                            ),
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
    );
  }

  /// L3 Storage layer with Hot → Cool → Archive and Hot Reader branch
  Widget _buildL3StorageLayer(Map<String, String> layers) {
    return _buildLayerCard('L3', 'Storage', null, [
      // Hot Writer glue (if coming from different cloud)
      if (_hasCrossCloudBoundary('L2', 'L3_hot')) ...[
        _buildGlueComponentBox('Hot Writer', layers['L3_hot']),
        _buildArrow(small: true),
      ],
      // Hot storage with Hot Reader branch
      Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Column(
            children: [
              _buildStorageBox('Hot', _getL3HotService(layers['L3_hot']), layers['L3_hot']),
              _buildArrow(small: true),
              _buildStorageBox('Cool', _getL3CoolService(layers['L3_cool']), layers['L3_cool']),
              _buildArrow(small: true),
              _buildStorageBox('Archive', _getL3ArchiveService(layers['L3_archive']), layers['L3_archive']),
            ],
          ),
          if (_hasCrossCloudBoundary('L3_hot', 'L4')) ...[
            const SizedBox(width: 16),
            Column(
              children: [
                const SizedBox(height: 4),
                Icon(Icons.arrow_forward, size: 16, color: glueColor),
                const SizedBox(height: 4),
                _buildGlueComponentBox('Hot Reader', layers['L3_hot']),
                const SizedBox(height: 4),
                Text('→ L4/L5', style: TextStyle(fontSize: 10, color: Colors.grey.shade600)),
              ],
            ),
          ],
        ],
      ),
    ], isStorage: true);
  }

  Paint _edgePaint() => Paint()
    ..color = Colors.grey.shade500
    ..strokeWidth = 2
    ..style = PaintingStyle.stroke;

  // ===== UI BUILDING BLOCKS =====

  Widget _buildSourceBox(String name, IconData icon) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.grey.shade100,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.shade400),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 20, color: Colors.grey.shade700),
          const SizedBox(width: 10),
          Text(name, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Colors.grey.shade800)),
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
