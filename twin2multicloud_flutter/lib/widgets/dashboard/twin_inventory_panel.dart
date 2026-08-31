import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/twin.dart';
import '../../theme/spacing.dart';
import '../../utils/twin_state_utils.dart';
import 'dashboard_strings.dart';

class TwinInventoryPanel extends StatelessWidget {
  final List<Twin> twins;
  final bool isBusy;
  final VoidCallback onCreate;
  final VoidCallback onImport;
  final VoidCallback onRefresh;
  final ValueChanged<Twin> onOpen;
  final ValueChanged<Twin> onDuplicate;
  final ValueChanged<Twin> onExport;
  final ValueChanged<Twin> onDelete;

  const TwinInventoryPanel({
    super.key,
    required this.twins,
    required this.isBusy,
    required this.onCreate,
    required this.onImport,
    required this.onRefresh,
    required this.onOpen,
    required this.onDuplicate,
    required this.onExport,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final sortedTwins = List<Twin>.of(twins)
      ..sort((first, second) {
        final updatedComparison = second.updatedAt.compareTo(first.updatedAt);
        if (updatedComparison != 0) return updatedComparison;
        return first.name.toLowerCase().compareTo(second.name.toLowerCase());
      });

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _InventoryHeader(
          isBusy: isBusy,
          onCreate: onCreate,
          onImport: onImport,
          onRefresh: onRefresh,
        ),
        const SizedBox(height: AppSpacing.lg),
        if (sortedTwins.isEmpty)
          const _EmptyInventory()
        else
          ...sortedTwins.map(
            (twin) => Padding(
              key: ValueKey(twin.id),
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: _TwinInventoryRow(
                twin: twin,
                isBusy: isBusy,
                onOpen: () => onOpen(twin),
                onDuplicate: () => onDuplicate(twin),
                onExport: () => onExport(twin),
                onDelete: () => onDelete(twin),
              ),
            ),
          ),
      ],
    );
  }
}

class _InventoryHeader extends StatelessWidget {
  final bool isBusy;
  final VoidCallback onCreate;
  final VoidCallback onImport;
  final VoidCallback onRefresh;

  const _InventoryHeader({
    required this.isBusy,
    required this.onCreate,
    required this.onImport,
    required this.onRefresh,
  });

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, _) {
      final textScale = MediaQuery.textScalerOf(context).scale(1);
      final compact =
          MediaQuery.sizeOf(context).width < AppSpacing.maxContentWidthMedium ||
          textScale > AppSpacing.resolvedArchitectureWideTextScaleLimit;
      final title = Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            DashboardStrings.title,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            DashboardStrings.supportingText,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
        ],
      );
      final actions = Wrap(
        spacing: AppSpacing.sm,
        runSpacing: AppSpacing.sm,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          if (isBusy)
            const SizedBox.square(
              dimension: AppSpacing.iconMd,
              child: CircularProgressIndicator(
                strokeWidth: AppSpacing.compactProgressIndicatorStrokeWidth,
              ),
            ),
          IconButton(
            onPressed: isBusy ? null : onRefresh,
            icon: const Icon(Icons.refresh),
            tooltip: DashboardStrings.refreshTooltip,
          ),
          TextButton.icon(
            onPressed: isBusy ? null : onImport,
            icon: const Icon(Icons.upload_file_outlined),
            label: const Text(DashboardStrings.importTwin),
          ),
          FilledButton.icon(
            onPressed: isBusy ? null : onCreate,
            icon: const Icon(Icons.add),
            label: const Text(DashboardStrings.newTwin),
          ),
        ],
      );

      if (compact) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            title,
            const SizedBox(height: AppSpacing.md),
            actions,
          ],
        );
      }
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: title),
          const SizedBox(width: AppSpacing.md),
          Flexible(child: actions),
        ],
      );
    },
  );
}

class _TwinInventoryRow extends StatelessWidget {
  final Twin twin;
  final bool isBusy;
  final VoidCallback onOpen;
  final VoidCallback onDuplicate;
  final VoidCallback onExport;
  final VoidCallback onDelete;

