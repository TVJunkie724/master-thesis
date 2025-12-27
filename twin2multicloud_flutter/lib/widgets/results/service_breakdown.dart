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
        _buildLayerAccordion(context, 'Layer 1: Data Acquisition',
          result.awsCosts.l1, result.azureCosts.l1, result.gcpCosts.l1),
        _buildLayerAccordion(context, 'Layer 2: Data Processing',
          result.awsCosts.l2, result.azureCosts.l2, result.gcpCosts.l2),
        _buildLayerAccordion(context, 'Layer 3: Hot Storage',
          result.awsCosts.l3Hot, result.azureCosts.l3Hot, result.gcpCosts.l3Hot),
        _buildLayerAccordion(context, 'Layer 3: Cool Storage',
          result.awsCosts.l3Cool, result.azureCosts.l3Cool, result.gcpCosts.l3Cool),
        _buildLayerAccordion(context, 'Layer 3: Archive Storage',
          result.awsCosts.l3Archive, result.azureCosts.l3Archive, result.gcpCosts.l3Archive),
        _buildLayerAccordion(context, 'Layer 4: Twin Management',
          result.awsCosts.l4, result.azureCosts.l4, result.gcpCosts.l4),
        _buildLayerAccordion(context, 'Layer 5: Visualization',
          result.awsCosts.l5, result.azureCosts.l5, result.gcpCosts.l5),
      ],
    );
  }

  Widget _buildLayerAccordion(
    BuildContext context, 
    String title,
    LayerCost? aws,
    LayerCost? azure,
    LayerCost? gcp,
  ) {
    // If no data for any provider, skip
    bool hasData = (aws?.components.isNotEmpty ?? false) || 
                   (azure?.components.isNotEmpty ?? false) || 
                   (gcp?.components.isNotEmpty ?? false);
    
    if (!hasData) return const SizedBox.shrink();

    return Card(
      elevation: 0,
      color: Theme.of(context).colorScheme.surfaceContainerHighest.withAlpha(50),
      margin: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        title: Text(
          title,
          style: Theme.of(context).textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.bold,
          ),
        ),
        subtitle: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _buildMiniTotal('AWS', aws?.cost, Colors.orange),
            const SizedBox(width: 12),
            _buildMiniTotal('Azure', azure?.cost, Colors.blue),
            const SizedBox(width: 12),
            _buildMiniTotal('GCP', gcp?.cost, Colors.green),
          ],
        ),
        children: [
          Container(
            padding: const EdgeInsets.all(8.0),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildProviderColumn(context, 'AWS', aws, Colors.orange),
                const SizedBox(width: 8),
                _buildProviderColumn(context, 'Azure', azure, Colors.blue),
                const SizedBox(width: 8),
                _buildProviderColumn(context, 'GCP', gcp, Colors.green),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMiniTotal(String label, double? cost, Color color) {
    if (cost == null) return const SizedBox();
    return Text(
      //'$label: \$${cost.toStringAsFixed(2)}',
      '\$${cost.toStringAsFixed(2)}',
      style: TextStyle(
        fontSize: 12,
        fontWeight: FontWeight.bold,
        color: color,
      ),
    );
  }

  Widget _buildProviderColumn(
    BuildContext context,
    String providerName,
    LayerCost? cost,
    Color color,
  ) {
    return Expanded(
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(color: color.withAlpha(50)),
          borderRadius: BorderRadius.circular(4),
        ),
        child: Column(
          children: [
            // Header
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
              decoration: BoxDecoration(
                color: color,
                borderRadius: const BorderRadius.vertical(top: Radius.circular(3)),
              ),
              child: Text(
                providerName,
                style: const TextStyle(
                  color: Colors.white, 
                  fontWeight: FontWeight.bold,
                  fontSize: 12,
                ),
              ),
            ),
            
            // Content
            if (cost != null && cost.components.isNotEmpty)
              Padding(
                padding: const EdgeInsets.all(8.0),
                child: Column(
                  children: [
                    ...cost.components.entries.map((e) => Padding(
                      padding: const EdgeInsets.only(bottom: 4.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Expanded(
                            child: Text(
                              _getDisplayName(e.key), 
                              style: const TextStyle(fontSize: 11),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Text(
                            '\$${e.value.toStringAsFixed(2)}',
                             style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    )),
                    const Divider(height: 12),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Total', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11)),
                        Text('\$${cost.cost.toStringAsFixed(2)}', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11, color: color)),
                      ],
                    )
                  ],
                ),
              )
            else
               const Padding(
                 padding: EdgeInsets.all(16.0),
                 child: Text('-', style: TextStyle(color: Colors.grey)),
               ),
          ],
        ),
      ),
    );
  }
}
