import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';

void main() {
  late Map<String, dynamic> architecture;

  setUpAll(() {
    final raw = File(
      '../contracts/architecture-profiles/v1/fixtures/valid/'
      'mixed-baseline-resolved-architecture.json',
    ).readAsStringSync();
    architecture = Map<String, dynamic>.from(jsonDecode(raw) as Map);
  });

  Map<String, dynamic> readJson() => {
    'twin_id': 'twin-1',
    'calculation_run_id': architecture['calculation_run_id'],
    'selected_for_deployment_at': '2026-08-03T10:00:00Z',
    'architecture_compatibility_status': 'ready',
    'origin': 'native_v1',
    'architecture': jsonDecode(jsonEncode(architecture)),
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
}
