"""
Prometheus metrics for JobFlow.
Tracks HTTP requests, active users, logins, registrations, and site visitors.
"""

import time
from collections import defaultdict
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# --- Counters ---
HTTP_REQUESTS_TOTAL = Counter(
    "jobflow_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

USER_LOGINS_TOTAL = Counter(
    "jobflow_user_logins_total",
    "Total successful user logins",
)

USER_REGISTRATIONS_TOTAL = Counter(
    "jobflow_user_registrations_total",
    "Total user registrations",
)

SITE_VISITS_TOTAL = Counter(
    "jobflow_site_visits_total",
    "Total site visits (all requests from unique IPs per day)",
)

# --- Histograms ---
HTTP_REQUEST_DURATION = Histogram(
    "jobflow_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# --- Gauges (set periodically via /metrics endpoint) ---
TOTAL_USERS = Gauge(
    "jobflow_total_users",
    "Total registered users",
)

TOTAL_JOBS = Gauge(
    "jobflow_total_jobs",
    "Total jobs in database",
)

TOTAL_APPLICATIONS = Gauge(
    "jobflow_total_applications",
    "Total applications tracked",
)

DAILY_ACTIVE_USERS = Gauge(
    "jobflow_daily_active_users",
    "Users who logged in today",
)

UNIQUE_VISITORS_TODAY = Gauge(
    "jobflow_unique_visitors_today",
    "Unique IP addresses seen today",
)

# --- In-memory trackers ---
# Track unique IPs per day and active user IDs per day
_daily_ips: set[str] = set()
_daily_active_user_ids: set[int] = set()
_current_day: str = ""


def _get_today() -> str:
    return time.strftime("%Y-%m-%d")


def _reset_if_new_day():
    global _current_day, _daily_ips, _daily_active_user_ids
    today = _get_today()
    if today != _current_day:
        _daily_ips = set()
        _daily_active_user_ids = set()
        _current_day = today


def track_visitor(ip: str):
    """Track a unique visitor IP."""
    _reset_if_new_day()
    if ip not in _daily_ips:
        _daily_ips.add(ip)
        SITE_VISITS_TOTAL.inc()
    UNIQUE_VISITORS_TODAY.set(len(_daily_ips))


def track_active_user(user_id: int):
    """Track an active authenticated user."""
    _reset_if_new_day()
    _daily_active_user_ids.add(user_id)
    DAILY_ACTIVE_USERS.set(len(_daily_active_user_ids))


def _normalize_path(path: str) -> str:
    """Collapse path IDs to prevent cardinality explosion.
    /api/jobs/123 -> /api/jobs/{id}
    """
    parts = path.rstrip("/").split("/")
    normalized = []
    for part in parts:
        if part.isdigit():
            normalized.append("{id}")
        else:
            normalized.append(part)
    return "/".join(normalized) or "/"


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP metrics for every request."""

    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        path = _normalize_path(request.url.path)

        # Track visitor by IP
        client_ip = request.headers.get("x-real-ip") or (
            request.client.host if request.client else "unknown"
        )
        track_visitor(client_ip)

        # Time the request
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status="500").inc()
            HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(
                time.perf_counter() - start
            )
            raise

        duration = time.perf_counter() - start
        status = str(response.status_code)

        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(duration)

        return response


async def metrics_endpoint(request: Request) -> Response:
    """Expose Prometheus metrics at /metrics."""
    # Update gauge values from database counts
    await _refresh_db_gauges()
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


async def _refresh_db_gauges():
    """Query database for current totals and update gauges."""
    try:
        from app.database import async_session
        from sqlalchemy import text

        async with async_session() as db:
            result = await db.execute(text("SELECT COUNT(*) FROM users"))
            TOTAL_USERS.set(result.scalar() or 0)

            result = await db.execute(text("SELECT COUNT(*) FROM jobs"))
            TOTAL_JOBS.set(result.scalar() or 0)

            result = await db.execute(text("SELECT COUNT(*) FROM applications"))
            TOTAL_APPLICATIONS.set(result.scalar() or 0)
    except Exception:
        pass  # Don't break metrics if DB is unavailable
