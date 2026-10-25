from __future__ import annotations

import json
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATABASE = PROJECT_ROOT / "database" / "catalog.db"
TRIAL_WORKERS = (12, 8, 8, 12, 12, 8)
EXPECTED_CATEGORIES = 24
EXPECTED_OCCURRENCES = 522
EXPECTED_PRODUCTS = 518
EXPECTED_RELATIONS = 522
EXPECTED_SCHEMA_VERSION = 6
FIXED_CONFIGURATION = {
    "detail_workers": 24,
    "http_workers": 28,
    "jsf_http_concurrency": 8,
    "download_images": False,
    "thread_sessions": True,
}


def _read_database_summary(path: Path) -> dict[str, Any]:
    uri = path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=30)
    try:
        integrity = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        required = {"products", "categories", "product_categories", "schema_migrations"}
        if not required.issubset(tables):
            raise ValueError(f"La base no contiene las tablas esperadas de FCM: {path}")
        schema_row = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()
        schema_version = int(schema_row[0] or 0) if schema_row else 0
        counts = {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in ("products", "categories", "product_categories")
        }
    finally:
        connection.close()
    return {
        "path": str(path.resolve()),
        "integrity": integrity,
        "schema_version": schema_version,
        "counts": counts,
    }


def _create_seed_database(source_path: Path, seed_path: Path) -> dict[str, Any]:
    source = _read_database_summary(source_path)
    expected_counts = {
        "products": EXPECTED_PRODUCTS,
        "categories": EXPECTED_CATEGORIES,
        "product_categories": EXPECTED_RELATIONS,
    }
    if source["integrity"] != "ok":
        raise RuntimeError(f"La base origen no supera quick_check: {source['integrity']}")
    if source["schema_version"] != EXPECTED_SCHEMA_VERSION:
        raise RuntimeError(
            f"Se esperaba esquema v{EXPECTED_SCHEMA_VERSION}; "
            f"se encontró v{source['schema_version']}."
        )
    if source["counts"] != expected_counts:
        raise RuntimeError(
            "La base origen no coincide con el baseline vigente "
            f"518 productos/522 relaciones/24 categorías: {source['counts']}"
        )

    source_connection = sqlite3.connect(
        source_path.resolve().as_uri() + "?mode=ro",
        uri=True,
        timeout=30,
    )
    target_connection = sqlite3.connect(seed_path, timeout=30)
    try:
        source_connection.backup(target_connection)
        target_connection.commit()
    finally:
        target_connection.close()
        source_connection.close()

    seed_summary = _read_database_summary(seed_path)
    if seed_summary["integrity"] != "ok" or seed_summary["counts"] != expected_counts:
        raise RuntimeError("La copia semilla no pasó las comprobaciones de integridad/conteos.")
    return source


def _remove_sqlite_files(path: Path) -> None:
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        with suppress(OSError):
            candidate.unlink(missing_ok=True)


