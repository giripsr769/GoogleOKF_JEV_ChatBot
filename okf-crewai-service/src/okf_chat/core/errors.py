"""Errors shared between the framework-free core and the agent layer."""


class LlmError(Exception):
    """The language model could not be reached, timed out, or returned something unusable."""
