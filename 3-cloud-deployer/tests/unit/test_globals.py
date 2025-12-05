import globals

def test_config_loaded():
    assert globals.config["digital_twin_name"] == "test-twin"
    assert globals.config["mode"] == "DEBUG"

def test_credentials_loaded():
    assert globals.config_credentials_aws["aws_access_key_id"] == "testing"
