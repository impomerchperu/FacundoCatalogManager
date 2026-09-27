from __future__ import annotations

import argparse
import json
import pathlib
import typing


SUPPORTED_SCHEMA_VERSION = 1
CONFIGURATION_KEYS = (
    "category_workers",
    "detail_workers",
    "http_workers",
    "jsf_http_concurrency",
    "jsf_page_workers",
    "category_page_workers",
    "thread_sessions",
)

TIMING_KEYS = (
    "collection_seconds",
    "enrichment_seconds",
    "pipeline_seconds",
)

HTTP_KEYS = (
    "http_requests",
    "http_successes",
    "http_errors",
    "http_terminal_errors",
    "http_retries",
    "http_retry_sleep_seconds",
    "http_total_seconds",
    "http_max_seconds",
    "http_max_in_flight",
)

DETAIL_KEYS = (
    "detail_requests",
    "detail_cache_hits",
    "detail_cache_size",
    "detail_skipped",
)


class BenchmarkComparisonError(ValueError):
    """Indica que dos artefactos de benchmark no son comparables."""


def load_benchmark_report(path: str | pathlib.Path) -> dict[str, typing.Any]:
    """Carga y valida la forma mínima de un artefacto benchmark."""
    report_path = pathlib.Path(path).expanduser()
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BenchmarkComparisonError(
            f"No se pudo leer el benchmark '{report_path}': {error}"
        ) from error

    if not isinstance(payload, dict):
        raise BenchmarkComparisonError(
            f"El benchmark '{report_path}' debe contener un objeto JSON."
        )

    schema_version = payload.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise BenchmarkComparisonError(
            "schema_version no soportada: "
            f"{schema_version!r}; esperada={SUPPORTED_SCHEMA_VERSION}."
        )

    mode = payload.get("mode")
    if not isinstance(mode, str) or not mode.strip():
        raise BenchmarkComparisonError(
            "El benchmark debe declarar un 'mode' no vacío."
        )

    return payload


def _numeric_value(mapping: dict[str, typing.Any], key: str) -> float | int | None:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _numeric_deltas(
    baseline: dict[str, typing.Any],
    candidate: dict[str, typing.Any],
    keys: tuple[str, ...],
) -> dict[str, dict[str, float | int]]:
    result: dict[str, dict[str, float | int]] = {}
    for key in keys:
        baseline_value = _numeric_value(baseline, key)
        candidate_value = _numeric_value(candidate, key)
        if baseline_value is None or candidate_value is None:
            continue

        delta = candidate_value - baseline_value
        relative_percent = (
            (delta / baseline_value) * 100
            if baseline_value != 0
            else 0.0
        )
        result[key] = {
            "baseline": baseline_value,
            "candidate": candidate_value,
            "delta": delta,
            "relative_percent": relative_percent,
        }
    return result


def _configuration(report: dict[str, typing.Any]) -> dict[str, typing.Any]:
    raw = report.get("configuration")
    if not isinstance(raw, dict):
        return {}
    return {
        key: raw[key]
        for key in CONFIGURATION_KEYS
        if key in raw
    }


def _coverage_signature(report: dict[str, typing.Any]) -> dict[str, int]:
    coverage = report.get("coverage")
    if not isinstance(coverage, dict):
        return {}

    keys = (
        "categories",
        "expected_occurrences",
        "found_occurrences",
    )
    signature: dict[str, int] = {}
    for key in keys:
        value = coverage.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        signature[key] = value
    return signature


