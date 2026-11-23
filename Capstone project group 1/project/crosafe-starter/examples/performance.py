"""Measure read-only CroSafe endpoint latency against a running test stack."""
import argparse
import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from statistics import median
from time import perf_counter
from urllib.error import URLError
from urllib.request import Request, urlopen

ROUTES = ("/health", "/v1/admin/analysis", "/v1/admin/plantings.geojson", "/v1/notifications")


def measure(url: str, header: str) -> tuple[float, bool]:
    started = perf_counter()
    try:
        with urlopen(Request(url, headers={"Authorization": header}), timeout=20) as result:
            result.read()
            return (perf_counter() - started) * 1000, 200 <= result.status < 300
    except (URLError, TimeoutError):
        return (perf_counter() - started) * 1000, False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    args = parser.parse_args()
    if min(args.requests, args.concurrency) < 1:
        parser.error("requests and concurrency must be positive")
    user = os.getenv("CROSAFE_ADMIN_USER", "admin")
    key = os.environ["CROSAFE_ADMIN_PASSWORD"]
    header = "Basic " + base64.b64encode(f"{user}:{key}".encode()).decode()
    report = {}
    with ThreadPoolExecutor(max_workers=args.concurrency) as workers:
        for path in ROUTES:
            url = args.base_url.rstrip("/") + path
            attempts = list(workers.map(lambda _: measure(url, header), range(args.requests)))
            durations = sorted(ms for ms, ok in attempts if ok)
            report[path] = {
                "requests": len(attempts), "errors": len(attempts) - len(durations),
                "p50_ms": round(median(durations), 2) if durations else None,
                "p95_ms": round(durations[ceil(len(durations) * 0.95) - 1], 2) if durations else None,
            }
    print(json.dumps(report, indent=2))
    if any(route["errors"] for route in report.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
