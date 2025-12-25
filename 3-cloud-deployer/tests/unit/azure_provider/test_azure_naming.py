"""
Unit tests for Azure naming conventions.

Tests the AzureNaming class to ensure all resource names follow
Azure naming rules and restrictions.
"""

import pytest
from src.providers.azure.naming import AzureNaming


class TestAzureNaming:
    """Tests for AzureNaming class."""
    
    def test_twin_name_property(self):
        """twin_name property should return the initialized name."""
        naming = AzureNaming("my-digital-twin")
        assert naming.twin_name == "my-digital-twin"
    
    def test_resource_group_name_format(self):
        """resource_group() should return {twin_name}-rg format."""
        naming = AzureNaming("test-twin")
        assert naming.resource_group() == "test-twin-rg"
    
    def test_managed_identity_name_format(self):
        """managed_identity() should return {twin_name}-identity format."""
        naming = AzureNaming("test-twin")
        assert naming.managed_identity() == "test-twin-identity"
    
    def test_storage_account_name_no_hyphens(self):
        """storage_account() should remove hyphens (Azure restriction)."""
        naming = AzureNaming("test-twin-name")
        storage_name = naming.storage_account()
        assert "-" not in storage_name
        assert storage_name == "testtwinnamestorage"
    
    def test_storage_account_name_max_24_chars(self):
        """storage_account() should truncate to 24 chars max."""
        naming = AzureNaming("very-long-digital-twin-name-that-exceeds")
        storage_name = naming.storage_account()
        assert len(storage_name) <= 24
    
    def test_storage_account_name_lowercase(self):
        """storage_account() should be lowercase."""
        naming = AzureNaming("Test-Twin")
        storage_name = naming.storage_account()
        assert storage_name == storage_name.lower()
    
    def test_glue_function_app_name_format(self):
        """glue_function_app() should return {twin_name}-l0-functions."""
        naming = AzureNaming("test-twin")
        assert naming.glue_function_app() == "test-twin-l0-functions"
    
    def test_cosmos_account_name_format(self):
        """cosmos_account() should return {twin_name}-cosmos."""
        naming = AzureNaming("test-twin")
        assert naming.cosmos_account() == "test-twin-cosmos"
    
    def test_iot_hub_name_format(self):
        """iot_hub() should return {twin_name}-iothub."""
        naming = AzureNaming("test-twin")
        assert naming.iot_hub() == "test-twin-iothub"


class TestAzureNamingFunctions:
    """Tests for L0 function naming."""
    
    def test_ingestion_function_name(self):
        """ingestion_function() should return 'ingestion'."""
        naming = AzureNaming("test-twin")
        assert naming.ingestion_function() == "ingestion"
    
    def test_hot_writer_function_name(self):
        """hot_writer_function() should return 'hot-writer'."""
        naming = AzureNaming("test-twin")
        assert naming.hot_writer_function() == "hot-writer"
    
    def test_cold_writer_function_name(self):
        """cold_writer_function() should return 'cold-writer'."""
        naming = AzureNaming("test-twin")
        assert naming.cold_writer_function() == "cold-writer"
    
    def test_archive_writer_function_name(self):
        """archive_writer_function() should return 'archive-writer'."""
        naming = AzureNaming("test-twin")
        assert naming.archive_writer_function() == "archive-writer"
    
    def test_hot_reader_function_name(self):
        """hot_reader_function() should return 'hot-reader'."""
        naming = AzureNaming("test-twin")
        assert naming.hot_reader_function() == "hot-reader"
    
    def test_hot_reader_last_entry_function_name(self):
        """hot_reader_last_entry_function() should return 'hot-reader-last-entry'."""
        naming = AzureNaming("test-twin")
        assert naming.hot_reader_last_entry_function() == "hot-reader-last-entry"


class TestAzureNamingLayers:
    """Tests for layer-specific naming."""
    
    def test_l1_function_app_name(self):
        """l1_function_app() should return {twin_name}-l1-functions."""
        naming = AzureNaming("test-twin")
        assert naming.l1_function_app() == "test-twin-l1-functions"
    
    def test_l1_app_service_plan_name(self):
        """l1_app_service_plan() should return {twin_name}-l1-plan."""
        naming = AzureNaming("test-twin")
        assert naming.l1_app_service_plan() == "test-twin-l1-plan"
    
    def test_event_grid_subscription_name(self):
        """event_grid_subscription() should return {twin_name}-dispatcher-sub."""
        naming = AzureNaming("test-twin")
        assert naming.event_grid_subscription() == "test-twin-dispatcher-sub"
    
    def test_dispatcher_function_name(self):
        """dispatcher_function() should return 'dispatcher'."""
        naming = AzureNaming("test-twin")
        assert naming.dispatcher_function() == "dispatcher"
    
    def test_l2_function_app_name(self):
        """l2_function_app() should return {twin_name}-l2-functions."""
        naming = AzureNaming("test-twin")
        assert naming.l2_function_app() == "test-twin-l2-functions"
    
    def test_l3_function_app_name(self):
        """l3_function_app() should return {twin_name}-l3-functions."""
        naming = AzureNaming("test-twin")
        assert naming.l3_function_app() == "test-twin-l3-functions"
    
    def test_cosmos_database_name(self):
        """cosmos_database() should return 'iot-data'."""
        naming = AzureNaming("test-twin")
        assert naming.cosmos_database() == "iot-data"
    
    def test_hot_cosmos_container_name(self):
        """hot_cosmos_container() should return 'hot-data'."""
        naming = AzureNaming("test-twin")
        assert naming.hot_cosmos_container() == "hot-data"
    
    def test_cold_blob_container_name(self):
        """cold_blob_container() should return 'cold-data'."""
        naming = AzureNaming("test-twin")
        assert naming.cold_blob_container() == "cold-data"
    
    def test_archive_blob_container_name(self):
        """archive_blob_container() should return 'archive-data'."""
        naming = AzureNaming("test-twin")
        assert naming.archive_blob_container() == "archive-data"


class TestAzureNamingDevices:
    """Tests for device-specific naming."""
    
    def test_processor_function_name_with_device(self):
        """processor_function() should include device_id."""
        naming = AzureNaming("test-twin")
        assert naming.processor_function("sensor-001") == "sensor-001-processor"
    
    def test_connector_function_name_with_device(self):
        """connector_function() should include device_id."""
        naming = AzureNaming("test-twin")
        assert naming.connector_function("sensor-001") == "sensor-001-connector"
    
    def test_iot_device_name(self):
        """iot_device() should return {twin_name}-{device_id}."""
        naming = AzureNaming("test-twin")
        assert naming.iot_device("sensor-001") == "test-twin-sensor-001"
