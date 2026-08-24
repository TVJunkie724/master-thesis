from __future__ import annotations

from dataclasses import dataclass
import hashlib

import pytest

from src.schemas.cloud_bootstrap import (
    AWSBootstrapCredential,
    AWSBootstrapTarget,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
)
from src.services.aws_cloud_bootstrap_driver import (
    AWSClients,
    AWSCloudBootstrapDriver,
    MANAGED_BY,
    MANAGED_BY_TAG_KEY,
    OWNERSHIP_TAG_KEY,
    USER_PATH,
)
from src.services.cloud_bootstrap_adapters import (
    CloudBootstrapAdapterError,
    CloudBootstrapRollbackReceipt,
    SupervisedLiveCloudBootstrapAdapter,
)


class NotFoundError(RuntimeError):
    response = {"Error": {"Code": "NoSuchEntity"}}


@dataclass
class FakeAWSEnvironment:
    account_id: str = "123456789012"
    bootstrap_key: str = "AKIABOOTSTRAP0000001"
    bootstrap_secret: str = "submitted-aws-bootstrap-secret"
    bootstrap_user: str = "bootstrap-admin"
    generated_region_visible: bool = True
    unexpected_inline_policy: bool = False
    unexpected_group: bool = False

    def __post_init__(self):
        self.user = None
        self.policy = None
        self.attached = False
        self.generated_key = None
        self.generated_secret = None
        self.bootstrap_key_deleted = False
        self.key_counter = 0
        self.operations: list[str] = []

    def factory(self, access_key, secret, session_token, region):
        del session_token
        if (
            access_key == self.bootstrap_key
            and secret == self.bootstrap_secret
            and not self.bootstrap_key_deleted
        ):
            identity = "bootstrap"
        elif access_key == self.generated_key and secret == self.generated_secret:
            identity = "generated"
        else:
            raise RuntimeError("unknown fake credential")
        iam = FakeIAM(self, identity)
        return AWSClients(
            iam=iam,
            sts=FakeSTS(self, identity),
            ec2=FakeEC2(self, region),
        )


class FakeSTS:
    def __init__(self, environment, identity):
        self.environment = environment
        self.identity = identity

    def get_caller_identity(self):
        if self.identity == "bootstrap":
            arn = (
                f"arn:aws:iam::{self.environment.account_id}:user/"
                f"{self.environment.bootstrap_user}"
            )
        else:
            arn = self.environment.user["Arn"]
        return {"Account": self.environment.account_id, "Arn": arn, "UserId": "id"}


class FakeEC2:
    def __init__(self, environment, region):
        self.environment = environment
        self.region = region

    def describe_regions(self, *, RegionNames, AllRegions):
        assert AllRegions is False
        if self.environment.generated_region_visible:
            return {"Regions": [{"RegionName": RegionNames[0]}]}
        return {"Regions": []}