def _validate_profile_payload(
    payload: dict[str, Any],
    *,
    trial_number: int,
    workers: int,
    report_path: Path,
) -> dict[str, Any]:
    coverage = payload.get("coverage", {})
    http = payload.get("http", {})
    checks = {
        "categories": payload.get("categories") == EXPECTED_CATEGORIES,
        "expected_occurrences": coverage.get("expected_category_occurrences") == EXPECTED_OCCURRENCES,
        "collected_occurrences": coverage.get("collected_category_occurrences") == EXPECTED_OCCURRENCES,
        "enriched_occurrences": coverage.get("enriched_category_occurrences") == EXPECTED_OCCURRENCES,
        "coverage_flag": coverage.get("matches_current_category_counts") is True,
        "no_category_mismatches": not coverage.get("mismatched_categories"),
        "no_terminal_http_errors": int(http.get("terminal_errors", 0) or 0) == 0,
        "category_workers": payload.get("category_workers") == workers,
        "fixed_configuration": all(
            payload.get(key) == value for key, value in FIXED_CONFIGURATION.items()
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(
            f"Ensayo {trial_number} inválido (workers={workers}); fallaron "
            f"{', '.join(failed)}. Informe: {report_path}"
        )

    percentiles = http.get("latency_percentiles", {}).get("category", {})
    discovery_seconds = float(payload.get("discovery_seconds", 0.0) or 0.0)
    profile_seconds = float(payload.get("profile_seconds", 0.0) or 0.0)
    return {
        "trial": trial_number,
        "category_workers": workers,
        "categories": int(payload["categories"]),
        "expected_category_occurrences": int(coverage["expected_category_occurrences"]),
        "collected_category_occurrences": int(coverage["collected_category_occurrences"]),
        "enriched_category_occurrences": int(coverage["enriched_category_occurrences"]),
        "discovery_seconds": discovery_seconds,
        "profile_seconds": profile_seconds,
        "total_measured_seconds": discovery_seconds + profile_seconds,
        "http_requests": int(http.get("requests", 0) or 0),
        "category_requests": int(http.get("category_requests", 0) or 0),
        "detail_requests": int(http.get("detail_requests", 0) or 0),
        "retries": int(http.get("retries", 0) or 0),
        "errors": int(http.get("errors", 0) or 0),
        "terminal_errors": int(http.get("terminal_errors", 0) or 0),
        "category_http_total_seconds": float(http.get("category_total_seconds", 0.0) or 0.0),
        "category_http_p50_seconds": float(percentiles.get("p50", 0.0) or 0.0),
        "category_http_p95_seconds": float(percentiles.get("p95", 0.0) or 0.0),
        "category_http_p99_seconds": float(percentiles.get("p99", 0.0) or 0.0),
        "semaphore_wait_seconds": float(http.get("semaphore_wait_seconds", 0.0) or 0.0),
        "report_json": str(report_path),
    }


def _median(trials: list[dict[str, Any]], workers: int, metric: str) -> float:
    values = [
        float(trial[metric])
        for trial in trials
        if int(trial["category_workers"]) == workers
    ]
    if not values:
        raise ValueError(f"No hay ensayos válidos para category_workers={workers}.")
    return float(statistics.median(values))


def _build_summary(
    source_summary: dict[str, Any],
    trials: list[dict[str, Any]],
    output_directory: Path,
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for workers in (8, 12):
        selected = [trial for trial in trials if trial["category_workers"] == workers]
        summaries[str(workers)] = {
            "runs": len(selected),
            "profile_seconds_median": _median(trials, workers, "profile_seconds"),
            "profile_seconds_min": min(float(item["profile_seconds"]) for item in selected),
            "profile_seconds_max": max(float(item["profile_seconds"]) for item in selected),
            "total_measured_seconds_median": _median(trials, workers, "total_measured_seconds"),
            "category_http_p50_median": _median(trials, workers, "category_http_p50_seconds"),
            "category_http_p95_median": _median(trials, workers, "category_http_p95_seconds"),
            "category_http_p99_median": _median(trials, workers, "category_http_p99_seconds"),
            "http_requests_median": _median(trials, workers, "http_requests"),
            "retries_median": _median(trials, workers, "retries"),
            "errors_median": _median(trials, workers, "errors"),
            "semaphore_wait_seconds_median": _median(trials, workers, "semaphore_wait_seconds"),
        }
    median_12 = summaries["12"]["profile_seconds_median"]
    median_8 = summaries["8"]["profile_seconds_median"]
    improvement_pct = (
        ((median_12 - median_8) / median_12) * 100.0 if median_12 > 0 else 0.0
    )
    return {
        "report_type": "FCM_CATEGORY_WORKER_BENCHMARK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_database": source_summary,
        "baseline": {
            "categories": EXPECTED_CATEGORIES,
            "category_occurrences": EXPECTED_OCCURRENCES,
            "unique_products": EXPECTED_PRODUCTS,
            "product_category_relations": EXPECTED_RELATIONS,
        },
        "protocol": {
            "worker_order": list(TRIAL_WORKERS),
            "repetitions_per_setting": 3,
            "fixed_configuration": FIXED_CONFIGURATION,
            "database_isolation": "SQLite backup API seed; a fresh DB copy for each trial",
            "original_database_opened_read_only": True,
            "default_category_workers_changed": False,
        },
        "comparison": {
            "median_profile_seconds": {"workers_8": median_8, "workers_12": median_12},
            "relative_improvement_8_vs_12_pct": improvement_pct,
            "interpretation": (
                "Valor positivo significa que 8 workers fue más rápido en la mediana; "
                "valor negativo significa que fue más lento. No cambia el default de producción."
            ),
        },
        "summaries_by_workers": summaries,
        "trials": trials,
        "output_directory": str(output_directory),
    }


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_directory = Path(tempfile.gettempdir()) / (
        f"fcm_category_worker_benchmark_{stamp}_{os.getpid()}"
    )
    output_directory.mkdir(parents=True, exist_ok=False)
    seed_path = output_directory / "benchmark_seed.db"
    completed_trials: list[dict[str, Any]] = []
    source_summary: dict[str, Any] = {}

    try:
        source_summary = _create_seed_database(SOURCE_DATABASE, seed_path)
        print(
            "SOURCE_DATABASE|read_only=True"
            f"|integrity={source_summary['integrity']}"
            f"|schema={source_summary['schema_version']}"
            f"|products={source_summary['counts']['products']}"
            f"|relations={source_summary['counts']['product_categories']}"
            f"|categories={source_summary['counts']['categories']}"
        )

        for trial_number, workers in enumerate(TRIAL_WORKERS, start=1):
            trial_database = output_directory / f"trial_{trial_number:02d}_workers_{workers}.db"
            report_path = output_directory / f"trial_{trial_number:02d}_workers_{workers}.json"
            log_path = output_directory / f"trial_{trial_number:02d}_workers_{workers}.log"
            shutil.copy2(seed_path, trial_database)
            environment = os.environ.copy()
            environment["FCM_PROFILE_CATEGORY_WORKERS"] = str(workers)
            environment["FCM_PROFILE_HTTP_WORKERS"] = str(FIXED_CONFIGURATION["http_workers"])
            environment["FCM_PROFILE_JSF_HTTP_CONCURRENCY"] = str(
                FIXED_CONFIGURATION["jsf_http_concurrency"]
            )
            environment["FCM_PROFILE_DB_PATH"] = str(trial_database)
            environment["FCM_PROFILE_OUTPUT_PATH"] = str(report_path)

            try:
                result = subprocess.run(
                    [sys.executable, str(PROJECT_ROOT / "tools" / "profile_category_workers.py")],
                    cwd=PROJECT_ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                log_path.write_text(
                    result.stdout + ("\n--- STDERR ---\n" + result.stderr if result.stderr else ""),
                    encoding="utf-8",
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"Ensayo {trial_number} (workers={workers}) falló con código "
                        f"{result.returncode}. Revisa {log_path}"
                    )
                payload = json.loads(report_path.read_text(encoding="utf-8"))
                record = _validate_profile_payload(
                    payload,
                    trial_number=trial_number,
                    workers=workers,
                    report_path=report_path,
                )
                completed_trials.append(record)
                print(
                    f"TRIAL|{trial_number}/6|workers={workers}"
                    f"|profile_s={record['profile_seconds']:.3f}"
                    f"|total_s={record['total_measured_seconds']:.3f}"
                    f"|requests={record['http_requests']}"
                    f"|retries={record['retries']}"
                    f"|errors={record['errors']}"
                    f"|report={report_path}"
                )
            finally:
                _remove_sqlite_files(trial_database)

        summary = _build_summary(source_summary, completed_trials, output_directory)
        summary_path = output_directory / "summary.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        comparison = summary["comparison"]["median_profile_seconds"]
        print(f"MEDIAN_PROFILE_SECONDS|workers=8|{comparison['workers_8']:.3f}")
        print(f"MEDIAN_PROFILE_SECONDS|workers=12|{comparison['workers_12']:.3f}")
        print(
            "IMPROVEMENT_8_VS_12_PCT|"
            f"{summary['comparison']['relative_improvement_8_vs_12_pct']:.2f}"
        )
        print(f"SUMMARY_JSON|{summary_path}")
        print("PRODUCTION_DEFAULT_CHANGED|False")
        return 0
    except (OSError, RuntimeError, ValueError, sqlite3.Error, subprocess.SubprocessError) as error:
        failure = {
            "report_type": "FCM_CATEGORY_WORKER_BENCHMARK_FAILURE",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": f"{type(error).__name__}: {error}",
            "source_database": source_summary,
            "completed_trials": completed_trials,
            "output_directory": str(output_directory),
        }
        failure_path = output_directory / "failure.json"
        failure_path.write_text(
            json.dumps(failure, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"BENCHMARK_FAILED|{failure['error']}")
        print(f"FAILURE_JSON|{failure_path}")
        return 1
    else:
        return 0
    finally:
        _remove_sqlite_files(seed_path)


if __name__ == "__main__":
    raise SystemExit(main())
