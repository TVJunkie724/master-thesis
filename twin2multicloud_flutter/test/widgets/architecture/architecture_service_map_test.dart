// test/widgets/architecture/architecture_service_map_test.dart
// Tests for ArchitectureServiceMap utility class

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/widgets/architecture/architecture_service_map.dart';

void main() {
  group('ArchitectureServiceMap', () {
    group('getProviderColor', () {
      test('returns consistent color for AWS', () {
        final color = ArchitectureServiceMap.getProviderColor('AWS');
        expect(color, isA<Color>());
      });
      
      test('returns consistent color for AZURE', () {
        final color = ArchitectureServiceMap.getProviderColor('AZURE');
        expect(color, isA<Color>());
      });
      
      test('returns consistent color for GCP', () {
        final color = ArchitectureServiceMap.getProviderColor('GCP');
        expect(color, isA<Color>());
      });
      
      test('is case insensitive', () {
        expect(
          ArchitectureServiceMap.getProviderColor('aws'),
          ArchitectureServiceMap.getProviderColor('AWS'),
        );
        expect(
          ArchitectureServiceMap.getProviderColor('Azure'),
          ArchitectureServiceMap.getProviderColor('AZURE'),
        );
      });
      
      test('handles null provider', () {
        final color = ArchitectureServiceMap.getProviderColor(null);
        expect(color, isA<Color>());
      });
    });
    
    group('extractProviderFromSegment', () {
      test('extracts provider from L1 segment', () {
        expect(
          ArchitectureServiceMap.extractProviderFromSegment('L1_AWS'),
          'AWS',
        );
      });
      
      test('extracts provider from L2 segment', () {
        expect(
          ArchitectureServiceMap.extractProviderFromSegment('L2_AZURE'),
          'AZURE',
        );
      });
      
      test('extracts provider from L3 storage segment', () {
        expect(
          ArchitectureServiceMap.extractProviderFromSegment('L3_hot_GCP'),
          'GCP',
        );
      });
      
      test('returns null for invalid segment', () {
        expect(
          ArchitectureServiceMap.extractProviderFromSegment('invalid'),
          null,
        );
      });
    });
    
    group('L1 services', () {
      test('returns AWS IoT Core for AWS', () {
        expect(
          ArchitectureServiceMap.getL1Service('AWS'),
          'AWS IoT Core',
        );
      });
      
      test('returns Azure IoT Hub for Azure', () {
        expect(
          ArchitectureServiceMap.getL1Service('AZURE'),
          'Azure IoT Hub',
        );
      });
      
      test('returns default for unknown', () {
        expect(
          ArchitectureServiceMap.getL1Service('unknown'),
          'IoT Gateway',
        );
      });
    });
    
    group('L2 services', () {
      test('returns Lambda for AWS', () {
        expect(
          ArchitectureServiceMap.getL2Processor('AWS'),
          'Lambda',
        );
      });
      
      test('returns Azure Functions for Azure', () {
        expect(
          ArchitectureServiceMap.getL2Processor('AZURE'),
          'Azure Functions',
        );
      });
    });
    
    group('L3 icons', () {
      test('returns fire icon for hot tier', () {
        expect(
          ArchitectureServiceMap.getL3Icon('hot'),
          Icons.local_fire_department,
        );
      });
      
      test('returns snowflake icon for cool tier', () {
        expect(
          ArchitectureServiceMap.getL3Icon('cool'),
          Icons.ac_unit,
        );
      });
      
      test('returns archive icon for archive tier', () {
        expect(
          ArchitectureServiceMap.getL3Icon('archive'),
          Icons.archive,
        );
      });
    });
    
    group('getLayerTitle', () {
      test('returns correct title for L1', () {
        expect(ArchitectureServiceMap.getLayerTitle('L1'), 'Data Acquisition');
      });
      
      test('returns correct title for L4', () {
        expect(ArchitectureServiceMap.getLayerTitle('L4'), 'Digital Twin');
      });
    });
    
    group('buildProviderMap', () {
      test('builds map from cheapest path', () {
        final path = ['L1_AWS', 'L2_AZURE', 'L3_hot_GCP', 'L4_AWS'];
        final map = ArchitectureServiceMap.buildProviderMap(path);
        
        expect(map['L1'], 'AWS');
        expect(map['L2'], 'AZURE');
        expect(map['L3_hot'], 'GCP');
        expect(map['L4'], 'AWS');
      });
    });
  });
}