class FakeIAM:
    def __init__(self, environment, identity):
        self.environment = environment
        self.identity = identity

    def get_access_key_last_used(self, *, AccessKeyId):
        if AccessKeyId != self.environment.bootstrap_key:
            raise NotFoundError()
        return {"UserName": self.environment.bootstrap_user}

    def get_user(self, *, UserName=None):
        if UserName in {
            None,
            self.environment.user and self.environment.user["UserName"],
        }:
            if self.identity == "generated" and self.environment.user:
                return {"User": dict(self.environment.user)}
        if UserName == self.environment.bootstrap_user:
            return {
                "User": {
                    "UserName": self.environment.bootstrap_user,
                    "Path": "/",
                    "Arn": (
                        f"arn:aws:iam::{self.environment.account_id}:user/"
                        f"{self.environment.bootstrap_user}"
                    ),
                }
            }
        if self.environment.user and UserName == self.environment.user["UserName"]:
            return {"User": dict(self.environment.user)}
        raise NotFoundError()

    def create_user(self, *, Path, UserName, Tags):
        self.environment.operations.append("create_user")
        self.environment.user = {
            "Path": Path,
            "UserName": UserName,
            "Arn": (f"arn:aws:iam::{self.environment.account_id}:user{Path}{UserName}"),
            "Tags": list(Tags),
        }
        return {"User": dict(self.environment.user)}

    def get_policy(self, *, PolicyArn):
        if not self.environment.policy or self.environment.policy["Arn"] != PolicyArn:
            raise NotFoundError()
        return {"Policy": dict(self.environment.policy)}

    def create_policy(self, *, PolicyName, PolicyDocument, Description, Tags):
        del Description
        self.environment.operations.append("create_policy")
        self.environment.policy = {
            "PolicyName": PolicyName,
            "Arn": (f"arn:aws:iam::{self.environment.account_id}:policy/{PolicyName}"),
            "Path": "/",
            "DefaultVersionId": "v1",
            "IsAttachable": True,
            "Tags": list(Tags),
            "Document": PolicyDocument,
        }
        return {"Policy": dict(self.environment.policy)}

    def get_policy_version(self, *, PolicyArn, VersionId):
        assert PolicyArn == self.environment.policy["Arn"]
        assert VersionId == "v1"
        return {"PolicyVersion": {"Document": self.environment.policy["Document"]}}

    def list_entities_for_policy(self, *, PolicyArn):
        assert PolicyArn == self.environment.policy["Arn"]
        return {
            "PolicyUsers": (
                [{"UserName": self.environment.user["UserName"]}]
                if self.environment.attached
                else []
            ),
            "PolicyGroups": [],
            "PolicyRoles": [],
        }

    def list_attached_user_policies(self, *, UserName):
        assert UserName == self.environment.user["UserName"]
        return {
            "AttachedPolicies": (
                [{"PolicyArn": self.environment.policy["Arn"]}]
                if self.environment.attached
                else []
            )
        }

    def list_user_policies(self, *, UserName):
        assert UserName == self.environment.user["UserName"]
        return {
            "PolicyNames": (
                ["external-inline-policy"]
                if self.environment.unexpected_inline_policy
                else []
            )
        }

    def list_groups_for_user(self, *, UserName):
        assert UserName == self.environment.user["UserName"]
        return {
            "Groups": (
                [{"GroupName": "external-group"}]
                if self.environment.unexpected_group
                else []
            )
        }

    def attach_user_policy(self, *, UserName, PolicyArn):
        assert UserName == self.environment.user["UserName"]
        assert PolicyArn == self.environment.policy["Arn"]
        self.environment.operations.append("attach_user_policy")
        self.environment.attached = True

    def detach_user_policy(self, *, UserName, PolicyArn):
        del UserName, PolicyArn
        self.environment.operations.append("detach_user_policy")
        self.environment.attached = False

    def list_access_keys(self, *, UserName):
        if UserName == self.environment.bootstrap_user:
            return {
                "AccessKeyMetadata": (
                    []
                    if self.environment.bootstrap_key_deleted
                    else [{"AccessKeyId": self.environment.bootstrap_key}]
                )
            }
        assert UserName == self.environment.user["UserName"]
        return {
            "AccessKeyMetadata": (
                [{"AccessKeyId": self.environment.generated_key}]
                if self.environment.generated_key
                else []
            )
        }

    def create_access_key(self, *, UserName):
        assert UserName == self.environment.user["UserName"]
        self.environment.operations.append("create_access_key")
        self.environment.key_counter += 1
        self.environment.generated_key = (
            f"AKIAGENERATED{self.environment.key_counter:07d}"
        )
        self.environment.generated_secret = (
            f"generated-aws-deployment-secret-{self.environment.key_counter}"
        )
        return {
            "AccessKey": {
                "AccessKeyId": self.environment.generated_key,
                "SecretAccessKey": self.environment.generated_secret,
            }
        }

    def delete_access_key(self, *, UserName, AccessKeyId):
        self.environment.operations.append("delete_access_key")
        if UserName == self.environment.bootstrap_user:
            assert AccessKeyId == self.environment.bootstrap_key
            self.environment.bootstrap_key_deleted = True
            return
        assert UserName == self.environment.user["UserName"]
        if AccessKeyId != self.environment.generated_key:
            raise NotFoundError()
        self.environment.generated_key = None
        self.environment.generated_secret = None

    def list_policy_versions(self, *, PolicyArn):
        assert PolicyArn == self.environment.policy["Arn"]
        return {"Versions": [{"VersionId": "v1", "IsDefaultVersion": True}]}

    def delete_policy_version(self, *, PolicyArn, VersionId):
        raise AssertionError(f"unexpected non-default version {PolicyArn} {VersionId}")

    def delete_policy(self, *, PolicyArn):
        assert PolicyArn == self.environment.policy["Arn"]
        self.environment.operations.append("delete_policy")
        self.environment.policy = None

    def delete_user(self, *, UserName):
        assert UserName == self.environment.user["UserName"]
        if self.environment.unexpected_inline_policy or self.environment.unexpected_group:
            raise RuntimeError("user still has external authority")
        self.environment.operations.append("delete_user")
        self.environment.user = None


