import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/config/docs_config.dart';

void main() {
  test('normalizes the configured documentation base URL', () {
    expect(
      DocsConfig.normalizeBaseUrl(' https://docs.example.test/// '),
      'https://docs.example.test',
    );
    expect(
      DocsConfig.getProviderLinksUrl(
        'Google',
        baseUrl: 'https://docs.example.test/',
      ),
      'https://docs.example.test/cloud-setup/provider-links/#gcp',
    );
  });

  test('builds canonical provider links for every supported provider', () {
    const baseUrl = 'http://localhost:5010';

    expect(
      DocsConfig.getProviderLinksUrl('AWS', baseUrl: baseUrl),
      '$baseUrl/cloud-setup/provider-links/#aws',
    );
    expect(
      DocsConfig.getProviderLinksUrl('azure', baseUrl: baseUrl),
      '$baseUrl/cloud-setup/provider-links/#azure',
    );
    expect(
      DocsConfig.getProviderLinksUrl('gcp', baseUrl: baseUrl),
      '$baseUrl/cloud-setup/provider-links/#gcp',
    );
  });

  test('rejects unsafe or ambiguous documentation configuration', () {
    expect(() => DocsConfig.normalizeBaseUrl(''), throwsStateError);
    expect(
      () => DocsConfig.normalizeBaseUrl('file:///tmp/docs'),
      throwsStateError,
    );
    expect(
      () => DocsConfig.getProviderLinksUrl(
        'unknown',
        baseUrl: 'https://docs.example.test',
      ),
      throwsArgumentError,
    );
  });
}
