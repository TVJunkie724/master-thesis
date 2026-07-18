"""
Tests for file_manager CRUD operations.

Tests delete_project and update_project_info functions.
"""

import pytest
import os
import json
import io
from pathlib import Path
import zipfile

import file_manager
import constants as CONSTANTS
from tests.utils.deployment_specification import deployment_manifest


# ==========================================
# Test Fixtures
# ==========================================
@pytest.fixture
def temp_project_path(tmp_path):
    """Create a temporary project path for testing."""
    upload_dir = tmp_path / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
    upload_dir.mkdir()
    return str(tmp_path)


@pytest.fixture
def valid_zip_bytes():
    """Create a valid project zip file in memory with unique credentials."""
    import uuid

    unique_id = uuid.uuid4().hex[:4]

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        config = {
            "digital_twin_name": f"tt-{unique_id}",
            "hot_storage_size_in_days": 30,
            "cold_storage_size_in_days": 90,
            "mode": "DEBUG",
        }
        zf.writestr(CONSTANTS.CONFIG_FILE, json.dumps(config))
        zf.writestr(CONSTANTS.CONFIG_IOT_DEVICES_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_EVENTS_FILE, "[]")
        zf.writestr(CONSTANTS.CONFIG_HIERARCHY_FILE, "[]")
        zf.writestr(
            CONSTANTS.CONFIG_CREDENTIALS_FILE,
            json.dumps(
                {
                    "aws": {
                        "aws_access_key_id": f"AKIA{unique_id}",
                        "aws_secret_access_key": f"secret{unique_id}",
                        "aws_region": "us-east-1",
                    }
                }
            ),
        )
        zf.writestr(
            CONSTANTS.CONFIG_PROVIDERS_FILE,
            json.dumps(
                {
                    "layer_1_provider": "aws",
                    "layer_2_provider": "aws",
                    "layer_3_hot_provider": "aws",
                    "layer_4_provider": "aws",
                }
            ),
        )
        zf.writestr(CONSTANTS.CONFIG_OPTIMIZATION_FILE, json.dumps({"result": {}}))
        # Add required hierarchy file for layer_4_provider=aws
        zf.writestr("twin_hierarchy/aws_hierarchy.json", "[]")
        # Add function directory placeholder for layer_2_provider=aws
        zf.writestr("lambda_functions/placeholder.txt", "placeholder")
    bio.seek(0)
    return bio.getvalue()


def _valid_zip_with_manifest(resource_name: str) -> bytes:
    """Create a valid project ZIP with a DeploymentManifest contract."""
    import uuid

    unique_id = uuid.uuid4().hex[:4]
    files = {
        CONSTANTS.CONFIG_FILE: json.dumps(
            {
                "digital_twin_name": resource_name,
                "hot_storage_size_in_days": 30,
                "cold_storage_size_in_days": 90,
                "mode": "DEBUG",
            }
        ),
        CONSTANTS.CONFIG_IOT_DEVICES_FILE: "[]",
        CONSTANTS.CONFIG_EVENTS_FILE: "[]",
        CONSTANTS.CONFIG_HIERARCHY_FILE: "[]",
        CONSTANTS.CONFIG_CREDENTIALS_FILE: json.dumps(
            {
                "aws": {
                    "aws_access_key_id": f"AKIA{unique_id}",
                    "aws_secret_access_key": f"secret{unique_id}",
                    "aws_region": "us-east-1",
                }
            }
        ),
        CONSTANTS.CONFIG_PROVIDERS_FILE: json.dumps(
            {
                "layer_1_provider": "aws",
                "layer_2_provider": "aws",
                "layer_3_hot_provider": "aws",
                "layer_3_cold_provider": "aws",
                "layer_3_archive_provider": "aws",
                "layer_4_provider": "aws",
                "layer_5_provider": "aws",
            }
        ),
        CONSTANTS.CONFIG_OPTIMIZATION_FILE: json.dumps({"result": {}}),
        "config_user.json": json.dumps(
            {
                "admin_email": "admin@example.com",
                "admin_first_name": "Platform",
                "admin_last_name": "Admin",
            }
        ),
        "twin_hierarchy/aws_hierarchy.json": "[]",
        "lambda_functions/placeholder.txt": "placeholder",
    }
    manifest = deployment_manifest(
        package_files=sorted(files),
        resource_name=resource_name,
    )

    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        for path, content in files.items():
            zf.writestr(path, content)
        zf.writestr(CONSTANTS.DEPLOYMENT_MANIFEST_FILE, json.dumps(manifest))
    bio.seek(0)
    return bio.getvalue()