  const _TwinInventoryRow({
    required this.twin,
    required this.isBusy,
    required this.onOpen,
    required this.onDuplicate,
    required this.onExport,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) => FocusTraversalGroup(
    policy: OrderedTraversalPolicy(),
    child: Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: LayoutBuilder(
          builder: (context, _) {
            final textScale = MediaQuery.textScalerOf(context).scale(1);
            final compact =
                MediaQuery.sizeOf(context).width <
                    AppSpacing.maxContentWidthMedium ||
                textScale > AppSpacing.resolvedArchitectureWideTextScaleLimit;
            return compact ? _buildCompact(context) : _buildWide(context);
          },
        ),
      ),
    ),
  );

  Widget _buildWide(BuildContext context) => Row(
    children: [
      Expanded(
        flex: 3,
        child: Text(
          twin.name,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: Theme.of(context).textTheme.titleMedium,
        ),
      ),
      const SizedBox(width: AppSpacing.md),
      Expanded(
        flex: 2,
        child: Align(
          alignment: Alignment.centerLeft,
          child: TwinStateUtils.buildBadge(
            context,
            twin.state,
            showIcon: false,
          ),
        ),
      ),
      const SizedBox(width: AppSpacing.md),
      Expanded(flex: 2, child: Text(_updatedLabel(), maxLines: 2)),
      const SizedBox(width: AppSpacing.md),
      Expanded(
        flex: 3,
        child: FocusTraversalOrder(
          order: const NumericFocusOrder(1),
          child: _ContinuationButton(
            isDraft: twin.isDraft,
            isBusy: isBusy,
            onPressed: onOpen,
          ),
        ),
      ),
      const SizedBox(width: AppSpacing.xs),
      FocusTraversalOrder(
        order: const NumericFocusOrder(2),
        child: _TwinOverflowMenu(
          twinName: twin.name,
          isBusy: isBusy,
          onDuplicate: onDuplicate,
          onExport: onExport,
          onDelete: onDelete,
        ),
      ),
    ],
  );

  Widget _buildCompact(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Text(
              twin.name,
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          FocusTraversalOrder(
            order: const NumericFocusOrder(2),
            child: _TwinOverflowMenu(
              twinName: twin.name,
              isBusy: isBusy,
              onDuplicate: onDuplicate,
              onExport: onExport,
              onDelete: onDelete,
            ),
          ),
        ],
      ),
      const SizedBox(height: AppSpacing.sm),
      TwinStateUtils.buildBadge(context, twin.state),
      const SizedBox(height: AppSpacing.sm),
      Text(_updatedLabel()),
      const SizedBox(height: AppSpacing.md),
      FocusTraversalOrder(
        order: const NumericFocusOrder(1),
        child: _ContinuationButton(
          isDraft: twin.isDraft,
          isBusy: isBusy,
          onPressed: onOpen,
        ),
      ),
    ],
  );

  String _updatedLabel() =>
      '${DashboardStrings.updatedPrefix}${DateFormat('MMM d, yyyy').format(twin.updatedAt)}';
}

class _ContinuationButton extends StatelessWidget {
  final bool isDraft;
  final bool isBusy;
  final VoidCallback onPressed;

  const _ContinuationButton({
    required this.isDraft,
    required this.isBusy,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) => OutlinedButton(
    onPressed: isBusy ? null : onPressed,
    child: Text(
      isDraft
          ? DashboardStrings.continueConfiguration
          : DashboardStrings.openLifecycle,
    ),
  );
}

enum _TwinMenuAction { duplicate, export, delete }

class _TwinOverflowMenu extends StatelessWidget {
  final String twinName;
  final bool isBusy;
  final VoidCallback onDuplicate;
  final VoidCallback onExport;
  final VoidCallback onDelete;

  const _TwinOverflowMenu({
    required this.twinName,
    required this.isBusy,
    required this.onDuplicate,
    required this.onExport,
    required this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    final label = '${DashboardStrings.moreActionsPrefix}$twinName';
    return Semantics(
      button: true,
      label: label,
      child: PopupMenuButton<_TwinMenuAction>(
        enabled: !isBusy,
        tooltip: label,
        icon: const Icon(Icons.more_vert),
        onSelected: (action) {
          switch (action) {
            case _TwinMenuAction.duplicate:
              onDuplicate();
            case _TwinMenuAction.export:
              onExport();
            case _TwinMenuAction.delete:
              onDelete();
          }
        },
        itemBuilder: (context) => const [
          PopupMenuItem(
            value: _TwinMenuAction.duplicate,
            child: _MenuLabel(
              icon: Icons.copy_outlined,
              label: DashboardStrings.duplicate,
            ),
          ),
          PopupMenuItem(
            value: _TwinMenuAction.export,
            child: _MenuLabel(
              icon: Icons.download_outlined,
              label: DashboardStrings.export,
            ),
          ),
          PopupMenuItem(
            value: _TwinMenuAction.delete,
            child: _MenuLabel(
              icon: Icons.delete_outline,
              label: DashboardStrings.delete,
            ),
          ),
        ],
      ),
    );
  }
}

class _MenuLabel extends StatelessWidget {
  final IconData icon;
  final String label;

  const _MenuLabel({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) => Row(
    children: [
      Icon(icon, size: AppSpacing.iconMd),
      const SizedBox(width: AppSpacing.sm),
      Text(label),
    ],
  );
}

class _EmptyInventory extends StatelessWidget {
  const _EmptyInventory();

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.xxl),
    child: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.science_outlined,
            size: AppSpacing.xxl,
            color: Theme.of(context).colorScheme.outline,
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            DashboardStrings.emptyTitle,
            style: Theme.of(context).textTheme.titleMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            DashboardStrings.emptyDescription,
            style: Theme.of(context).textTheme.bodyMedium,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    ),
  );
}
