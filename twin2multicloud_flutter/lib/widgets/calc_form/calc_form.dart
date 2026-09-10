import 'package:flutter/material.dart';
import '../../models/calc_params.dart';
import '../../theme/spacing.dart';

enum CalcFormSection {
  scenarioAndCurrency,
  deviceTraffic,
  processing,
  retention,
  twinCapabilities,
}

/// Main calculation form with optimizer inputs organized by responsibility.
class CalcForm extends StatefulWidget {
  final void Function(CalcParams params)? onChanged;
  final void Function(bool isValid)? onValidChanged; // Reports form validity
  final CalcParams? initialParams; // Load from saved config
  final GlobalKey<FormState>?
  formKey; // Optional external form key for validation
  final CalcFormSection? section;
  final String? profileId;
  final String? profileVersion;

  const CalcForm({
    super.key,
    this.onChanged,
    this.onValidChanged,
    this.initialParams,
    this.formKey,
    this.section,
    this.profileId,
    this.profileVersion,
  });

  @override
  State<CalcForm> createState() => _CalcFormState();
}

class _CalcFormState extends State<CalcForm> {
  final _internalFormKey = GlobalKey<FormState>();
  GlobalKey<FormState> get _formKey => widget.formKey ?? _internalFormKey;
  SixLayerWorkloadScenario _sixLayerScenario = SixLayerWorkloadScenario.small;
  String _currency = 'USD';

  bool get _isSixLayerProfile =>
      widget.profileId == 'six-layer-eventing' && widget.profileVersion == '1';

  @override
  void initState() {
    super.initState();
    _restoreScenario();
    _notifyAfterFrame();
  }

