"""Fixed Azure Event-to-L4 research cut; plan-only unless explicitly approved.

Uses existing packages, deployed Event delivery and managed Twin-writer identity.
One processed fixture, no Core ingress, image publication, federation or L5.
"""
import argparse
import base64
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import signal
import time
from types import SimpleNamespace
import uuid

from scripts.l4_projection_check import DEVICE, matches, wait_for
from scripts.prepare_core_runtime import ROOT, prepare
from scripts.run_core_evaluation import Terraform, save, reserve, utc_now
from scripts.run_event_l4_evaluation import processed_fixture
from scripts.run_l4_evaluation import Experiment, deadline, lifecycle
from src.providers.azure.layers.layer_4_adt import six_layer_seed

TARGETS = ('module.azure_six_layer_ingress_package[0]', 'module.azure_six_layer_eventing_package[0]',
    'azurerm_digital_twins_instance.azure_azure_digital_twins[0]',
    'azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_projection_writer"]',
    'azurerm_role_assignment.azure_azure_entra_layer_access_bindings["twin_seed_deployer"]',
    'azurerm_role_assignment.azure_event_runtime', 'azurerm_eventhub_consumer_group.domain_standard',
    'azurerm_cosmosdb_sql_role_assignment.azure_azure_cosmos_db_nosql_raw_and_rollup')

ALLOWED = frozenset((
    'azurerm_container_registry.azure_azure_acr_basic_if_container_selected[0]',
    *('azurerm_cosmosdb_' + kind + '.azure_azure_cosmos_db_nosql_raw_and_rollup[0]'
      for kind in ('account', 'sql_container', 'sql_database')),
    *('azurerm_cosmosdb_sql_role_assignment.azure_azure_cosmos_db_nosql_raw_and_rollup["' + role + '"]'
      for role in ('raw_history_reader', 'runtime_writer')),
    'azurerm_digital_twins_instance.azure_azure_digital_twins[0]',
    *('azurerm_eventhub.domain_telemetry_standard["' + name + '"]' for name in ('failure', 'processed', 'received')),
    *('azurerm_eventhub_consumer_group.domain_standard["' + role + '"]' for role in ('historical-persistence', 'twin-state-update')),
    'azurerm_eventhub_namespace.eventing_standard[0]',
    *('azurerm_function_app_flex_consumption.' + name + '[0]' for name in
      ('azure_azure_functions_flex_event_adapter', 'azure_azure_functions_flex_raw_history_reader', 'event_runtime')),
    'azurerm_resource_group.main[0]',
    *('azurerm_role_assignment.azure_azure_entra_layer_access_bindings["' + role + '"]'
      for role in ('twin_projection_writer', 'twin_seed_deployer')),
    'azurerm_role_assignment.azure_event_publishers["control_sender"]',
    *('azurerm_role_assignment.azure_event_runtime["' + role + '"]'
      for role in ('control_receiver', 'event_failure_sender', 'event_hubs_receiver')),
    *('azurerm_service_plan.azure_six_layer_flex["' + name + '"]' for name in ('eventing', 'ingress', 'reader')),
    'azurerm_servicebus_namespace.eventing[0]', 'azurerm_servicebus_subscription.domain_control[0]',
    'azurerm_servicebus_topic.domain_control[0]', 'azurerm_storage_account.main[0]',
    'azurerm_storage_container.azure_event_function_package[0]',
    *('azurerm_storage_container.azure_six_layer_function_package["' + name + '"]' for name in ('ingress', 'reader')),
    'azurerm_user_assigned_identity.event_runtime[0]', 'azurerm_user_assigned_identity.main[0]',
    'random_id.deployment_suffix', 'random_password.azure_six_layer_raw_history_cursor_hmac[0]',
    'terraform_data.azure_eventing_capacity_guard[0]', 'terraform_data.validated_extension_package["processor.telemetry@1"]',
    *('module.azure_six_layer_' + package + '_package[0].' + resource
      for package in ('eventing', 'ingress') for resource in ('azurerm_resource_group_template_deployment.publish',
      'azurerm_storage_blob.package', 'terraform_data.package_revision'))))


def review(plan):
    changes = [r for r in plan.get('resource_changes', []) if r['mode'] == 'managed']
    if len(changes) != len(ALLOWED) or {r['address'] for r in changes} != ALLOWED or any(
        r['change']['actions'] != ['create'] for r in changes
    ):
        raise RuntimeError('AZURE_EVENT_L4_PLAN_SCOPE_REJECTED')


