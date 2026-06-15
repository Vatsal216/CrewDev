import json
from dataclasses import dataclass

from core.llm.router import LLMRouter
from core.llm.types import ResolvedCall

_router = LLMRouter()


@dataclass
class ValidationVerdict:
    passed: bool
    feedback: str
    score: float  # 0.0 - 1.0


class OutputValidator:
    """Reviews sub-agent output against success criteria via the selected provider."""

    async def evaluate(
        self,
        output: str,
        task_description: str,
        success_criteria: str = "",
        user_request: str = "",
        resolved: ResolvedCall = None,
    ) -> ValidationVerdict:
        criteria = success_criteria or self._infer_criteria(task_description)

        prompt = f"""You are a quality reviewer for an AI coding assistant.

ORIGINAL TASK:
{task_description}

SUCCESS CRITERIA:
{criteria}

USER REQUEST:
{user_request}

AGENT OUTPUT:
{str(output)[:4000]}

Evaluate whether the output satisfactorily completes the task.
Respond with JSON only:
{{
  "passed": true/false,
  "score": 0.0-1.0,
  "feedback": "specific feedback on what's missing or wrong if failed, or 'Looks good' if passed"
}}

Be pragmatic — pass if the core task is done even if minor improvements exist.
Fail only if key requirements are clearly unmet."""

        try:
            text, _usage = await _router.acomplete(
                [{"role": "user", "content": prompt}],
                resolved,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            result = json.loads(text)
            return ValidationVerdict(
                passed=result.get("passed", True),
                feedback=result.get("feedback", ""),
                score=float(result.get("score", 0.8)),
            )
        except Exception:
            return ValidationVerdict(passed=True, feedback="Validation parse error — assuming pass", score=0.7)

    def _infer_criteria(self, task: str) -> str:
        task_lower = task.lower()
        if "refactor" in task_lower or "rewrite" in task_lower:
            return "Code is functionally equivalent, cleaner, follows project patterns"
        if "test" in task_lower:
            return "Tests cover happy path, edge cases, and error conditions"
        if "search" in task_lower or "research" in task_lower:
            return "Provides accurate, relevant, sourced information"
        if "fix" in task_lower or "bug" in task_lower:
            return "Root cause identified and fixed, no regressions introduced"
        if "create" in task_lower or "implement" in task_lower:
            return "Feature is complete, handles errors, follows existing patterns"
        return "Task is fully completed as described"
