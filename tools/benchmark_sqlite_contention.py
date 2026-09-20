#!/usr/bin/env python3
"""Benchmark aislado de contención/latencia SQLite para FCM.

No toca database/catalog.db: cada escenario se ejecuta sobre una SQLite temporal
y usa la misma configuración WAL + synchronous=NORMAL + timeout=30s de DBManager.

El objetivo es obtener evidencia antes de cambiar el alcance de las transacciones.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import statistics
import tempfile
import threading
import time
from pathlib import Path

DEFAULT_PRODUCTS = 530
DEFAULT_READ_ITERATIONS = 250
DEFAULT_WRITE_BATCHES = 12
DEFAULT_WRITES_PER_BATCH = 40


def configure(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=30000")


def seed_database(path: Path, products: int) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    connection = sqlite3.connect(str(path), timeout=30)
    try:
        configure(connection)
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        for index in range(1, products + 1):
            connection.execute(
                """
                INSERT INTO products (
                    code, name, category, description, price,
                    price_sample, price_hundred, price_thousand, stock,
                    color_stock, image_url, image_path, image_hash, content_hash
                )
                VALUES (?, ?, ?, '', 1, 1, 1, 1, ?, '{}', '', '', '', ?)
                """,
                (
                    f"BENCH-{index:04d}",
                    f"Producto benchmark {index}",
                    "Benchmark",
                    index % 100,
                    f"hash-{index:04d}",
                ),
            )
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        connection.close()


def run_writer(
    path: Path,
    batches: int,
    writes_per_batch: int,
    products: int,
    barrier: threading.Barrier,
    latencies: list[float],
    errors: list[str],
) -> None:
    connection = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    configure(connection)
    try:
        barrier.wait()
        for batch in range(batches):
            started = time.perf_counter()
            try:
                connection.execute("BEGIN")
                for offset in range(writes_per_batch):
                    index = ((batch * writes_per_batch + offset) % products) + 1
                    connection.execute(
                        """
                        UPDATE products
                        SET stock = stock + 1,
                            content_hash = ?
                        WHERE code = ?
                        """,
                        (f"hash-{index:04d}-{batch}", f"BENCH-{index:04d}"),
                    )
                connection.execute(
                    """
                    INSERT INTO scraping_history (
                        started_at, finished_at, processed, updated,
                        unchanged, status, message
                    )
                    VALUES (
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, 0,
                        'SUCCESS', 'SQLite contention benchmark'
                    )
                    """,
                    (writes_per_batch, writes_per_batch),
                )
                connection.commit()
                latencies.append(time.perf_counter() - started)
            except Exception as exc:  # noqa: BLE001
                connection.rollback()
                errors.append(f"writer: {exc}")
    finally:
        connection.close()


def run_reader(
    path: Path,
    iterations: int,
    barrier: threading.Barrier,
    latencies: list[float],
    errors: list[str],
) -> None:
    connection = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    configure(connection)
    try:
        barrier.wait()
        for _ in range(iterations):
            started = time.perf_counter()
            try:
                connection.execute(
                    """
                    SELECT COUNT(*), COALESCE(SUM(stock), 0), COALESCE(MAX(id), 0)
                    FROM products
                    """
                ).fetchone()
                latencies.append(time.perf_counter() - started)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"reader: {exc}")
    finally:
        connection.close()


def percentile(values: list[float], factor: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = min(len(ordered) - 1, max(0, int((len(ordered) - 1) * factor)))
    return ordered[position]


def run_case(
    source: Path,
    products: int,
    readers: int,
    writers: int,
    read_iterations: int,
    write_batches: int,
    writes_per_batch: int,
) -> dict[str, float | int | str]:
    with tempfile.TemporaryDirectory(prefix="fcm-sqlite-bench-") as directory:
        db_path = Path(directory) / "bench.db"
        shutil.copy2(source, db_path)

        writer_latencies: list[float] = []
        reader_latencies: list[float] = []
        errors: list[str] = []
        total_workers = readers + writers
        barrier = threading.Barrier(total_workers)

        threads = [
            threading.Thread(
                target=run_writer,
                args=(
                    db_path,
                    write_batches,
                    writes_per_batch,
                    products,
                    barrier,
                    writer_latencies,
                    errors,
                ),
            )
            for _ in range(writers)
        ]
        threads.extend(
            threading.Thread(
                target=run_reader,
                args=(db_path, read_iterations, barrier, reader_latencies, errors),
            )
            for _ in range(readers)
        )

        started = time.perf_counter()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        wall = time.perf_counter() - started

        return {
            "readers": readers,
            "writers": writers,
            "wall_seconds": wall,
            "writer_count": len(writer_latencies),
            "writer_p50_ms": statistics.median(writer_latencies) * 1000
            if writer_latencies
            else 0.0,
            "writer_p95_ms": percentile(writer_latencies, 0.95) * 1000,
            "writer_max_ms": max(writer_latencies) * 1000
            if writer_latencies
            else 0.0,
            "reader_count": len(reader_latencies),
            "reader_p95_ms": percentile(reader_latencies, 0.95) * 1000,
            "errors": len(errors),
            "error_sample": errors[0] if errors else "",
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", type=int, default=DEFAULT_PRODUCTS)
    parser.add_argument("--read-iterations", type=int, default=DEFAULT_READ_ITERATIONS)
    parser.add_argument("--write-batches", type=int, default=DEFAULT_WRITE_BATCHES)
    parser.add_argument("--writes-per-batch", type=int, default=DEFAULT_WRITES_PER_BATCH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if min(args.products, args.read_iterations, args.write_batches, args.writes_per_batch) <= 0:
        raise SystemExit("Todos los parámetros deben ser mayores que cero.")

    with tempfile.TemporaryDirectory(prefix="fcm-sqlite-source-") as directory:
        source = Path(directory) / "seed.db"
        seed_database(source, args.products)

        print("FCM SQLite contention benchmark")
        print(f"products={args.products}")
        print(
            "workload="
            f"{args.write_batches} write-batches x {args.writes_per_batch} updates"
            f"; {args.read_iterations} read queries/reader"
        )
        print("journal_mode=WAL synchronous=NORMAL timeout=30s")
        print()

        cases = (
            (0, 1),
            (4, 1),
            (8, 1),
            (4, 2),
        )
        for readers, writers in cases:
            result = run_case(
                source,
                args.products,
                readers,
                writers,
                args.read_iterations,
                args.write_batches,
                args.writes_per_batch,
            )
            print(
                f"readers={result['readers']} writers={result['writers']} "
                f"wall={result['wall_seconds']:.3f}s "
                f"writes={result['writer_count']} "
                f"writer_p50={result['writer_p50_ms']:.2f}ms "
                f"writer_p95={result['writer_p95_ms']:.2f}ms "
                f"writer_max={result['writer_max_ms']:.2f}ms "
                f"reads={result['reader_count']} "
                f"reader_p95={result['reader_p95_ms']:.3f}ms "
                f"errors={result['errors']}"
            )
            if result["error_sample"]:
                print(f"  error_sample={result['error_sample']}")
        print()
        print("No se modificó database/catalog.db.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
