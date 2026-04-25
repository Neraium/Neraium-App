"""
Math-aware agent workflows — Claude-powered reasoning over hard mathematical
problems that arise in the monitoring pipeline.

The core engine is deterministic and fast, but some customer problems require
reasoning that goes beyond fixed algorithms:

  • "Why is this sensor cluster causing instability?"  requires natural-language
    explanation of a complex multi-component drift pattern.
  • "What is the optimal action sequence to return this system to STABLE?"
    requires combining optimization, causal reasoning, and domain knowledge.
  • Independent verification: solve the same problem two ways and compare to
    catch silent errors.

MathAgent wraps the Claude API (via the Anthropic SDK) with a structured
protocol for:

  1. Task decomposition  — break a hard problem into solvable sub-tasks.
  2. Dynamic method selection  — choose symbolic / numeric / probabilistic
     based on problem characteristics.
  3. Self-checking  — derive the answer via two independent paths and flag
     disagreements.
  4. Explanation generation  — produce operator-facing natural-language
     summaries backed by the math.

Optional dependency: ``anthropic``  (pip install anthropic)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    import anthropic as _anthropic

    _ANTHROPIC_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ANTHROPIC_AVAILABLE = False
    _anthropic = None  # type: ignore[assignment]


def _require_anthropic() -> None:
    if not _ANTHROPIC_AVAILABLE:
        raise ImportError(
            "anthropic SDK is required for math agent workflows. "
            "Install it with:  pip install 'neraium-core[math-agents]'"
        )


# ---------------------------------------------------------------------------
# Default model
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "claude-opus-4-6"
_SYSTEM_PROMPT = """You are a precision mathematical reasoning engine embedded in
a structural instability monitoring system. Your role is to:

1. Decompose complex mathematical problems into well-defined sub-problems.
2. Choose the most appropriate mathematical method (symbolic algebra, numerical
   optimization, probabilistic inference, etc.) for each sub-problem.
3. Solve each sub-problem rigorously, showing your work.
4. Verify results using an independent method where possible.
5. Explain conclusions in clear, actionable language for plant operators.

Always structure your responses as JSON when asked to return structured data.
Flag any assumptions or limitations explicitly."""


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Result returned by a MathAgent task."""

    task: str
    answer: str
    reasoning_steps: list[str] = field(default_factory=list)
    method_used: str = "claude"
    self_check_passed: bool | None = None
    self_check_notes: str = ""
    structured_data: dict[str, Any] = field(default_factory=dict)
    model: str = DEFAULT_MODEL
    input_tokens: int = 0
    output_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "answer": self.answer,
            "reasoning_steps": self.reasoning_steps,
            "method_used": self.method_used,
            "self_check_passed": self.self_check_passed,
            "self_check_notes": self.self_check_notes,
            "structured_data": self.structured_data,
            "model": self.model,
            "tokens": {"input": self.input_tokens, "output": self.output_tokens},
        }


@dataclass
class DecompositionResult:
    """Output of the task decomposition step."""

    original_task: str
    sub_tasks: list[str]
    recommended_methods: list[str]
    dependencies: list[tuple[int, int]]  # (from_idx, to_idx) execution deps

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_task": self.original_task,
            "sub_tasks": self.sub_tasks,
            "recommended_methods": self.recommended_methods,
            "dependencies": self.dependencies,
        }


# ---------------------------------------------------------------------------
# Core agent
# ---------------------------------------------------------------------------


