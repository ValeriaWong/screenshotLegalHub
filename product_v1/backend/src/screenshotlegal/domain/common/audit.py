"""Request identity shared across product adapters; never contains credentials."""
from contextvars import ContextVar
operation_context=ContextVar('operation_context',default={})