def compare_benchmark_reports(
    baseline: dict[str, typing.Any],
    candidate: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    """Compara dos benchmarks sin convertir sus deltas en una clasificación."""
    if baseline.get("schema_version") != candidate.get("schema_version"):
        raise BenchmarkComparisonError(
            "Los benchmarks usan versiones de esquema distintas."
        )

    baseline_mode = baseline.get("mode")
    candidate_mode = candidate.get("mode")
    if baseline_mode != candidate_mode:
        raise BenchmarkComparisonError(
            "Los benchmarks no tienen el mismo modo: "
            f"{baseline_mode!r} != {candidate_mode!r}."
        )

    baseline_coverage = _coverage_signature(baseline)
    candidate_coverage = _coverage_signature(candidate)
    for key in ("categories", "expected_occurrences"):
        if (
            key in baseline_coverage
            and key in candidate_coverage
            and baseline_coverage[key] != candidate_coverage[key]
        ):
            raise BenchmarkComparisonError(
                "La cobertura estructural no es comparable para "
                f"'{key}': {baseline_coverage[key]} != {candidate_coverage[key]}."
            )

    baseline_config = _configuration(baseline)
    candidate_config = _configuration(candidate)

    baseline_timing = baseline.get("timing")
    candidate_timing = candidate.get("timing")
    baseline_http = baseline.get("http")
    candidate_http = candidate.get("http")
    baseline_detail = baseline.get("detail")
    candidate_detail = candidate.get("detail")

    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "mode": baseline_mode,
        "configuration": {
            "baseline": baseline_config,
            "candidate": candidate_config,
        },
        "coverage": {
            "baseline": baseline_coverage,
            "candidate": candidate_coverage,
        },
        "timing": _numeric_deltas(
            baseline_timing if isinstance(baseline_timing, dict) else {},
            candidate_timing if isinstance(candidate_timing, dict) else {},
            TIMING_KEYS,
        ),
        "http": _numeric_deltas(
            baseline_http if isinstance(baseline_http, dict) else {},
            candidate_http if isinstance(candidate_http, dict) else {},
            HTTP_KEYS,
        ),
        "detail": _numeric_deltas(
            baseline_detail if isinstance(baseline_detail, dict) else {},
            candidate_detail if isinstance(candidate_detail, dict) else {},
            DETAIL_KEYS,
        ),
    }


def compare_benchmark_files(
    baseline_path: str | pathlib.Path,
    candidate_path: str | pathlib.Path,
) -> dict[str, typing.Any]:
    """Carga dos artefactos JSON y devuelve una comparación estructurada."""
    baseline = load_benchmark_report(baseline_path)
    candidate = load_benchmark_report(candidate_path)
    return compare_benchmark_reports(baseline, candidate)


def _format_metric_line(
    group: str,
    key: str,
    values: dict[str, float | int],
) -> str:
    baseline = values["baseline"]
    candidate = values["candidate"]
    delta = values["delta"]
    relative = values["relative_percent"]
    return (
        f"{group}.{key}: "
        f"baseline={baseline:g} "
        f"candidate={candidate:g} "
        f"delta={delta:+g} "
        f"relative={relative:+.2f}%"
    )


def _print_comparison(comparison: dict[str, typing.Any]) -> None:
    print("BENCHMARK COMPARISON")
    print(f"MODE: {comparison['mode']}")
    print("CONFIGURATION BASELINE:", comparison["configuration"]["baseline"])
    print("CONFIGURATION CANDIDATE:", comparison["configuration"]["candidate"])
    print("COVERAGE BASELINE:", comparison["coverage"]["baseline"])
    print("COVERAGE CANDIDATE:", comparison["coverage"]["candidate"])

    for group in ("timing", "http", "detail"):
        values = comparison[group]
        if not values:
            continue
        print(f"{group.upper()}:")
        for key, metric in values.items():
            print("  " + _format_metric_line(group, key, metric))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compara dos artefactos JSON de benchmark sin clasificarlos "
            "como ganadores o perdedores."
        )
    )
    parser.add_argument("baseline", type=pathlib.Path)
    parser.add_argument("candidate", type=pathlib.Path)
    args = parser.parse_args(argv)

    try:
        comparison = compare_benchmark_files(
            args.baseline,
            args.candidate,
        )
    except BenchmarkComparisonError as error:
        print(f"ERROR: {error}")
        return 2

    _print_comparison(comparison)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
