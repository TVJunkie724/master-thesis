import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';

import '../../models/resolved_twin_architecture.dart';
import '../../theme/spacing.dart';

class LogicalResolvedFlow extends StatefulWidget {
  final ResolvedTwinArchitecture architecture;

  const LogicalResolvedFlow({super.key, required this.architecture});

  @override
  State<LogicalResolvedFlow> createState() => _LogicalResolvedFlowState();
}

class _LogicalResolvedFlowState extends State<LogicalResolvedFlow> {
  final TransformationController _transformationController =
      TransformationController();
  double _scale = AppSpacing.logicalProfileFlowDefaultScale;

  @override
  void dispose() {
    _transformationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final viewportWidth = MediaQuery.sizeOf(context).width;
      final layoutWidth = viewportWidth > 0
          ? viewportWidth
          : constraints.maxWidth;
      final compact =
          layoutWidth < AppSpacing.logicalProfileFlowCompactBreakpoint;
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (!compact)
            Align(
              alignment: Alignment.centerRight,
              child: Wrap(
                spacing: AppSpacing.xs,
                children: [
                  IconButton(
                    tooltip: 'Zoom out resolved architecture',
                    onPressed: _scale <= AppSpacing.logicalProfileFlowMinScale
                        ? null
                        : () => _setZoom(
                            _scale - AppSpacing.logicalProfileFlowScaleStep,
                          ),
                    icon: const Icon(Icons.zoom_out),
                  ),
                  IconButton(
                    tooltip: 'Reset resolved architecture zoom',
                    onPressed:
                        _scale == AppSpacing.logicalProfileFlowDefaultScale
                        ? null
                        : _resetZoom,
                    icon: const Icon(Icons.center_focus_strong),
                  ),
                  IconButton(
                    tooltip: 'Zoom in resolved architecture',
                    onPressed: _scale >= AppSpacing.logicalProfileFlowMaxScale
                        ? null
                        : () => _setZoom(
                            _scale + AppSpacing.logicalProfileFlowScaleStep,
                          ),
                    icon: const Icon(Icons.zoom_in),
                  ),
                ],
              ),
            ),
          if (!compact) const SizedBox(height: AppSpacing.xs),
          if (compact)
            _CompactResolvedFlow(architecture: widget.architecture)
          else
            _ResolvedGraph(
              architecture: widget.architecture,
              transformationController: _transformationController,
            ),
        ],
      );
    },
  );

  void _setZoom(double value) {
    final scale = value.clamp(
      AppSpacing.logicalProfileFlowMinScale,
      AppSpacing.logicalProfileFlowMaxScale,
    );
    _transformationController.value = Matrix4.identity()
      ..setEntry(0, 0, scale)
      ..setEntry(1, 1, scale);
    setState(() => _scale = scale);
  }

  void _resetZoom() => _setZoom(AppSpacing.logicalProfileFlowDefaultScale);
}

class _ResolvedGraph extends StatelessWidget {
  final ResolvedTwinArchitecture architecture;
  final TransformationController transformationController;

  const _ResolvedGraph({
    required this.architecture,
    required this.transformationController,
  });

