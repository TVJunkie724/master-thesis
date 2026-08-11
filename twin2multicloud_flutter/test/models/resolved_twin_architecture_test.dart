import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';

void main() {
  late Map<String, dynamic> architecture;
  late Map<String, dynamic> v2Architecture;
  late Map<String, dynamic> sixLayerArchitecture;

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
    final sixLayerRaw = File(
      '../contracts/architecture-profiles/v2/fixtures/valid/'
      'six-layer-aws-azure-eventing-small-resolved.json',
    ).readAsStringSync();
    sixLayerArchitecture = Map<String, dynamic>.from(
      jsonDecode(sixLayerRaw) as Map,
    );
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

  test('parses canonical multi-provider v2 evaluation evidence', () {
    for (final fixture in const [
      'two-cloud-azure-l3l5-gcp-l4-medium-resolved.json',
      'three-cloud-mixed-large-resolved.json',
    ]) {
      final decoded = Map<String, dynamic>.from(
        jsonDecode(
              File(
                '../contracts/architecture-profiles/v2/fixtures/valid/$fixture',
              ).readAsStringSync(),
            )
            as Map,
      );
      final resolved = ResolvedTwinArchitectureRead.fromJson({
        'twin_id': 'twin-v2-multi',
        'calculation_run_id': decoded['calculation_run_id'],
        'selected_for_deployment_at': null,
        'architecture_compatibility_status': 'ready',
        'origin': 'native_v2',
        'architecture': decoded,
      });

      expect(resolved.architecture.providers.length, greaterThan(1));
      expect(resolved.architecture.pricingEvidenceDigests, isNotEmpty);
    }
  });

  test('parses the independent Six-layer Eventing responsibility', () {
    final resolved = ResolvedTwinArchitectureRead.fromJson({
      'twin_id': 'twin-six-layer',
      'calculation_run_id': sixLayerArchitecture['calculation_run_id'],
      'selected_for_deployment_at': null,
      'architecture_compatibility_status': 'ready',
      'origin': 'native_v2',
      'architecture': jsonDecode(jsonEncode(sixLayerArchitecture)),
    });

    expect(resolved.architecture.profileRef.id, 'six-layer-eventing');
    expect(resolved.architecture.profileRef.version, '1');
    expect(resolved.architecture.componentAssignments, hasLength(8));
    expect(
      resolved.architecture.componentAssignments
          .singleWhere(
            (item) => item.logicalComponentId == 'component.eventing',
          )
          .responsibilityId,
      'responsibility.eventing',
    );
    expect(resolved.architecture.resolvedEdges, hasLength(9));
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

  test('v2 rejects re-digested cost summaries that differ from evidence', () {
    final componentMismatch = v2ReadJson();
    final componentArchitecture =
        componentMismatch['architecture'] as Map<String, dynamic>;
    final componentSummary =
        componentArchitecture['cost_summary'] as Map<String, dynamic>;
    final componentTotals = componentSummary['component_totals'] as List;
    (componentTotals.first as Map<String, dynamic>)['monthly_amount'] = '1';
    componentSummary['monthly_total'] = '1';
    componentArchitecture['content_digest'] =
        ResolvedTwinArchitecture.calculateDigest(componentArchitecture);
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(componentMismatch),
      throwsFormatException,
    );

    final totalMismatch = v2ReadJson();
    final totalArchitecture =
        totalMismatch['architecture'] as Map<String, dynamic>;
    (totalArchitecture['cost_summary']
            as Map<String, dynamic>)['monthly_total'] =
        '1';
    totalArchitecture['content_digest'] =
        ResolvedTwinArchitecture.calculateDigest(totalArchitecture);
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(totalMismatch),
      throwsFormatException,
    );
  });
}
