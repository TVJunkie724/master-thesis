import 'package:flutter/material.dart';
import 'package:graphview/GraphView.dart';

import '../../../models/architecture_profile.dart';
import '../../../theme/spacing.dart';

enum _FlowMode { overview, components }

class LogicalProfileFlow extends StatefulWidget {
  static const compactBreakpoint =
      AppSpacing.logicalProfileFlowCompactBreakpoint;

  final ArchitectureProfileDetail detail;

  const LogicalProfileFlow({super.key, required this.detail});

  @override
  State<LogicalProfileFlow> createState() => _LogicalProfileFlowState();
}

class _LogicalProfileFlowState extends State<LogicalProfileFlow> {
  final TransformationController _transformationController =
      TransformationController();
  _FlowMode _mode = _FlowMode.overview;
  double _scale = AppSpacing.logicalProfileFlowDefaultScale;

  @override
  void dispose() {
    _transformationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final projection = _projection(widget.detail, _mode);
    return LayoutBuilder(
      builder: (context, constraints) {
        final viewportWidth = MediaQuery.sizeOf(context).width;
        final layoutWidth = viewportWidth > 0
            ? viewportWidth
            : constraints.maxWidth;
        final compact = layoutWidth < LogicalProfileFlow.compactBreakpoint;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                SegmentedButton<_FlowMode>(
                  segments: const [
                    ButtonSegment(
                      value: _FlowMode.overview,
                      label: Text('Overview'),
                      icon: Icon(Icons.view_agenda_outlined),
                    ),
                    ButtonSegment(
                      value: _FlowMode.components,
                      label: Text('Components'),
                      icon: Icon(Icons.account_tree_outlined),
                    ),
                  ],
                  selected: {_mode},
                  onSelectionChanged: (selection) {
                    setState(() => _mode = selection.single);
                    _resetZoom();
                  },
                ),
                if (!compact)
                  Wrap(
                    spacing: AppSpacing.xs,
                    children: [
                      IconButton(
                        tooltip: 'Zoom out',
                        onPressed:
                            _scale <= AppSpacing.logicalProfileFlowMinScale
                            ? null
                            : () => _setZoom(
                                _scale - AppSpacing.logicalProfileFlowScaleStep,
                              ),
                        icon: const Icon(Icons.zoom_out),
                      ),
                      IconButton(
                        tooltip: 'Reset zoom',
                        onPressed:
                            _scale == AppSpacing.logicalProfileFlowDefaultScale
                            ? null
                            : _resetZoom,
                        icon: const Icon(Icons.center_focus_strong),
                      ),
                      IconButton(
                        tooltip: 'Zoom in',
                        onPressed:
                            _scale >= AppSpacing.logicalProfileFlowMaxScale
                            ? null
                            : () => _setZoom(
                                _scale + AppSpacing.logicalProfileFlowScaleStep,
                              ),
                        icon: const Icon(Icons.zoom_in),
                      ),
                    ],
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            if (compact)
              _CompactFlow(projection: projection)
            else
              _GraphFlow(
                projection: projection,
                transformationController: _transformationController,
              ),
            if (projection.edges.isNotEmpty) ...[
              const SizedBox(height: AppSpacing.sm),
              _EdgeSummary(projection: projection),
            ],
          ],
        );
      },
    );
  }

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

class _CompactFlow extends StatelessWidget {
  final _FlowProjection projection;

  const _CompactFlow({required this.projection});

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      for (final node in projection.nodes) ...[
        _FlowNode(node: node),
        if (projection.outgoing(node.id).isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.md,
              AppSpacing.xs,
              AppSpacing.md,
              AppSpacing.sm,
            ),
            child: Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.xs,
              children: [
                for (final edge in projection.outgoing(node.id))
                  Semantics(
                    label: projection.edgeSemanticLabel(edge),
                    child: Chip(
                      avatar: const Icon(Icons.arrow_downward),
                      label: Text(projection.label(edge.destination)),
                    ),
                  ),
              ],
            ),
          ),
        if (node != projection.nodes.last)
          const SizedBox(height: AppSpacing.sm),
      ],
    ],
  );
}

class _GraphFlow extends StatelessWidget {
  final _FlowProjection projection;
  final TransformationController transformationController;

  const _GraphFlow({
    required this.projection,
    required this.transformationController,
  });

