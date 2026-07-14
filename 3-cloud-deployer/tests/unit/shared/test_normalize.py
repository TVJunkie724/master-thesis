"""Unit tests for telemetry normalization across all providers."""
from datetime import datetime, timezone


def _is_iso8601_like(value: str) -> bool:
    """Copy of function for testing."""
    if len(value) < 10:
        return False
    return value[4:5] == "-" and value[7:8] == "-" and value[:4].isdigit()


def _convert_to_iso8601(value) -> str:
    """Copy of function for testing."""
    if isinstance(value, str) and _is_iso8601_like(value):
        if value.endswith("Z") or "+" in value or value.endswith("-00:00"):
            return value
        return value + "Z"
    
    try:
        epoch = float(value)
        if epoch > 1e12:
            epoch = epoch / 1000
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError, OSError):
        return str(value)


class TestIsIso8601Like:
    """Tests for _is_iso8601_like."""
    
    def test_valid_iso8601_with_time(self):
        assert _is_iso8601_like("2026-01-30T18:00:00Z") is True
    
    def test_valid_date_only(self):
        assert _is_iso8601_like("2026-01-30") is True
    
    def test_epoch_string_rejected(self):
        assert _is_iso8601_like("1738267800000") is False
    
    def test_random_string_rejected(self):
        assert _is_iso8601_like("not-a-timestamp") is False
    
    def test_short_string_rejected(self):
        assert _is_iso8601_like("2026") is False


class TestConvertToIso8601:
    """Tests for _convert_to_iso8601."""
    
    def test_epoch_milliseconds_int(self):
        result = _convert_to_iso8601(1738267800000)
        assert result == "2025-01-30T20:10:00Z"
    
    def test_epoch_milliseconds_string(self):
        result = _convert_to_iso8601("1738267800000")
        assert result == "2025-01-30T20:10:00Z"
    
    def test_epoch_seconds_int(self):
        result = _convert_to_iso8601(1738267800)
        assert result == "2025-01-30T20:10:00Z"
    
    def test_epoch_seconds_string(self):
        result = _convert_to_iso8601("1738267800")
        assert result == "2025-01-30T20:10:00Z"
    
    def test_already_iso8601_with_z(self):
        result = _convert_to_iso8601("2026-01-30T18:00:00Z")
        assert result == "2026-01-30T18:00:00Z"
    
    def test_already_iso8601_without_z(self):
        result = _convert_to_iso8601("2026-01-30T18:00:00")
        assert result == "2026-01-30T18:00:00Z"
    
    def test_iso8601_with_offset(self):
        result = _convert_to_iso8601("2026-01-30T18:00:00+02:00")
        assert result == "2026-01-30T18:00:00+02:00"
    
    def test_invalid_string_treated_as_epoch(self):
        # "not-a-timestamp" doesn't match ISO8601, so tries epoch conversion
        # float("not-a-timestamp") fails, returns as-is
        result = _convert_to_iso8601("not-a-timestamp")
        assert result == "not-a-timestamp"
