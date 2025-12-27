import 'package:flutter/material.dart';
import '../../models/calc_params.dart';

/// Main calculation form with all 26 input fields organized by layer
class CalcForm extends StatefulWidget {
  final void Function(CalcParams params)? onChanged;
  final CalcParams? initialParams;  // Load from saved config

  const CalcForm({super.key, this.onChanged, this.initialParams});

  @override
  State<CalcForm> createState() => _CalcFormState();
}

class _CalcFormState extends State<CalcForm> {
  final _formKey = GlobalKey<FormState>();
  int _rebuildKey = 0; // Forces form rebuild when presets are applied
  int? _selectedPreset; // 1, 2, 3, or null if input modified by user

  // Layer 1 & 2 - Workload
  int _numberOfDevices = 100;
  double _deviceSendingIntervalInMinutes = 2.0;
  double _averageSizeOfMessageInKb = 0.25;
  int _numberOfDeviceTypes = 1;

  // Layer 2 - Processing
  bool _useEventChecking = false;
  int _eventsPerMessage = 1;
  bool _triggerNotificationWorkflow = false;
  int _orchestrationActionsPerMessage = 3;
  bool _returnFeedbackToDevice = false;
  int _numberOfEventActions = 0;
  bool _integrateErrorHandling = false;

  // Layer 3 - Storage
  int _hotStorageDurationInMonths = 1;
  int _coolStorageDurationInMonths = 3;
  int _archiveStorageDurationInMonths = 12;

  // Layer 4 - Twin Management
  bool _needs3DModel = false;
  int _entityCount = 0;
  double _average3DModelSizeInMB = 100.0;

  // Layer 5 - Visualization
  int _dashboardRefreshesPerHour = 2;
  int _apiCallsPerDashboardRefresh = 1;
  int _dashboardActiveHoursPerDay = 8;
  int _amountOfActiveEditors = 0;
  int _amountOfActiveViewers = 5;

  // Currency
  String _currency = 'USD';

