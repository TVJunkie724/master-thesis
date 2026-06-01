import sqlite3

from migrations.disable_legacy_twin_credentials import migrate


def test_disable_legacy_twin_credentials_migration_is_idempotent(tmp_path, monkeypatch):
    db_path = tmp_path / "management.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE twin_configurations (
            id VARCHAR PRIMARY KEY,
            aws_cloud_connection_id VARCHAR,
            azure_cloud_connection_id VARCHAR,
            gcp_cloud_connection_id VARCHAR,
            aws_access_key_id VARCHAR,
            aws_secret_access_key VARCHAR,
            aws_session_token VARCHAR,
            aws_sso_region VARCHAR,
            aws_region VARCHAR,
            aws_validated BOOLEAN,
            azure_subscription_id VARCHAR,
            azure_client_id VARCHAR,
            azure_client_secret VARCHAR,
            azure_tenant_id VARCHAR,
            azure_region VARCHAR,
            azure_validated BOOLEAN,
            gcp_project_id VARCHAR,
            gcp_billing_account VARCHAR,
            gcp_region VARCHAR,
            gcp_service_account_json TEXT,
            gcp_validated BOOLEAN
        )
        """
    )
    conn.execute(
        """
        INSERT INTO twin_configurations (
            id,
            aws_cloud_connection_id,
            gcp_cloud_connection_id,
            aws_access_key_id,
            aws_secret_access_key,
            aws_session_token,
            aws_sso_region,
            aws_region,
            aws_validated,
            azure_subscription_id,
            azure_client_id,
            azure_client_secret,
            azure_tenant_id,
            azure_region,
            azure_validated,
            gcp_project_id,
            gcp_billing_account,
            gcp_region,
            gcp_service_account_json,
            gcp_validated
        )
        VALUES (
            'config-1',
            'connection-aws',
            NULL,
            'encrypted-aws-key',
            'encrypted-aws-secret',
            'encrypted-session',
            'eu-central-1',
            'eu-central-1',
            1,
            'encrypted-subscription',
            'encrypted-client',
            'encrypted-client-secret',
            'encrypted-tenant',
            'westeurope',
            1,
            'public-gcp-project',
            'encrypted-billing',
            'europe-west1',
            'encrypted-service-account',
            1
        )
        """
    )
    conn.commit()
    conn.close()

    migrate()
    migrate()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM twin_configurations WHERE id = 'config-1'").fetchone()
    conn.close()

    assert row["aws_cloud_connection_id"] == "connection-aws"
    assert row["aws_region"] == "eu-central-1"
    assert row["aws_validated"] == 1
    assert row["gcp_project_id"] == "public-gcp-project"
    assert row["gcp_region"] == "europe-west1"
    assert row["gcp_validated"] == 0

    for field in (
        "aws_access_key_id",
        "aws_secret_access_key",
        "aws_session_token",
        "aws_sso_region",
        "azure_subscription_id",
        "azure_client_id",
        "azure_client_secret",
        "azure_tenant_id",
        "gcp_billing_account",
        "gcp_service_account_json",
    ):
        assert row[field] is None
