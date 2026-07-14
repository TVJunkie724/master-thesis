import json

import pytest

from backend.pricing_cache import (
    PricingRefreshInProgressError,
    provider_refresh_guard,
    write_json_atomically,
)


def test_provider_refresh_guard_rejects_duplicate_provider_refresh():
    with provider_refresh_guard("aws"):
        with pytest.raises(PricingRefreshInProgressError, match="already in progress"):
            with provider_refresh_guard("aws"):
                pass


def test_provider_refresh_guards_are_independent():
    with provider_refresh_guard("aws"):
        with provider_refresh_guard("gcp"):
            pass


def test_atomic_json_publication_replaces_complete_document(tmp_path):
    target = tmp_path / "pricing.json"
    target.write_text('{"old": true}\n', encoding="utf-8")

    write_json_atomically(target, {"provider": "aws", "price": 0.42})

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "provider": "aws",
        "price": 0.42,
    }
    assert list(tmp_path.glob("*.tmp")) == []
