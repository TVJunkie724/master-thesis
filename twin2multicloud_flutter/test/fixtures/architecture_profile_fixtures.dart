const fixtureDigest =
    'sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';
const fixtureDigestB =
    'sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb';

Map<String, dynamic> architectureProfileSummaryJson({
  String profileId = 'fixture-profile',
  String profileVersion = '2',
  String profileDigest = fixtureDigest,
  bool withExtensionSlot = true,
  bool withFlow = false,
}) => {
  'profile_id': profileId,
  'profile_version': profileVersion,
  'profile_digest': profileDigest,
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
    if (withFlow)
      {
        'responsibility_id': 'responsibility.storage',
        'display_name': 'Storage',
        'required': true,
        'capability_ids': ['capability.storage'],
        'workload_field_ids': ['workload.retention-days'],
      },
  ],
  'capability_ids': [
    'capability.ingestion',
    if (withFlow) 'capability.storage',
  ],
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
  'extension_slots': withExtensionSlot
      ? [
          {
            'slot_id': 'processor.telemetry',
            'slot_version': '1',
            'logical_component_id': 'component.ingestion',
          },
        ]
      : <Map<String, dynamic>>[],
};

Map<String, dynamic> architectureProfileDetailJson({
  String profileId = 'fixture-profile',
  String profileVersion = '2',
  String profileDigest = fixtureDigest,
  bool withExtensionSlot = true,
  bool withFlow = false,
}) => {
  ...architectureProfileSummaryJson(
    profileId: profileId,
    profileVersion: profileVersion,
    profileDigest: profileDigest,
    withExtensionSlot: withExtensionSlot,
    withFlow: withFlow,
  ),
  'logical_components': [
    {
      'component_id': 'component.ingestion',
      'component_kind': 'ingress',
      'cost_owner_ids': ['cost.ingestion'],
      'extension_slot_ids': withExtensionSlot
          ? ['processor.telemetry']
          : <String>[],
      'input_port_ids': <String>[],
      'observability_contract_id': 'observability.fixture',
      'output_port_ids': ['port.ingestion.telemetry-out'],
      'required': true,
      'required_capability_ids': ['capability.ingestion'],
      'responsibility_id': 'responsibility.ingestion',
    },
    if (withFlow)
      {
        'component_id': 'component.storage',
        'component_kind': 'hot-storage',
        'cost_owner_ids': ['cost.storage'],
        'extension_slot_ids': <String>[],
        'input_port_ids': ['port.storage.telemetry-in'],
        'observability_contract_id': 'observability.fixture',
        'output_port_ids': <String>[],
        'required': true,
        'required_capability_ids': ['capability.storage'],
        'responsibility_id': 'responsibility.storage',
      },
  ],
  'logical_edges': withFlow
      ? [
          {
            'edge_id': 'edge.ingestion-storage',
            'source_component_id': 'component.ingestion',
            'source_port_id': 'port.ingestion.telemetry-out',
            'destination_component_id': 'component.storage',
            'destination_port_id': 'port.storage.telemetry-in',
            'edge_contract_id': 'edge-contract.telemetry',
            'edge_contract_version': '1',
            'required': true,
            'cost_owner_ids': ['cost.transfer'],
            'transfer_workload_ref': {
              'id': 'workload.telemetry-transfer',
              'version': '1',
            },
            'delivery_requirements': {
              'dead_letter_policy': 'bounded',
              'idempotency': 'required',
              'mode': 'asynchronous',
              'ordering': 'partition',
              'replay': 'bounded',
              'retry_policy': 'bounded',
              'timeout_policy': 'bounded',
            },
            'observability_requirements': {
              'bounded_error_contract': 'required',
              'correlation': 'required',
              'metrics': 'required',
            },
            'trust_requirements': {
              'authentication': 'required',
              'authorization': 'required',
              'transport': 'encrypted',
            },
          },
        ]
      : <Map<String, dynamic>>[],
  'visualization': {
    'nodes': [
      {
        'id': 'component.ingestion',
        'label': 'Ingestion',
        'responsibility_id': 'responsibility.ingestion',
      },
      if (withFlow)
        {
          'id': 'component.storage',
          'label': 'Storage',
          'responsibility_id': 'responsibility.storage',
        },
    ],
    'edges': withFlow
        ? [
            {
              'id': 'edge.ingestion-storage',
              'source': 'component.ingestion',
              'destination': 'component.storage',
            },
          ]
        : <Map<String, dynamic>>[],
  },
};

Map<String, dynamic> architectureSelectionJson({
  String twinId = 'twin-1',
  int revision = 1,
  String profileId = 'fixture-profile',
  String profileVersion = '2',
  String profileDigest = fixtureDigest,
}) => {
  'twin_id': twinId,
  'profile_id': profileId,
  'profile_version': profileVersion,
  'profile_digest': profileDigest,
  'revision': revision,
  'selected_at': '2026-08-03T10:00:00Z',
  'updated_at': '2026-08-03T10:00:00Z',
  'selected_by_user_id': 'user-1',
};
