// test/bloc/wizard/services/wizard_zip_service_test.dart
// Unit tests for WizardZipService (stateless, no mocks required)

import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/services/wizard_zip_service.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard_state.dart';
import 'package:twin2multicloud_flutter/models/calc_params.dart';

void main() {
  late WizardZipService service;
  late WizardState initialState;

  setUp(() {
    service = WizardZipService();
    // Create a state with calc params for Section 3 validation
    initialState = WizardState(
      mode: WizardMode.create,
      status: WizardStatus.ready,
      zipUploadInProgress: true,
      calcParams: CalcParams.defaultParams(),
    );
  });

  group('WizardZipService', () {
    group('fileHasContent', () {
      test('returns false for null', () {
        expect(service.fileHasContent(null), false);
      });

      test('returns false for non-map types', () {
        expect(service.fileHasContent('string'), false);
        expect(service.fileHasContent(123), false);
        expect(service.fileHasContent([1, 2, 3]), false);
      });

      test('returns false if exists is false', () {
        expect(
          service.fileHasContent({'exists': false, 'content': 'data'}),
          false,
        );
      });

      test('returns false if content is null', () {
        expect(
          service.fileHasContent({'exists': true, 'content': null}),
          false,
        );
      });

      test('returns true if exists and has content', () {
        expect(
          service.fileHasContent({'exists': true, 'content': 'data'}),
          true,
        );
      });
    });

    group('isFileValid', () {
      test('returns false for null', () {
        expect(service.isFileValid(null), false);
      });

      test('returns false if validation_error exists', () {
        expect(
          service.isFileValid({
            'exists': true,
            'content': 'data',
            'validation_error': 'Some error',
          }),
          false,
        );
      });

      test('returns true if valid with no error', () {
        expect(
          service.isFileValid({
            'exists': true,
            'content': 'data',
            'validation_error': null,
          }),
          true,
        );
      });
    });

    group('extractContent', () {
      test('extracts digital_twin_name from config.json', () {
        final files = {
          'config.json': {
            'exists': true,
            'content': '{"digital_twin_name": "TestTwin"}',
          },
        };

        final extracted = service.extractContent(files, {}, {});

        expect(extracted.digitalTwinName, 'TestTwin');
      });

      test('extracts config_events.json content', () {
        final files = {
          'config_events.json': {'exists': true, 'content': '{"events": []}'},
        };

        final extracted = service.extractContent(files, {}, {});

        expect(extracted.configEvents, '{"events": []}');
      });

      test('extracts processors from functions', () {
        final functions = {
          'processors': {
            'device1': {'exists': true, 'content': 'def processor(): pass'},
            'device2': {'exists': true, 'content': 'def processor2(): pass'},
          },
        };

        final extracted = service.extractContent({}, functions, {});

        expect(extracted.processors.length, 2);
        expect(extracted.processors['device1'], 'def processor(): pass');
        expect(extracted.processors['device2'], 'def processor2(): pass');
      });

      test('extracts GLB upload status from assets', () {
        final assets = {
          'scene_glb': {'exists': true, 'saved': true},
        };

        final extracted = service.extractContent({}, {}, assets);

        expect(extracted.glbUploaded, true);
      });

      test('handles AWS state machine path', () {
        final files = {
          'state_machines/aws_step_function.json': {
            'exists': true,
            'content': '{"StartAt": "Init"}',
          },
        };

        final extracted = service.extractContent(files, {}, {});

        expect(extracted.stateMachine, '{"StartAt": "Init"}');
      });
    });

    group('buildValidationMaps', () {
      test('builds processor validation map', () {
        final functions = {
          'processors': {
            'device1': {'exists': true, 'content': 'code'},
            'device2': {
              'exists': true,
              'content': 'code',
              'validation_error': 'error',
            },
          },
        };

        final result = service.buildValidationMaps({}, functions);

        expect(result.processorValidation['device1'], true);
        expect(result.processorValidation['device2'], false);
      });

      test('validates config files', () {
        final files = {
          'config.json': {'exists': true, 'content': '{}'},
          'config_events.json': {
            'exists': true,
            'content': '{}',
            'validation_error': 'invalid',
          },
        };

        final result = service.buildValidationMaps(files, {});

        expect(result.configJsonValid, true);
        expect(result.eventsValid, false);
      });
    });

    group('processZipUpload', () {
      test('returns error for validation failures', () {
        final apiResult = {
          'success': false,
          'validation_errors': ['Missing config.json', 'Invalid structure'],
          'warnings': [],
          'files': {},
          'functions': {},
          'assets': {},
        };

        final result = service.processZipUpload(
          state: initialState,
          apiResult: apiResult,
        );

        expect(result.success, false);
        expect(result.state.errorMessage, contains('Missing config.json'));
        expect(result.state.zipUploadInProgress, false);
      });

      test('returns success with extracted content', () {
        final apiResult = {
          'success': true,
          'validation_errors': [],
          'warnings': [],
          'files': {
            'config.json': {
              'exists': true,
              'content': '{"digital_twin_name": "Test"}',
            },
            'config_events.json': {'exists': true, 'content': '{"events": []}'},
            'config_iot_devices.json': {
              'exists': true,
              'content': '{"devices": []}',
            },
          },
          'functions': {},
          'assets': {},
        };

        final result = service.processZipUpload(
          state: initialState,
          apiResult: apiResult,
        );

        expect(result.success, true);
        expect(result.state.deployerDigitalTwinName, 'Test');
        expect(result.state.configEventsJson, '{"events": []}');
        expect(result.state.hasUnsavedChanges, true);
        expect(result.state.successMessage, contains('items populated'));
      });

      test('includes warnings in result', () {
        final apiResult = {
          'success': true,
          'validation_errors': [],
          'warnings': ['Optional file missing'],
          'files': {},
          'functions': {},
          'assets': {},
        };

        final result = service.processZipUpload(
          state: initialState,
          apiResult: apiResult,
        );

        expect(result.state.warningMessage, 'Optional file missing');
      });
    });

    group('countExtracted', () {
      test('counts files with content', () {
        final files = {
          'file1': {'exists': true, 'content': 'data'},
          'file2': {'exists': false, 'content': null},
          'file3': {'exists': true, 'content': 'more data'},
        };

        final count = service.countExtracted(files, {}, {});

        expect(count, 2);
      });

      test('counts processors and event_actions', () {
        final functions = {
          'processors': {
            'p1': {'exists': true, 'content': 'code'},
          },
          'event_actions': {
            'a1': {'exists': true, 'content': 'code'},
            'a2': {'exists': true, 'content': 'code'},
          },
        };

        final count = service.countExtracted({}, functions, {});

        expect(count, 3);
      });
    });
  });
}
