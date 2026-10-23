"""Fixed AWS/Azure L3-to-L5 research evidence, not a full-profile deployment.

Plan first. Execute that immutable plan only with explicit live authorization.
Actual stored fixture points, authenticated cloud-generated SVG, immediate
Destroy and independent inventory. All responses/state remain private.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid
from urllib.parse import urlencode

from scripts.prepare_core_runtime import ROOT
from scripts.run_core_evaluation import Terraform, reserve, save, terraform_resource_timings, utc_now
from scripts.run_l4_evaluation import deadline, lifecycle
from src.core.secure_files import atomic_write_private_bytes
from src.providers.terraform.package_builders.aws_six_layer import build_aws_six_layer_domain_app
from src.providers.terraform.package_builders.azure_six_layer import build_azure_six_layer_graph_apps

DEVICE = 'l5-device'
METRIC = 'temperature'
AWS_ALLOWED = frozenset((
    'random_password.cursor', 'aws_dynamodb_table.raw', 'aws_dynamodb_table.rollup',
    *('aws_' + kind + '.runtime["' + name + '"]' for kind in ('iam_role', 'cloudwatch_log_group')
      for name in ('reader', 'visualization')),
    *('aws_iam_role_policy.logs["' + name + '"]' for name in ('reader', 'visualization')),
    *('aws_' + kind + '.' + name for kind in ('iam_role_policy', 'lambda_function', 'lambda_function_url')
      for name in ('reader', 'visualization')),
))
AZURE_ALLOWED = frozenset((
    'random_password.cursor', 'azurerm_resource_group.run', 'azurerm_storage_account.packages',
    *('azurerm_' + kind + '.' + name for kind, name in (
        ('cosmosdb_account', 'history'), ('cosmosdb_sql_database', 'history'),
        ('cosmosdb_sql_container', 'history'), ('cosmosdb_sql_role_assignment', 'reader'),
        ('cosmosdb_sql_role_assignment', 'fixture_writer'),
        ('function_app_flex_consumption', 'reader'), ('function_app_flex_consumption', 'visualization'))),
    *('azurerm_' + kind + '.' + group + '["' + name + '"]'
      for kind, group in (('storage_container', 'packages'), ('service_plan', 'runtime'))
      for name in ('reader', 'visualization')),
    *('module.' + name + '_package.' + resource for name in ('reader', 'visualization')
      for resource in ('terraform_data.package_revision', 'azurerm_storage_blob.package',
                       'azurerm_resource_group_template_deployment.publish')),
))


def review(plan, provider):
    managed = [x for x in plan.get('resource_changes', []) if x['mode'] == 'managed']
    allowed = AWS_ALLOWED if provider == 'aws' else AZURE_ALLOWED
    if ({x['address'] for x in managed} != allowed or len(managed) != len(allowed)
            or any(x['change']['actions'] != ['create'] for x in managed)):
        raise RuntimeError('L5_PLAN_SCOPE_REJECTED')
    if provider == 'azure':
        for item in managed:
            if item['address'].startswith('azurerm_function_app_flex_consumption.'):
                after = item['change'].get('after', {})
                unknown = item['change'].get('after_unknown', {})
                if (after.get('always_ready') or after.get('maximum_instance_count') != 1
                        or unknown.get('always_ready')):
                    raise RuntimeError('L5_CAPACITY_SCOPE_REJECTED')
    return len(managed)


def state_empty(module):
    return (not any(item.get('mode') == 'managed' for item in module.get('resources', []))
            and all(state_empty(child) for child in module.get('child_modules', [])))


def fixture(now=None):
    now = now or datetime.now(timezone.utc)
    hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=2)
    return [{'time': (hour + timedelta(hours=i)).isoformat().replace('+00:00', 'Z'), 'value': value}
            for i, value in enumerate((40, 42, 44))]


def verify_html(body, points):
    """Check real plotted values AND timestamps, not just status or headings."""
    if body.count('<svg ') != 2 or body.count('data-point-count="3"') != 2:
        raise RuntimeError('L5_GRAPH_COUNT_MISMATCH')
    actual = re.findall(r'<circle [^>]*data-time="([^"]+)" data-value="([^"]+)"', body)
    expected = [(p['time'], str(p['value'])) for p in points] * 2
    if actual != expected:
        raise RuntimeError('L5_GRAPH_DATA_MISMATCH')


def environment(credentials, provider):
    env = os.environ.copy()
    if provider == 'aws':
        aws = credentials['aws']
        env.update(AWS_ACCESS_KEY_ID=aws['aws_access_key_id'], AWS_SECRET_ACCESS_KEY=aws['aws_secret_access_key'])
        if aws.get('aws_session_token'):
            env['AWS_SESSION_TOKEN'] = aws['aws_session_token']
    else:
        az = credentials['azure']
        for source, target in (('azure_client_id', 'ARM_CLIENT_ID'), ('azure_client_secret', 'ARM_CLIENT_SECRET'),
                               ('azure_tenant_id', 'ARM_TENANT_ID'), ('azure_subscription_id', 'ARM_SUBSCRIPTION_ID')):
            env[target] = az[source]
    return env


def prepare(args):
    credentials = json.loads(args.credentials.read_text())
    root = args.output_dir.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    tfdir = root / 'terraform'
    shutil.copytree(ROOT / 'scripts/fixtures/l5' / args.provider, tfdir)
    if args.provider == 'azure':
        shutil.copytree(ROOT / '3-cloud-deployer/src/terraform/modules/azure_flex_package', tfdir / 'package_module')
    shutil.copyfile(ROOT / '3-cloud-deployer/src/terraform/.terraform.lock.hcl', tfdir / '.terraform.lock.hcl')
    runtime = root / 'runtime'
    runtime.mkdir()
    if args.provider == 'aws':
        package = build_aws_six_layer_domain_app(runtime)['aws_six-layer-domain']
    else:
        package = build_azure_six_layer_graph_apps(runtime, ('six-layer-domain',))['azure_six-layer-domain']
    prefix = 'l5-' + args.provider + '-' + uuid.uuid4().hex[:8]
    region_key = 'aws_region' if args.provider == 'aws' else 'azure_region'
    values = {'prefix': prefix, 'region': credentials[args.provider].get(region_key, 'eu-central-1' if args.provider == 'aws' else 'westeurope'),
              'package_path': str(package)}
    save(tfdir / 'terraform.tfvars.json', values)
    tf = Terraform(tfdir, environment(credentials, args.provider))
    with deadline(600):
        tf.run('init', '-input=false', '-no-color')
        tf.run('validate', '-no-color')
        tf.run('plan', '-input=false', '-no-color', '-out=reviewed.tfplan')
        plan = json.loads(tf.run('show', '-json', 'reviewed.tfplan').read_text())
    count = review(plan, args.provider)
    source = os.getenv('L5_SOURCE_REVISION', '')
    if not source and shutil.which('git'):
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}', source):
        raise ValueError('L5_SOURCE_REVISION_REQUIRED')
    manifest = {'provider': args.provider, 'prefix': prefix, 'source_revision': source, 'planned_creates': count,
                'plan_sha256': hashlib.sha256((tfdir / 'reviewed.tfplan').read_bytes()).hexdigest(),
                'package_sha256': hashlib.sha256(package.read_bytes()).hexdigest(), 'values': values}
    save(root / 'manifest.json', manifest)
    print(json.dumps({'provider': args.provider, 'planned_creates': count, 'apply_executed': False}))


class Experiment:
    def __init__(self, args):
        self.args, self.root = args, args.output_dir.resolve()
        self.manifest = json.loads((self.root / 'manifest.json').read_text())
        self.provider, self.prefix = self.manifest['provider'], self.manifest['prefix']
        if self.provider != args.provider or not re.fullmatch('l5-' + self.provider + '-[0-9a-f]{8}', self.prefix):
            raise RuntimeError('L5_IDENTITY_INVALID')
        self.credentials = json.loads(args.credentials.read_text())
        self.tf = Terraform(self.root / 'terraform', environment(self.credentials, self.provider))
        self.tf.sequence = max((int(p.stem.split('-')[-1]) for p in self.tf.folder.glob('command-*.log')), default=0)
        self.report = {'provider': self.provider, 'scope': 'isolated-l3-to-l5-stored-fixture',
                       'source_revision': self.manifest['source_revision'], 'started_at': utc_now(),
                       'runner_source_revision': os.getenv('L5_SOURCE_REVISION', self.manifest['source_revision']),
                       'plan_sha256': self.manifest['plan_sha256'], 'package_sha256': self.manifest['package_sha256']}
        self.report['http_observations'] = []
        if self.provider == 'azure':
            self.report['always_ready_instances'] = 0
        if self.provider == 'aws':
            import boto3
            from botocore.config import Config
            value = self.credentials['aws']
            self.session = boto3.Session(aws_access_key_id=value['aws_access_key_id'],
                                        aws_secret_access_key=value['aws_secret_access_key'],
                                        aws_session_token=value.get('aws_session_token'),
                                        region_name=self.manifest['values']['region'])
            self.sdk = {name: self.session.client(name, config=Config(connect_timeout=10, read_timeout=20,
                                                                      retries={'max_attempts': 3}))
                        for name in ('dynamodb', 'lambda', 'iam', 'logs')}
        else:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.resource.resources import ResourceManagementClient
            value = self.credentials['azure']
            self.credential = ClientSecretCredential(value['azure_tenant_id'], value['azure_client_id'], value['azure_client_secret'])
            self.resource = ResourceManagementClient(self.credential, value['azure_subscription_id'],
                                                     retry_total=1, connection_timeout=10, read_timeout=20)
            self.subscription = value['azure_subscription_id']

    def phase(self, name, action):
        print(name, flush=True)
        started = time.monotonic()
        try:
            return action()
        finally:
            self.report[name + '_seconds'] = round(time.monotonic() - started, 3)

    def auth_headers(self, url, app=None):
        if self.provider == 'aws':
            from botocore.auth import SigV4Auth
            from botocore.awsrequest import AWSRequest
            request = AWSRequest(method='GET', url=url)
            SigV4Auth(self.session.get_credentials().get_frozen_credentials(), 'lambda', self.manifest['values']['region']).add_auth(request)
            return dict(request.headers)
        import requests
        token = self.credential.get_token('https://management.azure.com/.default').token
        resource = f'/subscriptions/{self.subscription}/resourceGroups/{self.prefix}/providers/Microsoft.Web/sites/{self.prefix}-{app}'
        response = requests.post('https://management.azure.com' + resource + '/host/default/listkeys?api-version=2025-05-01',
                                 headers={'Authorization': 'Bearer ' + token}, timeout=30)
        response.raise_for_status()
        return {'x-functions-key': response.json()['functionKeys']['default']}

    def fetch(self, url, authenticated=True, app=None):
        import requests
        # Observe L5 before direct reader diagnostics; do not pre-warm L3 as a repair.
        headers = self.auth_headers(url, app) if authenticated else {}
        observation = {'surface': app, 'authenticated': authenticated}
        started = time.monotonic()
        try:
            response = requests.get(url, headers=headers,
                                    timeout=180 if self.provider == 'azure' and authenticated else 40,
                                    allow_redirects=False)
            observation['http_status'] = response.status_code
            if app == 'visualization' and response.status_code in (502, 503, 504):
                observation['response_origin'] = ('l5-data-unavailable'
                    if len(response.content) < 128 and response.content.strip() == b'L5 data unavailable'
                    else 'unclassified')
            return response
        except Exception as exc:
            observation['error_type'] = type(exc).__name__
            raise
        finally:
            observation['seconds'] = round(time.monotonic() - started, 3)
            self.report['http_observations'].append(observation)
            save(self.root / 'http-observations.json', self.report['http_observations'])

    def diagnose_reader(self):
        """Post-observation comparison, never a substitute for a successful L5 read."""
        observations = []
        self.report['reader_diagnostics'] = observations
        for bucket in ('0', '3600'):
            result = {'bucket_seconds': int(bucket), 'passed': False}
            observations.append(result)
            try:
                query = {'device_id': DEVICE, 'metric': METRIC, 'bucket_seconds': bucket,
                         'from': self.points[0]['time'],
                         'to': (datetime.fromisoformat(self.points[-1]['time'].replace('Z', '+00:00'))
                                + timedelta(hours=1)).isoformat().replace('+00:00', 'Z'), 'limit': '100'}
                response = self.fetch(self.outputs['reader_url'] + '?' + urlencode(query), app='reader')
                result['http_status'] = response.status_code
                response.raise_for_status()
                data = response.json()
                time_key, value_key = ('stored_at', 'value') if bucket == '0' else ('bucket_start', 'avg')
                actual = [(p[time_key], p[value_key]) for p in data['points']]
                result['passed'] = (data['schema_version'] == 'raw-history-query.v1'
                    and data['device_id'] == DEVICE and data['metric'] == METRIC
                    and data['truncated'] is False and data.get('next_cursor') is None
                    and actual == [(p['time'], p['value']) for p in self.points])
            except Exception as exc:
                result['error_type'] = type(exc).__name__
            finally:
                save(self.root / 'reader-diagnostics.json', observations)

    def seed(self):
        self.points = fixture()
        save(self.root / 'stored-fixture.json', self.points)
        if self.provider == 'aws':
            from boto3.dynamodb.types import TypeSerializer
            serializer = TypeSerializer()
            def put(table, value):
                self.sdk['dynamodb'].put_item(TableName=self.prefix + '-' + table,
                    Item={k: serializer.serialize(v) for k, v in value.items()})
            for i, point in enumerate(self.points):
                put('raw', {'device_id': DEVICE, 'event_id': 'fixture-' + str(i), 'metric': METRIC,
                            'stored_at': point['time'], 'stored_at_event_id': point['time'] + '#fixture-' + str(i),
                            'event_time': point['time'], 'value': point['value']})
                put('rollup', {'device_metric': DEVICE + '#' + METRIC, 'bucket_start': point['time'],
                               'sum': point['value'], 'count': 1, 'min': point['value'], 'max': point['value']})
        else:
            from azure.cosmos import CosmosClient
            container = CosmosClient(self.outputs['cosmos_endpoint'], self.credential).get_database_client('history').get_container_client('telemetry-history')
            for i, point in enumerate(self.points):
                common = {'device_id': DEVICE, 'metric': METRIC}
                container.upsert_item(common | {'id': 'raw-' + str(i), 'kind': 'raw', 'stored_at': point['time'],
                                                'event_time': point['time'], 'value': point['value']})
                container.upsert_item(common | {'id': 'rollup-' + str(i), 'kind': 'hourly_rollup',
                                                'bucket_start': point['time'], 'sum': point['value'], 'count': 1,
                                                'min': point['value'], 'max': point['value']})

    def functional(self):
        with deadline(600 if self.provider == 'aws' else 1800):
            if not self.inventory():
                raise RuntimeError('L5_PREFIX_NOT_EMPTY')
            plan = self.tf.folder / 'reviewed.tfplan'
            package = Path(self.manifest['values']['package_path'])
            for path, key in ((plan, 'plan_sha256'), (package, 'package_sha256')):
                if hashlib.sha256(path.read_bytes()).hexdigest() != self.manifest[key]:
                    raise RuntimeError('L5_ARTIFACT_CHANGED')
            review(json.loads(self.tf.run('show', '-json', 'reviewed.tfplan').read_text()), self.provider)
            reserve(self.args.ledger, self.provider, self.prefix, self.args.cap_eur, self.args.allowance_eur)
            self.phase('deploy', lambda: self.tf.run('apply', '-input=false', '-no-color', 'reviewed.tfplan'))
            self.outputs = self.tf.outputs()
            self.phase('fixture_seed', self.seed)
            try:
                self.verify_surface()
            except Exception:
                if self.provider == 'azure':
                    self.phase('reader_diagnostic', self.diagnose_reader)
                raise
            else:
                if self.provider == 'azure':
                    self.phase('reader_diagnostic', self.diagnose_reader)

    def verify_surface(self):
        started = time.monotonic()
        # Registration/identity propagation is bounded, not a reason for repeated Apply.
        last_status = None
        # Initial Azure requests may consume most of their 180 s allowance.
        # Leave room for the direct reader comparison inside the shared deadline.
        for attempt in range(3 if self.provider == 'azure' else 31):
            response = self.fetch(self.outputs['visualization_url'], app='visualization')
            last_status = response.status_code
            if response.status_code == 200:
                verify_html(response.text, self.points)
                break
            if response.status_code not in (404, 503):
                raise RuntimeError('L5_AUTHENTICATED_READ_FAILED')
            time.sleep(10)
        else:
            self.report['last_http_status'] = last_status
            raise RuntimeError('L5_READINESS_DEADLINE')
        self.report['verify_seconds'] = round(time.monotonic() - started, 3)
        self.report['readback_poll_attempts'] = attempt + 1
        body = response.content
        atomic_write_private_bytes(self.root / 'cloud-response.html', body)
        self.report['cloud_html_sha256'] = hashlib.sha256(body).hexdigest()
        negative = {name: self.fetch(self.outputs[name + '_url'], authenticated=False, app=name).status_code for name in ('reader', 'visualization')}
        if any(status not in (401, 403) for status in negative.values()):
            raise RuntimeError('L5_UNAUTHENTICATED_ACCESS_NOT_REJECTED')
        self.report.update(functional_pass=True, authentication_negative_statuses=negative,
                           panel_count=2, raw_point_count=3, hourly_point_count=3,
                           exact_values_and_timestamps_pass=True, cloud_generated_html=True)

    def cleanup(self):
        state = self.tf.folder / 'terraform.tfstate'
        if not state.exists():
            return True
        with deadline(1800):
            self.phase('destroy', lambda: self.tf.run('destroy', '-input=false', '-auto-approve', '-no-color'))
            result = json.loads(self.tf.run('show', '-json').read_text())
        return state_empty(result.get('values', {}).get('root_module', {}))

    def inventory(self):
        counts = {}
        if self.provider == 'azure':
            counts['resource_groups'] = int(self.resource.resource_groups.check_existence(self.prefix))
        else:
            counts['tables'] = sum(name.startswith(self.prefix + '-') for page in self.sdk['dynamodb'].get_paginator('list_tables').paginate()
                                   for name in page['TableNames'])
            counts['functions'] = sum(item['FunctionName'].startswith(self.prefix + '-') for page in self.sdk['lambda'].get_paginator('list_functions').paginate()
                                      for item in page['Functions'])
            counts['roles'] = sum(item['RoleName'].startswith(self.prefix + '-') for page in self.sdk['iam'].get_paginator('list_roles').paginate()
                                  for item in page['Roles'])
            counts['log_groups'] = sum(1 for page in self.sdk['logs'].get_paginator('describe_log_groups').paginate(logGroupNamePrefix='/aws/lambda/' + self.prefix + '-')
                                       for item in page['logGroups'])
        save(self.root / ('baseline-inventory.json' if not (self.tf.folder / 'terraform.tfstate').exists() else 'residual-inventory.json'), counts)
        self.report['inventory_counts'] = counts
        return not any(counts.values())

    def run(self):
        started = time.monotonic()
        lifecycle(self.functional, self.cleanup, self.inventory, self.report)
        self.report['completed_at'] = utc_now()
        self.report['total_seconds'] = round(time.monotonic() - started, 3)
        self.report['resource_timings'] = [item for log in sorted(self.tf.folder.glob('command-*.log'))
                                           for item in terraform_resource_timings(log)]
        save(self.root / 'result.json', self.report)
        print(json.dumps({key: self.report.get(key) for key in ('provider', 'functional_pass', 'cleanup_pass', 'inventory_pass', 'passed',
                                                               'deploy_seconds', 'verify_seconds', 'destroy_seconds', 'total_seconds',
                                                               'functional_error_type', 'functional_error_location')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('provider', choices=('aws', 'azure'))
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--approve-live', action='store_true')
    parser.add_argument('--ledger', type=Path)
    parser.add_argument('--cap-eur', type=float)
    parser.add_argument('--allowance-eur', type=float)
    args = parser.parse_args()
    os.umask(0o077)
    logging.disable(logging.CRITICAL)
    try:
        if not args.approve_live:
            prepare(args)
        else:
            if not args.ledger or not args.cap_eur or not args.allowance_eur:
                raise ValueError('L5_EXECUTION_ALLOWANCE_REQUIRED')
            Experiment(args).run()
    except BaseException as error:
        trace = error.__traceback__
        while trace and trace.tb_next:
            trace = trace.tb_next
        print(json.dumps({'provider': args.provider, 'error_type': type(error).__name__,
                          'error_location': {'file': Path(trace.tb_frame.f_code.co_filename).name,
                                             'line': trace.tb_lineno} if trace else None}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
