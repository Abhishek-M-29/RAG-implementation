import logging
import time

import google.api_core.exceptions
import requests.exceptions
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ragframework.observability.metrics import record_retry_attempt, record_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transient vs. non-transient error classification
# ---------------------------------------------------------------------------
# Transient errors are safe to retry: rate limits, temporary server
# unavailability, connection-level failures.
TRANSIENT_EXCEPTIONS = (
    google.api_core.exceptions.ResourceExhausted,
    google.api_core.exceptions.ServiceUnavailable,
    google.api_core.exceptions.InternalServerError,
    google.api_core.exceptions.DeadlineExceeded,
    ConnectionError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)

# Non-transient errors (not retried): auth/configuration failures,
# bad-request errors, and anything else that would never succeed on retry.
# These are listed explicitly for documentation and used to define
# the inverse of the transient set.
NON_TRANSIENT_EXCEPTIONS = (
    google.api_core.exceptions.Unauthenticated,
    google.api_core.exceptions.PermissionDenied,
    google.api_core.exceptions.InvalidArgument,
    google.api_core.exceptions.NotFound,
    google.api_core.exceptions.FailedPrecondition,
    google.api_core.exceptions.AlreadyExists,
    google.api_core.exceptions.OutOfRange,
)


def _is_transient(exc: BaseException) -> bool:
    return isinstance(exc, TRANSIENT_EXCEPTIONS)


def _before_retry(retry_state):
    logger.warning(
        "Retrying after transient error (attempt %d/%d)",
        retry_state.attempt_number, 3,
        extra={"error": str(retry_state.outcome.exception())},
    )
    record_retry_attempt("generation")


_retry_decorator = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_transient),
    reraise=True,
    before_sleep=_before_retry,
)


# ---------------------------------------------------------------------------
# Retryable wrapper for BaseChatModel
# ---------------------------------------------------------------------------

class RetryableChatModel(BaseChatModel):
    """Wraps a ``BaseChatModel`` with tenacity exponential-backoff retry.

    Only transient API errors (rate limits, transient 5xx, connection
    resets) are retried.  Authentication/configuration errors
    (Unauthenticated, PermissionDenied, InvalidArgument, …) are **not**
    retried — they fail immediately so the caller gets a clear error
    instead of a slow, ultimately failed retry cycle.
    """

    def __init__(self, inner: BaseChatModel, **kwargs):
        super().__init__(**kwargs)
        self._inner = inner

    @property
    def _llm_type(self) -> str:
        return self._inner._llm_type

    @property
    def model(self) -> str:
        inner_model = getattr(self._inner, "model", "")
        return inner_model if isinstance(inner_model, str) else str(inner_model)

    @property
    def model_name(self) -> str:
        return (
            getattr(self._inner, "model_name", "")
            or self.model
            or "unknown"
        )

    def _generate(
        self,
        messages,
        stop=None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        return _retry_call(
            self._inner._generate,
            messages,
            stop=stop,
            run_manager=run_manager,
            **kwargs,
        )

    def stream(self, input, config=None, **kwargs):
        return self._stream_with_retry(input, config=config, **kwargs)

    def _stream_with_retry(self, input, config=None, **kwargs):
        """Stream from the inner model, retrying to *establish* the stream.

        Once the first chunk has been yielded, mid-stream failures are
        **not** retried (to avoid duplicate output to the client).
        """
        attempt = 0
        max_attempts = 3
        last_exception = None
        while attempt < max_attempts:
            try:
                stream_iter = self._inner.stream(input, config=config, **kwargs)
                first = True
                for chunk in stream_iter:
                    if first:
                        first = False
                    yield chunk
                return
            except TRANSIENT_EXCEPTIONS as e:
                attempt += 1
                last_exception = e
                record_retry_attempt("generation")
                if attempt >= max_attempts:
                    logger.error(
                        "Stream failed after %d retries",
                        max_attempts,
                        extra={"error": str(e)},
                    )
                    record_error("generation", "retry_exhausted")
                    raise
                record_error("generation", "transient_retry")
                wait = min(10, 2 ** attempt)
                logger.warning(
                    "Stream attempt %d failed, retrying in %.1fs",
                    attempt, wait,
                    extra={"error": str(e)},
                )
                time.sleep(wait)

    def _stream(self, *args, **kwargs):
        return self._inner._stream(*args, **kwargs)


@_retry_decorator
def _retry_call(func, *args, **kwargs):
    return func(*args, **kwargs)