def _wrap_archive(content: bytes, *, extra_root_file: bool = False) -> bytes:
    source = io.BytesIO(content)
    target = io.BytesIO()
    with (
        zipfile.ZipFile(source, "r") as source_zip,
        zipfile.ZipFile(target, "w") as target_zip,
    ):
        for member in source_zip.infolist():
            target_zip.writestr(f"wrapped/{member.filename}", source_zip.read(member))
        if extra_root_file:
            target_zip.writestr("outside.txt", "ambiguous")
    return target.getvalue()


@pytest.fixture
def created_project(temp_project_path, valid_zip_bytes):
    """Create a project and return its name."""
    project_name = "test_crud_project"
    file_manager.create_project_from_zip(
        project_name,
        valid_zip_bytes,
        project_path=temp_project_path,
        description="Test project",
    )
    return project_name


# ==========================================
# Test: delete_project
# ==========================================
class TestDeleteProject:
    """Tests for the delete_project function."""

    def test_delete_removes_folder(self, temp_project_path, created_project):
        """Verify shutil.rmtree removes the project folder."""
        project_dir = os.path.join(
            temp_project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, created_project
        )
        assert os.path.exists(project_dir)

        file_manager.delete_project(created_project, project_path=temp_project_path)

        assert not os.path.exists(project_dir)

    def test_delete_nonexistent_project_raises(self, temp_project_path):
        """Verify ValueError for missing project."""
        with pytest.raises(ValueError, match="does not exist"):
            file_manager.delete_project(
                "nonexistent_project", project_path=temp_project_path
            )

    def test_delete_removes_all_contents(self, temp_project_path, created_project):
        """Verify all files and subdirectories are removed."""
        project_dir = os.path.join(
            temp_project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, created_project
        )

        # Add some additional files
        extra_dir = os.path.join(project_dir, "extra_subdir")
        os.makedirs(extra_dir)
        with open(os.path.join(extra_dir, "extra_file.txt"), "w") as f:
            f.write("extra content")

        file_manager.delete_project(created_project, project_path=temp_project_path)

        assert not os.path.exists(project_dir)

    def test_delete_with_versions(self, temp_project_path, created_project):
        """Verify deletion works when versions folder exists."""
        project_dir = os.path.join(
            temp_project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, created_project
        )
        versions_dir = os.path.join(project_dir, CONSTANTS.PROJECT_VERSIONS_DIR_NAME)

        # Versions should exist from creation
        assert os.path.exists(versions_dir)

        file_manager.delete_project(created_project, project_path=temp_project_path)

        assert not os.path.exists(project_dir)


class TestListProjects:
    """Tests for runtime project listing."""

    def test_list_projects_excludes_legacy_template_by_default(self, temp_project_path):
        upload_dir = os.path.join(temp_project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME)
        os.makedirs(os.path.join(upload_dir, CONSTANTS.DEFAULT_PROJECT_NAME))
        os.makedirs(os.path.join(upload_dir, "runtime-twin"))

        assert file_manager.list_projects(temp_project_path) == ["runtime-twin"]

    def test_list_projects_can_include_legacy_template_for_maintenance(
        self, temp_project_path
    ):
        upload_dir = os.path.join(temp_project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME)
        os.makedirs(os.path.join(upload_dir, CONSTANTS.DEFAULT_PROJECT_NAME))
        os.makedirs(os.path.join(upload_dir, "runtime-twin"))

        assert file_manager.list_projects(
            temp_project_path, include_templates=True
        ) == [
            "runtime-twin",
            CONSTANTS.DEFAULT_PROJECT_NAME,
        ]