  @override
  Widget build(BuildContext context) {
    if (projection.edges.isEmpty) {
      return Center(
        child: Wrap(
          spacing: AppSpacing.md,
          runSpacing: AppSpacing.md,
          children: [
            for (final node in projection.nodes)
              SizedBox(
                width: AppSpacing.logicalProfileFlowNodeWidth,
                child: _FlowNode(node: node),
              ),
          ],
        ),
      );
    }
    final graph = Graph();
    final nodes = {
      for (final item in projection.nodes) item.id: Node.Id(item.id),
    };
    for (final node in nodes.values) {
      graph.addNode(node);
    }
    for (final edge in projection.edges) {
      graph.addEdge(nodes[edge.source]!, nodes[edge.destination]!);
    }
    final configuration = SugiyamaConfiguration()
      ..nodeSeparation = AppSpacing.lg.toInt()
      ..levelSeparation = AppSpacing.xl.toInt()
      ..orientation = SugiyamaConfiguration.ORIENTATION_LEFT_RIGHT;

    return Semantics(
      label:
          'Logical architecture flow with ${nodes.length} nodes and ${projection.edges.length} connections',
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
              final projected = projection.byId(node.key!.value.toString());
              return SizedBox(
                width: AppSpacing.logicalProfileFlowNodeWidth,
                child: _FlowNode(node: projected),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _EdgeSummary extends StatelessWidget {
  final _FlowProjection projection;

  const _EdgeSummary({required this.projection});

  @override
  Widget build(BuildContext context) => Semantics(
    container: true,
    explicitChildNodes: true,
    label: 'Connection summary',
    child: ExpansionTile(
      tilePadding: EdgeInsets.zero,
      title: Text('Connections (${projection.edges.length})'),
      children: [
        for (final edge in projection.edges)
          ListTile(
            contentPadding: EdgeInsets.zero,
            dense: true,
            leading: const Icon(Icons.arrow_forward),
            title: Text(
              '${projection.label(edge.source)} → ${projection.label(edge.destination)}',
            ),
            subtitle: Text(edge.purpose),
          ),
      ],
    ),
  );
}

class _FlowNode extends StatelessWidget {
  final _ProjectedNode node;

  const _FlowNode({required this.node});

  @override
  Widget build(BuildContext context) => Semantics(
    label: node.semanticLabel,
    child: Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(node.label, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            Text(node.subtitle, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    ),
  );
}

class _FlowProjection {
  final List<_ProjectedNode> nodes;
  final List<_ProjectedEdge> edges;

  const _FlowProjection({required this.nodes, required this.edges});

  _ProjectedNode byId(String id) => nodes.firstWhere((node) => node.id == id);

  String label(String id) => byId(id).label;

  String edgeSemanticLabel(_ProjectedEdge edge) =>
      '${label(edge.source)} connects to ${label(edge.destination)}, '
      '${edge.purpose}';

  List<_ProjectedEdge> outgoing(String id) =>
      edges.where((edge) => edge.source == id).toList(growable: false);
}

class _ProjectedNode {
  final String id;
  final String label;
  final String subtitle;
  final String semanticLabel;

  const _ProjectedNode({
    required this.id,
    required this.label,
    required this.subtitle,
    required this.semanticLabel,
  });
}

class _ProjectedEdge {
  final String source;
  final String destination;
  final String purpose;

  const _ProjectedEdge({
    required this.source,
    required this.destination,
    required this.purpose,
  });
}

_FlowProjection _projection(ArchitectureProfileDetail detail, _FlowMode mode) {
  if (mode == _FlowMode.components) {
    return _FlowProjection(
      nodes: [
        for (final visual in detail.visualization.nodes)
          _componentNode(detail, visual),
      ],
      edges: [
        for (final edge in detail.visualization.edges)
          _ProjectedEdge(
            source: edge.source,
            destination: edge.destination,
            purpose: detail.logicalEdges
                .firstWhere((logical) => logical.edgeId == edge.id)
                .edgeContractId,
          ),
      ],
    );
  }

  final componentResponsibilities = {
    for (final component in detail.logicalComponents)
      component.componentId: component.responsibilityId,
  };
  final seenEdges = <String>{};
  final edges = <_ProjectedEdge>[];
  for (final edge in detail.logicalEdges) {
    final source = componentResponsibilities[edge.sourceComponentId]!;
    final destination = componentResponsibilities[edge.destinationComponentId]!;
    final key = '$source->$destination';
    if (source != destination && seenEdges.add(key)) {
      edges.add(
        _ProjectedEdge(
          source: source,
          destination: destination,
          purpose: edge.edgeContractId,
        ),
      );
    }
  }
  return _FlowProjection(
    nodes: [
      for (final responsibility in detail.summary.responsibilities)
        _ProjectedNode(
          id: responsibility.responsibilityId,
          label: responsibility.displayName,
          subtitle: responsibility.required ? 'Required' : 'Supporting',
          semanticLabel:
              '${responsibility.displayName}, ${responsibility.required ? 'required' : 'supporting'} responsibility, ${responsibility.capabilityIds.length} capabilities',
        ),
    ],
    edges: edges,
  );
}

_ProjectedNode _componentNode(
  ArchitectureProfileDetail detail,
  ArchitectureVisualizationNode visual,
) {
  final component = detail.logicalComponents.firstWhere(
    (item) => item.componentId == visual.id,
  );
  return _ProjectedNode(
    id: visual.id,
    label: visual.label,
    subtitle: component.componentKind,
    semanticLabel:
        '${visual.label}, responsibility ${visual.responsibilityId}, ${component.required ? 'required' : 'supporting'} component',
  );
}
