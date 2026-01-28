// lib/screens/wizard/helpers/step3_validation_helper.dart
// Extracted validation logic from step3_deployer.dart

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../bloc/wizard/wizard.dart';
import '../../../providers/twins_provider.dart';
import '../../../utils/api_error_handler.dart';

/// Helper class for Step 3 validation operations.
/// 
/// All methods are static and receive BuildContext as parameter
/// to avoid storing stale context references.
class Step3ValidationHelper {
  
  /// Validate config file via API
  static Future<Map<String, dynamic>> validateConfigFile(
    BuildContext context,
    String configType,
    String content,
    WizardState state,
  ) async {
    final twinId = state.twinId;
    if (twinId == null) {
      return {'valid': false, 'message': 'Save draft first to enable validation'};
    }

    if (content.trim().isEmpty) {
      return {'valid': false, 'message': 'No content to validate'};
    }

    try {
      final container = ProviderScope.containerOf(context);
      final api = container.read(apiServiceProvider);
      final result = await api.validateDeployerConfig(twinId, configType, content);
      
      final valid = result['valid'] == true;
      final message = result['message']?.toString() ?? (valid ? 'Valid ✓' : 'Validation failed');
      
      // Update BLoC state for persistence
      if (context.mounted) {
        context.read<WizardBloc>().add(WizardConfigValidationCompleted(configType, valid));
      }
      
      return {'valid': valid, 'message': message};
    } catch (e) {
      return {'valid': false, 'message': 'Validation failed: ${ApiErrorHandler.extractMessage(e)}'};
    }
  }

  /// Validate L2 content (function-code or state-machine)
  static Future<Map<String, dynamic>> validateL2Content(
    BuildContext context,
    String type,
    String content,
    WizardState state, {
    String? entityId,
  }) async {
    final twinId = state.twinId;
    final provider = state.layer2Provider;
    
    if (twinId == null) return {'valid': false, 'message': 'Save draft first'};
    if (provider == null) return {'valid': false, 'message': 'Complete Step 2 first'};
    if (content.trim().isEmpty) return {'valid': false, 'message': 'No content'};

    try {
      final container = ProviderScope.containerOf(context);
      final api = container.read(apiServiceProvider);
      final result = await api.validateL2Content(twinId, type, content, provider);
      final valid = result['valid'] == true;
      final message = result['message']?.toString() ?? (valid ? 'Valid ✓' : 'Failed');
      
      if (context.mounted && valid) {
        _dispatchL2ValidationEvent(context, type, entityId, valid);
      }
      
      return {'valid': valid, 'message': message};
    } catch (e) {
      return {'valid': false, 'message': ApiErrorHandler.extractMessage(e)};
    }
  }

  static void _dispatchL2ValidationEvent(BuildContext context, String type, String? entityId, bool valid) {
    final bloc = context.read<WizardBloc>();
    if (type == 'function-code') {
      if (entityId != null && entityId.startsWith('processor:')) {
        bloc.add(WizardProcessorValidationCompleted(entityId.substring(10), valid));
      } else if (entityId != null && entityId.startsWith('event-action:')) {
        bloc.add(WizardEventActionValidationCompleted(entityId.substring(13), valid));
      } else if (entityId == 'feedback') {
        bloc.add(WizardEventFeedbackValidationCompleted(valid));
      }
    } else if (type == 'state-machine') {
      bloc.add(WizardStateMachineValidationCompleted(valid));
    }
  }

  /// Validate L4/L5 content
  static Future<Map<String, dynamic>> validateL4Content(
    BuildContext context,
    String type,
    String content,
    WizardState state, {
    String? providerOverride,
  }) async {
    final twinId = state.twinId;
    if (twinId == null) {
      return {'valid': false, 'message': 'Save draft first'};
    }
    
    final provider = (providerOverride ?? state.layer4Provider)?.toLowerCase();
    if (provider == null) {
      final layer = type == 'user-config' ? 'L5' : 'L4';
      return {'valid': false, 'message': 'No $layer provider selected (Step 2)'};
    }
    
    try {
      final container = ProviderScope.containerOf(context);
      final api = container.read(apiServiceProvider);
      final bloc = context.read<WizardBloc>();
      final result = await api.validateL4Content(twinId, type, content, provider);
      
      final valid = result['valid'] == true;
      final message = result['message']?.toString() ?? (valid ? 'Valid' : 'Validation failed');
      
      switch (type) {
        case 'hierarchy':
          bloc.add(WizardHierarchyValidationCompleted(valid));
          break;
        case 'scene-config':
          bloc.add(WizardSceneConfigValidationCompleted(valid));
          break;
        case 'user-config':
          bloc.add(WizardUserConfigValidationCompleted(valid));
          break;
      }
      
      return {'valid': valid, 'message': message};
    } catch (e) {
      return {'valid': false, 'message': ApiErrorHandler.extractMessage(e)};
    }
  }
}