class TestCreateProjectManifestContract:
    """Tests for DeploymentManifest-backed project creation."""

    def test_create_project_accepts_matching_manifest_resource_name(
        self, temp_project_path
    ):
        project_name = "mfst-ok"

        result = file_manager.create_project_from_zip(
            project_name,
            _valid_zip_with_manifest(project_name),
            project_path=temp_project_path,
        )

        assert result["message"] == f"Project '{project_name}' created."
        project_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            project_name,
        )
        assert os.path.exists(
            os.path.join(project_dir, CONSTANTS.DEPLOYMENT_MANIFEST_FILE)
        )

    def test_create_project_rejects_manifest_resource_name_mismatch(
        self, temp_project_path
    ):
        with pytest.raises(ValueError, match="resource_name does not match"):
            file_manager.create_project_from_zip(
                "requested",
                _valid_zip_with_manifest("manifest"),
                project_path=temp_project_path,
            )

        rejected_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            "requested",
        )
        assert not os.path.exists(rejected_dir)

    def test_update_project_rejects_manifest_resource_name_mismatch(
        self, temp_project_path
    ):
        existing_project = "requested"
        file_manager.create_project_from_zip(
            existing_project,
            _valid_zip_with_manifest(existing_project),
            project_path=temp_project_path,
        )

        with pytest.raises(ValueError, match="resource_name does not match"):
            file_manager.update_project_from_zip(
                existing_project,
                _valid_zip_with_manifest("manifest"),
                project_path=temp_project_path,
            )

        manifest_path = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            existing_project,
            CONSTANTS.DEPLOYMENT_MANIFEST_FILE,
        )
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        assert manifest["twin"]["resource_name"] == existing_project


