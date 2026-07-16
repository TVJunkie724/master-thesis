Map<String, dynamic> platformProviderCapabilitiesJson() {
  Map<String, dynamic> source(bool available) => {
    'availability': available ? 'available' : 'unsupported',
    'roadmap': available ? 'none' : 'planned',
    'reason_code': available ? null : 'DEPLOYMENT_PATH_NOT_IMPLEMENTED',
    'reason': available ? null : 'Capability is not implemented.',
    'verification_level': available ? 'contract_tested' : 'not_verified',
  };

  return {
    'schema_version': 'platform-provider-capabilities.v1',
    'complete': true,
    'sources': {
      'optimizer': {
        'status': 'available',
        'schema_version': 'provider-service-capabilities.v1',
      },
      'deployer': {
        'status': 'available',
        'schema_version': 'provider-service-capabilities.v1',
      },
    },
    'providers': [
      for (final provider in const ['aws', 'azure', 'gcp'])
        {
          'provider': provider,
          'layers': [
            for (final layer in const [
              'l1',
              'l2',
              'l3_hot',
              'l3_cool',
              'l3_archive',
              'l4',
              'l5',
            ])
              {..._platformLayer(provider, layer, source)},
          ],
        },
    ],
  };
}

Map<String, dynamic> _platformLayer(
  String provider,
  String layer,
  Map<String, dynamic> Function(bool available) source,
) {
  final available = provider != 'gcp' || !{'l4', 'l5'}.contains(layer);
  return {
    'layer': layer,
    'availability': available ? 'available' : 'unsupported',
    'roadmap': available ? 'none' : 'planned',
    'reason_code': available ? null : 'DEPLOYMENT_PATH_NOT_IMPLEMENTED',
    'reason': available
        ? null
        : 'GCP ${layer.toUpperCase()} is outside the implemented thesis path.',
    'selectable': available,
    'sources_agree': true,
    'restriction_source': available ? 'none' : 'restricted_by_both',
    'verification_level': available ? 'contract_tested' : 'not_verified',
    'sources': {'optimizer': source(available), 'deployer': source(available)},
  };
}
