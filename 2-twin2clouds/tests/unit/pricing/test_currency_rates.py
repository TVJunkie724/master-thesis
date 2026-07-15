from unittest.mock import MagicMock, patch

import pytest

from backend import pricing_utils


def test_currency_rate_refresh_uses_one_authoritative_response():
    response = MagicMock()
    response.json.return_value = {
        "result": "success",
        "rates": {"EUR": 0.8},
    }

    with (
        patch("backend.pricing_utils.utils.is_file_fresh", return_value=False),
        patch("backend.pricing_utils.requests.get", return_value=response) as get,
        patch("backend.pricing_utils.write_json_atomically") as write,
    ):
        rates = pricing_utils.get_currency_rates()

    response.raise_for_status.assert_called_once_with()
    get.assert_called_once_with(
        "https://open.er-api.com/v6/latest/USD",
        timeout=5,
    )
    assert rates["usd_to_eur_rate"] == 0.8
    assert rates["eur_to_usd_rate"] == 1.25
    assert rates["source"] == "open.er-api.com/v6/latest/USD"
    write.assert_called_once()


def test_currency_rate_refresh_uses_valid_stale_snapshot_on_network_failure():
    cached = {"usd_to_eur_rate": 0.8, "eur_to_usd_rate": 1.25}

    with (
        patch("backend.pricing_utils.utils.is_file_fresh", return_value=False),
        patch("backend.pricing_utils.requests.get", side_effect=TimeoutError),
        patch("backend.pricing_utils.utils.file_exists", return_value=True),
        patch("backend.pricing_utils.config_loader.load_json_file", return_value=cached),
    ):
        assert pricing_utils.get_currency_rates() == cached


@pytest.mark.parametrize(
    "cached",
    [
        {},
        {"usd_to_eur_rate": 0, "eur_to_usd_rate": 1.25},
        {"usd_to_eur_rate": 0.8, "eur_to_usd_rate": float("inf")},
    ],
)
def test_currency_rate_refresh_rejects_invalid_stale_snapshot(cached):
    with (
        patch("backend.pricing_utils.utils.is_file_fresh", return_value=False),
        patch("backend.pricing_utils.requests.get", side_effect=TimeoutError),
        patch("backend.pricing_utils.utils.file_exists", return_value=True),
        patch("backend.pricing_utils.config_loader.load_json_file", return_value=cached),
    ):
        with pytest.raises(RuntimeError, match="No valid currency-rate snapshot"):
            pricing_utils.get_currency_rates()
