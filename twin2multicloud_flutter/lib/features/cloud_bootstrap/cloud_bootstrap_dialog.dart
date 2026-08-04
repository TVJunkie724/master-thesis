import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../../bloc/cloud_bootstrap/cloud_bootstrap.dart';
import '../../models/cloud_bootstrap.dart';
import '../../models/cloud_connection.dart';
import '../../services/management_api.dart';
import '../../widgets/cloud_connections/cloud_bootstrap_flow.dart';

Future<CloudBootstrapConnectionSummary?> showCloudBootstrapFlow({
  required BuildContext context,
  required CloudBootstrapApi api,
  required CloudProvider provider,
  required CloudBootstrapEntryPoint entryPoint,
  CloudBootstrapTarget? initialTarget,
  String? twinId,
}) {
  return showDialog<CloudBootstrapConnectionSummary>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) => BlocProvider(
      create: (_) => CloudBootstrapBloc(
        api: api,
        provider: provider,
        entryPoint: entryPoint,
        twinId: twinId,
      )..add(CloudBootstrapOpened(initialTarget: initialTarget)),
      child: CloudBootstrapFlow(
        provider: provider,
        entryPoint: entryPoint,
        onConnectionReady: (connection) =>
            Navigator.of(dialogContext).pop(connection),
        onClosed: () => Navigator.of(dialogContext).pop(),
      ),
    ),
  );
}