class TestProjectArchiveTransactions:
    def test_create_never_persists_uploaded_credentials(
        self,
        temp_project_path,
        valid_zip_bytes,
    ):
        file_manager.create_project_from_zip(
            "private-credentials",
            valid_zip_bytes,
            project_path=temp_project_path,
        )

        credentials_path = (
            Path(temp_project_path)
            / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
            / "private-credentials"
            / CONSTANTS.CONFIG_CREDENTIALS_FILE
        )

        assert not credentials_path.exists()

    """Tests for atomic project creation and replacement."""

    def test_create_failure_leaves_no_partial_project(
        self,
        monkeypatch,
        temp_project_path,
        valid_zip_bytes,
    ):
        def fail_extraction(*_args, **_kwargs):
            raise OSError("simulated extraction failure")

        monkeypatch.setattr(file_manager.shutil, "copyfileobj", fail_extraction)

        with pytest.raises(OSError, match="simulated extraction failure"):
            file_manager.create_project_from_zip(
                "atomic-create",
                valid_zip_bytes,
                project_path=temp_project_path,
            )

        upload_root = Path(temp_project_path) / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
        assert not (upload_root / "atomic-create").exists()
        assert list(upload_root.glob(".atomic-create.staging-*")) == []

    def test_update_replaces_content_and_preserves_controlled_metadata(
        self,
        temp_project_path,
        valid_zip_bytes,
    ):
        project_name = "atomic-update"
        file_manager.create_project_from_zip(
            project_name,
            valid_zip_bytes,
            project_path=temp_project_path,
            description="Preserved description",
        )
        project_dir = (
            Path(temp_project_path) / CONSTANTS.PROJECT_UPLOAD_DIR_NAME / project_name
        )
        (project_dir / "stale.txt").write_text("stale", encoding="utf-8")
        (project_dir / ".build").mkdir()
        (project_dir / ".build" / "old.zip").write_bytes(b"stale")
        original_info = json.loads(
            (project_dir / CONSTANTS.PROJECT_INFO_FILE).read_text(encoding="utf-8")
        )

        file_manager.update_project_from_zip(
            project_name,
            valid_zip_bytes,
            project_path=temp_project_path,
        )

        updated_info = json.loads(
            (project_dir / CONSTANTS.PROJECT_INFO_FILE).read_text(encoding="utf-8")
        )
        versions = list(
            (project_dir / CONSTANTS.PROJECT_VERSIONS_DIR_NAME).glob("*.zip")
        )
        assert not (project_dir / "stale.txt").exists()
        assert not (project_dir / ".build").exists()
        assert len(versions) == 2
        assert updated_info["description"] == "Preserved description"
        assert updated_info["created_at"] == original_info["created_at"]
        assert "updated_at" in updated_info

    def test_update_removes_all_runtime_outputs_from_project_definition(
        self,
        temp_project_path,
        valid_zip_bytes,
    ):
        project_name = "runtime-preservation"
        file_manager.create_project_from_zip(
            project_name,
            valid_zip_bytes,
            project_path=temp_project_path,
        )
        project_dir = (
            Path(temp_project_path) / CONSTANTS.PROJECT_UPLOAD_DIR_NAME / project_name
        )
        (project_dir / "terraform").mkdir()
        (project_dir / "terraform" / "terraform.tfstate").write_text("state")
        (project_dir / "terraform" / "generated.tfvars.json").write_text("secret")
        (project_dir / "iot_devices_auth" / "device").mkdir(parents=True)
        (project_dir / "iot_devices_auth" / "device" / "key.pem").write_text("key")
        generated = (
            project_dir
            / "iot_device_simulator"
            / "aws"
            / "device"
            / "config_generated.json"
        )
        generated.parent.mkdir(parents=True)
        generated.write_text("generated")
        metadata = project_dir / ".build" / "metadata" / "functions.json"
        metadata.parent.mkdir(parents=True)
        metadata.write_text("{}")
        (project_dir / ".build" / "artifact.zip").write_text("discard")

        file_manager.update_project_from_zip(
            project_name,
            valid_zip_bytes,
            project_path=temp_project_path,
        )

        assert not (project_dir / "terraform" / "terraform.tfstate").exists()
        assert not (project_dir / "terraform" / "generated.tfvars.json").exists()
        assert not (project_dir / "iot_devices_auth").exists()
        assert not generated.exists()
        assert not metadata.exists()
        assert not (project_dir / ".build" / "artifact.zip").exists()

    def test_update_requires_existing_project(self, temp_project_path, valid_zip_bytes):
        with pytest.raises(ValueError, match="does not exist"):
            file_manager.update_project_from_zip(
                "missing",
                valid_zip_bytes,
                project_path=temp_project_path,
            )

    def test_update_publication_failure_restores_previous_project(
        self,
        monkeypatch,
        temp_project_path,
        valid_zip_bytes,
    ):
        project_name = "rollback-update"
        file_manager.create_project_from_zip(
            project_name,
            valid_zip_bytes,
            project_path=temp_project_path,
        )
        project_dir = (
            Path(temp_project_path) / CONSTANTS.PROJECT_UPLOAD_DIR_NAME / project_name
        )
        marker = project_dir / "original.txt"
        marker.write_text("keep", encoding="utf-8")
        original_replace = Path.replace

        def fail_staging_publish(path, target):
            if path.name.startswith(f".{project_name}.staging-"):
                raise OSError("simulated publication failure")
            return original_replace(path, target)

        monkeypatch.setattr(Path, "replace", fail_staging_publish)

        with pytest.raises(OSError, match="simulated publication failure"):
            file_manager.update_project_from_zip(
                project_name,
                valid_zip_bytes,
                project_path=temp_project_path,
            )

        assert marker.read_text(encoding="utf-8") == "keep"
        assert list(project_dir.parent.glob(f".{project_name}.backup-*")) == []

    def test_uploaded_runtime_state_is_discarded(
        self,
        temp_project_path,
        valid_zip_bytes,
    ):
        archive = io.BytesIO(valid_zip_bytes)
        with zipfile.ZipFile(archive, "a") as zf:
            zf.writestr(".build/metadata.json", "secret")
            zf.writestr("terraform/terraform.tfstate", "secret")
            zf.writestr("versions/injected.zip", "secret")
            zf.writestr(CONSTANTS.PROJECT_INFO_FILE, '{"description": "injected"}')

        file_manager.create_project_from_zip(
            "sanitized-project",
            archive.getvalue(),
            project_path=temp_project_path,
            description="trusted",
        )
        project_dir = (
            Path(temp_project_path)
            / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
            / "sanitized-project"
        )

        assert not (project_dir / ".build").exists()
        assert not (project_dir / "terraform").exists()
        assert len(list((project_dir / "versions").glob("*.zip"))) == 1
        info = json.loads(
            (project_dir / CONSTANTS.PROJECT_INFO_FILE).read_text(encoding="utf-8")
        )
        assert info["description"] == "trusted"

    def test_single_archive_wrapper_is_flattened(
        self,
        temp_project_path,
        valid_zip_bytes,
    ):
        file_manager.create_project_from_zip(
            "wrapped-project",
            _wrap_archive(valid_zip_bytes),
            project_path=temp_project_path,
        )
        project_dir = (
            Path(temp_project_path)
            / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
            / "wrapped-project"
        )

        assert (project_dir / CONSTANTS.CONFIG_FILE).is_file()
        assert not (project_dir / "wrapped").exists()

    def test_archive_wrapper_rejects_files_outside_project_root(
        self,
        temp_project_path,
        valid_zip_bytes,
    ):
        with pytest.raises(ValueError, match="outside the canonical project root"):
            file_manager.create_project_from_zip(
                "ambiguous-project",
                _wrap_archive(valid_zip_bytes, extra_root_file=True),
                project_path=temp_project_path,
            )

        project_dir = (
            Path(temp_project_path)
            / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
            / "ambiguous-project"
        )
        assert not project_dir.exists()


