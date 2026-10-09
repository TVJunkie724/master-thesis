"""Fixed L4 infrastructure plan-only check; no Apply, seeding or cloud writes.

These partial research plans do not establish projection or full admission.
All account-bound inputs, logs and saved plans stay in a private output folder.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import uuid

from src.core.secure_files import atomic_write_private_bytes

AWS_ROOTS = (
    'aws_s3_bucket.aws_six_layer_twinmaker[0]',
    'aws_s3_bucket_public_access_block.aws_six_layer_twinmaker[0]',
    'aws_iam_role.aws_six_layer_twinmaker[0]',
    'aws_iam_role_policy.aws_six_layer_twinmaker[0]',
    'time_sleep.aws_six_layer_twinmaker_iam[0]',
    'awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0]',
)
AZURE_ROOTS = (
    'azurerm_resource_group.main[0]',
    'azurerm_digital_twins_instance.azure_azure_digital_twins[0]',
)
EXPECTED = {'aws': frozenset((*AWS_ROOTS, 'random_id.deployment_suffix')),
            'azure': frozenset(AZURE_ROOTS)}


def review(provider, plan):
    changes = [r for r in plan.get('resource_changes', []) if r['mode'] == 'managed']
    if (len(changes) != len(EXPECTED[provider])
            or {r['address'] for r in changes} != EXPECTED[provider]
            or any(r['change']['actions'] != ['create'] for r in changes)):
        raise RuntimeError('L4_PLAN_SCOPE_REJECTED')
    return len(changes)


def prepare(provider, credentials_path, terraform_dir, output):
    os.umask(0o077)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    credentials = json.loads(credentials_path.read_text())
    values = {'digital_twin_name': 'l4-' + provider + '-' + uuid.uuid4().hex[:8],
              'project_path': str(output), 'layer_1_provider': 'aws',
              'layer_2_provider': 'aws', 'layer_3_hot_provider': 'aws',
              'layer_3_cold_provider': 'aws', 'layer_3_archive_provider': 'aws',
              'layer_4_provider': provider, 'layer_5_provider': provider,
              'enable_aws_logging': False, 'enable_azure_logging': False,
              'enable_gcp_logging': False}
    aws = credentials['aws']
    values.update({k: aws[k] for k in ('aws_access_key_id', 'aws_secret_access_key', 'aws_region')})
    values.update({k: credentials['azure'][k] for k in (
        'azure_subscription_id', 'azure_tenant_id', 'azure_client_id', 'azure_client_secret')})
    inputs = output / 'private.tfvars.json'
    atomic_write_private_bytes(inputs, json.dumps(values).encode())
    roots = AWS_ROOTS if provider == 'aws' else AZURE_ROOTS
    saved_plan = output / 'review.plan'
    command = ['terraform', 'plan', '-input=false', '-no-color',
               '-state=' + str(output / 'fresh.tfstate'), '-out=' + str(saved_plan),
               '-var-file=' + str(inputs), *('-target=' + r for r in roots)]
    env = dict(os.environ, TF_IN_AUTOMATION='1')
    with (output / 'plan.log').open('wb') as log:
        result = subprocess.run(command, cwd=terraform_dir, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=300)
    if result.returncode:
        raise RuntimeError('L4_PLAN_FAILED_PRIVATE_LOG_RETAINED')
    with (output / 'plan.json').open('wb') as log:
        result = subprocess.run(['terraform', 'show', '-json', str(saved_plan)],
                                cwd=terraform_dir, env=env, stdout=log,
                                stderr=subprocess.PIPE, timeout=60)
    if result.returncode:
        raise RuntimeError('L4_PLAN_EXPORT_FAILED')
    count = review(provider, json.loads((output / 'plan.json').read_text()))
    return {'provider': provider, 'create_only_entries': count, 'apply_executed': False,
            'scope': 'l4_infrastructure_only', 'projection_verified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('provider', choices=('aws', 'azure'))
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--terraform-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.provider, args.credentials.resolve(),
                                 args.terraform_dir.resolve(), args.output_dir.resolve())))
    except Exception as error:
        # Never include provider diagnostics, paths or credential-bearing inputs.
        print(json.dumps({'provider': args.provider, 'failed': True,
                          'error_type': type(error).__name__, 'apply_executed': False}))
        raise SystemExit(1)
