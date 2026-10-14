"""Small L5 consumer of the existing authenticated L3 history contract.

No storage access, dashboard platform or client-side credentials. Two bounded
queries produce server-rendered SVG. Deployment readiness permits an explicit
empty state; the research probe still requires actual data by default.
"""
from datetime import datetime, timedelta, timezone
from html import escape
import math

HEADERS = {
    "Content-Type": "text/html; charset=utf-8",
    "Cache-Control": "no-store",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
}


def _time(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("VISUALIZATION_INVALID_DATA")
    return stamp.timestamp()


def _chart(payload, bucket, device, metric, *, allow_empty=False):
    if (payload.get("schema_version") != "raw-history-query.v1"
            or payload.get("device_id") != device or payload.get("metric") != metric
            or not isinstance(payload.get("truncated"), bool)
            or (payload["truncated"] and not isinstance(payload.get("next_cursor"), str))
            or (not payload["truncated"] and payload.get("next_cursor") is not None)
            or (not allow_empty and payload["truncated"])):
        raise ValueError("VISUALIZATION_INVALID_DATA")
    points = payload.get("points")
    if not isinstance(points, list) or not (0 if allow_empty else 1) <= len(points) <= 100:
        raise ValueError("VISUALIZATION_NO_BOUNDED_DATA")
    title = "Raw history" if bucket == 0 else "Hourly averages"
    if not points:
        if payload["truncated"]:
            raise ValueError("VISUALIZATION_INVALID_DATA")
        return (f'<section data-bucket-seconds="{bucket}" data-point-count="0" data-state="empty">'
                f'<h2>{title}</h2><p>No measurements available in this window.</p></section>')
    time_key, value_key = ("stored_at", "value") if bucket == 0 else ("bucket_start", "avg")
    data = []
    for item in points:
        value = item[value_key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("VISUALIZATION_INVALID_DATA")
        data.append((_time(item[time_key]), value, item[time_key]))
    data.sort()
    left, right = data[0][0], data[-1][0]
    low, high = min(x[1] for x in data), max(x[1] for x in data)
    dots = []
    coords = []
    for stamp, value, label in data:
        x = 50 + (stamp - left) / (right - left or 1) * 650
        y = 230 - (value - low) / (high - low or 1) * 180
        coords.append(f"{x:.3f},{y:.3f}")
        dots.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="5" data-time="{escape(label, quote=True)}" data-value="{value:g}"><title>{escape(label)}: {value:g}</title></circle>')
    note = '<p>Bounded view: additional records are not shown.</p>' if payload["truncated"] else ''
    return (f'<section data-bucket-seconds="{bucket}" data-point-count="{len(data)}" data-state="data"><h2>{title}</h2>{note}'
            f'<svg viewBox="0 0 740 280" role="img" aria-label="{title}"><path class="axis" d="M50 40 V230 H710"/>'
            f'<text x="5" y="50">{high:g}</text><text x="5" y="230">{low:g}</text>'
            f'<polyline points="{" ".join(coords)}"/>{"".join(dots)}'
            f'<text x="50" y="265">{escape(data[0][2])}</text></svg></section>')


def page(fetch, device, metric, now=None, *, allow_empty=False):
    """Fetch through L3 HTTP auth adapter, then render its real points."""
    now = now or datetime.now(timezone.utc)
    charts = []
    for bucket, age in ((0, timedelta(hours=24)), (3600, timedelta(days=30))):
        query = {"device_id": device, "metric": metric, "bucket_seconds": str(bucket),
                 "from": (now - age).isoformat().replace("+00:00", "Z"),
                 "to": now.isoformat().replace("+00:00", "Z"), "limit": "100"}
        charts.append(_chart(fetch(query), bucket, device, metric, allow_empty=allow_empty))
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>Twin2MultiCloud — L5 evidence</title><style>'
            'body{font:16px system-ui;background:#f5f7fa;color:#182538;margin:24px;max-width:900px}'
            'section{background:white;padding:16px;margin:16px 0;border:1px solid #ccd5df;border-radius:8px}'
            'svg{width:100%;height:auto}polyline{fill:none;stroke:#1769aa;stroke-width:3}'
            'circle{fill:#1769aa}.axis{fill:none;stroke:#9aa8b7}text{font-size:12px;fill:#455468}</style>'
            f'<h1>L5 · {escape(device)} · {escape(metric)}</h1><p>Authenticated L3 read · raw values and hourly averages</p>'
            + ''.join(charts) + '</html>')