class TestProjectFileBrowser:
    """Tests for safe project file browsing."""

    def test_file_tree_uses_explicit_project_context_path(self, tmp_path):
        canonical_template = tmp_path / "templates" / "digital-twin"
        legacy_template = (
            tmp_path
            / CONSTANTS.PROJECT_UPLOAD_DIR_NAME
            / CONSTANTS.DEFAULT_PROJECT_NAME
        )
        canonical_template.mkdir(parents=True)
        legacy_template.mkdir(parents=True)
        (canonical_template / "config.json").write_text('{"source": "canonical"}')
        (legacy_template / "legacy-only.json").write_text('{"source": "legacy"}')

        tree = file_manager.get_project_file_tree(
            CONSTANTS.DEFAULT_PROJECT_NAME,
            project_context_path=canonical_template,
        )

        assert [item["name"] for item in tree] == ["config.json"]

    def test_file_tree_hides_sensitive_credential_files(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "config.json").write_text("{}")
        (project_dir / "config_credentials.json").write_text('{"aws": "secret"}')
        (project_dir / "config_credentials.json.example").write_text("{}")

        tree = file_manager.get_project_file_tree(
            "project",
            project_context_path=project_dir,
        )

        names = {item["name"] for item in tree}
        assert "config.json" in names
        assert "config_credentials.json.example" in names
        assert "config_credentials.json" not in names

    def test_file_content_blocks_sensitive_credential_files(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "config_credentials.json").write_text('{"aws": "secret"}')

        with pytest.raises(PermissionError):
            file_manager.get_project_file_content(
                "project",
                "config_credentials.json",
                project_context_path=project_dir,
            )

    def test_file_content_allows_example_credential_files(self, tmp_path):
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "config_credentials.json.example").write_text('{"aws": {}}')

        result = file_manager.get_project_file_content(
            "project",
            "config_credentials.json.example",
            project_context_path=project_dir,
        )

        assert result["raw"] == '{"aws": {}}'


