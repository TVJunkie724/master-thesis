import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';

void main() {
  late Map<String, dynamic> architecture;
  late Map<String, dynamic> v2Architecture;

  setUpAll(() {
    final raw = File(
      '../contracts/architecture-profiles/v1/fixtures/valid/'
      'mixed-baseline-resolved-architecture.json',
    ).readAsStringSync();
    architecture = Map<String, dynamic>.from(jsonDecode(raw) as Map);
    final v2Raw = File(
      '../contracts/architecture-profiles/v2/fixtures/valid/'
      'single-cloud-aws-small-resolved.json',
    ).readAsStringSync();
    v2Architecture = Map<String, dynamic>.from(jsonDecode(v2Raw) as Map);
  });

  Map<String, dynamic> readJson() => {
    'twin_id': 'twin-1',
    'calculation_run_id': architecture['calculation_run_id'],
    'selected_for_deployment_at': '2026-08-03T10:00:00Z',
    'architecture_compatibility_status': 'ready',
    'origin': 'native_v1',
    'architecture': jsonDecode(jsonEncode(architecture)),
  };

  Map<String, dynamic> v2ReadJson() => {
    'twin_id': 'twin-v2',
    'calculation_run_id': v2Architecture['calculation_run_id'],
    'selected_for_deployment_at': null,
    'architecture_compatibility_status': 'ready',
    'origin': 'native_v2',
    'architecture': jsonDecode(jsonEncode(v2Architecture)),
  };

  test(
    'parses the canonical mixed-provider architecture without fixed slots',
    () {
      final resolved = ResolvedTwinArchitectureRead.fromJson(readJson());

      expect(resolved.twinId, 'twin-1');
      expect(resolved.architecture.componentAssignments, hasLength(7));
      expect(resolved.architecture.resolvedEdges, hasLength(6));
      expect(
        resolved.architecture.providers.map((item) => item.apiValue),
        containsAll(['aws', 'azure']),
      );
      expect(resolved.architecture.costSummary.monthlyTotal, '7.6');
      expect(resolved.architecture.functionalCompleteness.status, 'complete');
    },
  );

  test('rejects unknown versions, negative costs, and unresolved edges', () {
    final unknown = readJson();
    (unknown['architecture'] as Map)['schema_version'] =
        'resolved-twin-architecture.v2';
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(unknown),
      throwsFormatException,
    );

    final negative = readJson();
    final assignments =
        (negative['architecture'] as Map)['component_assignments'] as List;
    (assignments.first as Map)['cost_contribution'] = {
      'currency': 'USD',
      'monthly_amount': '-1',
    };
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(negative),
      throwsFormatException,
    );

    final unresolved = readJson();
    final edges = (unresolved['architecture'] as Map)['resolved_edges'] as List;
    (edges.first as Map)['destination_assignment_id'] = 'assignment.unknown';
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(unresolved),
      throwsFormatException,
    );
  });

  test('parses canonical Five-layer v2 evaluation evidence', () {
    final resolved = ResolvedTwinArchitectureRead.fromJson(v2ReadJson());

    expect(
      resolved.architecture.schemaVersion,
      ResolvedTwinArchitecture.v2SchemaVersion,
    );
    expect(resolved.architecture.resolutionStatus, 'offline_contract_fixture');
    expect(resolved.origin, ResolvedArchitectureOrigin.nativeV2);
    expect(resolved.architecture.profileRef.version, '2');
    expect(resolved.architecture.componentAssignments, hasLength(7));
    expect(resolved.architecture.resolvedEdges, hasLength(8));
  });

  test('v2 fails closed on digest tamper and origin mismatch', () {
    final digestTamper = v2ReadJson();
    (digestTamper['architecture'] as Map)['content_digest'] =
        'sha256:${List.filled(64, '0').join()}';
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(digestTamper),
      throwsFormatException,
    );

    final originMismatch = v2ReadJson()..['origin'] = 'native_v1';
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(originMismatch),
      throwsFormatException,
    );
  });
}
