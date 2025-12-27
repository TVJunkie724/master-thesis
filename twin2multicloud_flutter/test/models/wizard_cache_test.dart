import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/models/wizard_cache.dart';

void main() {
  group('WizardCache', () {
    late WizardCache cache;

    setUp(() {
      cache = WizardCache();
    });

    // ============================================================
    // Happy Path Tests
    // ============================================================

    group('dirty state management', () {
      test('initial state has no unsaved changes', () {
        expect(cache.hasUnsavedChanges, isFalse);
      });

      test('markDirty sets hasUnsavedChanges to true', () {
        cache.markDirty();
        expect(cache.hasUnsavedChanges, isTrue);
      });

      test('markClean sets hasUnsavedChanges to false', () {
        cache.markDirty();
        cache.markClean();
        expect(cache.hasUnsavedChanges, isFalse);
      });
    });

    group('credential source tracking', () {
      test('markAwsInherited sets source and valid flag', () {
        cache.markAwsInherited();
        expect(cache.awsCredentialSource, CredentialSource.inherited);
        expect(cache.awsValid, isTrue);
      });

      test('markAzureInherited sets source and valid flag', () {
        cache.markAzureInherited();
        expect(cache.azureCredentialSource, CredentialSource.inherited);
        expect(cache.azureValid, isTrue);
      });

      test('markGcpInherited sets source and valid flag', () {
        cache.markGcpInherited();
        expect(cache.gcpCredentialSource, CredentialSource.inherited);
        expect(cache.gcpValid, isTrue);
      });

      test('markAwsNewlyEntered sets source to newlyEntered', () {
        cache.markAwsNewlyEntered();
        expect(cache.awsCredentialSource, CredentialSource.newlyEntered);
      });

      test('hasNewAwsCredentials returns true for newlyEntered', () {
        cache.markAwsNewlyEntered();
        expect(cache.hasNewAwsCredentials, isTrue);
      });

      test('hasNewAwsCredentials returns false for inherited', () {
        cache.markAwsInherited();
        expect(cache.hasNewAwsCredentials, isFalse);
      });
    });

    group('navigation guards', () {
      test('canProceedToStep2 requires name and valid provider', () {
        expect(cache.canProceedToStep2, isFalse);

        cache.twinName = 'Test Twin';
        expect(cache.canProceedToStep2, isFalse);

        cache.awsValid = true;
        expect(cache.canProceedToStep2, isTrue);
      });

      test('canProceedToStep2 works with any valid provider', () {
        cache.twinName = 'Test Twin';
        
        cache.azureValid = true;
        expect(cache.canProceedToStep2, isTrue);
        
        cache.azureValid = false;
        cache.gcpValid = true;
        expect(cache.canProceedToStep2, isTrue);
      });
    });

    // ============================================================
    // Edge Case Tests
    // ============================================================

    group('clear', () {
      test('resets all fields to defaults', () {
        // Set up cache with data
        cache.twinName = 'My Twin';
        cache.debugMode = true;
        cache.awsCredentials = {'key': 'value'};
        cache.markAwsInherited();
        cache.markDirty();

        // Clear
        cache.clear();

        // Verify reset
        expect(cache.twinName, isNull);
        expect(cache.debugMode, isFalse);
        expect(cache.awsCredentials, isEmpty);
        expect(cache.awsValid, isFalse);
        expect(cache.awsCredentialSource, CredentialSource.none);
        expect(cache.hasUnsavedChanges, isFalse);
      });

      test('clears step 2 data', () {
        cache.calcParams = null;
        cache.pricingSnapshots = {'aws': {}};
        cache.pricingTimestamps = {'aws': '2025-01-01'};

        cache.clear();

        expect(cache.calcParams, isNull);
        expect(cache.calcResult, isNull);
        expect(cache.pricingSnapshots, isNull);
        expect(cache.pricingTimestamps, isNull);
      });
    });

    group('configuredProviders', () {
      test('returns empty set when no providers valid', () {
        expect(cache.configuredProviders, isEmpty);
      });

      test('returns correct set of valid providers', () {
        cache.awsValid = true;
        cache.gcpValid = true;
        
        expect(cache.configuredProviders, {'AWS', 'GCP'});
      });

      test('returns all providers when all valid', () {
        cache.awsValid = true;
        cache.azureValid = true;
        cache.gcpValid = true;
        
        expect(cache.configuredProviders, {'AWS', 'AZURE', 'GCP'});
      });
    });

    group('empty twin name edge cases', () {
      test('empty string blocks step 2', () {
        cache.twinName = '';
        cache.awsValid = true;
        expect(cache.canProceedToStep2, isFalse);
      });

      test('whitespace-only name is allowed (no trim)', () {
        cache.twinName = '   ';
        cache.awsValid = true;
        // Current implementation doesn't trim
        expect(cache.canProceedToStep2, isTrue);
      });
    });
  });
}