def test_aws_driver_provisions_validates_and_finalizes_exact_static_key():
    environment = FakeAWSEnvironment()
    adapter = _adapter(environment)
    target, credential = _input(environment)

    result = adapter.execute(
        session_id="aws-provider-driver-session",
        display_name="AWS deployment access",
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=credential,
    )

    assert result.connection.aws.access_key_id == environment.generated_key
    assert result.disposal_status == (
        CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED
    )
    assert result.bootstrap_finalization_required is True
    assert environment.operations[:4] == [
        "create_user",
        "create_policy",
        "attach_user_policy",
        "create_access_key",
    ]

    finalized = adapter.finalize_bootstrap(
        result=result,
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.DEDICATED_DISPOSABLE,
        credential=credential,
    )
    assert finalized.disposal_status == CloudBootstrapDisposalStatus.REVOKED
    assert environment.bootstrap_key_deleted is True
    assert environment.generated_key is not None


def test_aws_driver_reconciles_owned_retry_and_rollback_removes_only_gate_resources():
    environment = FakeAWSEnvironment()
    adapter = _adapter(environment)
    target, credential = _input(environment)
    first = adapter.execute(
        session_id="aws-reconcile-session",
        display_name="AWS deployment access",
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
        credential=credential,
    )
    first_key = first.connection.aws.access_key_id

    second = adapter.execute(
        session_id="aws-reconcile-session",
        display_name="AWS deployment access",
        target=target,
        credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
        credential=credential,
    )
    assert second.connection.aws.access_key_id != first_key
    assert environment.operations.count("create_user") == 1
    assert environment.operations.count("create_policy") == 1
    assert environment.operations.count("delete_access_key") == 1

    adapter.rollback(result=second, target=target, credential=credential)
    assert environment.generated_key is None
    assert environment.policy is None
    assert environment.user is None
    assert environment.bootstrap_key_deleted is False


def test_aws_generated_validation_failure_self_compensates_without_secret_output():
    environment = FakeAWSEnvironment(generated_region_visible=False)
    sleeps: list[float] = []
    adapter = SupervisedLiveCloudBootstrapAdapter(
        {
            "aws": AWSCloudBootstrapDriver(
                client_factory=environment.factory,
                sleeper=sleeps.append,
            )
        }
    )
    target, credential = _input(environment)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id="aws-validation-failure-session",
            display_name="AWS deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CONNECTION_VALIDATION_FAILED"
    assert environment.generated_key is None
    assert environment.policy is None
    assert environment.user is None
    assert sleeps == [1, 2, 4]
    assert environment.bootstrap_secret not in str(exc_info.value)


@pytest.mark.parametrize("extra", ["unexpected_inline_policy", "unexpected_group"])
def test_aws_generated_identity_rejects_external_authority_without_deleting_it(extra):
    environment = FakeAWSEnvironment(**{extra: True})
    adapter = _adapter(environment)
    target, credential = _input(environment)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id=f"aws-external-authority-{extra}",
            display_name="AWS deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CLEANUP_FAILED"
    assert environment.user is not None
    assert environment.generated_key is None
    assert environment.policy is None
    assert "delete_user" not in environment.operations


def test_aws_wrong_account_fails_before_any_mutation():
    environment = FakeAWSEnvironment(account_id="999999999999")
    adapter = _adapter(environment)
    target, credential = _input(environment, target_account="123456789012")

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id="aws-wrong-account-session",
            display_name="AWS deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_CREDENTIAL_INVALID"
    assert environment.operations == []


