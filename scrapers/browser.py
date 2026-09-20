import threading
import time

import requests

from config.scraping_config import (
    DEFAULT_HEADERS,
    JETSMARTFILTERS_AJAX_URL,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    SCRAPING_HTTP_WORKERS,
)


class Browser:
    def __init__(self, session=None, request_timeout=None, max_retries=None, http_workers=None):
        self.session = session
        self._owns_session = session is None
        self._thread_local = threading.local()
        self._sessions_lock = threading.Lock()
        self._thread_sessions: set[requests.Session] = set()
        self._closed = False
        self.http_workers = (
            SCRAPING_HTTP_WORKERS
            if http_workers is None
            else int(http_workers)
        )
        if self.http_workers <= 0:
            raise ValueError("http_workers debe ser mayor que cero.")
        self._http_semaphore = threading.BoundedSemaphore(self.http_workers)

        if session is None:
            self.session = requests.Session()

        self.headers = DEFAULT_HEADERS
        self.timeout = (
            REQUEST_TIMEOUT if request_timeout is None else int(request_timeout)
        )
        self.max_retries = (
            MAX_RETRIES if max_retries is None else int(max_retries)
        )

        if self.timeout <= 0:
            raise ValueError("request_timeout debe ser mayor que cero.")
        if self.max_retries <= 0:
            raise ValueError("max_retries debe ser mayor que cero.")

        self._metrics_lock = threading.Lock()
        self._http_requests = 0
        self._http_successes = 0
        self._http_errors = 0
        self._http_terminal_errors = 0
        self._http_retries = 0
        self._http_retry_sleep_seconds = 0.0
        self._http_retry_sleep_count = 0
        self._http_total_seconds = 0.0
        self._http_max_seconds = 0.0
        self._http_in_flight = 0
        self._http_max_in_flight = 0
        self._detail_http_requests = 0
        self._category_http_requests = 0
        self._jsf_http_requests = 0
        self._other_http_requests = 0
        self._detail_http_total_seconds = 0.0
        self._category_http_total_seconds = 0.0
        self._jsf_http_total_seconds = 0.0
        self._other_http_total_seconds = 0.0
        self._detail_http_max_seconds = 0.0
        self._category_http_max_seconds = 0.0
        self._jsf_http_max_seconds = 0.0
        self._other_http_max_seconds = 0.0
        self._detail_semaphore_wait_seconds = 0.0
        self._category_semaphore_wait_seconds = 0.0
        self._jsf_semaphore_wait_seconds = 0.0
        self._other_semaphore_wait_seconds = 0.0
        self._detail_semaphore_max_wait_seconds = 0.0
        self._category_semaphore_max_wait_seconds = 0.0
        self._jsf_semaphore_max_wait_seconds = 0.0
        self._other_semaphore_max_wait_seconds = 0.0
        self._detail_semaphore_wait_count = 0
        self._category_semaphore_wait_count = 0
        self._jsf_semaphore_wait_count = 0
        self._other_semaphore_wait_count = 0
        self._latency_buckets = {
            "lt_0_5": 0,
            "0_5_1": 0,
            "1_2": 0,
            "2_5": 0,
            "5_10": 0,
            "gte_10": 0,
        }
        self._slowest_requests: list[tuple[float, str]] = []
        self._retry_events: list[dict[str, object]] = []

    def _get_session(self):
        """Return a session safe for the current scraping worker."""
        if self._closed:
            raise RuntimeError("Browser ya está cerrado.")
        if self.session is not None and not getattr(
            self,
            "_use_thread_sessions",
            False,
        ):
            return self.session

        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            with self._sessions_lock:
                if self._closed:
                    session.close()
                    raise RuntimeError("Browser ya está cerrado.")
                self._thread_local.session = session
                self._thread_sessions.add(session)
        return session

    def close(self) -> None:
        """Cierra todas las sesiones HTTP creadas por este browser."""
        with self._sessions_lock:
            if self._closed:
                return
            self._closed = True
            sessions = list(self._thread_sessions)
            self._thread_sessions.clear()
            if self._owns_session and self.session is not None:
                sessions.append(self.session)

        seen: set[int] = set()
        for session in sessions:
            if id(session) in seen:
                continue
            seen.add(id(session))
            close = getattr(session, "close", None)
            if callable(close):
                close()

    def enable_thread_sessions(self):
        """Use one requests session per worker thread for concurrent scraping."""
        self._use_thread_sessions = True

    def fetch(self, url):
        return self.get(url)

    def get(self, url):
        last_error = None
        session = self._get_session()

        for attempt in range(self.max_retries):
            acquire_started = time.perf_counter()
            self._http_semaphore.acquire()
            self._record_semaphore_wait(url, time.perf_counter() - acquire_started)
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
                    self._record_terminal_error()
                    raise

                if attempt < self.max_retries - 1:
                    self._record_retry(
                        url=url,
                        error_type=type(error).__name__,
                        status_code=getattr(getattr(error, "response", None), "status_code", None),
                        elapsed=elapsed,
                        attempt=attempt,
                    )
                    retry_after_release = True
                else:
                    self._record_terminal_error()
            else:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=True, url=url)

                if attempt:
                    self._record_retry(
                        url=url,
                        error_type="retry_success",
                        status_code=getattr(response, "status_code", None),
                        elapsed=elapsed,
                        attempt=attempt,
                    )

                if hasattr(response, "text"):
                    return response.text
                return response
            finally:
                self._http_semaphore.release()

            if retry_after_release:
                self._record_retry_sleep(attempt + 1)
                time.sleep(attempt + 1)

        if last_error:
            raise last_error

    def post(self, url, data=None, headers=None):
        """POST using the same concurrency, retry and metrics pipeline as GET."""
        last_error = None
        session = self._get_session()
        request_headers = headers or self.headers

        for attempt in range(self.max_retries):
            acquire_started = time.perf_counter()
            self._http_semaphore.acquire()
            self._record_semaphore_wait(url, time.perf_counter() - acquire_started)
            started = time.perf_counter()
            self._begin_request(url)
            retry_after_release = False

            try:
                response = session.post(
                    url,
                    data=data,
                    headers=request_headers,
                    timeout=self.timeout,
                )
                if hasattr(response, "raise_for_status"):
                    response.raise_for_status()
            except requests.exceptions.RequestException as error:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=False, url=url)
                last_error = error

                if not self._is_retryable_error(error):
                    self._record_terminal_error()
                    raise

                if attempt < self.max_retries - 1:
                    self._record_retry(
                        url=url,
                        error_type=type(error).__name__,
                        status_code=getattr(getattr(error, "response", None), "status_code", None),
                        elapsed=elapsed,
                        attempt=attempt,
                    )
                    retry_after_release = True
                else:
                    self._record_terminal_error()
            else:
                elapsed = time.perf_counter() - started
                self._finish_request(elapsed, success=True, url=url)
                if attempt:
                    self._record_retry(
                        url=url,
                        error_type="retry_success",
                        status_code=getattr(response, "status_code", None),
                        elapsed=elapsed,
                        attempt=attempt,
                    )
                if hasattr(response, "text"):
                    return response.text
                return response
            finally:
                self._http_semaphore.release()

            if retry_after_release:
                self._record_retry_sleep(attempt + 1)
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

    @staticmethod
    def _request_class(url):
        url_text = str(url)
        if url_text.rstrip("/").casefold() == JETSMARTFILTERS_AJAX_URL.rstrip("/").casefold():
            return "jsf"
        if "/producto/" in url_text:
            return "detail"
        if "/categoria-producto/" in url_text or "/tienda/" in url_text:
            return "category"
        return "other"

    def _record_semaphore_wait(self, url, elapsed):
        request_class = self._request_class(url)
        with self._metrics_lock:
            if request_class == "detail":
                self._detail_semaphore_wait_seconds += elapsed
                self._detail_semaphore_max_wait_seconds = max(
                    self._detail_semaphore_max_wait_seconds,
                    elapsed,
                )
                self._detail_semaphore_wait_count += 1
            elif request_class == "category":
                self._category_semaphore_wait_seconds += elapsed
                self._category_semaphore_max_wait_seconds = max(
                    self._category_semaphore_max_wait_seconds,
                    elapsed,
                )
                self._category_semaphore_wait_count += 1
            elif request_class == "jsf":
                self._jsf_semaphore_wait_seconds += elapsed
                self._jsf_semaphore_max_wait_seconds = max(
                    self._jsf_semaphore_max_wait_seconds,
                    elapsed,
                )
                self._jsf_semaphore_wait_count += 1
            else:
                self._other_semaphore_wait_seconds += elapsed
                self._other_semaphore_max_wait_seconds = max(
                    self._other_semaphore_max_wait_seconds,
                    elapsed,
                )
                self._other_semaphore_wait_count += 1

    def _begin_request(self, url):
        with self._metrics_lock:
            self._http_requests += 1
            self._http_in_flight += 1
            self._http_max_in_flight = max(
                self._http_max_in_flight,
                self._http_in_flight,
            )

            request_class = self._request_class(url)
            if request_class == "detail":
                self._detail_http_requests += 1
            elif request_class == "category":
                self._category_http_requests += 1
            elif request_class == "jsf":
                self._jsf_http_requests += 1
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

            request_class = self._request_class(url)
            if request_class == "detail":
                self._detail_http_total_seconds += elapsed
                self._detail_http_max_seconds = max(
                    self._detail_http_max_seconds,
                    elapsed,
                )
            elif request_class == "category":
                self._category_http_total_seconds += elapsed
                self._category_http_max_seconds = max(
                    self._category_http_max_seconds,
                    elapsed,
                )
            elif request_class == "jsf":
                self._jsf_http_total_seconds += elapsed
                self._jsf_http_max_seconds = max(
                    self._jsf_http_max_seconds,
                    elapsed,
                )
            else:
                self._other_http_total_seconds += elapsed
                self._other_http_max_seconds = max(
                    self._other_http_max_seconds,
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

    def _record_retry(
        self,
        *,
        url=None,
        error_type=None,
        status_code=None,
        elapsed=0.0,
        attempt=0,
    ):
        with self._metrics_lock:
            self._http_retries += 1
            if url is not None and len(self._retry_events) < 20:
                self._retry_events.append(
                    {
                        "url": str(url),
                        "error_type": error_type,
                        "status_code": status_code,
                        "elapsed": float(elapsed),
                        "attempt": int(attempt),
                    }
                )

    def _record_retry_sleep(self, seconds):
        with self._metrics_lock:
            self._http_retry_sleep_seconds += float(seconds)
            self._http_retry_sleep_count += 1

    def _record_terminal_error(self):
        with self._metrics_lock:
            self._http_terminal_errors += 1

    def get_http_metrics(self):
        """Return accumulated HTTP timing and concurrency metrics."""
        with self._metrics_lock:
            return {
                "http_requests": self._http_requests,
                "http_successes": self._http_successes,
                "http_errors": self._http_errors,
                "http_terminal_errors": self._http_terminal_errors,
                "http_retries": self._http_retries,
                "http_retry_sleep_seconds": self._http_retry_sleep_seconds,
                "http_retry_sleep_count": self._http_retry_sleep_count,
                "http_total_seconds": self._http_total_seconds,
                "http_max_seconds": self._http_max_seconds,
                "http_in_flight": self._http_in_flight,
                "http_max_in_flight": self._http_max_in_flight,
                "max_concurrency": self._http_max_in_flight,
                "http_concurrency_limit": self.http_workers,
                "detail_http_requests": self._detail_http_requests,
                "category_http_requests": self._category_http_requests,
                "jsf_http_requests": self._jsf_http_requests,
                "other_http_requests": self._other_http_requests,
                "detail_http_total_seconds": self._detail_http_total_seconds,
                "category_http_total_seconds": self._category_http_total_seconds,
                "jsf_http_total_seconds": self._jsf_http_total_seconds,
                "other_http_total_seconds": self._other_http_total_seconds,
                "detail_http_max_seconds": self._detail_http_max_seconds,
                "category_http_max_seconds": self._category_http_max_seconds,
                "jsf_http_max_seconds": self._jsf_http_max_seconds,
                "other_http_max_seconds": self._other_http_max_seconds,
                "detail_semaphore_wait_seconds": self._detail_semaphore_wait_seconds,
                "category_semaphore_wait_seconds": self._category_semaphore_wait_seconds,
                "jsf_semaphore_wait_seconds": self._jsf_semaphore_wait_seconds,
                "other_semaphore_wait_seconds": self._other_semaphore_wait_seconds,
                "detail_semaphore_max_wait_seconds": self._detail_semaphore_max_wait_seconds,
                "category_semaphore_max_wait_seconds": self._category_semaphore_max_wait_seconds,
                "jsf_semaphore_max_wait_seconds": self._jsf_semaphore_max_wait_seconds,
                "other_semaphore_max_wait_seconds": self._other_semaphore_max_wait_seconds,
                "detail_semaphore_wait_count": self._detail_semaphore_wait_count,
                "category_semaphore_wait_count": self._category_semaphore_wait_count,
                "jsf_semaphore_wait_count": self._jsf_semaphore_wait_count,
                "other_semaphore_wait_count": self._other_semaphore_wait_count,
                "latency_buckets": dict(self._latency_buckets),
                "slowest_requests": list(self._slowest_requests),
                "retry_events": list(self._retry_events),
            }

    def reset_http_metrics(self):
        """Reset HTTP metrics before a new full scraping run."""
        with self._metrics_lock:
            self._http_requests = 0
            self._http_successes = 0
            self._http_errors = 0
            self._http_terminal_errors = 0
            self._http_retries = 0
            self._http_retry_sleep_seconds = 0.0
            self._http_retry_sleep_count = 0
            self._http_total_seconds = 0.0
            self._http_max_seconds = 0.0
            self._http_in_flight = 0
            self._http_max_in_flight = 0
            self._detail_http_requests = 0
            self._category_http_requests = 0
            self._jsf_http_requests = 0
            self._other_http_requests = 0
            self._detail_http_total_seconds = 0.0
            self._category_http_total_seconds = 0.0
            self._jsf_http_total_seconds = 0.0
            self._other_http_total_seconds = 0.0
            self._detail_http_max_seconds = 0.0
            self._category_http_max_seconds = 0.0
            self._jsf_http_max_seconds = 0.0
            self._other_http_max_seconds = 0.0
            self._detail_semaphore_wait_seconds = 0.0
            self._category_semaphore_wait_seconds = 0.0
            self._jsf_semaphore_wait_seconds = 0.0
            self._other_semaphore_wait_seconds = 0.0
            self._detail_semaphore_max_wait_seconds = 0.0
            self._category_semaphore_max_wait_seconds = 0.0
            self._jsf_semaphore_max_wait_seconds = 0.0
            self._other_semaphore_max_wait_seconds = 0.0
            self._detail_semaphore_wait_count = 0
            self._category_semaphore_wait_count = 0
            self._jsf_semaphore_wait_count = 0
            self._other_semaphore_wait_count = 0
            self._latency_buckets = {
                "lt_0_5": 0,
                "0_5_1": 0,
                "1_2": 0,
                "2_5": 0,
                "5_10": 0,
                "gte_10": 0,
            }
            self._slowest_requests = []
            self._retry_events = []