  @override
  void didUpdateWidget(covariant CalcForm oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.profileId != widget.profileId ||
        oldWidget.profileVersion != widget.profileVersion) {
      _restoreScenario();
      _notifyAfterFrame();
    }
  }

  void _restoreScenario() {
    final initial = widget.initialParams;
    _sixLayerScenario = initial?.isSixLayer == true
        ? initial!.scenario!
        : SixLayerWorkloadScenario.small;
    _currency = initial?.isSixLayer == true ? initial!.currency : 'USD';
  }

  void _notifyAfterFrame() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _updateParams();
    });
  }

  void _updateParams() {
    if (!_isSixLayerProfile) {
      widget.onValidChanged?.call(false);
      return;
    }
    widget.onChanged?.call(
      CalcParams.sixLayer(scenario: _sixLayerScenario, currency: _currency),
    );
    widget.onValidChanged?.call(true);
  }

  @override
  Widget build(BuildContext context) {
    if (!_isSixLayerProfile) {
      return Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Text(
          'A verified Six-layer architecture is required before configuring the workload.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
    }
    return _buildSixLayerForm();
  }

  Widget _buildSixLayerForm() {
    final params = CalcParams.sixLayer(
      scenario: _sixLayerScenario,
      currency: _currency,
    );
    return Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _section(CalcFormSection.scenarioAndCurrency, [
            _buildSectionHeader(
              'Frozen thesis scenario',
              icon: Icons.science_outlined,
              description:
                  'Choose one reproducible Small, Medium, or Large workload.',
            ),
            _buildSixLayerScenarioCards(),
            const SizedBox(height: AppSpacing.md),
            _buildCurrencySection(),
            const SizedBox(height: AppSpacing.md),
            const _Phase8EventsNotice(),
          ]),
          _section(CalcFormSection.deviceTraffic, [
            _buildV2ReadOnlyCard('Device traffic', [
              ('Devices', '${params.numberOfDevices}'),
              (
                'Sending interval',
                '${params.deviceSendingIntervalInMinutes} minutes',
              ),
              ('Average message', '${params.averageSizeOfMessageInKb} KB'),
              ('Device types', '${params.numberOfDeviceTypes}'),
            ]),
          ]),
          _section(CalcFormSection.processing, [
            _buildV2ReadOnlyCard('Independent Event Layer workload', [
              ('Event scenario', params.eventingScenarioId!),
              ('Rule/action check', 'Mandatory'),
              ('Notification workflow', 'Embedded'),
              ('Device feedback', 'Mandatory'),
            ]),
          ]),
          _section(CalcFormSection.retention, [
            _buildV2ReadOnlyCard('Storage retention', [
              ('Hot', '${params.hotStorageDurationInMonths} month'),
              ('Cool', '${params.coolStorageDurationInMonths} months'),
              ('Archive', '${params.archiveStorageDurationInMonths} months'),
            ]),
          ]),
          _section(CalcFormSection.twinCapabilities, [
            _buildV2ReadOnlyCard('Twin and dashboard activity', [
              ('Twin entities', '${params.entityCount}'),
              (
                'State materializations',
                '${params.twinStateMaterializationsPerSecond}/second',
              ),
              ('Graph updates', '${params.twinGraphUpdatesPerSecond}/second'),
              (
                'Aggregate refreshes',
                '${params.dashboardRefreshesPerHour}/hour',
              ),
              ('Monthly editors', '${params.amountOfActiveEditors}'),
              ('Monthly viewers', '${params.amountOfActiveViewers}'),
            ]),
          ]),
        ],
      ),
    );
  }

  Widget _buildSixLayerScenarioCards() => LayoutBuilder(
    builder: (context, constraints) {
      final viewportWidth = MediaQuery.sizeOf(context).width;
      final roundedViewportWidth = viewportWidth.roundToDouble();
      final columns = roundedViewportWidth >= AppSpacing.maxContentWidthLarge
          ? 3
          : roundedViewportWidth >=
                AppSpacing.configurationWorkloadCompactBreakpoint
          ? 2
          : 1;
      final cardWidth =
          (constraints.maxWidth - (columns - 1) * AppSpacing.md) / columns;
      return Wrap(
        spacing: AppSpacing.md,
        runSpacing: AppSpacing.md,
        children: SixLayerWorkloadScenario.values
            .map(
              (scenario) => SizedBox(
                key: ValueKey('six-layer-scenario-card-${scenario.name}'),
                width: cardWidth,
                child: _buildSixLayerScenarioCard(scenario),
              ),
            )
            .toList(growable: false),
      );
    },
  );

  Widget _buildSixLayerScenarioCard(SixLayerWorkloadScenario scenario) {
    final selected = scenario == _sixLayerScenario;
    final params = CalcParams.sixLayer(scenario: scenario);
    final color = Theme.of(context).colorScheme.primary;
    return Semantics(
      selected: selected,
      button: true,
      label:
          "${scenario.label}, ${params.numberOfDevices} devices, "
          "${params.eventingScenarioId}, ${selected ? 'selected' : 'not selected'}",
      child: Card(
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
          side: selected
              ? BorderSide(color: color, width: AppSpacing.xxs)
              : BorderSide(color: Theme.of(context).dividerColor),
        ),
        child: InkWell(
          key: ValueKey('six-layer-scenario-${scenario.name}'),
          onTap: () {
            if (selected) return;
            setState(() => _sixLayerScenario = scenario);
            _updateParams();
          },
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        scenario.label,
                        style: Theme.of(context).textTheme.titleMedium
                            ?.copyWith(fontWeight: FontWeight.bold),
                      ),
                    ),
                    if (selected) Icon(Icons.check_circle, color: color),
                  ],
                ),
                const SizedBox(height: AppSpacing.sm),
                Text('${params.numberOfDevices} devices'),
                Text(
                  params.eventingScenarioId!,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildV2ReadOnlyCard(String title, List<(String, String)> rows) =>
      Card(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: Theme.of(
                  context,
                ).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: AppSpacing.md),
              for (final row in rows) ...[
                _ReadOnlyValueRow(label: row.$1, value: row.$2),
                if (row != rows.last) const Divider(height: AppSpacing.lg),
              ],
              const SizedBox(height: AppSpacing.md),
              Text(
                'Values are fixed for the reproducible thesis comparison.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
        ),
      );

  Widget _section(CalcFormSection section, List<Widget> children) => Offstage(
    offstage: widget.section != null && widget.section != section,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: children,
    ),
  );

  Widget _buildSectionHeader(
    String title, {
    String? description,
    IconData? icon,
  }) {
    final headerColor = Theme.of(context).colorScheme.primary;
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md, top: AppSpacing.sm),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (icon != null) ...[
                Icon(icon, color: headerColor, size: AppSpacing.iconMd),
                const SizedBox(width: AppSpacing.sm),
              ],
              Expanded(
                child: Text(
                  title,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: headerColor,
                  ),
                ),
              ),
            ],
          ),
          if (description != null) ...[
            const SizedBox(height: AppSpacing.xs),
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
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Wrap(
          spacing: AppSpacing.md,
          runSpacing: AppSpacing.sm,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            const Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.attach_money),
                SizedBox(width: AppSpacing.sm),
                Text('Currency:'),
              ],
            ),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'USD', label: Text('USD (\$)')),
                ButtonSegment(value: 'EUR', label: Text('EUR (€)')),
              ],
              selected: {_currency},
              onSelectionChanged: (values) {
                setState(() {
                  _currency = values.first;
                });
                _updateParams();
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _Phase8EventsNotice extends StatelessWidget {
  const _Phase8EventsNotice();

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.primaryContainer,
      borderRadius: BorderRadius.circular(AppSpacing.borderRadiusLg),
    ),
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            Icons.event_available,
            color: Theme.of(context).colorScheme.onPrimaryContainer,
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Text(
              'Events use the independent Event Layer and are always active in the standalone Six-layer profile. '
              'They are part of the canonical PoC workload and cannot be disabled.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onPrimaryContainer,
              ),
            ),
          ),
        ],
      ),
    ),
  );
}

class _ReadOnlyValueRow extends StatelessWidget {
  final String label;
  final String value;

  const _ReadOnlyValueRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final compact =
          constraints.maxWidth < AppSpacing.resolvedDeploymentWideBreakpoint;
      final labelWidget = Text(
        label,
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      );
      final valueWidget = SelectableText(
        value,
        style: Theme.of(
          context,
        ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
      );
      if (compact) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            labelWidget,
            const SizedBox(height: AppSpacing.xs),
            valueWidget,
          ],
        );
      }
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: labelWidget),
          const SizedBox(width: AppSpacing.md),
          Expanded(child: valueWidget),
        ],
      );
    },
  );
}
