"""Make CrewAI safe to run inside a server. Import this BEFORE crewai.

CrewAI otherwise prints a tracing opt-in box, phones home with telemetry, checks for new versions, and its console
formatter crashes on emoji when stdout is a Windows cp1252 console. Every default can still be overridden by setting
the environment variable yourself before starting the service.
"""
import os
import sys

_DEFAULTS = {
    "CREWAI_TRACING_ENABLED": "false",
    "CREWAI_DISABLE_TELEMETRY": "true",
    "CREWAI_DISABLE_TRACKING": "true",
    "OTEL_SDK_DISABLED": "true",
    "CREWAI_NONINTERACTIVE": "true",
    "CREWAI_DISABLE_VERSION_CHECK": "true",
}


def suppress_console() -> None:
    """CrewAI's event listener prints panels even with verbose=False. The switch is a context variable, so call this
    in every context that runs an agent (it is cheap); importing this module does it for the main context."""
    try:
        from crewai_core.printer import set_suppress_console_output
        set_suppress_console_output(True)
    except ImportError:
        pass  # a CrewAI version without the switch: nothing to suppress


def quiet_crewai() -> None:
    for key, value in _DEFAULTS.items():
        os.environ.setdefault(key, value)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass  # not a real console (for example under pytest capture): nothing to fix


quiet_crewai()
suppress_console()
