import 'dart:convert';
import 'dart:io';

import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/architecture_profile.dart';
import 'package:twin2multicloud_flutter/models/cloud_connection.dart';
import 'package:twin2multicloud_flutter/models/resolved_deployment_specification.dart';
import 'package:twin2multicloud_flutter/models/resolved_twin_architecture.dart';

import 'architecture_profile_fixtures.dart';
import 'typed_api_fixtures.dart';

WizardState architectureReadyWizardState({
  bool withExtensionSlot = false,
  String twinId = 'twin-1',
  bool persisted = true,
  String profileId = 'six-layer-eventing',
  String? profileVersion,
  String profileDigest = fixtureDigest,
}) {
  final resolvedProfileVersion =
      profileVersion ?? (profileId == 'six-layer-eventing' ? '1' : '2');
  final detail = ArchitectureProfileDetail.fromJson(
    architectureProfileDetailJson(
      withExtensionSlot: withExtensionSlot,
      profileId: profileId,
      profileVersion: resolvedProfileVersion,
      profileDigest: profileDigest,
    ),
  );
  final selection = TwinArchitectureSelection.fromJson(
    architectureSelectionJson(
      twinId: twinId,
      profileId: profileId,
      profileVersion: resolvedProfileVersion,
      profileDigest: profileDigest,
    ),
  );
  return WizardState(
    status: WizardStatus.ready,
    twinId: persisted ? twinId : null,
    twinName: 'Factory twin',
    architectureSelection: selection,
    architectureDetailPhase: ArchitectureDetailPhase.ready,
    architectureProfileDetail: detail,
  );
}

ResolvedTwinArchitectureRead resolvedArchitectureFixture({
  String runId = 'run-123',
  String twinId = 'twin-1',
  CloudProvider? provider,
  String profileId = 'six-layer-eventing',
  String? profileVersion,
  String profileDigest = fixtureDigest,
}) {
  final resolvedProfileVersion =
      profileVersion ?? (profileId == 'six-layer-eventing' ? '1' : '2');
  final architecture = Map<String, dynamic>.from(
    jsonDecode(
          File(
            '../contracts/architecture-profiles/v2/fixtures/valid/'
            'six-layer-aws-azure-eventing-small-resolved.json',
          ).readAsStringSync(),
        )
        as Map,
  );
  architecture['calculation_run_id'] = runId;
  architecture['resolution_status'] = 'publishable';
  architecture['architecture_profile_ref'] = {
    'id': profileId,
    'version': resolvedProfileVersion,
    'digest': profileDigest,
  };
  final deploymentRef =
      architecture['deployment_specification_ref'] as Map<String, dynamic>;
  deploymentRef['calculation_run_id'] = runId;
  deploymentRef['digest'] = ResolvedDeploymentSpecificationData.calculateDigest(
    TypedApiFixtures.deploymentSpecificationJson(runId: runId),
  );

  if (provider != null) {
    final providerRefs = architecture['provider_profile_refs'] as List;
    final existingProviderRefs = providerRefs.cast<Map>();
    final matchingRefs = existingProviderRefs.where(
      (item) => item['provider'] == provider.apiValue,
    );
    final fullProviderRef = Map<String, dynamic>.from(
      matchingRefs.isNotEmpty ? matchingRefs.first : existingProviderRefs.first,
    );
    if (matchingRefs.isEmpty) {
      fullProviderRef
        ..['provider'] = provider.apiValue
        ..['id'] = 'provider-profile.${provider.apiValue}.fixture';
      providerRefs.add(fullProviderRef);
    }
    final selectedProviderRef = Map<String, dynamic>.from(fullProviderRef)
      ..remove('provider');
    for (final raw in architecture['component_assignments'] as List) {
      final assignment = raw as Map<String, dynamic>;
      assignment['provider'] = provider.apiValue;
      assignment['provider_implementation_profile_ref'] =
          Map<String, dynamic>.from(selectedProviderRef);
      assignment['service_id'] =
          '${provider.apiValue}.fixture.${assignment['logical_component_id']}';
    }
    for (final raw in architecture['resolved_edges'] as List) {
      final edge = raw as Map<String, dynamic>;
      edge['transfer_route_class'] = 'same_provider_same_region';
      edge['mechanism'] = 'provider_native_trigger';
      edge['edge_implementation_id'] =
          'edge-implementation.${provider.apiValue}.fixture';
    }
  }

  architecture['content_digest'] = ResolvedTwinArchitecture.calculateDigest(
    architecture,
  );

  return ResolvedTwinArchitectureRead.fromJson({
    'twin_id': twinId,
    'calculation_run_id': runId,
    'selected_for_deployment_at': '2026-08-03T10:00:00Z',
    'architecture_compatibility_status': 'ready',
    'origin': 'native_v2',
    'architecture': architecture,
  });
}
