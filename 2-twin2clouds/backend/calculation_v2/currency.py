"""Result-currency conversion for cost optimization output."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any

import backend.constants as CONSTANTS
from backend.config_loader import load_json_file


SUPPORTED_RESULT_CURRENCIES = frozenset({"USD", "EUR"})


def apply_result_currency(
    result: dict[str, Any],
    requested_currency: str,
    *,
    rates_path: Path = CONSTANTS.CURRENCY_CONVERSION_FILE_PATH,
) -> dict[str, Any]:
    """Convert all result cost fields from the canonical USD calculation currency."""

    target_currency = str(requested_currency or "USD").upper()
    if target_currency not in SUPPORTED_RESULT_CURRENCIES:
        raise ValueError(
            f"Unsupported result currency: {requested_currency}. Use USD or EUR."
        )

    rate = 1.0
    rate_source = "identity"
    rate_updated_at = None
    if target_currency == "EUR":
        payload = load_json_file(rates_path)
        rate = _positive_rate(payload.get("usd_to_eur_rate"))
        rate_source = "cached_exchange_rate"
        rate_updated_at = payload.get("retrieved_at") or datetime.fromtimestamp(
            Path(rates_path).stat().st_mtime,
            tz=timezone.utc,
        ).isoformat()

    if target_currency == "EUR":
        _convert_provider_costs(result, rate)
        _convert_complete_path_costs(result, rate)
        _convert_trace_costs(result, rate, target_currency)
        result["totalCost"] = round(_money(result.get("totalCost"), rate), 2)

    result["currency"] = target_currency
    result["currencyConversion"] = {
        "schema_version": "currency-conversion.v1",
        "source_currency": "USD",
        "target_currency": target_currency,
        "rate": rate,
        "rate_source": rate_source,
        "rate_updated_at": rate_updated_at,
    }
    return result


def _positive_rate(value: Any) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError("Cached USD/EUR exchange rate is missing or invalid")
    rate = float(value)
    if not isfinite(rate) or rate <= 0:
        raise ValueError("Cached USD/EUR exchange rate must be finite and positive")
    return rate


def _convert_provider_costs(result: dict[str, Any], rate: float) -> None:
    for provider_key in ("awsCosts", "azureCosts", "gcpCosts"):
        for layer in (result.get(provider_key) or {}).values():
            if not isinstance(layer, dict):
                continue
            if isinstance(layer.get("cost"), (int, float)):
                layer["cost"] = _money(layer["cost"], rate)
            components = layer.get("components") or {}
            for component, value in components.items():
                if isinstance(value, (int, float)):
                    components[component] = _money(value, rate)
            _convert_calculation_details(layer.get("details"), rate)

    for segment, value in (result.get("transferCosts") or {}).items():
        if isinstance(value, (int, float)):
            result["transferCosts"][segment] = _money(value, rate)


def _convert_calculation_details(details: Any, rate: float) -> None:
    if not isinstance(details, dict):
        return
    calculation = details.get("calculation")
    if not isinstance(calculation, dict) or calculation.get("currency") != "USD":
        return
    for dimension in calculation.get("dimensions") or []:
        if not isinstance(dimension, dict):
            continue
        _convert_key(dimension, "unitPrice", rate)
        _convert_key(dimension, "contribution", rate)
    calculation["sourceCurrency"] = "USD"
    calculation["currency"] = "EUR"


def _convert_complete_path_costs(result: dict[str, Any], rate: float) -> None:
    transfer_context = result.get("transferPricingContext") or {}
    transfer_context["currency"] = "EUR"
    for route in transfer_context.get("routes") or []:
        for key in ("egressCost", "glueCost", "totalCost"):
            _convert_key(route, key, rate)
        for contribution in route.get("tierContributions") or []:
            _convert_key(contribution, "unitPrice", rate)
            _convert_key(contribution, "cost", rate)
    for pool in transfer_context.get("pools") or []:
        _convert_key(pool, "aggregateEgressCost", rate)

    diagnostics = result.get("optimizationDiagnostics") or {}
    for key in (
        "winningScore",
        "winningLayerCost",
        "winningTransferCost",
    ):
        _convert_key(diagnostics, key, rate)
    diagnostics["scoreUnit"] = "EUR/month"


def _convert_trace_costs(
    result: dict[str, Any], rate: float, target_currency: str
) -> None:
    intent_trace = result.get("intentTrace") or {}
    for entry in intent_trace.get("selected_path") or []:
        _convert_key(entry, "cost", rate)
    for entry in intent_trace.get("transfer_trace") or []:
        _convert_key(entry, "cost", rate)
    for record in intent_trace.get("records") or []:
        contribution = record.get("contribution") or {}
        _convert_key(contribution, "cost", rate)
        for segment in contribution.get("transfer_segments") or []:
            _convert_key(segment, "cost", rate)

    for entry in result.get("resultTrace") or []:
        _convert_key(entry, "cost_contribution", rate)
        entry["source_currency"] = entry.get("currency") or "USD"
        entry["currency"] = target_currency


def _convert_key(payload: dict[str, Any], key: str, rate: float) -> None:
    if isinstance(payload.get(key), (int, float)):
        payload[key] = _money(payload[key], rate)


def _money(value: Any, rate: float) -> float:
    return round(float(value) * rate, 12)
