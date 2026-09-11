import time
import csv
import os
import statistics
from datetime import datetime

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

import MySQL_Handler
import Redis_Handler
from player import Player

CSV_FILE    = 'comparisons.csv'
CSV_HEADERS = [
    'Timestamp', 'Database', 'Operation', 'Records',
    'Execution_Time_ms', 'Avg_Latency_ms', 'Min_Latency_ms', 'Max_Latency_ms',
    'Throughput_ops_sec', 'Success_Count', 'Failure_Count', 'Success_Rate',
    'CPU_Percent', 'Memory_MB',
]

# ── CSV ───────────────────────────────────────────────────────────────────────

def _ensure_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            csv.writer(f).writerow(CSV_HEADERS)

def _append_csv(rows: list[dict]):
    _ensure_csv()
    with open(CSV_FILE, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        for row in rows:
            w.writerow(row)


# ── System snapshot ───────────────────────────────────────────────────────────

def _sys_snapshot() -> dict:
    if not PSUTIL_AVAILABLE:
        return {'cpu': 'N/A', 'mem': 'N/A'}
    proc = psutil.Process(os.getpid())
    return {
        'cpu': round(proc.cpu_percent(interval=0.1), 2),
        'mem': round(proc.memory_info().rss / 1024 / 1024, 2),   # MB
    }


# ── Core timing harness ───────────────────────────────────────────────────────

def _run_timed(fn, runs: int) -> dict:
    """Call fn() `runs` times, collect per-call latencies.
    fn must return truthy on success, falsy/raise on failure.
    Returns a metrics dict.
    """
    latencies = []
    successes = 0
    failures  = 0
    snap      = _sys_snapshot()

    total_start = time.perf_counter()
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            result = fn()
            latencies.append((time.perf_counter() - t0) * 1000)
            if result is not None and result is not False:
                successes += 1
            else:
                failures += 1
        except Exception:
            latencies.append((time.perf_counter() - t0) * 1000)
            failures += 1
    total_ms = (time.perf_counter() - total_start) * 1000

    avg_lat = statistics.mean(latencies)
    return {
        'execution_ms': round(total_ms, 2),
        'avg_lat':      round(avg_lat, 2),
        'min_lat':      round(min(latencies), 2),
        'max_lat':      round(max(latencies), 2),
        'throughput':   round(runs / (total_ms / 1000), 2),
        'successes':    successes,
        'failures':     failures,
        'success_rate': round(successes / runs * 100, 1),
        'cpu':          snap['cpu'],
        'mem':          snap['mem'],
    }


# ── Terminal table printers ───────────────────────────────────────────────────

def _print_detail_table(operation: str, records: int, redis_m: dict, mysql_m: dict):
    sep   = '=' * 52
    dash  = '-' * 52
    speedup = round(mysql_m['execution_ms'] / redis_m['execution_ms'], 2) if redis_m['execution_ms'] else '∞'

    print(f"\n{sep}")
    print(f"{'REDIS vs MYSQL PERFORMANCE':^52}")
    print(sep)
    print(f"\n{'Operation:':<20}{operation}")
    print(f"{'Records Tested:':<20}{records:,}")
    print(f"\n{'':20}{'Redis':<16}MySQL")
    print(dash)

    rows = [
        ('Execution Time',  f"{redis_m['execution_ms']} ms",  f"{mysql_m['execution_ms']} ms"),
        ('Average Latency', f"{redis_m['avg_lat']} ms",       f"{mysql_m['avg_lat']} ms"),
        ('Min Latency',     f"{redis_m['min_lat']} ms",       f"{mysql_m['min_lat']} ms"),
        ('Max Latency',     f"{redis_m['max_lat']} ms",       f"{mysql_m['max_lat']} ms"),
        ('Throughput',      f"{redis_m['throughput']} ops/s", f"{mysql_m['throughput']} ops/s"),
        ('Success Rate',    f"{redis_m['success_rate']}%",    f"{mysql_m['success_rate']}%"),
    ]
    if PSUTIL_AVAILABLE:
        rows += [
            ('CPU %',       str(redis_m['cpu']),              str(mysql_m['cpu'])),
            ('Memory MB',   str(redis_m['mem']),              str(mysql_m['mem'])),
        ]

    for label, r_val, m_val in rows:
        print(f"{label:<20}{r_val:<16}{m_val}")

    print(dash)
    print(f"\nRedis Speed Improvement: {speedup}x")
    print(sep)


def _print_summary_table(results: list[dict]):
    """results: [{'operation', 'redis_avg', 'mysql_avg'}, ...]"""
    sep  = '-' * 52
    print(f"\n{'PERFORMANCE SUMMARY':^52}")
    print(sep)
    print(f"{'Operation':<18}{'Redis':<12}{'MySQL':<12}Faster")
    print(sep)
    for r in results:
        faster = 'Redis' if r['redis_avg'] <= r['mysql_avg'] else 'MySQL'
        print(
            f"{r['operation']:<18}"
            f"{str(r['redis_avg']) + ' ms':<12}"
            f"{str(r['mysql_avg']) + ' ms':<12}"
            f"{faster}"
        )
    print(sep)


# ── CSV row builder ───────────────────────────────────────────────────────────

def _build_csv_row(ts: str, db: str, operation: str, records: int, m: dict) -> dict:
    return {
        'Timestamp':          ts,
        'Database':           db,
        'Operation':          operation,
        'Records':            records,
        'Execution_Time_ms':  m['execution_ms'],
        'Avg_Latency_ms':     m['avg_lat'],
        'Min_Latency_ms':     m['min_lat'],
        'Max_Latency_ms':     m['max_lat'],
        'Throughput_ops_sec': m['throughput'],
        'Success_Count':      m['successes'],
        'Failure_Count':      m['failures'],
        'Success_Rate':       m['success_rate'],
        'CPU_Percent':        m['cpu'],
        'Memory_MB':          m['mem'],
    }


# ── Individual benchmark runners ──────────────────────────────────────────────

def _bench_pair(operation: str, records: int, redis_fn, mysql_fn) -> dict:
    """Run both fns, print the detail table, return summary dict for the summary table."""
    redis_m = _run_timed(redis_fn, records)
    mysql_m = _run_timed(mysql_fn, records)
    _print_detail_table(operation, records, redis_m, mysql_m)

    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _append_csv([
        _build_csv_row(ts, 'Redis', operation, records, redis_m),
        _build_csv_row(ts, 'MySQL', operation, records, mysql_m),
    ])
    return {
        'operation': operation,
        'redis_avg': redis_m['avg_lat'],
        'mysql_avg': mysql_m['avg_lat'],
    }


# ── Public benchmark entry points ─────────────────────────────────────────────

def bench_read(player_name: str, runs: int = 1000):
    return _bench_pair(
        operation = 'READ',
        records   = runs,
        redis_fn  = lambda: Redis_Handler.getCachedPlayer(player_name),
        mysql_fn  = lambda: MySQL_Handler.getPlayer(player_name),
    )


def bench_write(sample_players: list, runs: int = 1000):
    """Fires addPlayer against both stores.
    Uses a rotating sample list so the same player isn't re-inserted every time.
    MySQL AUTO_INCREMENT means each insert is genuinely new; Redis just overwrites.
    """
    idx = [0]
    def redis_write():
        p = sample_players[idx[0] % len(sample_players)]
        idx[0] += 1
        Redis_Handler.cachePlayer(p)
        return True

    def mysql_write():
        p = sample_players[idx[0] % len(sample_players)]
        idx[0] += 1
        MySQL_Handler.addPlayer(p)
        return True

    return _bench_pair('WRITE', runs, redis_write, mysql_write)


def bench_rank(player_name: str, runs: int = 1000):
    return _bench_pair(
        operation = 'GET RANK',
        records   = runs,
        redis_fn  = lambda: Redis_Handler.getCachedPlayerRank(player_name),
        mysql_fn  = lambda: MySQL_Handler.getPlayerRank(player_name),
    )


def bench_top_ten( runs: int = 1000):
    return _bench_pair(
        operation = f'TOP 10',
        records   = runs,
        redis_fn  = lambda: Redis_Handler.getCachedTopTen(),
        mysql_fn  = lambda: MySQL_Handler.getTopTen(),
    )


def bench_leaderboard(runs: int = 1000):
    return _bench_pair(
        operation = 'LEADERBOARD',
        records   = runs,
        redis_fn  = lambda: Redis_Handler.getCachedLeaderboard(),
        mysql_fn  = lambda: MySQL_Handler.getLeaderboard(),
    )


def run_full_benchmark(player_name: str, runs: int = 1000):
    """Run all operations in sequence and print the summary table at the end."""
    print(f"\nStarting full benchmark — {runs} runs per operation...")
    summary = []
    summary.append(bench_read(player_name, runs))
    summary.append(bench_rank(player_name, runs))
    summary.append(bench_top_ten(runs))
    summary.append(bench_leaderboard(runs))
    _print_summary_table(summary)
    print(f"\nResults written to '{CSV_FILE}'")

# ── Operation trace logger ────────────────────────────────────────────────────

def log_operation(operation: str, datasource: str, latency_ms: float):
    """Print a single-line trace showing datasource and latency for any operation.
    Call this from main.py after every read — datasource is 'Redis' or 'MySQL'.
    """
    src_colour = '\033[92m' if datasource == 'Redis' else '\033[93m'  # green / yellow
    reset      = '\033[0m'
    print(f"  [{src_colour}{datasource}{reset}] {operation:<18} {latency_ms:.2f} ms")