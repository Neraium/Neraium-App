"""Evidence-bound operational reasoning package.

This layer must answer strictly from admitted system context and always
separate observed facts, inference, insufficient evidence, and operational
implication.
"""

from .context_builder import build_admitted_events, build_reasoning_context
from .models import AdmittedEvent
from .reasoner import generate_reasoned_response

__all__ = ["AdmittedEvent", "build_admitted_events", "build_reasoning_context", "generate_reasoned_response"]
