// test/bloc/wizard/helpers/credentials_helper_test.dart
// Tests for CredentialsHelper utility functions

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/helpers/credentials_helper.dart';

void main() {
  group('CredentialsHelper', () {
    group('extractMaskedCredentials', () {
      test('returns empty map for null input', () {
        final result = CredentialsHelper.extractMaskedCredentials(null);
        expect(result.isEmpty, true);
      });
      
      test('returns empty map for non-map input', () {
        final result = CredentialsHelper.extractMaskedCredentials('string');
        expect(result.isEmpty, true);
      });
      
      test('masks all non-null values', () {
        final config = {
          'access_key': 'AKIAIOSFODNN7EXAMPLE',
          'secret_key': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
          'region': 'us-east-1',
        };
        final result = CredentialsHelper.extractMaskedCredentials(config);
        
        expect(result['access_key'], '••••••••');
        expect(result['secret_key'], '••••••••');
        expect(result['region'], '••••••••');
      });
      
      test('skips null values', () {
        final config = {
          'key1': 'value1',
          'key2': null,
        };
        final result = CredentialsHelper.extractMaskedCredentials(config);
        
        expect(result.containsKey('key1'), true);
        expect(result.containsKey('key2'), false);
      });
      
      test('handles empty map', () {
        final result = CredentialsHelper.extractMaskedCredentials({});
        expect(result.isEmpty, true);
      });
    });
    
    group('hasStoredCredentials', () {
      test('returns true when masked values present', () {
        final credentials = {
          'access_key': '••••••••',
          'secret_key': '••••••••',
        };
        
        expect(CredentialsHelper.hasStoredCredentials(credentials), true);
      });
      
      test('returns false for empty map', () {
        expect(CredentialsHelper.hasStoredCredentials({}), false);
      });
      
      test('returns false for null map', () {
        expect(CredentialsHelper.hasStoredCredentials(null), false);
      });
      
      test('returns true for non-masked values too', () {
        final credentials = {
          'access_key': 'AKIAIOSFODNN7EXAMPLE',
        };
        
        expect(CredentialsHelper.hasStoredCredentials(credentials), true);
      });
    });
    
    group('getRequiredFields', () {
      test('returns AWS required fields', () {
        final fields = CredentialsHelper.getRequiredFields('aws');
        
        expect(fields.contains('access_key_id'), true);
        expect(fields.contains('secret_access_key'), true);
        expect(fields.contains('region'), true);
      });
      
      test('returns Azure required fields', () {
        final fields = CredentialsHelper.getRequiredFields('azure');
        
        expect(fields.contains('subscription_id'), true);
        expect(fields.contains('client_id'), true);
        expect(fields.contains('client_secret'), true);
        expect(fields.contains('tenant_id'), true);
      });
      
      test('returns GCP required fields', () {
        final fields = CredentialsHelper.getRequiredFields('gcp');
        
        expect(fields.contains('project_id'), true);
        expect(fields.contains('service_account_json'), true);
      });
      
      test('returns empty list for unknown provider', () {
        final fields = CredentialsHelper.getRequiredFields('unknown');
        expect(fields.isEmpty, true);
      });
      
      test('handles case insensitivity', () {
        expect(CredentialsHelper.getRequiredFields('AWS').isNotEmpty, true);
        expect(CredentialsHelper.getRequiredFields('Azure').isNotEmpty, true);
        expect(CredentialsHelper.getRequiredFields('GCP').isNotEmpty, true);
      });
    });
    
    group('areAllRequiredFieldsFilled', () {
      test('returns true when all required fields filled', () {
        final awsCreds = {
          'access_key_id': 'AKIA...',
          'secret_access_key': 'secret...',
          'region': 'us-east-1',
        };
        
        expect(CredentialsHelper.areAllRequiredFieldsFilled('aws', awsCreds), true);
      });
      
      test('returns false when required field missing', () {
        final awsCreds = {
          'access_key_id': 'AKIA...',
          // secret_access_key missing
          'region': 'us-east-1',
        };
        
        expect(CredentialsHelper.areAllRequiredFieldsFilled('aws', awsCreds), false);
      });
      
      test('returns false when required field empty', () {
        final awsCreds = {
          'access_key_id': 'AKIA...',
          'secret_access_key': '',  // Empty string
          'region': 'us-east-1',
        };
        
        expect(CredentialsHelper.areAllRequiredFieldsFilled('aws', awsCreds), false);
      });
      
      test('returns false for null credentials', () {
        expect(CredentialsHelper.areAllRequiredFieldsFilled('aws', null), false);
      });
    });
  });
}
