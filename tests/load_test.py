"""
tests/load_test.py

Standalone async load test for TrackSense API.
Requires: pip install httpx

Usage:
    python tests/load_test.py [BASE_URL] [CONCURRENCY] [REQUESTS_PER_WORKER]

Defaults:
    BASE_URL = http://localhost:8000
    CONCURRENCY = 20
    REQUESTS_PER_WORKER = 50

The script:
  1. Authenticates once to obtain a JWT.
  2. Fires concurrent requests against key read endpoints.
  3. Prints a summary: total, success, errors, p50/p95/p99 latencies.

This is a dev/QA harness — not a replacement for production load tooling
(k6, Locust, Gatling). Designed to be run standalone, not via pytest.
"""

import asyncio
import statistics
import sys
import time
from typing import Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx is required. Install it with: pip install httpx")
    sys.exit(1)

# ─── Config ──────────────────────────────────────────────────────────────────
BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
CONCURRENCY = int(sys.argv[2]) if len(sys.argv) > 2 else 20
REQUESTS_PER_WORKER = int(sys.argv[3]) if len(sys.argv) > 3 else 50
LOGIN_USERNAME = "admin"
LOGIN_PASSWORD = "tracksense"

# Endpoints to hit (unauthenticated and authenticated mixed)
ENDPOINTS = [
    "/health",
    "/race/status",
    "/race/state",
]
AUTH_ENDPOINTS = [
    "/horses",
    "/admin/users",
    "/webhooks",
]


# ─── Auth ─────────────────────────────────────────────────────────────────────

async def get_token(client: httpx.AsyncClient) -> Optional[str]:
    try:
        r = await client.post(
            f"{BASE_URL}/auth/login",
            json={"username": LOGIN_USERNAME, "password": LOGIN_PASSWORD},
            timeout=10.0,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
    except Exception as e:
        print(f"[auth] Login failed: {e}")
    return None


# ─── Worker ───────────────────────────────────────────────────────────────────

async def worker(
    worker_id: int,
    client: httpx.AsyncClient,
    token: Optional[str],
    results: list,
    n_requests: int,
):
    all_endpoints = ENDPOINTS[:]
    if token:
        all_endpoints.extend(AUTH_ENDPOINTS)

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    for i in range(n_requests):
        endpoint = all_endpoints[i % len(all_endpoints)]
        url = f"{BASE_URL}{endpoint}"
        start = time.perf_counter()
        status = None
        error = None
        try:
            r = await client.get(url, headers=headers, timeout=10.0)
            status = r.status_code
        except Exception as e:
            error = str(e)
        elapsed_ms = (time.perf_counter() - start) * 1000
        results.append({
            "worker": worker_id,
            "endpoint": endpoint,
            "status": status,
            "error": error,
            "elapsed_ms": elapsed_ms,
        })


# ─── Main ─────────────────────────────────────────────────────────────────────

async def run():
    print(f"\nTrackSense Load Test")
    print(f"  Base URL     : {BASE_URL}")
    print(f"  Concurrency  : {CONCURRENCY}")
    print(f"  Req/worker   : {REQUESTS_PER_WORKER}")
    print(f"  Total target : {CONCURRENCY * REQUESTS_PER_WORKER} requests\n")

    async with httpx.AsyncClient() as client:
        print("[1/3] Authenticating...")
        token = await get_token(client)
        if token:
            print("      JWT obtained successfully")
        else:
            print("      No JWT — running unauthenticated (auth endpoints will be skipped)")

        print("[2/3] Firing requests...")
        results: list = []
        t0 = time.perf_counter()
        tasks = [
            worker(wid, client, token, results, REQUESTS_PER_WORKER)
            for wid in range(CONCURRENCY)
        ]
        await asyncio.gather(*tasks)
        total_elapsed = time.perf_counter() - t0

    print(f"[3/3] Results ({len(results)} requests in {total_elapsed:.2f}s)\n")

    total = len(results)
    successes = sum(1 for r in results if r["status"] and 200 <= r["status"] < 300)
    errors = sum(1 for r in results if r["error"] or (r["status"] and r["status"] >= 400))
    latencies = sorted(r["elapsed_ms"] for r in results)

    def pct(p):
        if not latencies:
            return 0.0
        idx = int(len(latencies) * p / 100)
        return latencies[min(idx, len(latencies) - 1)]

    print(f"  Total requests   : {total}")
    print(f"  Successes (2xx)  : {successes}")
    print(f"  Errors (4xx/5xx) : {errors}")
    print(f"  Throughput       : {total / total_elapsed:.1f} req/s")
    print(f"  Latency p50      : {pct(50):.1f} ms")
    print(f"  Latency p95      : {pct(95):.1f} ms")
    print(f"  Latency p99      : {pct(99):.1f} ms")
    print(f"  Latency mean     : {statistics.mean(latencies):.1f} ms")
    print(f"  Latency max      : {max(latencies):.1f} ms\n")

    # Per-endpoint breakdown
    endpoint_groups: dict[str, list] = {}
    for r in results:
        endpoint_groups.setdefault(r["endpoint"], []).append(r["elapsed_ms"])

    print("  Per-endpoint (p50 / p99):")
    for ep, lats in sorted(endpoint_groups.items()):
        lats.sort()
        p50 = lats[int(len(lats) * 0.50)]
        p99 = lats[min(int(len(lats) * 0.99), len(lats) - 1)]
        print(f"    {ep:<35} p50={p50:.0f}ms  p99={p99:.0f}ms  n={len(lats)}")

    if errors > total * 0.05:
        print(f"\nWARNING: Error rate {errors/total*100:.1f}% exceeds 5% threshold")
        sys.exit(1)
    else:
        print(f"\nPASS: Error rate {errors/total*100:.1f}% is within acceptable limits")


if __name__ == "__main__":
    asyncio.run(run())
