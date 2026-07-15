import 'package:flutter/material.dart';

import '../../../widgets/selectable_scaffold.dart';

class ConfigurationWorkspaceScaffold extends StatelessWidget {
  final PreferredSizeWidget appBar;
  final bool isLoading;
  final Widget header;
  final Widget alerts;
  final Widget workspace;
  final Widget navigation;

  const ConfigurationWorkspaceScaffold({
    super.key,
    required this.appBar,
    required this.isLoading,
    required this.header,
    required this.alerts,
    required this.workspace,
    required this.navigation,
  });

  @override
  Widget build(BuildContext context) {
    return SelectableScaffold(
      appBar: appBar,
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                header,
                alerts,
                Expanded(child: workspace),
                navigation,
              ],
            ),
    );
  }
}
