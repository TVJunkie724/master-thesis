import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';

void main() {
  late Map<String, dynamic> architecture;

  setUpAll(() {
    architecture = Map<String, dynamic>.from(
      jsonDecode(
            File(
              '../contracts/architecture-profiles/v2/fixtures/valid/'
              'six-layer-aws-azure-eventing-small-resolved.json',
            ).readAsStringSync(),
          )
          as Map,
    );
  });

  Map<String, dynamic> readJson() => {
    'twin_id': 'twin-six-layer',
    'calculation_run_id': architecture['calculation_run_id'],
    'selected_for_deployment_at': null,
    'architecture_compatibility_status': 'ready',
    'origin': 'native_v2',
    'architecture': jsonDecode(jsonEncode(architecture)),
  };

  test('parses the independent Six-layer Eventing responsibility', () {
    final resolved = ResolvedTwinArchitectureRead.fromJson(readJson());

    expect(
      resolved.architecture.schemaVersion,
      ResolvedTwinArchitecture.v2SchemaVersion,
    );
    expect(resolved.architecture.resolutionStatus, 'offline_contract_fixture');
    expect(resolved.origin, ResolvedArchitectureOrigin.nativeV2);
    expect(resolved.architecture.profileRef.id, 'six-layer-eventing');
    expect(resolved.architecture.profileRef.version, '1');
    expect(resolved.architecture.componentAssignments, hasLength(8));
    expect(resolved.architecture.resolvedEdges, hasLength(9));
    expect(resolved.architecture.providers.length, 2);
    expect(resolved.architecture.pricingEvidenceDigests, isNotEmpty);
    expect(
      resolved.architecture.componentAssignments
          .singleWhere(
            (item) => item.logicalComponentId == 'component.eventing',
          )
          .responsibilityId,
      'responsibility.eventing',
    );
  });

  test('fails closed on unsupported schema, digest, and origin', () {
    final unsupported = readJson();
    (unsupported['architecture'] as Map)['schema_version'] =
        'resolved-twin-architecture.v1';
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(unsupported),
      throwsFormatException,
    );

    final digestTamper = readJson();
    (digestTamper['architecture'] as Map)['content_digest'] =
        'sha256:${List.filled(64, '0').join()}';
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(digestTamper),
      throwsFormatException,
    );

    final originMismatch = readJson()..['origin'] = 'native_v1';
    expect(
      () => ResolvedTwinArchitectureRead.fromJson(originMismatch),
      throwsFormatException,
    );
  });

  test('rejects negative costs and unresolved edges', () {
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

  test('rejects re-digested cost summaries that differ from evidence', () {
    final mismatch = readJson();
    final resolved = mismatch['architecture'] as Map<String, dynamic>;
    final summary = resolved['cost_summary'] as Map<String, dynamic>;
    (summary['component_totals'] as List).first['monthly_amount'] = '1';
    summary['monthly_total'] = '1';
    resolved['content_digest'] = ResolvedTwinArchitecture.calculateDigest(
      resolved,
    );

    expect(
      () => ResolvedTwinArchitectureRead.fromJson(mismatch),
      throwsFormatException,
    );
  });
}
