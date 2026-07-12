import 'package:flutter_test/flutter_test.dart';
import 'package:twin2multicloud_flutter/bloc/wizard/wizard.dart';
import 'package:twin2multicloud_flutter/models/deployer_artifact_validation.dart';

/// Unit tests for L4/L5 WizardBloc events and WizardState properties.
///
/// These tests verify that L4/L5 events are correctly processed and that
/// the state properly reflects changes for hierarchy, scene config, GLB,
/// and user config functionality.
void main() {
  // ============================================================
  // WizardState L4/L5 Fields Tests
  // ============================================================

  group('WizardState L4/L5 Fields', () {
    test('initial state has null L4/L5 fields', () {
      const state = WizardState();
      expect(state.hierarchyContent, isNull);
      expect(state.hierarchyValidated, isFalse);
      expect(state.sceneGlbUploaded, isFalse);
      expect(state.sceneConfigContent, isNull);
      expect(state.sceneConfigValidated, isFalse);
      expect(state.userConfigContent, isNull);
      expect(state.userConfigValidated, isFalse);
    });

    test('copyWith updates hierarchy fields', () {
      const state = WizardState();
      final updated = state.copyWith(
        hierarchyContent: '{"entities": []}',
        hierarchyValidated: true,
      );

      expect(updated.hierarchyContent, '{"entities": []}');
      expect(updated.hierarchyValidated, isTrue);
    });

    test('copyWith updates scene config fields', () {
      const state = WizardState();
      final updated = state.copyWith(
        sceneConfigContent: '{"specVersion": "1.0"}',
        sceneConfigValidated: true,
        sceneGlbUploaded: true,
      );

      expect(updated.sceneConfigContent, '{"specVersion": "1.0"}');
      expect(updated.sceneConfigValidated, isTrue);
      expect(updated.sceneGlbUploaded, isTrue);
    });

    test('copyWith updates user config fields', () {
      const state = WizardState();
      final updated = state.copyWith(
        userConfigContent: '{"admin_email": "test@example.com"}',
        userConfigValidated: true,
      );

      expect(updated.userConfigContent, '{"admin_email": "test@example.com"}');
      expect(updated.userConfigValidated, isTrue);
    });

    test('copyWith preserves other fields when updating L4/L5', () {
      const state = WizardState(
        twinName: 'My Twin',
        debugMode: true,
        currentStep: 3,
      );
      final updated = state.copyWith(hierarchyContent: 'new content');

      expect(updated.twinName, 'My Twin');
      expect(updated.debugMode, isTrue);
      expect(updated.currentStep, 3);
      expect(updated.hierarchyContent, 'new content');
    });
  });

  // ============================================================
  // WizardState L4/L5 Provider Getters Tests
  // ============================================================

  group('WizardState L4/L5 Provider Getters', () {
    test('layer4Provider returns null when calcResult is null', () {
      const state = WizardState();
      expect(state.layer4Provider, isNull);
    });

    test('layer5Provider returns null when calcResult is null', () {
      const state = WizardState();
      expect(state.layer5Provider, isNull);
    });

    test('layer4Provider returns provider from cheapest path', () {
      // Note: This test would require mocking calcResult which needs complex setup
      // For now, we test the null case above
    });
  });

  // ============================================================
  // L4/L5 Event Class Tests
  // ============================================================

  group('L4 Hierarchy Events', () {
    test('WizardHierarchyContentChanged has correct props', () {
      const event = WizardHierarchyContentChanged('{"entities": []}');
      expect(event.content, '{"entities": []}');
      expect(event.props, ['{"entities": []}']);
    });

    test('hierarchy validation request has correct props', () {
      const request = DeployerArtifactValidationRequest(
        type: DeployerArtifactType.hierarchy,
        content: '{"entities": []}',
        provider: 'AWS',
      );
      const event = WizardArtifactValidationRequested(request);
      expect(event.props, [request]);
    });
  });

  group('L4 Scene Config Events', () {
    test('WizardSceneConfigContentChanged has correct props', () {
      const event = WizardSceneConfigContentChanged('{"specVersion": "1.0"}');
      expect(event.content, '{"specVersion": "1.0"}');
      expect(event.props, ['{"specVersion": "1.0"}']);
    });

    test('WizardSceneGlbUploadStatusChanged has correct props', () {
      const event = WizardSceneGlbUploadStatusChanged(true);
      expect(event.uploaded, isTrue);
      expect(event.props, [true]);
    });
  });

  group('L5 User Config Events', () {
    test('WizardUserConfigContentChanged has correct props', () {
      const event = WizardUserConfigContentChanged(
        '{"admin_email": "test@example.com"}',
      );
      expect(event.content, '{"admin_email": "test@example.com"}');
      expect(event.props, ['{"admin_email": "test@example.com"}']);
    });
  });

  group('L4 Cleanup Event', () {
    test('WizardL4CleanupRequested has empty props', () {
      const event = WizardL4CleanupRequested();
      expect(event.props, isEmpty);
    });
  });
}