# ==========================================
# Test: update_project_info
# ==========================================
class TestUpdateProjectInfo:
    """Tests for the update_project_info function."""

    def test_update_changes_description(self, temp_project_path, created_project):
        """Verify description is updated in project_info.json."""
        file_manager.update_project_info(
            created_project, "Updated description", project_path=temp_project_path
        )

        info_path = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            created_project,
            CONSTANTS.PROJECT_INFO_FILE,
        )

        with open(info_path, "r") as f:
            info = json.load(f)

        assert info["description"] == "Updated description"

    def test_update_adds_updated_at_timestamp(self, temp_project_path, created_project):
        """Verify updated_at timestamp is added."""
        file_manager.update_project_info(
            created_project, "New description", project_path=temp_project_path
        )

        info_path = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            created_project,
            CONSTANTS.PROJECT_INFO_FILE,
        )

        with open(info_path, "r") as f:
            info = json.load(f)

        assert "updated_at" in info

    def test_update_preserves_created_at(self, temp_project_path, created_project):
        """Verify created_at timestamp is preserved."""
        info_path = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            created_project,
            CONSTANTS.PROJECT_INFO_FILE,
        )

        # Get original created_at
        with open(info_path, "r") as f:
            original_info = json.load(f)
        original_created_at = original_info.get("created_at")

        file_manager.update_project_info(
            created_project, "New description", project_path=temp_project_path
        )

        with open(info_path, "r") as f:
            updated_info = json.load(f)

        assert updated_info.get("created_at") == original_created_at

    def test_update_nonexistent_project_raises(self, temp_project_path):
        """Verify ValueError for missing project."""
        with pytest.raises(ValueError, match="does not exist"):
            file_manager.update_project_info(
                "nonexistent_project", "description", project_path=temp_project_path
            )

    def test_update_creates_info_file_if_missing(
        self, temp_project_path, valid_zip_bytes
    ):
        """Verify info file is created if it doesn't exist."""
        project_name = "project_no_info"
        project_dir = os.path.join(
            temp_project_path, CONSTANTS.PROJECT_UPLOAD_DIR_NAME, project_name
        )
        os.makedirs(project_dir)

        # No project_info.json exists
        info_path = os.path.join(project_dir, CONSTANTS.PROJECT_INFO_FILE)
        assert not os.path.exists(info_path)

        file_manager.update_project_info(
            project_name, "New description", project_path=temp_project_path
        )

        assert os.path.exists(info_path)
        with open(info_path, "r") as f:
            info = json.load(f)
        assert info["description"] == "New description"


class TestProjectFileBrowserSecurity:
    """Tests for safe project file browser behavior."""

    def test_file_tree_excludes_runtime_credentials_but_keeps_examples(
        self,
        temp_project_path,
        created_project,
    ):
        """Runtime credentials must not be listed by the generic file API."""
        project_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            created_project,
        )
        with open(
            os.path.join(project_dir, "config_credentials.json.example"), "w"
        ) as f:
            f.write("{}")
        with open(os.path.join(project_dir, "config_credentials_aws.json"), "w") as f:
            f.write("{}")

        files = file_manager.get_project_file_tree(
            created_project,
            project_path=temp_project_path,
        )
        paths = {item["path"] for item in files if item["type"] == "file"}

        assert "config_credentials.json" not in paths
        assert "config_credentials_aws.json" not in paths
        assert "config_credentials.json.example" in paths

    def test_file_content_blocks_runtime_credentials(
        self,
        temp_project_path,
        created_project,
    ):
        """Credential files are protected even if callers know the exact path."""
        with pytest.raises(PermissionError, match="protected"):
            file_manager.get_project_file_content(
                created_project,
                "config_credentials.json",
                project_path=temp_project_path,
            )

    def test_file_content_allows_credential_example(
        self,
        temp_project_path,
        created_project,
    ):
        """Credential example files remain readable for documentation and UI help."""
        project_dir = os.path.join(
            temp_project_path,
            CONSTANTS.PROJECT_UPLOAD_DIR_NAME,
            created_project,
        )
        with open(
            os.path.join(project_dir, "config_credentials.json.example"), "w"
        ) as f:
            f.write('{"aws": {"aws_access_key_id": "example"}}')

        result = file_manager.get_project_file_content(
            created_project,
            "config_credentials.json.example",
            project_path=temp_project_path,
        )

        assert result["path"] == "config_credentials.json.example"
        assert result["content"]["aws"]["aws_access_key_id"] == "example"
