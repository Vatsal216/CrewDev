from dataclasses import dataclass, field


@dataclass
class TokenTracker:
    """Provider-aware token + cost accumulator.

    Cost is supplied per call by the LLM router (LiteLLM's pricing map),
    so there is no hardcoded per-model pricing here.
    """
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    calls: int = 0
    by_agent: dict = field(default_factory=dict)

    def add(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        agent: str = "orchestrator",
        model: str = "",
    ):
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost_usd
        self.calls += 1
        a = self.by_agent.setdefault(agent, {"in": 0, "out": 0, "cost": 0.0, "model": model})
        a["in"] += input_tokens
        a["out"] += output_tokens
        a["cost"] = round(a["cost"] + cost_usd, 6)
        if model:
            a["model"] = model  # last-wins by design: v1 uses one model per session

    def add_usage(self, usage, agent: str = "orchestrator"):
        """Accept a router `Usage` (input_tokens, output_tokens, cost_usd, model)."""
        self.add(
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            cost_usd=getattr(usage, "cost_usd", 0.0),
            agent=agent,
            model=getattr(usage, "model", ""),
        )

    def over_budget(self, max_tokens: int) -> bool:
        return (self.input_tokens + self.output_tokens) >= max_tokens

    def summary(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.input_tokens + self.output_tokens,
            "calls": self.calls,
            "cost_usd": round(self.cost_usd, 6),
            "by_agent": self.by_agent,
        }
