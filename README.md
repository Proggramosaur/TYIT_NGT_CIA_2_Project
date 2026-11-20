# TYIT_NGT_CIA_2_Project
# In-Memory Caching & Player Leaderboard System
### Redis vs MySQL — Performance Benchmarking on a 50,000-Record Dataset

> Academic Project — TYIT (Third Year IT) | CIA-2 Evaluation  
> Subject: Next Generation Technologies (NGT) | 2026

---

## Overview

This project demonstrates the performance advantage of **Redis in-memory caching** over traditional **MySQL disk-based storage** in a real-world leaderboard scenario. A player management system is built on top of a 50,000-row MySQL database, with Redis acting as a cache layer using the **cache-aside pattern**.

All operations are benchmarked — read, write, update, delete, rank lookup, and leaderboard retrieval — with latency, throughput, and system resource metrics recorded to CSV for analysis.

---

## Key Results

| Operation | Redis Avg Latency | MySQL Avg Latency | Speed Improvement |
|-----------|:-----------------:|:-----------------:|:-----------------:|
| GET RANK  | 2.32 ms           | 37.4 ms           | **16.09x faster** |
| READ      | ~4.5 ms (cache hit) | ~16 ms          | **~3–4x faster**  |

> Redis consistently outperformed MySQL across all read-heavy operations.  
> Results exported to `comparisons.csv` with per-run statistics.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                   main.py                   │
│            (CLI Menu & App Logic)           │
└────────┬──────────────────────┬─────────────┘
         │                      │
         ▼                      ▼
┌─────────────────┐    ┌─────────────────────┐
│  Redis_Handler  │    │   MySQL_Handler      │
│  (Cache Layer)  │    │  (Persistent Store)  │
│                 │    │                      │
│ • TTL: 900s     │    │ • 50,000 player rows │
│ • Sorted Sets   │    │ • Full CRUD          │
│ • Pipeline ops  │    │ • Rank subqueries    │
│ • Cache-aside   │    │                      │
└─────────────────┘    └─────────────────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
         ┌─────────────────────┐
         │    Benchmark.py     │
         │                     │
         │ • Latency metrics   │
         │ • Throughput ops/s  │
         │ • CPU & Memory via  │
         │   psutil            │
         │ • CSV export        │
         └─────────────────────┘
```

---

## Project Structure

```
TYIT_NGT_CIA_2_Project/
│
├── main.py              # Entry point — CLI menu and session management
├── player.py            # Player data class (ID, Name, Level, Score)
├── MySQL_Handler.py     # MySQL CRUD operations and leaderboard queries
├── Redis_Handler.py     # Redis cache operations, sorted sets, TTL, pipelines
├── Benchmark.py         # Performance benchmarking and CSV export
├── comparisons.csv      # Auto-generated benchmark results
├── .env                 # Environment variables (not committed)
└── requirements.txt     # Python dependencies
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.x |
| Persistent DB | MySQL |
| Cache | Redis (via `redis-py`) |
| ORM/Connector | `mysql-connector-python` |
| Benchmarking | `psutil`, `statistics`, `csv` |
| Environment | WSL (Windows Subsystem for Linux) |
| Config | `python-dotenv` |

---

## Features

- **Full CRUD** — Add, Read, Update, Delete players with dual-write to MySQL and Redis
- **Cache-aside pattern** — Redis checked first; falls back to MySQL on cache miss and repopulates
- **TTL-based expiry** — Player records expire after 900 seconds; leaderboard sorted set persists
- **Redis Sorted Sets** — Used for O(log N) rank lookups and top-N leaderboard retrieval
- **Pipeline batching** — Multi-command Redis operations batched to reduce round-trips
- **Stale key eviction** — On rename/update, old name-pointer keys are explicitly deleted
- **Performance Benchmarking** — Configurable runs per operation with full statistical output
- **CSV Export** — Benchmark results written to `comparisons.csv` with timestamps
- **System Metrics** — Optional CPU % and Memory MB tracking via `psutil`

---

## Setup & Running

### Prerequisites
- Python 3.10+
- MySQL Server running locally
- Redis Server running locally (WSL recommended on Windows)

### 1. Clone the repository
```bash
git clone https://github.com/Proggramosaur/TYIT_NGT_CIA_2_Project.git
cd TYIT_NGT_CIA_2_Project
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file in the project root:
```env
MYSQL_Host=localhost
MYSQL_User=your_mysql_user
MYSQL_Password=your_mysql_password
MYSQL_DB=your_database_name

REDIS_Host=localhost
REDIS_Port=6379
REDIS_DB=0
```

### 4. Run the application
```bash
python main.py
```

---

## Benchmark Output (Sample)

```
====================================================
              REDIS vs MYSQL PERFORMANCE
====================================================

Operation:          GET RANK
Records Tested:     10

                    Redis           MySQL
----------------------------------------------------
Execution Time      23.25 ms        374.04 ms
Average Latency     2.32 ms         37.4 ms
Min Latency         1.36 ms         36.27 ms
Max Latency         3.89 ms         39.15 ms
Throughput          430.07 ops/s    26.74 ops/s
Success Rate        100.0%          100.0%
----------------------------------------------------

Redis Speed Improvement: 16.09x
====================================================
```

---

## Notes

- The MySQL database is pre-populated with 50,000 player records for benchmarking realism
- `comparisons.csv` is auto-created on first benchmark run
- Project developed and tested on WSL (Ubuntu) with Python 3.x

---
