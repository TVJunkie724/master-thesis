import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

// lib/widgets/credentials/credential_doc_links.dart
// Extracted documentation links widget for cloud credentials

/// A widget displaying documentation links for credential setup.
///
/// Features:
/// - Provider-specific links
/// - Opens in browser or VS Code (local files)
/// - Consistent styling
class CredentialDocLinks extends StatelessWidget {
  final String provider;
  final List<CredentialDocLink> links;
  final String? headerText;

  const CredentialDocLinks({
    super.key,
    required this.provider,
    required this.links,
    this.headerText,
  });

  Future<void> _openLink(String target) async {
    final uri = Uri.parse(target);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    if (links.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (headerText != null) ...[
          Text(
            headerText!,
            style: TextStyle(
              fontSize: 12,
              color: theme.colorScheme.onSurfaceVariant,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 8),
        ],
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: links.map((link) => _buildLinkChip(context, link)).toList(),
        ),
      ],
    );
  }

  Widget _buildLinkChip(BuildContext context, CredentialDocLink link) {
    final theme = Theme.of(context);

    return ActionChip(
      avatar: Icon(
        link.icon ?? _getDefaultIcon(link.target),
        size: 16,
        color: theme.colorScheme.primary,
      ),
      label: Text(
        link.label,
        style: TextStyle(color: theme.colorScheme.primary, fontSize: 12),
      ),
      backgroundColor: theme.colorScheme.primaryContainer.withValues(
        alpha: 0.3,
      ),
      side: BorderSide.none,
      onPressed: () => _openLink(link.target),
    );
  }

  IconData _getDefaultIcon(String target) {
    if (target.startsWith('file://')) {
      return Icons.folder_open;
    }
    if (target.contains('docs') || target.contains('documentation')) {
      return Icons.description;
    }
    return Icons.open_in_new;
  }
}

/// A documentation link definition
class CredentialDocLink {
  final String label;
  final String target;
  final IconData? icon;

  const CredentialDocLink({
    required this.label,
    required this.target,
    this.icon,
  });
}

/// Predefined documentation links for each provider
class CredentialDocLinkPresets {
  static List<CredentialDocLink> aws(String baseDocsPath) => [
    CredentialDocLink(
      label: 'AWS Setup Guide',
      target: '$baseDocsPath/aws-credentials.html',
      icon: Icons.description,
    ),
    CredentialDocLink(
      label: 'IAM Console',
      target: 'https://console.aws.amazon.com/iam/',
      icon: Icons.open_in_new,
    ),
  ];

  static List<CredentialDocLink> azure(String baseDocsPath) => [
    CredentialDocLink(
      label: 'Azure Setup Guide',
      target: '$baseDocsPath/azure-credentials.html',
      icon: Icons.description,
    ),
    CredentialDocLink(
      label: 'Azure Portal',
      target: 'https://portal.azure.com/',
      icon: Icons.open_in_new,
    ),
  ];

  static List<CredentialDocLink> gcp(String baseDocsPath) => [
    CredentialDocLink(
      label: 'GCP Setup Guide',
      target: '$baseDocsPath/gcp-credentials.html',
      icon: Icons.description,
    ),
    CredentialDocLink(
      label: 'GCP Console',
      target: 'https://console.cloud.google.com/iam-admin/serviceaccounts',
      icon: Icons.open_in_new,
    ),
  ];
}
