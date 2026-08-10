"""Fail-closed contracts for SDK-owned post-deployment resources."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.providers.terraform import aws_deployer, azure_deployer
from src.providers.aws.layers import layer_5_grafana as aws_layer_5_grafana
from src.providers.azure.layers import layer_5_grafana
from src.providers.azure.layers import layer_4_adt
from src.providers.terraform.runtime_outcome import ProviderRuntimeError, RuntimeRun


class ConflictError(Exception):
    pass


class ResourceNotFoundError(Exception):
    pass


TERRAFORM_ROOT = Path(__file__).resolve().parents[3] / "src" / "terraform"


def _aws_context(*, hierarchy=None, devices=None, five_layer_v2=False):
    twinmaker = SimpleNamespace(
        exceptions=SimpleNamespace(ConflictException=ConflictError),
    )
    lambda_client = SimpleNamespace(
        exceptions=SimpleNamespace(ResourceNotFoundException=ResourceNotFoundError),
    )
    provider = SimpleNamespace(
        clients={"twinmaker": twinmaker, "lambda": lambda_client},
        region="eu-central-1",
    )
    config = SimpleNamespace(
        digital_twin_name="factory",
        hierarchy=hierarchy if hierarchy is not None else [],
        iot_devices=devices if devices is not None else [],
    )
    graph = SimpleNamespace(
        profile_ref={
            "id": "five-layer-baseline" if five_layer_v2 else "legacy",
            "version": "2" if five_layer_v2 else "1",
        }
    )
    return SimpleNamespace(
        providers={"aws": provider},
        config=config,
        resolved_deployment_graph=graph,
    ), provider


def test_runtime_run_redacts_and_aggregates_without_stopping_siblings():
    run = RuntimeRun("AWS", "IoT", aws_deployer.logger)
    calls = []

    run.attempt(
        "device-one",
        lambda: (_ for _ in ()).throw(RuntimeError("private_key=must-not-leak")),
    )
    run.attempt("device-two", lambda: calls.append("continued"))

    with pytest.raises(ProviderRuntimeError) as exc_info:
        run.raise_if_failed()

    assert calls == ["continued"]
    assert "must-not-leak" not in str(exc_info.value)
    assert exc_info.value.failures[0].resource == "device-one"


def test_aws_v2_identity_center_user_requires_explicit_invite_intent():
    terraform = (TERRAFORM_ROOT / "aws_five_layer_v2.tf").read_text("utf-8")

    assert 'var.aws_layer_access_principal_intent == "invite_builtin"' in terraform
    assert "INTERACTIVE_PRINCIPAL_NOT_FOUND" in terraform
    assert "terraform_data.aws_v2_layer_access_principal_admission" in terraform


def test_gcp_grafana_readiness_waits_for_content_probe_marker():
    terraform = (TERRAFORM_ROOT / "gcp_five_layer_v2.tf").read_text("utf-8")

    assert 'command = ["test", "-f", "/tmp/twin2multicloud-ready"]' in terraform
    assert terraform.count('path   = "/api/health"') == 1


def test_gcp_twin_explorer_readiness_waits_for_seed_readback():
    terraform = (TERRAFORM_ROOT / "gcp_five_layer_v2.tf").read_text("utf-8")
    explorer = terraform.split(
        'resource "google_cloud_run_v2_service" "gcp_gcp_cloud_run_iap_twin_explorer"',
        1,
    )[1].split('resource "random_password"', 1)[0]

    assert 'path = "/healthz"' in explorer
    assert 'name  = "IOT_DEVICES_JSON"' in explorer
    assert (
        "google_cloud_run_v2_service.gcp_gcp_cloud_run_twin_api_materializer"
        in explorer
    )


def test_twinmaker_requires_workspace_output(tmp_path):
    context, _provider = _aws_context(
        hierarchy=[{"type": "entity", "id": "machine"}],
    )

    with pytest.raises(RuntimeError, match="workspace_id"):
        aws_deployer.create_twinmaker_entities(context, tmp_path, {})


def test_twinmaker_continues_siblings_then_fails_the_operation(tmp_path):
    context, provider = _aws_context(
        hierarchy=[
            {"type": "entity", "id": "broken"},
            {"type": "entity", "id": "healthy"},
        ],
    )
    calls = []

    def create_entity(**kwargs):
        calls.append(kwargs["entityId"])
        if kwargs["entityId"] == "broken":
            raise RuntimeError("aws_secret_access_key=must-not-leak")

    provider.clients["twinmaker"].create_entity = create_entity

    with pytest.raises(ProviderRuntimeError) as exc_info:
        aws_deployer.create_twinmaker_entities(
            context,
            tmp_path,
            {
                "aws_twinmaker_workspace_id": "workspace",
                "aws_l4_connector_function_arn": "connector",
                "aws_l4_connector_last_entry_function_arn": "last-entry",
            },
        )

    assert calls == ["broken", "healthy"]
    assert "must-not-leak" not in str(exc_info.value)


def test_aws_v2_creates_and_reads_back_deterministic_visible_seed(tmp_path):
    context, provider = _aws_context(
        hierarchy=[],
        devices=[{"id": "sensor-1"}],
        five_layer_v2=True,
    )
    entities = {}
    component_types = {}

    def create_entity(**kwargs):
        entities.setdefault(
            kwargs["entityId"],
            {
                "entityId": kwargs["entityId"],
                "parentEntityId": kwargs.get("parentEntityId"),
                "components": {},
            },
        )

    def create_component_type(**kwargs):
        component_types[kwargs["componentTypeId"]] = {
            "status": {"state": "ACTIVE"}
        }

    def update_entity(**kwargs):
        entities[kwargs["entityId"]]["components"].update(kwargs["componentUpdates"])

    provider.clients["twinmaker"].create_entity = create_entity
    provider.clients["twinmaker"].create_component_type = create_component_type
    provider.clients["twinmaker"].get_component_type = lambda **kwargs: component_types[
        kwargs["componentTypeId"]
    ]
    provider.clients["twinmaker"].update_entity = update_entity
    provider.clients["twinmaker"].get_entity = lambda **kwargs: entities[
        kwargs["entityId"]
    ]

    aws_deployer.create_twinmaker_entities(
        context,
        tmp_path,
        {
            "aws_twinmaker_workspace_id": "workspace",
            "aws_l4_connector_function_arn": "connector",
            "aws_l4_connector_last_entry_function_arn": "last-entry",
        },
    )

    assert entities[aws_deployer.V2_SEED_DEVICE_ID]["parentEntityId"] == (
        aws_deployer.V2_SEED_ROOT_ID
    )
    component = entities[aws_deployer.V2_SEED_DEVICE_ID]["components"][
        aws_deployer.V2_SEED_COMPONENT_NAME
    ]
    assert component["componentTypeId"] == (
        f"factory-{aws_deployer.V2_SEED_COMPONENT_NAME}"
    )


def test_iot_registration_continues_devices_and_fails_aggregate(monkeypatch, tmp_path):
    context, provider = _aws_context(devices=[{"id": "one"}, {"id": "two"}])
    provider.clients.update(
        {
            "iot": SimpleNamespace(
                describe_endpoint=lambda **_kwargs: {"endpointAddress": "iot.example"}
            ),
            "sts": SimpleNamespace(
                get_caller_identity=lambda: {"Account": "123456789012"}
            ),
        }
    )
    calls = []

    def register(_provider, _path, device, *_args):
        calls.append(device["id"])
        if device["id"] == "one":
            raise RuntimeError("private_key=must-not-leak")

    monkeypatch.setattr(aws_deployer, "_register_iot_device", register)

    with pytest.raises(ProviderRuntimeError):
        aws_deployer.register_aws_iot_devices(context, tmp_path)

    assert calls == ["one", "two"]


def test_aws_grafana_requires_every_terraform_output():
    context, _provider = _aws_context()

    with pytest.raises(RuntimeError, match="Missing AWS Grafana outputs"):
        aws_deployer.configure_aws_grafana(context, {})


def test_azure_grafana_requires_hot_reader_output():
    context = SimpleNamespace(providers={"azure": object()})

    with pytest.raises(RuntimeError, match="azure_l3_hot_reader_url"):
        azure_deployer.configure_azure_grafana(context, {})


def test_azure_v2_grafana_uses_typed_component_output_and_inventory(monkeypatch):
    provider = SimpleNamespace()
    graph = SimpleNamespace(profile_ref={"id": "five-layer-baseline", "version": "2"})
    context = SimpleNamespace(
        providers={"azure": provider},
        resolved_deployment_graph=graph,
        config=SimpleNamespace(
            iot_devices=[
                {
                    "id": "sensor-1",
                    "properties": [{"name": "temperature"}],
                }
            ]
        ),
    )
    configure = MagicMock()
    monkeypatch.setattr(layer_5_grafana, "configure_five_layer_v2_grafana", configure)

    azure_deployer.configure_azure_grafana(
        context,
        {
            "azure_component_visualization_output": {
                "workspace_name": "factory-grafana",
                "workspace_url": "https://grafana.example/",
                "access_url": "https://grafana.example/d/t2mc-raw-rollups/raw-rollups",
                "reader_url": "https://reader.example/api/raw-history/v1",
                "reader_function_name": "factory-history",
            }
        },
    )

    configure.assert_called_once_with(
        provider,
        workspace_name="factory-grafana",
        grafana_url="https://grafana.example",
        hot_reader_url="https://reader.example/api/raw-history/v1",
        function_app_name="factory-history",
        device_id="sensor-1",
        metric="temperature",
    )


def test_azure_post_deployment_requires_initialized_provider(tmp_path):
    context = SimpleNamespace(providers={}, config=object())

    with pytest.raises(RuntimeError, match="Azure provider not initialized"):
        azure_deployer.register_azure_iot_devices(context, tmp_path)


def test_new_aws_certificate_is_compensated_when_local_write_fails(
    monkeypatch,
    tmp_path,
):
    iot = MagicMock()
    iot.exceptions = SimpleNamespace(ResourceAlreadyExistsException=ConflictError)
    iot.create_keys_and_certificate.return_value = {
        "certificateArn": "arn:aws:iot:region:account:cert/cert-1",
        "certificatePem": "certificate",
        "keyPair": {"PrivateKey": "private", "PublicKey": "public"},
    }
    provider = SimpleNamespace(clients={"iot": iot}, region="eu-central-1")
    monkeypatch.setattr(
        aws_deployer,
        "atomic_write_private_bytes",
        lambda *_args: (_ for _ in ()).throw(OSError("disk full")),
    )

    with pytest.raises(OSError, match="disk full"):
        aws_deployer._register_iot_device(
            provider,
            tmp_path,
            {"id": "device-1"},
            "factory",
            "123456789012",
            "iot.example",
        )

    iot.update_certificate.assert_called_once_with(
        certificateId="cert-1",
        newStatus="INACTIVE",
    )
    iot.delete_certificate.assert_called_once_with(
        certificateId="cert-1",
        forceDelete=True,
    )


def test_existing_aws_certificate_must_match_attached_cloud_identity(tmp_path):
    cert_dir = tmp_path / "iot_devices_auth" / "device-1"
    cert_dir.mkdir(parents=True)
    (cert_dir / "certificate.pem.crt").write_text("local", encoding="utf-8")
    (cert_dir / "private.pem.key").write_text("private", encoding="utf-8")
    iot = MagicMock()
    iot.exceptions = SimpleNamespace(ResourceAlreadyExistsException=ConflictError)
    iot.list_thing_principals.return_value = {
        "principals": ["arn:aws:iot:region:account:cert/cert-1"]
    }
    iot.describe_certificate.return_value = {
        "certificateDescription": {"certificatePem": "remote"}
    }
    provider = SimpleNamespace(clients={"iot": iot}, region="eu-central-1")

    with pytest.raises(RuntimeError, match="does not match"):
        aws_deployer._register_iot_device(
            provider,
            tmp_path,
            {"id": "device-1"},
            "factory",
            "123456789012",
            "iot.example",
        )


def test_azure_grafana_lookup_error_is_not_treated_as_missing(monkeypatch):
    monkeypatch.setattr(
        layer_5_grafana, "get_grafana_workspace_url", lambda _p: "https://grafana"
    )
    monkeypatch.setattr(
        layer_5_grafana, "_get_grafana_service_account_token", lambda _p: "token"
    )
    response = SimpleNamespace(status_code=401)
    monkeypatch.setattr(
        layer_5_grafana.requests, "get", lambda *_args, **_kwargs: response
    )
    post = MagicMock()
    monkeypatch.setattr(layer_5_grafana.requests, "post", post)
    provider = SimpleNamespace(twin_name="factory")

    with pytest.raises(RuntimeError, match="lookup returned HTTP 401"):
        layer_5_grafana.configure_grafana_datasource(provider, "https://reader")

    post.assert_not_called()


def test_azure_v2_datasource_stores_function_key_only_as_secure_header(monkeypatch):
    response_not_found = SimpleNamespace(status_code=404)
    response_created = SimpleNamespace(status_code=201)
    monkeypatch.setattr(
        layer_5_grafana.requests,
        "get",
        lambda *_args, **_kwargs: response_not_found,
    )
    create = MagicMock(return_value=response_created)
    monkeypatch.setattr(layer_5_grafana.requests, "post", create)

    layer_5_grafana._upsert_v2_datasource(
        grafana_url="https://grafana.example",
        grafana_token="grafana-token",
        datasource_name="factory-hot-reader",
        hot_reader_url="https://reader.example/api/raw-history/v1",
        function_key="function-secret",
    )

    payload = create.call_args.kwargs["json"]
    assert payload["jsonData"]["httpHeaderName1"] == "x-functions-key"
    assert payload["secureJsonData"] == {"httpHeaderValue1": "function-secret"}
    assert "function-secret" not in str(payload["jsonData"])


def test_azure_v2_dashboard_has_bounded_raw_and_rollup_queries():
    dashboard = layer_5_grafana._v2_dashboard("sensor-1", "temperature")

    assert dashboard["uid"] == layer_5_grafana.V2_DASHBOARD_UID
    targets = [
        dashboard["panels"][1]["targets"][0],
        dashboard["panels"][2]["targets"][0],
    ]
    assert [dict(target["params"])["bucket_seconds"] for target in targets] == [
        "0",
        "3600",
    ]
    assert all(dict(target["params"])["limit"] == "1000" for target in targets)
    assert (
        "No data is a valid initial state"
        in dashboard["panels"][0]["options"]["content"]
    )


def test_azure_v2_surface_probe_executes_reader_health_and_dashboard(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        if url == "https://reader.example/api/raw-history/v1":
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"schema_version": "raw-history-query.v1"},
            )
        if url.endswith("/health"):
            return SimpleNamespace(status_code=200, json=lambda: {"status": "OK"})
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(layer_5_grafana.requests, "get", get)

    layer_5_grafana._probe_v2_surface(
        grafana_url="https://grafana.example",
        grafana_token="short-lived-token",
        hot_reader_url="https://reader.example/api/raw-history/v1",
        function_key="function-secret",
        device_id="sensor-1",
        metric="temperature",
    )

    reader_calls = [call for call in calls if call[0].startswith("https://reader")]
    assert [call[1]["params"]["bucket_seconds"] for call in reader_calls] == [
        "0",
        "3600",
    ]
    assert all(
        call[1]["headers"] == {"x-functions-key": "function-secret"}
        for call in reader_calls
    )
    assert calls[-2][0].endswith("/api/datasources/uid/t2mc-azure-hot-reader/health")
    assert calls[-1][0].endswith("/api/dashboards/uid/t2mc-raw-rollups")


def test_aws_v2_dashboard_has_bounded_raw_and_rollup_queries():
    dashboard = aws_layer_5_grafana._v2_dashboard("sensor-1", "temperature")

    assert dashboard["uid"] == aws_layer_5_grafana.V2_DASHBOARD_UID
    assert dashboard["title"] == "Twin2MultiCloud Raw & Rollups"
    targets = [
        dashboard["panels"][1]["targets"][0],
        dashboard["panels"][2]["targets"][0],
    ]
    assert [dict(target["params"])["bucket_seconds"] for target in targets] == [
        "0",
        "3600",
    ]
    assert all(dict(target["params"])["limit"] == "1000" for target in targets)
    assert "test-message utility" in dashboard["panels"][0]["options"]["content"]


def test_aws_v2_surface_probe_rejects_non_ok_datasource_health(monkeypatch):
    def get(url, **_kwargs):
        if url == "https://reader.example/":
            return SimpleNamespace(
                status_code=200,
                json=lambda: {"schema_version": "raw-history-query.v1"},
            )
        return SimpleNamespace(status_code=200, json=lambda: {"status": "ERROR"})

    monkeypatch.setattr(aws_layer_5_grafana.requests, "get", get)

    with pytest.raises(RuntimeError, match="health probe was not OK"):
        aws_layer_5_grafana._probe_v2_surface(
            grafana_url="https://grafana.example",
            token="short-lived-token",
            reader_url="https://reader.example/",
            reader_key="reader-secret",
            device_id="sensor-1",
            metric="temperature",
        )


def test_aws_v2_datasource_keeps_reader_key_only_in_secure_data(monkeypatch):
    not_found = SimpleNamespace(status_code=404)
    created = SimpleNamespace(status_code=201)
    create = MagicMock(return_value=created)
    monkeypatch.setattr(
        aws_layer_5_grafana.requests,
        "get",
        lambda *_args, **_kwargs: not_found,
    )
    monkeypatch.setattr(aws_layer_5_grafana.requests, "post", create)

    aws_layer_5_grafana._upsert_v2_datasource(
        grafana_url="https://grafana.example",
        token="short-lived-token",
        reader_url="https://reader.example/",
        reader_key="reader-secret",
    )

    payload = create.call_args.kwargs["json"]
    assert payload["jsonData"]["httpHeaderName1"] == "X-Twin-Reader-Key"
    assert payload["secureJsonData"] == {"httpHeaderValue1": "reader-secret"}
    assert "reader-secret" not in str(payload["jsonData"])


def test_aws_v2_provisioner_is_deleted_when_content_setup_fails(monkeypatch):
    provider = SimpleNamespace()
    deleted = MagicMock()
    monkeypatch.setattr(aws_layer_5_grafana, "_install_reader_key", MagicMock())
    monkeypatch.setattr(
        aws_layer_5_grafana,
        "_provisioning_service_account",
        lambda *_args: ("service-account", "short-lived-token"),
    )
    monkeypatch.setattr(
        aws_layer_5_grafana,
        "_ensure_exact_plugin",
        MagicMock(side_effect=RuntimeError("plugin unavailable")),
    )
    monkeypatch.setattr(
        aws_layer_5_grafana,
        "_delete_provisioning_service_account",
        deleted,
    )

    with pytest.raises(RuntimeError, match="plugin unavailable"):
        aws_layer_5_grafana.configure_five_layer_v2_grafana(
            provider,
            workspace_id="g-1234567890",
            grafana_url="https://grafana.example",
            reader_url="https://reader.example/",
            reader_function_name="reader",
            device_id="sensor-1",
            metric="temperature",
        )

    deleted.assert_called_once_with(provider, "g-1234567890", "service-account")


def test_aws_deployer_routes_five_layer_v2_to_the_exact_configurator(monkeypatch):
    provider = SimpleNamespace()
    config = SimpleNamespace(
        iot_devices=[
            {
                "id": "sensor-1",
                "properties": [{"name": "temperature"}],
            }
        ]
    )
    context = SimpleNamespace(
        providers={"aws": provider},
        config=config,
        resolved_deployment_graph=SimpleNamespace(
            profile_ref={"id": "five-layer-baseline", "version": "2"}
        ),
    )
    configure = MagicMock()
    monkeypatch.setattr(aws_layer_5_grafana, "configure_five_layer_v2_grafana", configure)

    aws_deployer.configure_aws_grafana(
        context,
        {
            "aws_component_visualization_output": {
                "workspace_id": "g-1234567890",
                "workspace_url": "https://grafana.example/",
                "reader_url": "https://reader.example/",
                "reader_function_name": "reader",
            }
        },
    )

    configure.assert_called_once_with(
        provider,
        workspace_id="g-1234567890",
        grafana_url="https://grafana.example",
        reader_url="https://reader.example/",
        reader_function_name="reader",
        device_id="sensor-1",
        metric="temperature",
    )


def test_azure_v2_plugin_preflight_rejects_wrong_loaded_version(monkeypatch):
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {"info": {"version": "1.3.28"}},
    )
    monkeypatch.setattr(
        layer_5_grafana.requests, "get", lambda *_args, **_kwargs: response
    )

    with pytest.raises(RuntimeError, match="version mismatch"):
        layer_5_grafana._wait_for_exact_plugin(
            "https://grafana.example", "token", attempts=1, delay_seconds=0
        )


def test_azure_v2_plugin_readiness_retries_role_propagation(monkeypatch):
    responses = iter(
        [
            SimpleNamespace(status_code=403),
            SimpleNamespace(
                status_code=200,
                json=lambda: {
                    "info": {"version": layer_5_grafana.JSON_DATASOURCE_PLUGIN_VERSION}
                },
            ),
        ]
    )
    monkeypatch.setattr(
        layer_5_grafana.requests,
        "get",
        lambda *_args, **_kwargs: next(responses),
    )
    sleep = MagicMock()
    monkeypatch.setattr(layer_5_grafana.time, "sleep", sleep)

    layer_5_grafana._wait_for_exact_plugin(
        "https://grafana.example", "token", attempts=2, delay_seconds=0
    )

    sleep.assert_called_once_with(0)


def test_azure_v2_reader_key_is_function_scoped_and_reused(monkeypatch):
    credential = SimpleNamespace(
        get_token=lambda _scope: SimpleNamespace(token="management-token")
    )
    provider = SimpleNamespace(
        credential=credential,
        subscription_id="11111111-1111-1111-1111-111111111111",
        naming=SimpleNamespace(resource_group=lambda: "factory-rg"),
    )
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {"properties": {"twin2multicloud-grafana": "existing-key"}},
    )
    lookup = MagicMock(return_value=response)
    update = MagicMock()
    monkeypatch.setattr(layer_5_grafana.requests, "post", lookup)
    monkeypatch.setattr(layer_5_grafana.requests, "put", update)

    value = layer_5_grafana._ensure_reader_function_key(provider, "factory-history")

    assert value == "existing-key"
    assert "/functions/v2-raw-history-reader/listkeys" in lookup.call_args.args[0]
    update.assert_not_called()


def test_azure_v2_reader_key_is_created_without_exposing_it_in_outputs(monkeypatch):
    credential = SimpleNamespace(
        get_token=lambda _scope: SimpleNamespace(token="management-token")
    )
    provider = SimpleNamespace(
        credential=credential,
        subscription_id="11111111-1111-1111-1111-111111111111",
        naming=SimpleNamespace(resource_group=lambda: "factory-rg"),
    )
    lookup_response = SimpleNamespace(
        status_code=200,
        json=lambda: {"properties": {}},
    )
    create_response = SimpleNamespace(status_code=200)
    monkeypatch.setattr(
        layer_5_grafana.requests,
        "post",
        MagicMock(return_value=lookup_response),
    )
    create = MagicMock(return_value=create_response)
    monkeypatch.setattr(layer_5_grafana.requests, "put", create)
    monkeypatch.setattr(
        layer_5_grafana.secrets,
        "token_urlsafe",
        lambda _length: "generated-function-key",
    )

    value = layer_5_grafana._ensure_reader_function_key(provider, "factory-history")

    assert value == "generated-function-key"
    assert "/functions/v2-raw-history-reader/keys/" in create.call_args.args[0]
    assert create.call_args.kwargs["json"] == {
        "name": "twin2multicloud-grafana",
        "value": "generated-function-key",
    }


def test_azure_twin_failures_are_aggregated_after_relationship_attempt(monkeypatch):
    calls = []

    class Client:
        def create_models(self, models):
            return models

        def upsert_digital_twin(self, twin_id, _twin):
            calls.append(("twin", twin_id))
            if twin_id == "broken":
                raise RuntimeError("azure_client_secret=must-not-leak")

        def upsert_relationship(self, source_id, relationship_id, _relationship):
            calls.append(("relationship", source_id, relationship_id))

    monkeypatch.setattr(layer_4_adt, "_get_adt_data_client", lambda _provider: Client())
    config = SimpleNamespace(
        hierarchy={
            "models": [{"@id": "dtmi:factory;1"}],
            "twins": [
                {"$dtId": "broken"},
                {"$dtId": "healthy"},
            ],
            "relationships": [
                {
                    "$dtId": "healthy",
                    "$relationshipId": "contains",
                    "$targetId": "broken",
                    "$relationshipName": "contains",
                }
            ],
        }
    )

    with pytest.raises(ProviderRuntimeError) as exc_info:
        layer_4_adt.upload_dtdl_models(object(), config, "unused")

    assert calls == [
        ("twin", "broken"),
        ("twin", "healthy"),
        ("relationship", "healthy", "contains"),
    ]
    assert "must-not-leak" not in str(exc_info.value)


def test_azure_v2_empty_hierarchy_gets_deterministic_visible_seed(monkeypatch):
    created = {"models": [], "twins": [], "relationships": []}
    read = {"models": [], "twins": [], "relationships": []}

    class Client:
        def create_models(self, models):
            created["models"].extend(models)
            return models

        def upsert_digital_twin(self, twin_id, twin):
            created["twins"].append((twin_id, twin))

        def upsert_relationship(self, source_id, relationship_id, relationship):
            created["relationships"].append((source_id, relationship_id, relationship))

        def get_model(self, model_id):
            read["models"].append(model_id)
            return {"id": model_id}

        def get_digital_twin(self, twin_id):
            read["twins"].append(twin_id)
            return {"$dtId": twin_id}

        def get_relationship(self, source_id, relationship_id):
            read["relationships"].append((source_id, relationship_id))
            assert source_id == "factory-root"
            assert relationship_id == "contains-seed-device"
            return {
                "$targetId": "sensor-1",
                "$relationshipName": "contains",
            }

    monkeypatch.setattr(layer_4_adt, "_get_adt_data_client", lambda _provider: Client())
    config = SimpleNamespace(
        digital_twin_name="factory",
        iot_devices=[{"id": "sensor-1"}],
        hierarchy={"models": [], "twins": [], "relationships": []},
    )

    layer_4_adt.upload_dtdl_models(object(), config, "unused", ensure_v2_seed=True)

    assert [model["@id"] for model in created["models"]] == [
        layer_4_adt.V2_SEED_MODEL_ID
    ]
    assert [twin_id for twin_id, _twin in created["twins"]] == [
        "factory-root",
        "sensor-1",
    ]
    assert created["relationships"] == [
        (
            "factory-root",
            "contains-seed-device",
            {"$targetId": "sensor-1", "$relationshipName": "contains"},
        )
    ]
    assert read == {
        "models": [layer_4_adt.V2_SEED_MODEL_ID],
        "twins": ["factory-root", "sensor-1"],
        "relationships": [("factory-root", "contains-seed-device")],
    }
