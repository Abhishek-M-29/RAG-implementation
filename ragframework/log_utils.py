"""Deprecated — use ragframework.observability.logging.configure_logging instead."""
import warnings

warnings.warn(
    "ragframework.log_utils is deprecated; use "
    "ragframework.observability.logging.configure_logging",
    DeprecationWarning,
    stacklevel=2,
)
