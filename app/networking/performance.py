import time
import statistics
import requests
from datetime import datetime

def run_http_benchmark(target_url, request_count=20, timeout=3.0):
    """
    Executes a real HTTP benchmark against target_url using requests.
    Calculates accurate response times with time.perf_counter().
    Limits request_count between 1 and 100 to avoid destructive loads.
    """
    request_count = max(1, min(int(request_count), 100))
    latencies_ms = []
    success_count = 0
    fail_count = 0
    status_codes = {}

    start_bench = time.perf_counter()

    for _ in range(request_count):
        req_start = time.perf_counter()
        try:
            resp = requests.get(target_url, timeout=timeout)
            duration_ms = (time.perf_counter() - req_start) * 1000.0
            latencies_ms.append(duration_ms)
            status_codes[resp.status_code] = status_codes.get(resp.status_code, 0) + 1
            if resp.status_code < 400:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            duration_ms = (time.perf_counter() - req_start) * 1000.0
            latencies_ms.append(duration_ms)
            fail_count += 1
            status_codes['ERR'] = status_codes.get('ERR', 0) + 1

    total_duration_sec = time.perf_counter() - start_bench

    # Metric calculations
    if latencies_ms:
        avg_ms = round(statistics.mean(latencies_ms), 2)
        min_ms = round(min(latencies_ms), 2)
        max_ms = round(max(latencies_ms), 2)
        median_ms = round(statistics.median(latencies_ms), 2)
        # 95th percentile
        sorted_latencies = sorted(latencies_ms)
        p95_index = int(0.95 * len(sorted_latencies))
        p95_ms = round(sorted_latencies[min(p95_index, len(sorted_latencies) - 1)], 2)
    else:
        avg_ms = min_ms = max_ms = median_ms = p95_ms = 0.0

    throughput_rps = round(request_count / total_duration_sec, 2) if total_duration_sec > 0 else 0.0
    failure_percentage = round((fail_count / request_count) * 100, 2) if request_count > 0 else 0.0

    return {
        "target_url": target_url,
        "request_count": request_count,
        "successful_requests": success_count,
        "failed_requests": fail_count,
        "failure_percentage": failure_percentage,
        "avg_response_ms": avg_ms,
        "min_response_ms": min_ms,
        "max_response_ms": max_ms,
        "median_response_ms": median_ms,
        "p95_response_ms": p95_ms,
        "throughput_rps": throughput_rps,
        "total_duration_sec": round(total_duration_sec, 3),
        "status_codes": status_codes,
        "individual_latencies": [round(x, 2) for x in latencies_ms],
        "metric_definitions": {
            "HTTP Response Time": "Total round-trip time in milliseconds measured from socket dispatch to receipt of the full HTTP response body.",
            "Average Response Time": "Arithmetic mean of all measured HTTP request latencies.",
            "Median (P50)": "Middle latency value separating the fastest 50% from the slowest 50%.",
            "95th Percentile (P95)": "Response time threshold under which 95% of all requests completed.",
            "Throughput": "Completed requests per elapsed real second (requests/sec).",
            "Limitations": "Measured over application HTTP layer; includes Python WSGI/server processing and network stack latency, not pure wire propagation delay."
        }
    }

def record_benchmark_result(db, test_name, metrics):
    """Save benchmark metrics to SQLite performance_metrics table."""
    db.execute(
        """INSERT INTO performance_metrics 
           (test_name, request_count, successful_requests, failed_requests,
            avg_response_ms, min_response_ms, max_response_ms, median_response_ms,
            p95_response_ms, throughput_rps, total_duration_sec)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (test_name, metrics['request_count'], metrics['successful_requests'],
         metrics['failed_requests'], metrics['avg_response_ms'], metrics['min_response_ms'],
         metrics['max_response_ms'], metrics['median_response_ms'], metrics['p95_response_ms'],
         metrics['throughput_rps'], metrics['total_duration_sec'])
    )
    db.commit()

def get_performance_history(db, limit=20):
    """Retrieve historical performance benchmark runs."""
    rows = db.execute(
        "SELECT * FROM performance_metrics ORDER BY timestamp DESC LIMIT ?",
        (limit,)
    ).fetchall()
    return [dict(r) for r in rows]