def expected_projection(event):
    identity = event['event_id'] + ':twin.state.upserted:component.historical-persistence'
    return dict(event, event_id=str(uuid.uuid5(uuid.NAMESPACE_URL, identity)))


class AzureEventExperiment(Experiment):
    def allowed_resources(self):
        return ALLOWED

    def state(self):
        state = self.folder / 'fresh.tfstate'
        if not state.exists():
            return {}
        data = json.loads(self.terraform('show', '-json', str(state)).read_text())
        def collect(module):
            resources = {r['address']: r['values'] for r in module.get('resources', []) if r['mode'] == 'managed'}
            for child in module.get('child_modules', []):
                resources.update(collect(child))
            return resources
        resources = collect(data.get('values', {}).get('root_module', {}))
        if not set(resources) <= ALLOWED:
            raise RuntimeError('AZURE_EVENT_L4_STATE_SCOPE_REJECTED')
        return resources

    def functional(self):
        from azure.digitaltwins.core import DigitalTwinsClient
        from azure.eventhub import EventHubProducerClient, EventData, TransportType
        with deadline(1500):
            if not self.inventory():
                raise RuntimeError('AZURE_EVENT_L4_PREFIX_NOT_EMPTY')
            self.apply_started = True
            started = time.monotonic()
            try:
                self.terraform('apply', '-input=false', '-no-color', '-parallelism=2',
                    '-state=' + str(self.folder / 'fresh.tfstate'), str(self.folder / 'review.plan'))
            finally:
                self.report['apply_seconds'] = time.monotonic() - started
            resources = self.state()
            instance = resources['azurerm_digital_twins_instance.azure_azure_digital_twins[0]']
            self.data = DigitalTwinsClient('https://' + instance['host_name'].removeprefix('https://'),
                self.credential, retry_total=1, connection_timeout=10, read_timeout=20)
            def authorized():
                try:
                    self.data.get_model('dtmi:twin2multicloud:poc:TwinNode;1')
                    return True
                except Exception as exc:
                    if getattr(exc, 'status_code', None) == 404:
                        return True
                    if getattr(exc, 'status_code', None) == 403:
                        return False
                    raise
            self.report['role_readiness_attempts'] = wait_for(authorized, attempts=60, interval=3)
            seed = six_layer_seed(SimpleNamespace(digital_twin_name=self.name, iot_devices=[{'id': DEVICE}]))
            started = time.monotonic()
            self.data.create_models(seed['models'])
            for twin in seed['twins']:
                self.data.upsert_digital_twin(twin['$dtId'], {k: v for k, v in twin.items() if k != '$dtId'})
            for rel in seed['relationships']:
                self.data.upsert_relationship(rel['$dtId'], rel['$relationshipId'], {k: v for k, v in rel.items() if k != '$dtId'})
            self.report['seed_seconds'] = time.monotonic() - started
            namespace = resources['azurerm_eventhub_namespace.eventing_standard[0]']
            self.scope, self.role_id = namespace['id'], str(uuid.uuid4())
            save(self.folder / 'sdk-owned.json', {'scope': self.scope, 'role_id': self.role_id})
            roles = list(self.auth.role_definitions.list(self.scope, filter="roleName eq 'Azure Event Hubs Data Sender'"))
            if len(roles) != 1:
                raise RuntimeError('AZURE_EVENT_L4_SENDER_ROLE_AMBIGUOUS')
            token = self.credential.get_token('https://management.azure.com/.default').token
            principal = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '==='))['oid']
            self.auth.role_assignments.create(self.scope, self.role_id, {'role_definition_id': roles[0].id,
                'principal_id': principal, 'principal_type': 'ServicePrincipal'})
            event = processed_fixture(self.name)
            self.report.update(scope='azure_event_to_l4_deployed_identity', fixture=event,
                fixture_sha256=hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest())
            hub = resources['azurerm_eventhub.domain_telemetry_standard["processed"]']['name']
            started = time.monotonic()
            with EventHubProducerClient(fully_qualified_namespace=namespace['name'] + '.servicebus.windows.net',
                eventhub_name=hub, credential=self.credential, retry_total=1,
                transport_type=TransportType.AmqpOverWebsocket) as producer:
                # Reading partition metadata waits for data-role propagation without sending duplicates.
                def sender_ready():
                    try:
                        producer.get_partition_ids()
                        return True
                    except Exception as exc:
                        if type(exc).__name__ in ('AuthenticationError', 'ConnectError'):
                            return False
                        raise
                self.report['sender_readiness_attempts'] = wait_for(sender_ready, attempts=30, interval=3)
                batch = producer.create_batch(partition_key=DEVICE)
                batch.add(EventData(json.dumps(event)))
                producer.send_batch(batch)
            self.report['publish_seconds'] = time.monotonic() - started
            started = time.monotonic()
            self.report['projection_readback_attempts'] = wait_for(lambda: matches(
                self.data.get_digital_twin(DEVICE), expected_projection(event), 'azure'), attempts=120, interval=3)
            self.report['projection_seconds'] = time.monotonic() - started
            self.report['functional_pass'] = True


