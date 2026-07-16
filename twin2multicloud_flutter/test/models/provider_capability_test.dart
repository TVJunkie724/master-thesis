import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/provider_capability.dart';

import '../fixtures/provider_capability_fixture.dart';

void main() {
  test('parses the complete platform capability matrix', () {
    final contract = PlatformProviderCapabilities.fromJson(
      platformProviderCapabilitiesJson(),
    );

    expect(contract.providers, hasLength(3));
    expect(contract.providers.every((item) => item.layers.length == 7), isTrue);
    expect(contract.capability('AWS', 'L1').selectable, isTrue);
    final gcpL4 = contract.capability('google', 'l4');
    expect(gcpL4.selectable, isFalse);
    expect(gcpL4.availability, CapabilityAvailability.unsupported);
    expect(gcpL4.roadmap, CapabilityRoadmap.planned);
    expect(gcpL4.sourcesAgree, isTrue);
    expect(gcpL4.restrictionSource, 'restricted_by_both');
  });

  test('rejects incomplete, malformed, and inconsistent contracts', () {
    final malformedSchema = platformProviderCapabilitiesJson()
      ..['schema_version'] = 'platform-provider-capabilities.v2';
    expect(
      () => PlatformProviderCapabilities.fromJson(malformedSchema),
      throwsFormatException,
    );

    final incomplete = platformProviderCapabilitiesJson();
    (incomplete['providers'] as List).removeLast();
    expect(
      () => PlatformProviderCapabilities.fromJson(incomplete),
      throwsFormatException,
    );

    final inconsistent = platformProviderCapabilitiesJson();
    final providers = inconsistent['providers'] as List;
    final layers = (providers.first as Map)['layers'] as List;
    (layers.first as Map)['selectable'] = false;
    expect(
      () => PlatformProviderCapabilities.fromJson(inconsistent),
      throwsFormatException,
    );

    final unexpected = platformProviderCapabilitiesJson()..['extra'] = true;
    expect(
      () => PlatformProviderCapabilities.fromJson(unexpected),
      throwsFormatException,
    );
  });
}
