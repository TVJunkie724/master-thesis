import 'package:flutter/material.dart';
import '../../models/calc_result.dart';

/// Expandable accordion showing service-level cost breakdown
class ServiceBreakdown extends StatelessWidget {
  final CalcResult result;

  const ServiceBreakdown({
    super.key,
    required this.result,
  });

  /// Map internal service keys to display names
  static const componentNames = {
    // L1
    'iot_core': 'AWS IoT Core',
    'dispatcher_lambda': 'Dispatcher Lambda',
    'iot_hub': 'Azure IoT Hub',
    'dispatcher_function': 'Dispatcher Function',
    'pubsub': 'GCP Pub/Sub',
    'iotCore': 'AWS IoT Core',
    'dispatcherLambda': 'Dispatcher Lambda',
    'iotHub': 'Azure IoT Hub',
    'dispatcherFunction': 'Dispatcher Function',
    
    // L2
    'event_checker_lambda': 'Event Checker Lambda',
    'processor_lambda': 'Processor Lambda',
    'orchestration': 'Step Functions / Logic Apps',
    'eventCheckerLambda': 'Event Checker Lambda',
    'processorLambda': 'Processor Lambda',
    'functions': 'Cloud Functions',
    'logicApps': 'Logic Apps',
    'stepFunctions': 'Step Functions',
    'eventGrid': 'Event Grid',
    
    // L3 Hot
    'dynamodb': 'DynamoDB',
    'cosmosdb': 'CosmosDB',
    'firestore': 'Firestore',
    'dynamoDB': 'DynamoDB',
    'cosmosDB': 'CosmosDB',
    
    // L3 Cool
    's3_ia': 'S3 Infrequent Access',
    'blob_cool': 'Blob Storage (Cool)',
    'gcs_nearline': 'GCS Nearline',
    's3InfrequentAccess': 'S3 Infrequent Access',
    'blobCool': 'Blob Storage (Cool)',
    'gcsNearline': 'GCS Nearline',
    
    // L3 Archive
    's3_glacier': 'S3 Glacier Deep Archive',
    'blob_archive': 'Blob Storage (Archive)',
    'gcs_coldline': 'GCS Coldline',
    's3Glacier': 'S3 Glacier Deep Archive',
    'blobArchive': 'Blob Storage (Archive)',
    'gcsColdline': 'GCS Coldline',
    
    // L4
    'twinmaker': 'AWS TwinMaker',
    'digital_twins': 'Azure Digital Twins',
    'twinMaker': 'AWS TwinMaker',
    'digitalTwins': 'Azure Digital Twins',
    
    // L5
    'managed_grafana': 'AWS Managed Grafana',
    'grafana_workspace': 'Azure Grafana Workspace',
    'managedGrafana': 'AWS Managed Grafana',
    'grafanaWorkspace': 'Azure Grafana Workspace',
  };

  String _getDisplayName(String key) {
    return componentNames[key] ?? key;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildProviderSection(context, 'AWS', result.awsCosts, Colors.orange),
        const SizedBox(height: 8),
        _buildProviderSection(context, 'Azure', result.azureCosts, Colors.blue),
        const SizedBox(height: 8),
        _buildProviderSection(context, 'GCP', result.gcpCosts, Colors.red),
      ],
    );
  }

  Widget _buildProviderSection(
    BuildContext context,
    String provider,
    ProviderCosts costs,
    Color color,
  ) {
    final layers = <String, LayerCost?>{
      'L1': costs.l1,
      'L2': costs.l2,
      'L3 Hot': costs.l3Hot,
      'L3 Cool': costs.l3Cool,
      'L3 Archive': costs.l3Archive,
      'L4': costs.l4,
      'L5': costs.l5,
    };

    return ExpansionTile(
      leading: Container(
        width: 24,
        height: 24,
        decoration: BoxDecoration(
          color: color,
          shape: BoxShape.circle,
        ),
        child: const Icon(Icons.cloud, color: Colors.white, size: 16),
      ),
      title: Text(
        provider,
        style: TextStyle(fontWeight: FontWeight.bold, color: color),
      ),
      children: layers.entries
          .where((e) => e.value != null && e.value!.components.isNotEmpty)
          .map((entry) => _buildLayerBreakdown(context, entry.key, entry.value!))
          .toList(),
    );
  }

  Widget _buildLayerBreakdown(
    BuildContext context,
    String layerName,
    LayerCost layerCost,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            layerName,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          ...layerCost.components.entries.map((entry) => Padding(
            padding: const EdgeInsets.only(left: 16, top: 2),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  _getDisplayName(entry.key),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                Text(
                  '\$${entry.value.toStringAsFixed(4)}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          )),
          const Divider(),
        ],
      ),
    );
  }
}