class MathAgent:
    """
    Math-aware Claude agent for hard reasoning tasks in the monitoring pipeline.

    Parameters
    ----------
    model : str
        Claude model ID.  Defaults to ``claude-opus-4-6``.
    api_key : str | None
        Anthropic API key.  If None, reads ``ANTHROPIC_API_KEY`` from env.
    max_tokens : int
        Maximum tokens per response.
    self_check : bool
        If True, verify each answer via an independent derivation path.

    Example
    -------
    >>> agent = MathAgent()
    >>> result = agent.explain_instability(
    ...     components={"relational_drift": 2.1, "spectral": 1.8, ...},
    ...     state="ALERT",
    ...     context="Cannabis grow facility, temperature sensor cluster 3",
    ... )
    >>> print(result.answer)
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        api_key: str | None = None,
        max_tokens: int = 2048,
        self_check: bool = True,
    ) -> None:
        _require_anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.self_check = self_check
        self._client: Any = _anthropic.Anthropic(api_key=api_key)  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def explain_instability(
        self,
        components: dict[str, float],
        state: str,
        context: str = "",
        score: float | None = None,
    ) -> AgentResult:
        """
        Generate a natural-language explanation of the current instability state.

        Combines the raw component values with mathematical reasoning to
        produce an operator-facing explanation of *what* is happening,
        *why* the specific components are elevated, and *what* actions
        would reduce risk.
        """
        top_components = sorted(
            components.items(), key=lambda kv: kv[1], reverse=True
        )[:4]
        top_str = ", ".join(f"{k}={v:.3f}" for k, v in top_components)

        prompt = (
            f"The structural monitoring system has classified state as {state}.\n"
            f"Composite instability score: {score if score is not None else 'N/A'}\n"
            f"Top driving components: {top_str}\n"
            f"All components: {json.dumps(components, indent=2)}\n"
        )
        if context:
            prompt += f"Operational context: {context}\n"

        prompt += (
            "\nProvide:\n"
            "1. A concise explanation of what the numbers mean physically.\n"
            "2. Which component is the primary driver and why.\n"
            "3. Two or three concrete actions to reduce instability.\n"
            "Keep the response under 200 words, suitable for an operator dashboard."
        )

        return self._run_task("explain_instability", prompt)

    def decompose_task(self, task_description: str) -> DecompositionResult:
        """
        Decompose a complex math task into ordered sub-tasks with method recommendations.

        Returns a structured DecompositionResult listing sub-tasks and the
        mathematical method recommended for each (symbolic, numeric, probabilistic, etc.).
        """
        prompt = (
            f"Decompose the following mathematical problem into sub-tasks.\n"
            f"Problem: {task_description}\n\n"
            f"Return your response as JSON with this exact schema:\n"
            f'{{"sub_tasks": ["task1", "task2", ...], '
            f'"recommended_methods": ["method1", "method2", ...], '
            f'"dependencies": [[0, 1], ...]}}\n'
            f"Where dependencies are [from_index, to_index] pairs indicating "
            f"which sub-tasks must complete before others."
        )

        result = self._run_task("decompose", prompt, expect_json=True)

        try:
            data = result.structured_data
            return DecompositionResult(
                original_task=task_description,
                sub_tasks=data.get("sub_tasks", []),
                recommended_methods=data.get("recommended_methods", []),
                dependencies=[(a, b) for a, b in data.get("dependencies", [])],
            )
        except Exception as exc:
            logger.warning("decompose_task: could not parse structured response: %s", exc)
            return DecompositionResult(
                original_task=task_description,
                sub_tasks=[task_description],
                recommended_methods=["numeric"],
                dependencies=[],
            )

    def select_method(
        self,
        problem_description: str,
        available_methods: list[str] | None = None,
    ) -> str:
        """
        Dynamically select the most appropriate mathematical method for a problem.

        Returns one of: "symbolic", "numeric", "probabilistic", "optimization",
        "verification", or "hybrid".
        """
        methods = available_methods or [
            "symbolic", "numeric", "probabilistic",
            "optimization", "verification", "hybrid",
        ]
        prompt = (
            f"Given the following problem, select the single best mathematical method.\n"
            f"Problem: {problem_description}\n"
            f"Available methods: {', '.join(methods)}\n\n"
            f"Consider:\n"
            f"- Use 'symbolic' for exact closed-form solutions.\n"
            f"- Use 'numeric' for iterative / approximate solutions.\n"
            f"- Use 'probabilistic' when uncertainty quantification matters.\n"
            f"- Use 'optimization' for planning or threshold tuning.\n"
            f"- Use 'verification' for checking correctness of existing results.\n"
            f"- Use 'hybrid' when multiple approaches are needed.\n\n"
            f"Reply with ONLY the method name, nothing else."
        )
        result = self._run_task("select_method", prompt)
        chosen = result.answer.strip().lower()
        if chosen not in methods:
            chosen = "hybrid"
        return chosen

    def self_check_result(
        self,
        problem: str,
        answer: str,
        method_used: str = "numeric",
    ) -> tuple[bool, str]:
        """
        Verify ``answer`` using an independent derivation path.

        Returns (passed: bool, notes: str).
        """
        prompt = (
            f"A math problem was solved using the '{method_used}' method.\n"
            f"Problem: {problem}\n"
            f"Claimed answer: {answer}\n\n"
            f"Verify this answer using a DIFFERENT approach from '{method_used}'.\n"
            f"Return JSON: {{\"agrees\": true/false, \"verification_method\": \"...\", "
            f"\"notes\": \"...\"}}"
        )
        result = self._run_task("self_check", prompt, expect_json=True)
        data = result.structured_data
        agrees = bool(data.get("agrees", True))
        notes = str(data.get("notes", ""))
        return agrees, notes

    def solve(
        self,
        problem: str,
        context: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        General-purpose math problem solver with optional self-check.

        Solves ``problem`` step by step, then verifies the result via an
        independent method if ``self_check=True``.
        """
        ctx_str = ""
        if context:
            ctx_str = f"\nContext data: {json.dumps(context, indent=2)}"

        prompt = (
            f"Solve the following mathematical problem step by step.{ctx_str}\n\n"
            f"Problem: {problem}\n\n"
            f"Show your reasoning clearly. After solving, state the final answer on "
            f"a line beginning with 'ANSWER:'"
        )

        result = self._run_task("solve", prompt)

        # Extract reasoning steps (lines before ANSWER:)
        lines = result.answer.split("\n")
        steps = [line for line in lines if not line.startswith("ANSWER:")]
        answer_lines = [line for line in lines if line.startswith("ANSWER:")]
        final_answer = answer_lines[-1].replace("ANSWER:", "").strip() if answer_lines else result.answer
        result.reasoning_steps = [s.strip() for s in steps if s.strip()]

        if self.self_check:
            passed, notes = self.self_check_result(problem, final_answer)
            result.self_check_passed = passed
            result.self_check_notes = notes
            if not passed:
                logger.warning(
                    "MathAgent self-check disagreement on task '%s': %s",
                    problem[:80],
                    notes,
                )

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_task(
        self,
        task_name: str,
        prompt: str,
        expect_json: bool = False,
    ) -> AgentResult:
        messages = [{"role": "user", "content": prompt}]
        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=_SYSTEM_PROMPT,
                messages=messages,
            )
            text = response.content[0].text if response.content else ""
            input_tokens = getattr(response.usage, "input_tokens", 0)
            output_tokens = getattr(response.usage, "output_tokens", 0)

            structured: dict[str, Any] = {}
            if expect_json:
                structured = _extract_json(text)

            return AgentResult(
                task=task_name,
                answer=text,
                method_used="claude",
                structured_data=structured,
                model=self.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except Exception as exc:
            logger.error("MathAgent._run_task('%s') failed: %s", task_name, exc)
            return AgentResult(
                task=task_name,
                answer=f"[MathAgent error: {exc}]",
                model=self.model,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract the first JSON object from a free-form text response.
    Returns empty dict on failure.
    """
    import re

    # Try to find a JSON block (```json ... ``` or raw {...})
    patterns = [
        r"```json\s*([\s\S]+?)\s*```",
        r"```\s*([\s\S]+?)\s*```",
        r"(\{[\s\S]+\})",
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    return {}


# ---------------------------------------------------------------------------
# Convenience: pipeline-level math reasoning
# ---------------------------------------------------------------------------


class PipelineMathReasoner:
    """
    Higher-level wrapper that combines MathAgent with the other math engines
    to answer questions about a specific processed result.

    Designed to be called from the service layer to attach rich math
    reasoning to outputs when requested.
    """

    def __init__(self, agent: MathAgent | None = None) -> None:
        self._agent = agent or MathAgent()

    def annotate_result(
        self,
        result: dict[str, Any],
        customer_context: str = "",
    ) -> dict[str, Any]:
        """
        Attach a math_reasoning block to a pipeline result dict.

        Adds:
          - explanation: natural-language instability explanation.
          - boundary_distances: how far each component is from state boundaries.
          - method_recommendation: which math method is best for follow-up.
        """
        components = result.get("components", {})
        state = result.get("state", "UNKNOWN")
        score = result.get("structural_drift_score")

        explanation_result = self._agent.explain_instability(
            components=components,
            state=state,
            score=score,
            context=customer_context,
        )

        result["math_reasoning"] = {
            "explanation": explanation_result.answer,
            "model": explanation_result.model,
            "tokens": {
                "input": explanation_result.input_tokens,
                "output": explanation_result.output_tokens,
            },
        }
        return result
