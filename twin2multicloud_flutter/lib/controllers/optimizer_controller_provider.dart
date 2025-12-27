import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/wizard_cache.dart';
import '../providers/twins_provider.dart';
import 'optimizer_controller.dart';

/// Provider for OptimizerController.
/// 
/// Uses .family to allow passing the WizardCache instance from the widget.
/// This enables the controller to update the cache when calculations complete.
/// 
/// Usage in widget:
/// ```dart
/// final controller = ref.read(optimizerControllerProvider(_cache));
/// final result = await controller.calculate(params);
/// ```
final optimizerControllerProvider = Provider.family<OptimizerController, WizardCache>(
  (ref, cache) => OptimizerController(
    ref.read(apiServiceProvider),
    cache,
  ),
);
