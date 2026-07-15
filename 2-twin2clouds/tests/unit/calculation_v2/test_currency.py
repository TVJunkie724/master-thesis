import json

import pytest

from backend.calculation_v2.currency import apply_result_currency


def _result_payload() -> dict:
    return {
        "awsCosts": {"L1": {"cost": 10.0, "components": {"iot": 4.0}}},
        "azureCosts": {"L1": {"cost": 8.0, "components": {"iot": 3.0}}},
        "gcpCosts": {"L1": {"cost": 9.0, "components": {"iot": 2.0}}},
        "transferCosts": {"L1_to_L2": 2.0},
        "totalCost": 10.0,
        "intentTrace": {
            "selected_path": [{"cost": 8.0}],
            "transfer_trace": [{"cost": 2.0}],
            "records": [
                {
                    "contribution": {
                        "cost": 8.0,
                        "transfer_segments": [{"cost": 2.0}],
                    }
                }
            ],
        },
        "resultTrace": [{"cost_contribution": 8.0, "currency": "USD"}],
    }


def test_eur_conversion_updates_costs_and_trace_metadata(tmp_path):
    rates = tmp_path / "currency.json"
    rates.write_text(
        json.dumps({"usd_to_eur_rate": 0.8, "retrieved_at": "2026-07-14T00:00:00Z"}),
        encoding="utf-8",
    )

    result = apply_result_currency(_result_payload(), "EUR", rates_path=rates)

    assert result["currency"] == "EUR"
    assert result["totalCost"] == 8.0
    assert result["awsCosts"]["L1"]["cost"] == 8.0
    assert result["awsCosts"]["L1"]["components"]["iot"] == 3.2
    assert result["transferCosts"]["L1_to_L2"] == 1.6
    assert result["intentTrace"]["records"][0]["contribution"]["cost"] == 6.4
    assert result["resultTrace"][0]["cost_contribution"] == 6.4
    assert result["resultTrace"][0]["source_currency"] == "USD"
    assert result["resultTrace"][0]["currency"] == "EUR"
    assert result["currencyConversion"] == {
        "schema_version": "currency-conversion.v1",
        "source_currency": "USD",
        "target_currency": "EUR",
        "rate": 0.8,
        "rate_source": "cached_exchange_rate",
        "rate_updated_at": "2026-07-14T00:00:00Z",
    }


def test_usd_result_has_explicit_identity_conversion():
    result = apply_result_currency(_result_payload(), "USD")

    assert result["totalCost"] == 10.0
    assert result["currency"] == "USD"
    assert result["currencyConversion"]["rate"] == 1.0
    assert result["currencyConversion"]["rate_source"] == "identity"


def test_eur_identity_rate_still_updates_trace_currency(tmp_path):
    rates = tmp_path / "currency.json"
    rates.write_text(json.dumps({"usd_to_eur_rate": 1.0}), encoding="utf-8")

    result = apply_result_currency(_result_payload(), "EUR", rates_path=rates)

    assert result["currency"] == "EUR"
    assert result["resultTrace"][0]["source_currency"] == "USD"
    assert result["resultTrace"][0]["currency"] == "EUR"


@pytest.mark.parametrize("rate", [None, 0, -1, float("inf"), "0.8"])
def test_eur_conversion_rejects_invalid_cached_rates(tmp_path, rate):
    rates = tmp_path / "currency.json"
    rates.write_text(json.dumps({"usd_to_eur_rate": rate}), encoding="utf-8")

    with pytest.raises(ValueError, match="rate"):
        apply_result_currency(_result_payload(), "EUR", rates_path=rates)


def test_result_currency_rejects_unknown_currency():
    with pytest.raises(ValueError, match="Unsupported result currency"):
        apply_result_currency(_result_payload(), "GBP")