  void _updateParams() {
    final params = CalcParams(
      numberOfDevices: _numberOfDevices,
      deviceSendingIntervalInMinutes: _deviceSendingIntervalInMinutes,
      averageSizeOfMessageInKb: _averageSizeOfMessageInKb,
      numberOfDeviceTypes: _numberOfDeviceTypes,
      useEventChecking: _useEventChecking,
      eventsPerMessage: _eventsPerMessage,
      triggerNotificationWorkflow: _triggerNotificationWorkflow,
      orchestrationActionsPerMessage: _orchestrationActionsPerMessage,
      returnFeedbackToDevice: _returnFeedbackToDevice,
      numberOfEventActions: _numberOfEventActions,
      integrateErrorHandling: _integrateErrorHandling,
      hotStorageDurationInMonths: _hotStorageDurationInMonths,
      coolStorageDurationInMonths: _coolStorageDurationInMonths,
      archiveStorageDurationInMonths: _archiveStorageDurationInMonths,
      needs3DModel: _needs3DModel,
      entityCount: _entityCount,
      average3DModelSizeInMB: _average3DModelSizeInMB,
      dashboardRefreshesPerHour: _dashboardRefreshesPerHour,
      apiCallsPerDashboardRefresh: _apiCallsPerDashboardRefresh,
      dashboardActiveHoursPerDay: _dashboardActiveHoursPerDay,
      amountOfActiveEditors: _amountOfActiveEditors,
      amountOfActiveViewers: _amountOfActiveViewers,
      currency: _currency,
    );
    widget.onChanged?.call(params);
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (widget.initialParams != null) {
        // Load from saved params
        _loadFromParams(widget.initialParams!);
      } else {
        // Select Preset 1 (Smart Home) by default on first load
        _fillPreset(
          presetNumber: 1,
          devices: 100,
          interval: 2.0,
          messageSize: 0.25,
          deviceTypes: 3,
          hotMonths: 1,
          coolMonths: 3,
          archiveMonths: 12,
          needs3D: false,
          entities: 0,
          modelSize: 100.0,
          refreshesPerHour: 2,
          editors: 0,
          viewers: 2,
          activeHours: 12,
          eventChecking: true,
          eventsPerMsg: 1,
          notification: true,
          orchestrationActions: 1,
          feedback: true,
          eventActions: 3,
          errorHandling: false,
        );
      }
    });
  }

  /// Load form from saved CalcParams
  void _loadFromParams(CalcParams p) {
    setState(() {
      _numberOfDevices = p.numberOfDevices;
      _deviceSendingIntervalInMinutes = p.deviceSendingIntervalInMinutes;
      _averageSizeOfMessageInKb = p.averageSizeOfMessageInKb;
      _numberOfDeviceTypes = p.numberOfDeviceTypes;
      _useEventChecking = p.useEventChecking;
      _eventsPerMessage = p.eventsPerMessage;
      _triggerNotificationWorkflow = p.triggerNotificationWorkflow;
      _orchestrationActionsPerMessage = p.orchestrationActionsPerMessage;
      _returnFeedbackToDevice = p.returnFeedbackToDevice;
      _numberOfEventActions = p.numberOfEventActions;
      _integrateErrorHandling = p.integrateErrorHandling;
      _hotStorageDurationInMonths = p.hotStorageDurationInMonths;
      _coolStorageDurationInMonths = p.coolStorageDurationInMonths;
      _archiveStorageDurationInMonths = p.archiveStorageDurationInMonths;
      _needs3DModel = p.needs3DModel;
      _entityCount = p.entityCount;
      _average3DModelSizeInMB = p.average3DModelSizeInMB;
      _dashboardRefreshesPerHour = p.dashboardRefreshesPerHour;
      _apiCallsPerDashboardRefresh = p.apiCallsPerDashboardRefresh;
      _dashboardActiveHoursPerDay = p.dashboardActiveHoursPerDay;
      _amountOfActiveEditors = p.amountOfActiveEditors;
      _amountOfActiveViewers = p.amountOfActiveViewers;
      _currency = p.currency;
      _selectedPreset = null;  // No preset when loading saved
      _rebuildKey++;
    });
    _updateParams();
  }

  /// Fill form with preset scenario values
  void _fillPreset({
    required int presetNumber,
    required int devices,
    required double interval,
    required double messageSize,
    required int deviceTypes,
    required int hotMonths,
    required int coolMonths,
    required int archiveMonths,
    required bool needs3D,
    required int entities,
    required double modelSize,
    required int refreshesPerHour,
    required int editors,
    required int viewers,
    required int activeHours,
    required bool eventChecking,
    required int eventsPerMsg,
    required bool notification,
    required int orchestrationActions,
    required bool feedback,
    required int eventActions,
    required bool errorHandling,
  }) {
    setState(() {
      _rebuildKey++; // Force form rebuild to update text fields
      _selectedPreset = presetNumber; // Track which preset is selected
      _numberOfDevices = devices;
      _deviceSendingIntervalInMinutes = interval;
      _averageSizeOfMessageInKb = messageSize;
      _numberOfDeviceTypes = deviceTypes;
      _hotStorageDurationInMonths = hotMonths;
      _coolStorageDurationInMonths = coolMonths;
      _archiveStorageDurationInMonths = archiveMonths;
      _needs3DModel = needs3D;
      _entityCount = entities;
      _average3DModelSizeInMB = modelSize;
      _dashboardRefreshesPerHour = refreshesPerHour;
      _amountOfActiveEditors = editors;
      _amountOfActiveViewers = viewers;
      _dashboardActiveHoursPerDay = activeHours;
      _useEventChecking = eventChecking;
      _eventsPerMessage = eventsPerMsg;
      _triggerNotificationWorkflow = notification;
      _orchestrationActionsPerMessage = orchestrationActions;
      _returnFeedbackToDevice = feedback;
      _numberOfEventActions = eventActions;
      _integrateErrorHandling = errorHandling;
    });
    _updateParams();
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: KeyedSubtree(
        key: ValueKey(_rebuildKey),
        child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Preset Scenarios
          _buildPresetsSection(),
          const SizedBox(height: 24),

          // Currency Selection
          _buildCurrencySection(),
          const SizedBox(height: 24),

          // Layer 1 & 2: Workload
          _buildSectionHeader(
            'Layer 1 & 2: IoT Workload',
            icon: Icons.sensors,
            description: 'Device count, message frequency, and message size drive ingestion and processing costs.',
          ),
          _buildWorkloadSection(),
          const SizedBox(height: 24),

          // Layer 2: Processing
          _buildSectionHeader(
            'Layer 2: Processing & Orchestration',
            icon: Icons.memory,
            description: 'Configure event handling, notifications, and error management.',
          ),
          _buildProcessingSection(),
          const SizedBox(height: 24),

          // Layer 3: Storage
          _buildSectionHeader(
            'Layer 3: Storage Tiers',
            icon: Icons.storage,
            description: 'Set data retention periods for hot, cool, and archive storage.',
          ),
          _buildStorageSection(),
          const SizedBox(height: 24),

          // Layer 4: Twin Management
          _buildSectionHeader(
            'Layer 4: Twin Management',
            icon: Icons.view_in_ar,
            description: 'Configure 3D model requirements for digital twin visualization.',
          ),
          _buildTwinManagementSection(),
          const SizedBox(height: 24),

          // Layer 5: Visualization
          _buildSectionHeader(
            'Layer 5: Visualization',
            icon: Icons.dashboard,
            description: 'Dashboard usage patterns and user access configuration.',
          ),
          _buildVisualizationSection(),
        ],
        ),
      ),
    );
  }

  Widget _buildPresetsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.auto_fix_high, color: Theme.of(context).primaryColor),
            const SizedBox(width: 8),
            Text(
              'Quick Presets',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          'Click a scenario to auto-fill the form with preset values',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 16),
        Center(
          child: Wrap(
            alignment: WrapAlignment.center,
            spacing: 12,
            runSpacing: 12,
            children: [
              _buildPresetCard(
                presetNumber: 1,
                title: 'Smart Home',
                description: 'Small scale, low frequency. Ideal for home automation.',
                icon: Icons.home,
                color: Colors.blue,
                isSelected: _selectedPreset == 1,
                onTap: () => _fillPreset(
                  presetNumber: 1,
                  devices: 100,
                  interval: 2.0,
                  messageSize: 0.25,
                  deviceTypes: 3,
                  hotMonths: 1,
                  coolMonths: 3,
                  archiveMonths: 12,
                  needs3D: false,
                  entities: 0,
                  modelSize: 100.0,
                  refreshesPerHour: 2,
                  editors: 0,
                  viewers: 2,
                  activeHours: 12,
                  eventChecking: true,
                  eventsPerMsg: 1,
                  notification: true,
                  orchestrationActions: 1,
                  feedback: true,
                  eventActions: 3,
                  errorHandling: false,
                ),
              ),
              _buildPresetCard(
                presetNumber: 2,
                title: 'Smart Industrial',
                description: 'Medium scale, high frequency. Factory monitoring.',
                icon: Icons.factory,
                color: Colors.orange,
                isSelected: _selectedPreset == 2,
                onTap: () => _fillPreset(
                  presetNumber: 2,
                  devices: 4000,
                  interval: 0.5,
                  messageSize: 0.5,
                  deviceTypes: 5,
                  hotMonths: 3,
                  coolMonths: 12,
                  archiveMonths: 36,
                  needs3D: false,
                  entities: 0,
                  modelSize: 100.0,
                  refreshesPerHour: 25,
                  editors: 10,
                  viewers: 60,
                  activeHours: 16,
                  eventChecking: true,
                  eventsPerMsg: 1,
                  notification: true,
                  orchestrationActions: 2,
                  feedback: true,
                  eventActions: 5,
                  errorHandling: true,
                ),
              ),
              _buildPresetCard(
                presetNumber: 3,
                title: 'Large Building',
                description: 'Large scale, very high frequency. 3D digital twin.',
                icon: Icons.apartment,
                color: Colors.green,
                isSelected: _selectedPreset == 3,
                onTap: () => _fillPreset(
                  presetNumber: 3,
                  devices: 30000,
                  interval: 0.1,
                  messageSize: 0.8,
                  deviceTypes: 8,
                  hotMonths: 3,
                  coolMonths: 12,
                  archiveMonths: 24,
                  needs3D: true,
                  entities: 1200,
                  modelSize: 100.0,
                  refreshesPerHour: 100,
                  editors: 50,
                  viewers: 120,
                  activeHours: 24,
                  eventChecking: true,
                  eventsPerMsg: 5,
                  notification: true,
                  orchestrationActions: 5,
                  feedback: true,
                  eventActions: 10,
                  errorHandling: true,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildPresetCard({
    required int presetNumber,
    required String title,
    required String description,
    required IconData icon,
    required Color color,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return SizedBox(
      width: 220,
      child: Card(
        clipBehavior: Clip.antiAlias,
        elevation: isSelected ? 4 : 1,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: isSelected 
            ? BorderSide(color: color, width: 2)
            : BorderSide.none,
        ),
        color: isSelected 
          ? color.withAlpha(25) 
          : null,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(icon, color: color),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        title,
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: color,
                        ),
                      ),
                    ),
                    if (isSelected)
                      Icon(Icons.check_circle, color: color, size: 20),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  description,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title, {String? description, IconData? icon}) {
    final headerColor = Theme.of(context).colorScheme.primary;
    return Padding(
      padding: const EdgeInsets.only(bottom: 16, top: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (icon != null) ...[
                Icon(icon, color: headerColor, size: 22),
                const SizedBox(width: 8),
              ],
              Text(
                title,
                style: Theme.of(context).textTheme.titleLarge?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: headerColor,
                ),
              ),
            ],
          ),
          if (description != null) ...[
            const SizedBox(height: 4),
            Text(
              description,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildCurrencySection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            const Icon(Icons.attach_money),
            const SizedBox(width: 12),
            const Text('Currency:'),
            const SizedBox(width: 12),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'USD', label: Text('USD (\$)')),
                ButtonSegment(value: 'EUR', label: Text('EUR (€)')),
              ],
              selected: {_currency},
              onSelectionChanged: (values) {
                setState(() {
                  _currency = values.first;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildWorkloadSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _buildNumberInput(
              label: 'Number of IoT Devices',
              value: _numberOfDevices,
              min: 1,
              onChanged: (v) {
                setState(() {
                  _numberOfDevices = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 16),
            _buildDecimalInput(
              label: 'Sending Interval (minutes)',
              value: _deviceSendingIntervalInMinutes,
              min: 0.1,
              onChanged: (v) {
                setState(() {
                  _deviceSendingIntervalInMinutes = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 16),
            _buildDecimalInput(
              label: 'Average Message Size (KB)',
              value: _averageSizeOfMessageInKb,
              min: 0.01,
              onChanged: (v) {
                setState(() {
                  _averageSizeOfMessageInKb = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 16),
            _buildNumberInput(
              label: 'Number of Device Types',
              value: _numberOfDeviceTypes,
              min: 1,
              onChanged: (v) {
                setState(() {
                  _numberOfDeviceTypes = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProcessingSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // Event Checking
            SwitchListTile(
              title: const Text('Enable Event Checking'),
              value: _useEventChecking,
              onChanged: (v) {
                setState(() {
                  _useEventChecking = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            if (_useEventChecking)
              Padding(
                padding: const EdgeInsets.only(left: 16),
                child: _buildNumberInput(
                  label: 'Events per Message',
                  value: _eventsPerMessage,
                  min: 1,
                  onChanged: (v) {
                    setState(() {
                      _eventsPerMessage = v;
                      _selectedPreset = null;
                    });
                    _updateParams();
                  },
                ),
              ),

            const Divider(),

            // Notification Workflow
            SwitchListTile(
              title: const Text('Trigger Notification Workflow'),
              value: _triggerNotificationWorkflow,
              onChanged: (v) {
                setState(() {
                  _triggerNotificationWorkflow = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            if (_triggerNotificationWorkflow)
              Padding(
                padding: const EdgeInsets.only(left: 16),
                child: _buildNumberInput(
                  label: 'Orchestration Actions per Message',
                  value: _orchestrationActionsPerMessage,
                  min: 1,
                  onChanged: (v) {
                    setState(() {
                      _orchestrationActionsPerMessage = v;
                      _selectedPreset = null;
                    });
                    _updateParams();
                  },
                ),
              ),

            const Divider(),

            // Feedback to Device
            SwitchListTile(
              title: const Text('Return Feedback to Device'),
              value: _returnFeedbackToDevice,
              onChanged: (v) {
                setState(() {
                  _returnFeedbackToDevice = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            if (_returnFeedbackToDevice)
              Padding(
                padding: const EdgeInsets.only(left: 16),
                child: _buildNumberInput(
                  label: 'Number of Event Actions',
                  value: _numberOfEventActions,
                  min: 0,
                  onChanged: (v) {
                    setState(() {
                      _numberOfEventActions = v;
                      _selectedPreset = null;
                    });
                    _updateParams();
                  },
                ),
              ),

            const Divider(),

            // Error Handling
            SwitchListTile(
              title: const Text('Integrate Error Handling'),
              value: _integrateErrorHandling,
              onChanged: (v) {
                setState(() {
                  _integrateErrorHandling = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStorageSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _buildSliderInput(
              label: 'Hot Storage Duration',
              value: _hotStorageDurationInMonths,
              min: 1,
              max: 12,
              suffix: 'months',
              onChanged: (v) {
                setState(() {
                  _hotStorageDurationInMonths = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 24),
            _buildSliderInput(
              label: 'Cool Storage Duration',
              value: _coolStorageDurationInMonths,
              min: 1,
              max: 24,
              suffix: 'months',
              onChanged: (v) {
                setState(() {
                  _coolStorageDurationInMonths = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 24),
            _buildSliderInput(
              label: 'Archive Storage Duration',
              value: _archiveStorageDurationInMonths,
              min: 6,
              max: 36,
              suffix: 'months',
              onChanged: (v) {
                setState(() {
                  _archiveStorageDurationInMonths = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 16),
            // Validation warning
            if (_hotStorageDurationInMonths > _coolStorageDurationInMonths ||
                _coolStorageDurationInMonths > _archiveStorageDurationInMonths)
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: Colors.red[50],
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.warning, color: Colors.red, size: 16),
                    SizedBox(width: 8),
                    Text(
                      'Duration must be: Hot ≤ Cool ≤ Archive',
                      style: TextStyle(color: Colors.red, fontSize: 12),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildTwinManagementSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            // 3D Model Toggle
            SwitchListTile(
              title: const Text('Is a 3D Model Necessary?'),
              value: _needs3DModel,
              onChanged: (v) {
                setState(() {
                  _needs3DModel = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            if (_needs3DModel) ...[
              const SizedBox(height: 16),
              _buildNumberInput(
                label: 'Number of 3D Entities',
                value: _entityCount,
                min: 0,
                onChanged: (v) {
                  setState(() {
                    _entityCount = v;
                    _selectedPreset = null;
                  });
                  _updateParams();
                },
              ),
              const SizedBox(height: 16),
              _buildDecimalInput(
                label: 'Average 3D Model Size (MB)',
                value: _average3DModelSizeInMB,
                min: 0.1,
                onChanged: (v) {
                  setState(() {
                    _average3DModelSizeInMB = v;
                    _selectedPreset = null;
                  });
                  _updateParams();
                },
              ),
            ],

            const Divider(),

            // GCP Self-Hosted L4 (disabled)
            ListTile(
              title: const Text('Allow GCP Self-Hosted L4'),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.grey[200],
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      'Not Implemented',
                      style: TextStyle(fontSize: 11, color: Colors.grey),
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Switch(value: false, onChanged: null),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVisualizationSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _buildNumberInput(
              label: 'Dashboard Refreshes per Hour',
              value: _dashboardRefreshesPerHour,
              min: 0,
              onChanged: (v) {
                setState(() {
                  _dashboardRefreshesPerHour = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 16),
            _buildNumberInput(
              label: 'API Calls per Dashboard Refresh',
              value: _apiCallsPerDashboardRefresh,
              min: 1,
              onChanged: (v) {
                setState(() {
                  _apiCallsPerDashboardRefresh = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 16),
            _buildSliderInput(
              label: 'Dashboard Active Hours per Day',
              value: _dashboardActiveHoursPerDay,
              min: 0,
              max: 24,
              suffix: 'hours',
              onChanged: (v) {
                setState(() {
                  _dashboardActiveHoursPerDay = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 16),
            _buildNumberInput(
              label: 'Monthly Active Editors',
              value: _amountOfActiveEditors,
              min: 0,
              onChanged: (v) {
                setState(() {
                  _amountOfActiveEditors = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),
            const SizedBox(height: 16),
            _buildNumberInput(
              label: 'Monthly Active Viewers',
              value: _amountOfActiveViewers,
              min: 0,
              onChanged: (v) {
                setState(() {
                  _amountOfActiveViewers = v;
                  _selectedPreset = null;
                });
                _updateParams();
              },
            ),

            const Divider(),

            // GCP Self-Hosted L5 (disabled)
            ListTile(
              title: const Text('Allow GCP Self-Hosted L5'),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: Colors.grey[200],
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: const Text(
                      'Not Implemented',
                      style: TextStyle(fontSize: 11, color: Colors.grey),
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Switch(value: false, onChanged: null),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNumberInput({
    required String label,
    required int value,
    required int min,
    required void Function(int) onChanged,
  }) {
    return Row(
      children: [
        Expanded(
          flex: 2,
          child: Text(label),
        ),
        Expanded(
          child: TextFormField(
            initialValue: value.toString(),
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              isDense: true,
              border: OutlineInputBorder(),
            ),
            onChanged: (text) {
              final parsed = int.tryParse(text);
              if (parsed != null && parsed >= min) {
                onChanged(parsed);
              }
            },
          ),
        ),
      ],
    );
  }

  Widget _buildDecimalInput({
    required String label,
    required double value,
    required double min,
    required void Function(double) onChanged,
  }) {
    return Row(
      children: [
        Expanded(
          flex: 2,
          child: Text(label),
        ),
        Expanded(
          child: TextFormField(
            initialValue: value.toString(),
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(
              isDense: true,
              border: OutlineInputBorder(),
            ),
            onChanged: (text) {
              final parsed = double.tryParse(text);
              if (parsed != null && parsed >= min) {
                onChanged(parsed);
              }
            },
          ),
        ),
      ],
    );
  }

  Widget _buildSliderInput({
    required String label,
    required int value,
    required int min,
    required int max,
    required String suffix,
    required void Function(int) onChanged,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label),
            Text(
              '$value $suffix',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ],
        ),
        Slider(
          value: value.toDouble(),
          min: min.toDouble(),
          max: max.toDouble(),
          divisions: max - min,
          onChanged: (v) => onChanged(v.round()),
        ),
      ],
    );
  }
}
