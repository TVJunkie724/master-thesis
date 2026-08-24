"""AWS setup-only driver for the supervised guided-bootstrap transaction."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import time
from typing import Any, Callable, Protocol
from urllib.parse import unquote

from src.schemas.cloud_bootstrap import (
    AWSBootstrapCredential,
    AWSBootstrapTarget,
    CloudBootstrapCredential,
    CloudBootstrapCredentialOrigin,
    CloudBootstrapDisposalStatus,
    CloudBootstrapTarget,
)
from src.schemas.cloud_connection import CloudConnectionCreate
from src.schemas.twin_config import AWSCredentials
from src.services.cloud_bootstrap_adapters import (
    CloudBootstrapAdapterError,
    CloudBootstrapAdapterResult,
    CloudBootstrapFinalizationResult,
    CloudBootstrapRollbackReceipt,
    SupervisedLiveBootstrapPlan,
)


MANAGED_BY = "twin2multicloud-setup-only"
OWNERSHIP_TAG_KEY = "twin2mc:run-id"
MANAGED_BY_TAG_KEY = "twin2mc:managed-by"
USER_PATH = "/twin2multicloud/setup-only/"


class AWSClient(Protocol):
    """Structural marker for injected boto3 clients."""


@dataclass(frozen=True)
class AWSClients:
    iam: AWSClient
    sts: AWSClient
    ec2: AWSClient


AWSClientFactory = Callable[
    [str, str, str | None, str],
    AWSClients,
]


def default_aws_client_factory(
    access_key_id: str,
    secret_access_key: str,
    session_token: str | None,
    region: str,
) -> AWSClients:
    """Create boto3 clients lazily so offline imports never discover credentials."""

    import boto3

    session = boto3.Session(
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=session_token,
        region_name=region,
    )
    return AWSClients(
        iam=session.client("iam"),
        sts=session.client("sts"),
        ec2=session.client("ec2", region_name=region),
    )


class AWSCloudBootstrapDriver:
    """Create and validate one gate-owned IAM-user deployment identity."""

    def __init__(
        self,
        *,
        client_factory: AWSClientFactory = default_aws_client_factory,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client_factory = client_factory
        self._sleep = sleeper

    def provision(
        self,
        *,
        plan: SupervisedLiveBootstrapPlan,
        display_name: str,
        target: CloudBootstrapTarget,
        credential_origin: CloudBootstrapCredentialOrigin,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapAdapterResult:
        if (
            plan.provider != "aws"
            or not isinstance(target, AWSBootstrapTarget)
            or not isinstance(credential, AWSBootstrapCredential)
        ):
            raise self._invalid_credential()
        clients = self._bootstrap_clients(credential, target.region)
        self._validate_bootstrap_identity(clients, target, credential)
        bundle = plan.deployment_document()
        self._validate_bundle(bundle, plan, target)
        user_name = bundle["identity"]["user_name"]
        policy = bundle["managed_policy"]
        policy_arn = policy["arn"]
        generated_access_key_id: str | None = None
        receipt: CloudBootstrapRollbackReceipt | None = None
        try:
            self._ensure_user(clients.iam, user_name, plan.run_id)
            receipt = CloudBootstrapRollbackReceipt(
                provider="aws",
                run_id=plan.run_id,
                resource_ids=(("user_name", user_name),),
            )
            self._ensure_policy(
                clients.iam,
                policy_arn=policy_arn,
                policy_name=policy["name"],
                policy_document=policy["document"],
                run_id=plan.run_id,
                user_name=user_name,
            )
            receipt = CloudBootstrapRollbackReceipt(
                provider="aws",
                run_id=plan.run_id,
                resource_ids=(
                    ("policy_arn", policy_arn),
                    ("user_name", user_name),
                ),
            )
            self._ensure_attachment(clients.iam, user_name, policy_arn)
            key = self._replace_generated_access_key(clients.iam, user_name)
            generated_access_key_id = self._required_string(key, "AccessKeyId")
            generated_secret = self._required_string(key, "SecretAccessKey")
            receipt = CloudBootstrapRollbackReceipt(
                provider="aws",
                run_id=plan.run_id,
                resource_ids=(
                    ("access_key_id", generated_access_key_id),
                    ("policy_arn", policy_arn),
                    ("user_name", user_name),
                ),
            )
            self._validate_generated_credential(
                account_id=target.account_id,
                region=target.region,
                user_name=user_name,
                policy_arn=policy_arn,
                policy_document=policy["document"],
                access_key_id=generated_access_key_id,
                secret_access_key=generated_secret,
            )
        except Exception as exc:
            try:
                if receipt is not None:
                    self._cleanup(clients.iam, receipt)
            except Exception as cleanup_exc:
                raise CloudBootstrapAdapterError(
                    "BOOTSTRAP_CLEANUP_FAILED",
                    f"AWS setup run {plan.run_id} requires manual cleanup.",
                ) from cleanup_exc
            if isinstance(exc, CloudBootstrapAdapterError):
                raise
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "AWS rejected the reviewed setup-only identity transaction.",
            ) from exc

        disposal_status, expiry, finalize = self._provisional_disposal(
            credential_origin,
            credential,
            target,
        )
        return CloudBootstrapAdapterResult(
            connection=CloudConnectionCreate(
                provider="aws",
                purpose="deployment",
                display_name=display_name,
                auth_type="access_key",
                permission_set_version="thesis-demo-v2",
                cloud_scope={
                    "account_id": target.account_id,
                    "region": target.region,
                    "bootstrap_mode": "supervised_live",
                },
                aws=AWSCredentials(
                    access_key_id=generated_access_key_id,
                    secret_access_key=generated_secret,
                    region=target.region,
                ),
            ),
            safe_credential_identifier=credential.access_key_id.get_secret_value(),
            disposal_status=disposal_status,
            credential_expires_at=expiry,
            generated_credential_validated=True,
            # A successful transaction always advances the receipt through the
            # user, policy, and generated-key ownership boundaries above.
            rollback_receipt=receipt,
            bootstrap_finalization_required=finalize,
        )

    def rollback(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> None:
        if (
            receipt.provider != "aws"
            or not isinstance(target, AWSBootstrapTarget)
            or not isinstance(credential, AWSBootstrapCredential)
        ):
            raise self._invalid_credential()
        clients = self._bootstrap_clients(credential, target.region)
        self._validate_bootstrap_identity(clients, target, credential)
        self._validate_receipt_scope(receipt, target)
        self._cleanup(clients.iam, receipt)

    def finalize_bootstrap(
        self,
        *,
        receipt: CloudBootstrapRollbackReceipt,
        target: CloudBootstrapTarget,
        credential: CloudBootstrapCredential,
    ) -> CloudBootstrapFinalizationResult:
        if (
            receipt.provider != "aws"
            or not isinstance(target, AWSBootstrapTarget)
            or not isinstance(credential, AWSBootstrapCredential)
        ):
            raise self._invalid_credential()
        if credential.session_token is not None:
            if target.session_expires_at is None:
                raise self._invalid_credential()
            return CloudBootstrapFinalizationResult(
                disposal_status=CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER,
                credential_expires_at=target.session_expires_at,
            )

        access_key_id = credential.access_key_id.get_secret_value()
        clients = self._bootstrap_clients(credential, target.region)
        caller = self._caller(clients.sts)
        owner = clients.iam.get_access_key_last_used(AccessKeyId=access_key_id)
        owner_name = self._required_string(owner, "UserName")
        user = clients.iam.get_user(UserName=owner_name)["User"]
        if (
            caller["Account"] != target.account_id
            or caller["Arn"] != user.get("Arn")
            or access_key_id
            not in {
                item.get("AccessKeyId")
                for item in clients.iam.list_access_keys(UserName=owner_name).get(
                    "AccessKeyMetadata", []
                )
            }
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "AWS bootstrap-key ownership could not be proven for automatic deletion.",
            )
        clients.iam.delete_access_key(
            UserName=owner_name,
            AccessKeyId=access_key_id,
        )
        return CloudBootstrapFinalizationResult(
            disposal_status=CloudBootstrapDisposalStatus.REVOKED,
        )

    def _bootstrap_clients(
        self,
        credential: AWSBootstrapCredential,
        region: str,
    ) -> AWSClients:
        return self._client_factory(
            credential.access_key_id.get_secret_value(),
            credential.secret_access_key.get_secret_value(),
            (
                credential.session_token.get_secret_value()
                if credential.session_token is not None
                else None
            ),
            region,
        )

    def _validate_bootstrap_identity(
        self,
        clients: AWSClients,
        target: AWSBootstrapTarget,
        credential: AWSBootstrapCredential,
    ) -> None:
        caller = self._caller(clients.sts)
        if caller["Account"] != target.account_id or caller["Arn"].endswith(":root"):
            raise self._invalid_credential()
        access_key_id = credential.access_key_id.get_secret_value()
        if credential.session_token is None:
            owner = clients.iam.get_access_key_last_used(AccessKeyId=access_key_id)
            owner_name = self._required_string(owner, "UserName")
            user = clients.iam.get_user(UserName=owner_name)["User"]
            if caller["Arn"] != user.get("Arn"):
                raise self._invalid_credential()
        elif target.session_expires_at is None:
            raise self._invalid_credential()

    @staticmethod
    def _validate_bundle(
        bundle: dict[str, Any],
        plan: SupervisedLiveBootstrapPlan,
        target: AWSBootstrapTarget,
    ) -> None:
        if (
            bundle.get("schema_version") != "aws-deployment-identity-bundle.v1"
            or bundle.get("provider") != "aws"
            or bundle.get("account_id") != target.account_id
            or bundle.get("region") != target.region
            or bundle.get("permission_set_version") != "thesis-demo-v2"
            or bundle.get("identity_binding_id") != "aws.thesis-demo-v2.iam-user-v1"
            or bundle.get("identity", {}).get("user_name") != f"{plan.run_id}-deployer"
            or bundle.get("managed_policy", {}).get("name")
            != f"{plan.run_id}-deployment"
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The AWS provider bundle does not match the reviewed v2 contract.",
            )

    @staticmethod
    def _ensure_user(iam: AWSClient, user_name: str, run_id: str) -> None:
        tags = AWSCloudBootstrapDriver._tags(run_id)
        try:
            user = iam.get_user(UserName=user_name)["User"]
        except Exception as exc:
            if not AWSCloudBootstrapDriver._is_not_found(exc):
                raise
            user = iam.create_user(
                Path=USER_PATH,
                UserName=user_name,
                Tags=tags,
            )["User"]
        if (
            user.get("UserName") != user_name
            or user.get("Path") != USER_PATH
            or AWSCloudBootstrapDriver._tag_map(user.get("Tags"))
            != AWSCloudBootstrapDriver._tag_map(tags)
            or user.get("PermissionsBoundary") is not None
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "An existing AWS user does not match the setup-run ownership boundary.",
            )

    @staticmethod
    def _ensure_policy(
        iam: AWSClient,
        *,
        policy_arn: str,
        policy_name: str,
        policy_document: dict[str, Any],
        run_id: str,
        user_name: str,
    ) -> None:
        tags = AWSCloudBootstrapDriver._tags(run_id)
        try:
            policy = iam.get_policy(PolicyArn=policy_arn)["Policy"]
        except Exception as exc:
            if not AWSCloudBootstrapDriver._is_not_found(exc):
                raise
            policy = iam.create_policy(
                PolicyName=policy_name,
                PolicyDocument=AWSCloudBootstrapDriver._canonical(policy_document),
                Description="Twin2MultiCloud setup-only thesis-demo-v2 policy",
                Tags=tags,
            )["Policy"]
        if (
            policy.get("PolicyName") != policy_name
            or policy.get("Arn") != policy_arn
            or policy.get("Path", "/") != "/"
            or policy.get("IsAttachable", True) is not True
            or AWSCloudBootstrapDriver._tag_map(policy.get("Tags"))
            != AWSCloudBootstrapDriver._tag_map(tags)
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "An existing AWS policy does not match the setup-run ownership boundary.",
            )
        version = iam.get_policy_version(
            PolicyArn=policy_arn,
            VersionId=policy["DefaultVersionId"],
        )["PolicyVersion"]
        if AWSCloudBootstrapDriver._policy_document(version.get("Document")) != (
            policy_document
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
                "The existing gate-owned AWS policy differs from the reviewed v2 document.",
            )
        entities = iam.list_entities_for_policy(PolicyArn=policy_arn)
        users = {item.get("UserName") for item in entities.get("PolicyUsers", [])}
        if (
            entities.get("IsTruncated")
            or not users.issubset({user_name})
            or entities.get("PolicyGroups")
            or entities.get("PolicyRoles")
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The gate-owned AWS policy is attached outside the selected setup run.",
            )

    @staticmethod
    def _ensure_attachment(iam: AWSClient, user_name: str, policy_arn: str) -> None:
        response = iam.list_attached_user_policies(UserName=user_name)
        if response.get("IsTruncated"):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The gate-owned AWS user's policy inventory is incomplete.",
            )
        attached = {
            item.get("PolicyArn")
            for item in response.get("AttachedPolicies", [])
        }
        if attached - {policy_arn}:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "The gate-owned AWS user has an unexpected managed-policy attachment.",
            )
        if policy_arn not in attached:
            iam.attach_user_policy(UserName=user_name, PolicyArn=policy_arn)

    @staticmethod
    def _replace_generated_access_key(iam: AWSClient, user_name: str) -> dict[str, Any]:
        for item in iam.list_access_keys(UserName=user_name).get(
            "AccessKeyMetadata", []
        ):
            access_key_id = item.get("AccessKeyId")
            if access_key_id:
                iam.delete_access_key(
                    UserName=user_name,
                    AccessKeyId=access_key_id,
                )
        return iam.create_access_key(UserName=user_name)["AccessKey"]

    def _validate_generated_credential(
        self,
        *,
        account_id: str,
        region: str,
        user_name: str,
        policy_arn: str,
        policy_document: dict[str, Any],
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                clients = self._client_factory(
                    access_key_id,
                    secret_access_key,
                    None,
                    region,
                )
                caller = self._caller(clients.sts)
                if caller["Account"] != account_id or not caller["Arn"].endswith(
                    f":user{USER_PATH}{user_name}"
                ):
                    raise self._invalid_credential()
                attached_response = clients.iam.list_attached_user_policies(
                    UserName=user_name
                )
                inline_response = clients.iam.list_user_policies(UserName=user_name)
                groups_response = clients.iam.list_groups_for_user(UserName=user_name)
                policy = clients.iam.get_policy(PolicyArn=policy_arn)["Policy"]
                version = clients.iam.get_policy_version(
                    PolicyArn=policy_arn,
                    VersionId=policy["DefaultVersionId"],
                )["PolicyVersion"]
                attached = {
                    item.get("PolicyArn")
                    for item in attached_response.get("AttachedPolicies", [])
                }
                regions = {
                    item.get("RegionName")
                    for item in clients.ec2.describe_regions(
                        RegionNames=[region],
                        AllRegions=False,
                    ).get("Regions", [])
                }
                if (
                    attached_response.get("IsTruncated")
                    or inline_response.get("IsTruncated")
                    or groups_response.get("IsTruncated")
                    or attached != {policy_arn}
                    or inline_response.get("PolicyNames")
                    or groups_response.get("Groups")
                    or policy.get("Arn") != policy_arn
                    or self._policy_document(version.get("Document"))
                    != policy_document
                    or regions != {region}
                ):
                    raise self._invalid_credential()
                return
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    self._sleep(2**attempt)
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_CONNECTION_VALIDATION_FAILED",
            "The generated AWS credential did not pass identity, authority, and region checks.",
        ) from last_error

    @staticmethod
    def _cleanup(iam: AWSClient, receipt: CloudBootstrapRollbackReceipt) -> None:
        identifiers = dict(receipt.resource_ids)
        user_name = identifiers.get("user_name")
        policy_arn = identifiers.get("policy_arn")
        access_key_id = identifiers.get("access_key_id")
        if user_name and access_key_id:
            AWSCloudBootstrapDriver._ignore_not_found(
                lambda: iam.delete_access_key(
                    UserName=user_name,
                    AccessKeyId=access_key_id,
                )
            )
        if user_name and policy_arn:
            AWSCloudBootstrapDriver._ignore_not_found(
                lambda: iam.detach_user_policy(
                    UserName=user_name,
                    PolicyArn=policy_arn,
                )
            )
        if policy_arn:
            try:
                versions = iam.list_policy_versions(PolicyArn=policy_arn).get(
                    "Versions", []
                )
                for version in versions:
                    if not version.get("IsDefaultVersion") and version.get("VersionId"):
                        iam.delete_policy_version(
                            PolicyArn=policy_arn,
                            VersionId=version["VersionId"],
                        )
                iam.delete_policy(PolicyArn=policy_arn)
            except Exception as exc:
                if not AWSCloudBootstrapDriver._is_not_found(exc):
                    raise
        if user_name:
            AWSCloudBootstrapDriver._ignore_not_found(
                lambda: iam.delete_user(UserName=user_name)
            )

    @staticmethod
    def _validate_receipt_scope(
        receipt: CloudBootstrapRollbackReceipt,
        target: AWSBootstrapTarget,
    ) -> None:
        identifiers = dict(receipt.resource_ids)
        expected_user = f"{receipt.run_id}-deployer"
        expected_policy = (
            f"arn:aws:iam::{target.account_id}:policy/{receipt.run_id}-deployment"
        )
        if (
            identifiers.get("user_name") != expected_user
            or identifiers.get("policy_arn") not in {None, expected_policy}
            or ("access_key_id" in identifiers and "policy_arn" not in identifiers)
        ):
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_CLEANUP_FAILED",
                "The AWS rollback receipt does not match its setup-run scope.",
            )

    @staticmethod
    def _provisional_disposal(
        origin: CloudBootstrapCredentialOrigin,
        credential: AWSBootstrapCredential,
        target: AWSBootstrapTarget,
    ) -> tuple[CloudBootstrapDisposalStatus, datetime | None, bool]:
        if origin == CloudBootstrapCredentialOrigin.EXISTING_USER_OWNED:
            return (
                CloudBootstrapDisposalStatus.NOT_RETAINED_USER_MANAGED,
                None,
                False,
            )
        if credential.session_token is not None:
            if target.session_expires_at is None:
                raise AWSCloudBootstrapDriver._invalid_credential()
            return (
                CloudBootstrapDisposalStatus.EXPIRES_AT_PROVIDER,
                target.session_expires_at,
                False,
            )
        return (
            CloudBootstrapDisposalStatus.MANUAL_REVOCATION_REQUIRED,
            None,
            True,
        )

    @staticmethod
    def _caller(sts: AWSClient) -> dict[str, str]:
        caller = sts.get_caller_identity()
        return {
            "Account": AWSCloudBootstrapDriver._required_string(caller, "Account"),
            "Arn": AWSCloudBootstrapDriver._required_string(caller, "Arn"),
        }

    @staticmethod
    def _required_string(document: dict[str, Any], key: str) -> str:
        value = document.get(key)
        if not isinstance(value, str) or not value:
            raise CloudBootstrapAdapterError(
                "BOOTSTRAP_IDENTITY_CREATION_FAILED",
                "AWS returned an incomplete setup-only response.",
            )
        return value

    @staticmethod
    def _tags(run_id: str) -> list[dict[str, str]]:
        return [
            {"Key": OWNERSHIP_TAG_KEY, "Value": run_id},
            {"Key": MANAGED_BY_TAG_KEY, "Value": MANAGED_BY},
        ]

    @staticmethod
    def _tag_map(tags: Any) -> dict[str, str]:
        if not isinstance(tags, list):
            return {}
        return {
            str(item.get("Key")): str(item.get("Value"))
            for item in tags
            if isinstance(item, dict) and item.get("Key") is not None
        }

    @staticmethod
    def _policy_document(document: Any) -> dict[str, Any]:
        if isinstance(document, dict):
            return document
        if isinstance(document, str):
            parsed = json.loads(unquote(document))
            if isinstance(parsed, dict):
                return parsed
        raise CloudBootstrapAdapterError(
            "BOOTSTRAP_AUTHORITY_PACK_MISMATCH",
            "AWS returned an invalid managed-policy document.",
        )

    @staticmethod
    def _canonical(document: dict[str, Any]) -> str:
        return json.dumps(document, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _is_not_found(error: Exception) -> bool:
        response = getattr(error, "response", {})
        return response.get("Error", {}).get("Code") in {
            "NoSuchEntity",
            "NoSuchEntityException",
        }

    @staticmethod
    def _ignore_not_found(operation: Callable[[], Any]) -> None:
        try:
            operation()
        except Exception as exc:
            if not AWSCloudBootstrapDriver._is_not_found(exc):
                raise

    @staticmethod
    def _invalid_credential() -> CloudBootstrapAdapterError:
        return CloudBootstrapAdapterError(
            "BOOTSTRAP_CREDENTIAL_INVALID",
            "The AWS bootstrap credential does not match the selected account or supported credential shape.",
        )
