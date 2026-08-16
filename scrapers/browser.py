import threading
import time

import requests

from config.scraping_config import (
    DEFAULT_HEADERS,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SCRAPING_CATEGORY_WORKERS,
)


class Browser:
    def __init__(self, session=None):
        self.session = session
        self._thread_local = threading.local()
        self._http_semaphore = threading.BoundedSemaphore(SCRAPING_CATEGORY_WORKERS)

        if session is None:
            self.session = requests.Session()

        self.headers = DEFAULT_HEADERS
        self.timeout = REQUEST_TIMEOUT
        self.max_retries = MAX_RETRIES

        self._metrics_lock = threading.Lock()
        self._http_requests = 0
        self._http_successes = 0
        self._http_errors = 0
        self._http_retries = 0
        self._http_total_seconds = 0.0
        self._http_max_seconds = 0.0
        self._http_in_flight = 0
        self._http_max_in_flight = 0
        self._detail_http_requests = 0
        self._category_http_requests = 0
        self._other_http_requests = 0
        self._latency_buckets = {
            "lt_0_5": 0,
            "0_5_1": 0,
            "1_2": 0,
            "2_5": 0,
            "5_10": 0,
            "gte_10": 0,
        }
        self._slowest_requests: list[tuple[float, str]] = []

    def _get_session(self):
        """Return a session safe for the current scraping worker."""
        if self.session is not None and not getattr(
            self,
            "_use_thread_sessions",
            False,
        ):
            return self.session

        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            self._thread_local.session = session
        return session

    def enable_thread_sessions(self):
        """Use one requests session per worker thread for concurrent scraping."""
        self._use_thread_sessions = True

    def fetch(self, url):
        return self.get(url)

    def get(self, url):
        last_error = None
        session = self._get_session()

        for attempt in range(self.max_retries):
            self._http_semaphore.acquire()
            started = time.perf_counter()
            self._begin_request(url)
            retry_after_release = False

            try:
                response = session.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout,
                )

                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
            except requests.exceptions.RequestException as error:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=False, url=url)
                last_error = error

                if not self._is_retryable_error(error):
                    raise

                if attempt < self.max_retries - 1:
                    self._record_retry()
                    retry_after_release = True
            else:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=True, url=url)

                if attempt:
                    self._record_retry()

                if hasattr(response, "text"):
                    return response.text
                return response
            finally:
                self._http_semaphore.release()

            if retry_after_release:
                time.sleep(attempt + 1)

        if last_error:
            raise last_error

    @staticmethod
    def _is_retryable_error(error):
        """Retry only transient network/server failures, not permanent 4xx errors."""
        if isinstance(
            error,
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ),
        ):
            return True

        if isinstance(error, requests.exceptions.HTTPError):
            response = getattr(error, "response", None)
            status_code = getattr(response, "status_code", None)
            return status_code == 429 or (
                isinstance(status_code, int) and status_code >= 500
            )

        return False

    def _begin_request(self, url):
        with self._metrics_lock:
            self._http_requests += 1
            self._http_in_flight += 1
            self._http_max_in_flight = max(
                self._http_max_in_flight,
                self._http_in_flight,
            )

            url_text = str(url)
            if "/producto/" in url_text:
                self._detail_http_requests += 1
            elif "/categoria-producto/" in url_text or "/tienda/" in url_text:
                self._category_http_requests += 1
            else:
                self._other_http_requests += 1

    def _finish_request(self, elapsed, success, url):
        with self._metrics_lock:
            self._http_in_flight = max(0, self._http_in_flight - 1)
            self._http_total_seconds += elapsed
            self._http_max_seconds = max(
                self._http_max_seconds,
                elapsed,
            )

            if success:
                self._http_successes += 1
            else:
                self._http_errors += 1

            if elapsed < 0.5:
                bucket = "lt_0_5"
            elif elapsed < 1:
                bucket = "0_5_1"
            elif elapsed < 2:
                bucket = "1_2"
            elif elapsed < 5:
                bucket = "2_5"
            elif elapsed < 10:
                bucket = "5_10"
            else:
                bucket = "gte_10"
            self._latency_buckets[bucket] += 1

            self._slowest_requests.append((elapsed, str(url)))
            self._slowest_requests.sort(reverse=True)
            del self._slowest_requests[10:]

    def _record_retry(self):
        with self._metrics_lock:
            self._http_retries += 1

    def get_http_metrics(self):
        """Return accumulated HTTP timing and concurrency metrics."""
        with self._metrics_lock:
            return {
                "http_requests": self._http_requests,
                "http_successes": self._http_successes,
                "http_errors": self._http_errors,
                "http_retries": self._http_retries,
                "http_total_seconds": self._http_total_seconds,
                "http_max_seconds": self._http_max_seconds,
                "http_in_flight": self._http_in_flight,
                "http_max_in_flight": self._http_max_in_flight,
                "detail_http_requests": self._detail_http_requests,
                "category_http_requests": self._category_http_requests,
                "other_http_requests": self._other_http_requests,
                "latency_buckets": dict(self._latency_buckets),
                "slowest_requests": list(self._slowest_requests),
            }

    def reset_http_metrics(self):
        """Reset HTTP metrics before a new full scraping run."""
        with self._metrics_lock:
            self._http_requests = 0
            self._http_successes = 0
            self._http_errors = 0
            self._http_retries = 0
            self._http_total_seconds = 0.0
            self._http_max_seconds = 0.0
            self._http_in_flight = 0
            self._http_max_in_flight = 0
            self._detail_http_requests = 0
            self._category_http_requests = 0
            self._other_http_requests = 0
            self._latency_buckets = {
                "lt_0_5": 0,
                "0_5_1": 0,
                "1_2": 0,
                "2_5": 0,
                "5_10": 0,
                "gte_10": 0,
            }
            self._slowest_requests = []
