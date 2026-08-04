const fixtureDigest =
    'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const fixtureDigestB =
    'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

Map<String, dynamic> architectureProfileSummaryJson() => {
  'profile_id': 'fixture-profile',
  'profile_version': '2',
  'profile_digest': fixtureDigest,
  'display_name': 'Fixture profile',
  'description': 'A strict populated profile used only by contract tests.',
  'lifecycle_status': 'active',
  'responsibilities': [
    {
      'responsibility_id': 'responsibility.ingestion',
      'display_name': 'Ingestion',
      'required': true,
      'capability_ids': ['capability.ingestion'],
      'workload_field_ids': ['workload.telemetry-update-count'],
    },
  ],
  'capability_ids': ['capability.ingestion'],
  'workload_contract_ref': {
    'id': 'digital_twin_workload_v2',
    'version': '2',
    'digest': fixtureDigestB,
  },
  'available_providers': [
    {
      'provider': 'aws',
      'supported': true,
      'profile_id': 'provider-profile.aws.fixture',
      'profile_version': '1',
      'reason_codes': <String>[],
    },
  ],
  'unsupported_providers': [
    {
      'provider': 'gcp',
      'supported': false,
      'profile_id': 'provider-profile.gcp.fixture',
      'profile_version': '1',
      'reason_codes': ['fixture-incomplete'],
    },
  ],
  'extension_slots': [
    {
      'slot_id': 'processor.telemetry',
      'slot_version': '1',
      'logical_component_id': 'component.ingestion',
    },
  ],
};

Map<String, dynamic> architectureProfileDetailJson() => {
  ...architectureProfileSummaryJson(),
  'logical_components': [
    {
      'component_id': 'component.ingestion',
      'component_kind': 'ingress',
      'cost_owner_ids': ['cost.ingestion'],
      'extension_slot_ids': ['processor.telemetry'],
      'input_port_ids': <String>[],
      'observability_contract_id': 'observability.fixture',
      'output_port_ids': ['port.ingestion.telemetry-out'],
      'required': true,
      'required_capability_ids': ['capability.ingestion'],
      'responsibility_id': 'responsibility.ingestion',
    },
  ],
  'logical_edges': <Map<String, dynamic>>[],
  'visualization': {
    'nodes': [
      {
        'id': 'component.ingestion',
        'label': 'Ingestion',
        'responsibility_id': 'responsibility.ingestion',
      },
    ],
    'edges': <Map<String, dynamic>>[],
  },
};

Map<String, dynamic> architectureSelectionJson({
  String twinId = 'twin-1',
  int revision = 1,
}) => {
  'twin_id': twinId,
  'profile_id': 'fixture-profile',
  'profile_version': '2',
  'profile_digest': fixtureDigest,
  'revision': revision,
  'selected_at': '2026-08-03T10:00:00Z',
  'updated_at': '2026-08-03T10:00:00Z',
  'selected_by_user_id': 'user-1',
};

Map<String, dynamic> architecturePreviewJson({int revision = 1}) => {
  'current': {
    'id': 'historical-profile',
    'version': '1',
    'digest': fixtureDigestB,
  },
  'target': {'id': 'fixture-profile', 'version': '2', 'digest': fixtureDigest},
  'expected_revision': revision,
  'incompatible_workload_fields': [
    {'field_id': 'legacy.field', 'display_label': 'Legacy field'},
  ],
  'incompatible_extension_bindings': [
    {
      'slot_id': 'legacy.slot',
      'slot_version': '1',
      'artifact_id': 'artifact-1',
    },
  ],
  'selected_calculation_run_id': 'run-old',
  'deployment_readiness_sections': ['architecture', 'cloud_access'],
  'invalidation_digest': fixtureDigestB,
};

Map<String, dynamic> architectureSelectionResultJson({
  String twinId = 'twin-1',
  int revision = 2,
}) => {
  'selection': architectureSelectionJson(twinId: twinId, revision: revision),
  'revision': revision,
  'invalidated_calculation_run_id': 'run-old',
  'unbound_extension_slot_ids': ['legacy.slot'],
  'cleared_workload_field_ids': ['legacy.field'],
  'deployment_readiness_state': 'invalidated',
};
