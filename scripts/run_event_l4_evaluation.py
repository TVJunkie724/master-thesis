"""Fixed AWS Event-to-L4 research cut, reusing isolated L4 cleanup and models.

Default is plan-only. No full-profile admission, source-cloud deployment or L5.
"""
import argparse
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import time
from types import SimpleNamespace
import uuid

from scripts import core_live_aws as core
from scripts.l4_projection_check import DEVICE, BoundedClient, native_snapshot, matches, wait_for
from scripts.prepare_core_runtime import ROOT, prepare
from scripts.prepare_l4_evaluation import AWS_ROOTS
from scripts.run_core_evaluation import Terraform, save, reserve, utc_now, retry_create_count
from scripts.run_l4_evaluation import Experiment, deadline, lifecycle, workspace_role_propagation_failure
from src.providers.terraform.aws_deployer import create_twinmaker_entities

TARGETS = (*AWS_ROOTS, 'aws_lambda_event_source_mapping.event_runtime["twin-state-update"]',
           'aws_iam_role_policy.aws_six_layer_lambda_data[0]', 'aws_iam_role_policy_attachment.aws_six_layer_lambda_logs[0]')
ALLOWED = frozenset((*AWS_ROOTS, 'random_id.deployment_suffix',
    *('aws_cloudwatch_log_group.aws_six_layer_lambda["' + key + '"]'
      for key in ('DOMAIN-consumer', 'L1-event-adapter', 'L5-raw-history-reader')),
    'aws_cloudwatch_log_group.eventing[0]',
    'aws_dynamodb_table.aws_aws_dynamodb_on_demand_hourly_rollup[0]',
    'aws_dynamodb_table.aws_aws_dynamodb_on_demand_raw[0]',
    'aws_iam_role.aws_six_layer_lambda[0]', 'aws_iam_role.event_runtime[0]',
    'aws_iam_role_policy.aws_six_layer_lambda_data[0]', 'aws_iam_role_policy.event_runtime[0]',
    'aws_iam_role_policy_attachment.aws_six_layer_lambda_logs[0]',
    'aws_iam_role_policy_attachment.event_runtime_logs[0]',
    'aws_kinesis_stream.domain_telemetry["processed"]', 'aws_kinesis_stream.domain_telemetry["received"]',
    'aws_kinesis_stream_consumer.domain_consumers["historical-persistence"]',
    'aws_kinesis_stream_consumer.domain_consumers["twin-state-update"]',
    'aws_lambda_event_source_mapping.event_runtime["twin-state-update"]',
    'aws_lambda_function.aws_six_layer_domain_consumer[0]',
    *('aws_lambda_function.event_runtime["' + role + '"]'
      for role in ('control-router', 'historical-persistence', 'twin-state-update')),
    'aws_s3_bucket.event_telemetry_dlq[0]', 'aws_sns_topic.domain_control[0]',
    'aws_sqs_queue.domain_control[0]', 'aws_sqs_queue.event_control_dlq[0]',
    'terraform_data.aws_eventing_capacity_guard[0]',
    'terraform_data.validated_extension_package["processor.telemetry@1"]'))


def review(plan):
    changes = [r for r in plan.get('resource_changes', []) if r['mode'] == 'managed']
    if len(changes) != len(ALLOWED) or {r['address'] for r in changes} != ALLOWED or any(
        r['change']['actions'] != ['create'] for r in changes
    ):
        raise RuntimeError('EVENT_L4_PLAN_SCOPE_REJECTED')


def processed_fixture(name):
    now = utc_now()
    return {'schema_version': 'canonical-domain-event.v1', 'event_id': name + '-processed',
        'event_type': 'telemetry.processed.v1', 'deployment_id': name, 'source_id': DEVICE,
        'source_sequence': 'TRACE-' + uuid.uuid4().hex.upper(), 'occurred_at': now,
        'correlation_id': name, 'causation_id': name + '-received', 'producer': 'component.telemetry-processor',
        'payload': {'device_id': DEVICE, 'twin_id': DEVICE, 'metric': 'temperature', 'value': 20.5,
                    'quality': 'accepted', 'projection_candidate': True, 'event_time': now}}