  @override
  Widget build(BuildContext context) {
    if (architecture.resolvedEdges.isEmpty) {
      return Wrap(
        spacing: AppSpacing.md,
        runSpacing: AppSpacing.md,
        children: [
          for (final assignment in architecture.componentAssignments)
            SizedBox(
              width: AppSpacing.logicalProfileFlowNodeWidth,
              child: _ResolvedFlowNode(assignment: assignment),
            ),
        ],
      );
    }
    final graph = Graph();
    final nodes = {
      for (final assignment in architecture.componentAssignments)
        assignment.assignmentId: Node.Id(assignment.assignmentId),
    };
    for (final node in nodes.values) {
      graph.addNode(node);
    }
    for (final edge in architecture.resolvedEdges) {
      graph.addEdge(
        nodes[edge.sourceAssignmentId]!,
        nodes[edge.destinationAssignmentId]!,
      );
    }
    final configuration = SugiyamaConfiguration()
      ..nodeSeparation = AppSpacing.lg.toInt()
      ..levelSeparation = AppSpacing.xl.toInt()
      ..orientation = SugiyamaConfiguration.ORIENTATION_LEFT_RIGHT;

    return Semantics(
      label:
          'Resolved logical flow with ${nodes.length} components and '
          '${architecture.resolvedEdges.length} declared connections',
      child: SizedBox(
        height: AppSpacing.logicalProfileFlowViewportHeight,
        child: InteractiveViewer(
          transformationController: transformationController,
          constrained: false,
          boundaryMargin: const EdgeInsets.all(AppSpacing.xl),
          minScale: AppSpacing.logicalProfileFlowMinScale,
          maxScale: AppSpacing.logicalProfileFlowMaxScale,
          child: GraphView(
            graph: graph,
            algorithm: SugiyamaAlgorithm(configuration),
            animated: false,
            paint: Paint()
              ..color = Theme.of(context).colorScheme.outline
              ..strokeWidth = AppSpacing.logicalProfileFlowEdgeWidth
              ..style = PaintingStyle.stroke,
            builder: (node) {
              final assignment = architecture.componentAssignments.firstWhere(
                (item) => item.assignmentId == node.key!.value.toString(),
              );
              return SizedBox(
                width: AppSpacing.logicalProfileFlowNodeWidth,
                child: _ResolvedFlowNode(assignment: assignment),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _CompactResolvedFlow extends StatelessWidget {
  final ResolvedTwinArchitecture architecture;

  const _CompactResolvedFlow({required this.architecture});

  @override
  Widget build(BuildContext context) {
    if (architecture.resolvedEdges.isEmpty) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final assignment in architecture.componentAssignments) ...[
            _ResolvedFlowNode(assignment: assignment),
            if (assignment != architecture.componentAssignments.last)
              const SizedBox(height: AppSpacing.sm),
          ],
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final edge in architecture.resolvedEdges)
          _ResolvedFlowEdge(
            edge: edge,
            source: _assignment(architecture, edge.sourceAssignmentId),
            destination: _assignment(
              architecture,
              edge.destinationAssignmentId,
            ),
          ),
      ],
    );
  }
}

class _ResolvedFlowNode extends StatelessWidget {
  final ResolvedComponentAssignment assignment;

  const _ResolvedFlowNode({required this.assignment});

  @override
  Widget build(BuildContext context) => Semantics(
    label:
        '${assignment.logicalComponentId}, ${assignment.provider.label}, '
        '${assignment.serviceId}, ${assignment.required ? 'required' : 'supporting'}',
    child: Card(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.sm),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              assignment.logicalComponentId,
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: AppSpacing.xs),
            Text('${assignment.provider.label} · ${assignment.serviceId}'),
          ],
        ),
      ),
    ),
  );
}

class _ResolvedFlowEdge extends StatelessWidget {
  final ResolvedArchitectureEdge edge;
  final ResolvedComponentAssignment source;
  final ResolvedComponentAssignment destination;

  const _ResolvedFlowEdge({
    required this.edge,
    required this.source,
    required this.destination,
  });

  @override
  Widget build(BuildContext context) => Semantics(
    label:
        '${source.logicalComponentId} connects to '
        '${destination.logicalComponentId}, '
        '${edge.edgeId}, '
        '${edge.isCrossCloud ? 'cross-cloud bridge' : 'provider-local transport'}, '
        '${edge.mechanism}, ${edge.deliveryMode}, ${edge.ordering}',
    child: Card(
      child: ListTile(
        leading: Icon(
          edge.isCrossCloud ? Icons.cloud_sync : Icons.arrow_downward,
        ),
        title: Text(
          '${source.logicalComponentId} → ${destination.logicalComponentId}',
        ),
        subtitle: Text(
          '${source.provider.label} → ${destination.provider.label} · '
          '${edge.mechanism}',
        ),
      ),
    ),
  );
}

ResolvedComponentAssignment _assignment(
  ResolvedTwinArchitecture architecture,
  String assignmentId,
) => architecture.componentAssignments.firstWhere(
  (item) => item.assignmentId == assignmentId,
);