def run(args):
    # Fail before plan/reservation/mutation if the evaluation SDK is unavailable.
    importlib.import_module('azure.eventhub')
    os.umask(0o077)
    root = args.output_dir.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    values = prepare('azure', root / 'runtime')
    values.update(digital_twin_name='l4-azure-' + uuid.uuid4().hex[:8], evaluation_scope='full',
        layer_1_provider='aws', layer_2_provider='aws', layer_4_provider='azure', layer_5_provider='azure')
    credentials = json.loads(args.credentials.read_text())
    for provider, keys in (('aws', ('aws_access_key_id', 'aws_secret_access_key', 'aws_region')),
        ('azure', ('azure_subscription_id', 'azure_tenant_id', 'azure_client_id', 'azure_client_secret'))):
        values.update({k: credentials[provider][k] for k in keys})
    save(root / 'private.tfvars.json', values)
    tfdir = root / 'terraform'
    shutil.copytree(ROOT / '3-cloud-deployer/src/terraform', tfdir,
        ignore=shutil.ignore_patterns('.terraform', '*.tfstate*', '*.tfplan'))
    shutil.copytree(args.provider_cache, tfdir / '.terraform')
    tf = Terraform(tfdir, dict(os.environ, TF_IN_AUTOMATION='1', TF_INPUT='0'))
    tf.run('init', '-no-color')
    tf.run('plan', '-input=false', '-no-color', '-state=' + str(root / 'fresh.tfstate'),
        '-var-file=' + str(root / 'private.tfvars.json'), '-out=' + str(root / 'review.plan'),
        *('-target=' + r for r in TARGETS))
    plan = json.loads(tf.run('show', '-json', str(root / 'review.plan')).read_text())
    review(plan)
    save(root / 'plan.json', plan)
    print(json.dumps({'create_entries': len(ALLOWED), 'plan_reviewed': True, 'live_requested': args.approve_live}), flush=True)
    if not args.approve_live:
        return {'plan_only': True}
    experiment = AzureEventExperiment('azure', credentials, tfdir, root)
    reserve(args.ledger, 'azure-event-l4', values['digital_twin_name'], args.cap_eur, args.reserve_eur)
    def interrupted(*_):
        raise SystemExit('AZURE_EVENT_L4_INTERRUPTED')
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        with (root / 'sdk.log').open('w') as log, redirect_stdout(log), redirect_stderr(log):
            lifecycle(experiment.functional, experiment.cleanup, experiment.inventory, experiment.report)
    finally:
        signal.signal(signal.SIGTERM, previous)
        experiment.report['finished_at'] = utc_now()
        save(root / 'result.json', experiment.report)
    return {k: experiment.report.get(k) for k in ('functional_pass', 'cleanup_pass', 'inventory_pass', 'passed')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--provider-cache', type=Path, required=True)
    parser.add_argument('--ledger', type=Path, required=True)
    parser.add_argument('--cap-eur', type=float, required=True)
    parser.add_argument('--reserve-eur', type=float, required=True)
    parser.add_argument('--approve-live', action='store_true')
    try:
        result = run(parser.parse_args())
        print(json.dumps(result))
        raise SystemExit(0 if result.get('passed') or result.get('plan_only') else 1)
    except Exception as exc:
        print(json.dumps({'error_type': type(exc).__name__, 'passed': False}))
        raise SystemExit(1)
