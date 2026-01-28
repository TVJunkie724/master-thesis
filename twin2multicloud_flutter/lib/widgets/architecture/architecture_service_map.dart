// lib/widgets/architecture/architecture_service_map.dart
// Shared service mapping utilities for architecture visualization

import 'package:flutter/material.dart';
import '../../theme/colors.dart';

/// Centralized service name mappings for cloud providers.
/// 
/// This class provides consistent service name resolution across
/// all architecture visualization components.
class ArchitectureServiceMap {
  // ================================================================
  // L1: Data Acquisition
  // ================================================================
  
  static String getL1Service(String? provider) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return 'AWS IoT Core';
      case 'AZURE': return 'Azure IoT Hub';
      case 'GCP': return 'Cloud IoT Core';
      default: return 'IoT Gateway';
    }
  }
  
  static IconData getL1Icon(String? provider) {
    return Icons.sensors;
  }
  
  // ================================================================
  // L2: Processing
  // ================================================================
  
  static String getL2Processor(String? provider) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return 'Lambda';
      case 'AZURE': return 'Azure Functions';
      case 'GCP': return 'Cloud Functions';
      default: return 'Serverless Function';
    }
  }
  
  static String getL2StateMachine(String? provider) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return 'Step Functions';
      case 'AZURE': return 'Logic Apps';
      case 'GCP': return 'Workflows';
      default: return 'State Machine';
    }
  }
  
  static IconData getL2Icon(String? provider) {
    return Icons.memory;
  }
  
  // ================================================================
  // L3: Storage
  // ================================================================
  
  static String getL3HotService(String? provider) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return 'DynamoDB';
      case 'AZURE': return 'Cosmos DB';
      case 'GCP': return 'Firestore';
      default: return 'NoSQL Database';
    }
  }
  
  static String getL3CoolService(String? provider) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return 'S3 IA';
      case 'AZURE': return 'Blob Cool';
      case 'GCP': return 'GCS Nearline';
      default: return 'Cool Storage';
    }
  }
  
  static String getL3ArchiveService(String? provider) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return 'S3 Glacier';
      case 'AZURE': return 'Blob Archive';
      case 'GCP': return 'GCS Coldline';
      default: return 'Archive Storage';
    }
  }
  
  static IconData getL3Icon(String tier) {
    switch (tier.toLowerCase()) {
      case 'hot': return Icons.local_fire_department;
      case 'cool': return Icons.ac_unit;
      case 'archive': return Icons.archive;
      default: return Icons.storage;
    }
  }
  
  // ================================================================
  // L4: Digital Twin
  // ================================================================
  
  static String getL4Service(String? provider) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return 'IoT TwinMaker';
      case 'AZURE': return 'Azure Digital Twins';
      case 'GCP': return 'Custom DT';
      default: return 'Digital Twin';
    }
  }
  
  static IconData getL4Icon(String? provider) {
    return Icons.view_in_ar;
  }
  
  // ================================================================
  // L5: Visualization
  // ================================================================
  
  static String getL5Service(String? provider) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return 'Managed Grafana';
      case 'AZURE': return 'Managed Grafana';
      case 'GCP': return 'Custom Viz';
      default: return 'Dashboard';
    }
  }
  
  static IconData getL5Icon(String? provider) {
    return Icons.dashboard;
  }
  
  // ================================================================
  // Provider Colors
  // ================================================================
  
  static Color getProviderColor(String? provider, {bool isDark = false}) {
    switch (provider?.toUpperCase()) {
      case 'AWS': return AppColors.aws;
      case 'AZURE': return AppColors.azure;
      case 'GCP': return AppColors.gcp;
      default: return isDark ? Colors.grey.shade400 : Colors.grey.shade600;
    }
  }
  
  static Color getProviderBackgroundColor(String? provider, {bool isDark = false}) {
    final baseColor = getProviderColor(provider, isDark: isDark);
    return baseColor.withOpacity(isDark ? 0.15 : 0.1);
  }
  
  // ================================================================
  // Layer Names
  // ================================================================
  
  static String getLayerTitle(String layer) {
    switch (layer) {
      case 'L1': return 'Data Acquisition';
      case 'L2': return 'Processing';
      case 'L3': return 'Storage';
      case 'L3_hot': return 'Hot Storage';
      case 'L3_cool': return 'Cool Storage';
      case 'L3_archive': return 'Archive Storage';
      case 'L4': return 'Digital Twin';
      case 'L5': return 'Visualization';
      default: return layer;
    }
  }
  
  // ================================================================
  // Cross-Cloud Detection
  // ================================================================
  
  static bool hasCrossCloudBoundary(String? provider1, String? provider2) {
    if (provider1 == null || provider2 == null) return false;
    return provider1.toUpperCase() != provider2.toUpperCase();
  }
  
  /// Extract provider from cheapest path segment (e.g., "L1_AWS" -> "AWS")
  static String? extractProviderFromSegment(String segment) {
    final parts = segment.split('_');
    if (parts.length >= 3 && segment.startsWith('L3')) {
      return parts[2].toUpperCase();
    } else if (parts.length >= 2) {
      return parts[1].toUpperCase();
    }
    return null;
  }
  
  /// Build provider map from cheapest path
  static Map<String, String?> buildProviderMap(List<String> cheapestPath) {
    final map = <String, String?>{};
    for (final segment in cheapestPath) {
      final layerParts = segment.split('_');
      if (layerParts.isEmpty) continue;
      
      String layerKey;
      String? provider;
      
      if (segment.startsWith('L3_') && layerParts.length >= 3) {
        // L3_hot_AWS -> key: L3_hot, provider: AWS
        layerKey = '${layerParts[0]}_${layerParts[1]}';
        provider = layerParts[2].toUpperCase();
      } else if (layerParts.length >= 2) {
        layerKey = layerParts[0];
        provider = layerParts[1].toUpperCase();
      } else {
        continue;
      }
      
      map[layerKey] = provider;
    }
    return map;
  }
}