def test_aws_target_region_must_match_frozen_deployment_bundle():
    environment = FakeAWSEnvironment()
    adapter = _adapter(environment)
    target, credential = _input(environment, target_region="us-east-1")

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id="aws-region-mismatch-session",
            display_name="AWS deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_AUTHORITY_PACK_MISMATCH"
    assert environment.operations == []


def test_aws_rollback_revalidates_account_before_cleanup():
    environment = FakeAWSEnvironment(account_id="999999999999")
    driver = AWSCloudBootstrapDriver(
        client_factory=environment.factory,
        sleeper=lambda _seconds: None,
    )
    target, credential = _input(environment, target_account="123456789012")
    run_id = "twin2mc-e2e-rollback-scope"
    receipt = CloudBootstrapRollbackReceipt(
        provider="aws",
        run_id=run_id,
        resource_ids=(("user_name", f"{run_id}-deployer"),),
    )

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        driver.rollback(receipt=receipt, target=target, credential=credential)

    assert exc_info.value.code == "BOOTSTRAP_CREDENTIAL_INVALID"
    assert environment.operations == []


def test_aws_unowned_user_name_collision_is_not_deleted():
    environment = FakeAWSEnvironment()
    session_id = "aws-unowned-user-collision"
    run_id = f"twin2mc-e2e-{hashlib.sha256(session_id.encode()).hexdigest()[:12]}"
    environment.user = {
        "Path": USER_PATH,
        "UserName": f"{run_id}-deployer",
        "Arn": (
            f"arn:aws:iam::{environment.account_id}:user{USER_PATH}"
            f"{run_id}-deployer"
        ),
        "Tags": [{"Key": "owner", "Value": "someone-else"}],
    }
    adapter = _adapter(environment)
    target, credential = _input(environment)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id=session_id,
            display_name="AWS deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_IDENTITY_CREATION_FAILED"
    assert environment.user is not None
    assert "delete_user" not in environment.operations


def test_aws_unowned_policy_collision_is_not_deleted():
    environment = FakeAWSEnvironment()
    session_id = "aws-unowned-policy-collision"
    run_id = f"twin2mc-e2e-{hashlib.sha256(session_id.encode()).hexdigest()[:12]}"
    user_name = f"{run_id}-deployer"
    policy_name = f"{run_id}-deployment"
    environment.user = {
        "Path": USER_PATH,
        "UserName": user_name,
        "Arn": f"arn:aws:iam::{environment.account_id}:user{USER_PATH}{user_name}",
        "Tags": [
            {"Key": OWNERSHIP_TAG_KEY, "Value": run_id},
            {"Key": MANAGED_BY_TAG_KEY, "Value": MANAGED_BY},
        ],
    }
    environment.policy = {
        "PolicyName": policy_name,
        "Arn": f"arn:aws:iam::{environment.account_id}:policy/{policy_name}",
        "Path": "/",
        "DefaultVersionId": "v1",
        "IsAttachable": True,
        "Tags": [{"Key": "owner", "Value": "someone-else"}],
        "Document": "{}",
    }
    adapter = _adapter(environment)
    target, credential = _input(environment)

    with pytest.raises(CloudBootstrapAdapterError) as exc_info:
        adapter.execute(
            session_id=session_id,
            display_name="AWS deployment access",
            target=target,
            credential_origin=CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED,
            credential=credential,
        )

    assert exc_info.value.code == "BOOTSTRAP_IDENTITY_CREATION_FAILED"
    assert environment.policy is not None
    assert "delete_policy" not in environment.operations


def _adapter(environment):
    return SupervisedLiveCloudBootstrapAdapter(
        {
            "aws": AWSCloudBootstrapDriver(
                client_factory=environment.factory,
                sleeper=lambda _seconds: None,
            )
        }
    )


def _input(environment, *, target_account=None, target_region="eu-central-1"):
    return (
        AWSBootstrapTarget(
            provider="aws",
            account_id=target_account or environment.account_id,
            region=target_region,
        ),
        AWSBootstrapCredential(
            provider="aws",
            access_key_id=environment.bootstrap_key,
            secret_access_key=environment.bootstrap_secret,
        ),
    )