class EventExperiment(Experiment):
    def allowed_resources(self):
        return ALLOWED

    def inventory(self):
        super().inventory()
        self.report['residual_counts'].update(core.inventory(self.variables, self.name))
        return not any(self.report['residual_counts'].values())

    def cleanup(self):
        if self.apply_started and (self.folder / 'fresh.tfstate').exists():
            try:
                core.before_destroy(self.variables, json.loads((self.folder / 'fresh.tfstate').read_text()))
            except Exception as exc:
                self.report['prepare_destroy_error'] = type(exc).__name__
        result = super().cleanup()
        return result and not self.report.get('prepare_destroy_error')

    def functional(self):
        with deadline(900):
            if not self.inventory():
                raise RuntimeError('EVENT_L4_PREFIX_NOT_EMPTY')
            if self.tm.get_pricing_plan().get('currentPricingPlan', {}).get('pricingMode') != 'STANDARD':
                raise RuntimeError('EVENT_L4_PRICING_MODE_REJECTED')
            self.apply_started = True
            started = time.monotonic()
            try:
                selected = self.folder / 'review.plan'
                for attempt in range(3):
                    try:
                        self.terraform('apply', '-input=false', '-no-color', '-parallelism=2',
                            '-state=' + str(self.folder / 'fresh.tfstate'), str(selected))
                        break
                    except RuntimeError:
                        if attempt == 2 or not workspace_role_propagation_failure(self.last_log):
                            raise
                        self.report['workspace_role_retries'] = attempt + 1
                        time.sleep(20 * (attempt + 1))
                        selected = self.folder / f'workspace-retry-{attempt + 1}.plan'
                        self.terraform('plan', '-input=false', '-no-color',
                            '-state=' + str(self.folder / 'fresh.tfstate'),
                            '-var-file=' + str(self.folder / 'private.tfvars.json'), '-out=' + str(selected),
                            *('-target=' + r for r in TARGETS))
                        retry_create_count(json.loads(self.terraform('show', '-json', str(selected)).read_text()), ALLOWED)
            finally:
                self.report['apply_seconds'] = time.monotonic() - started
            resources = self.state()
            workspace = resources['awscc_iottwinmaker_workspace.aws_aws_iot_twinmaker_standard[0]']['workspace_id']
            client = BoundedClient(self.tm)
            context = SimpleNamespace(providers={'aws': SimpleNamespace(clients={'twinmaker': client})},
                config=SimpleNamespace(digital_twin_name=self.name, hierarchy=[], iot_devices=[{'id': DEVICE}]),
                resolved_deployment_graph=SimpleNamespace(profile_ref={'id': 'six-layer-eventing', 'version': '1'}))
            started = time.monotonic()
            create_twinmaker_entities(context, self.folder, {'aws_component_twin_state_output': {'workspace_id': workspace}})
            self.report['seed_seconds'] = time.monotonic() - started
            aws = core.session(self.variables)
            mapping = resources['aws_lambda_event_source_mapping.event_runtime["twin-state-update"]']['uuid']
            wait_for(lambda: aws.client('lambda').get_event_source_mapping(UUID=mapping)['State'] == 'Enabled')
            event = processed_fixture(self.name)
            expected = dict(event, event_id=str(uuid.uuid5(uuid.NAMESPACE_URL, event['event_id'] + ':twin.state.upserted')))
            self.report.update(scope='aws_event_to_l4_deployed_identity', fixture=event,
                fixture_sha256=hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest())
            stream = resources['aws_kinesis_stream.domain_telemetry["processed"]']['name']
            started = time.monotonic()
            aws.client('kinesis').put_record(StreamName=stream, PartitionKey=DEVICE, Data=json.dumps(event).encode())
            self.report['projection_readback_attempts'] = wait_for(lambda: matches(native_snapshot(
                client.get_entity(workspaceId=workspace, entityId=DEVICE)), expected, 'aws'))
            self.report['projection_seconds'] = time.monotonic() - started
            self.report.update(functional_pass=True, sdk_read_seed_calls=client.calls)


def run(args):
    os.umask(0o077)
    root = args.output_dir.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    values = prepare('aws', root / 'runtime')
    values.update(digital_twin_name='l4-aws-' + uuid.uuid4().hex[:8], evaluation_scope='full',
                  layer_1_provider='azure', layer_2_provider='azure', layer_4_provider='aws', layer_5_provider='aws')
    credentials = json.loads(args.credentials.read_text())
    values.update({k: credentials['aws'][k] for k in ('aws_access_key_id', 'aws_secret_access_key', 'aws_region')})
    values.update({k: credentials['azure'][k] for k in ('azure_subscription_id', 'azure_tenant_id', 'azure_client_id', 'azure_client_secret')})
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
    print(json.dumps({'create_entries': len(ALLOWED), 'plan_reviewed': True, 'live_requested': args.approve_live}), flush=True)
    if not args.approve_live:
        return {'plan_only': True}
    experiment = EventExperiment('aws', credentials, tfdir, root)
    reserve(args.ledger, 'aws-event-l4', values['digital_twin_name'], args.cap_eur, args.reserve_eur)
    def interrupted(*_):
        raise SystemExit('EVENT_L4_INTERRUPTED')
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
