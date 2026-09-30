"""Minimal robots.txt matcher with the `*` and `$` wildcards VOA's file relies on.

urllib.robotparser treats `Disallow: /*?p=*` as a literal prefix, so it would allow
every paginated URL. The longest matching rule wins; Allow wins a tie.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Rule:
    allow: bool
    pattern: str

    def regex(self) -> re.Pattern[str]:
        body = re.escape(self.pattern).replace(r"\*", ".*")
        return re.compile(body[:-2] + "$" if body.endswith(r"\$") else body)

    @property
    def length(self) -> int:
        return len(self.pattern)


@dataclass
class RobotsRules:
    rules: list[Rule] = field(default_factory=list)

    @classmethod
    def parse(cls, text: str, agent: str) -> "RobotsRules":
        """Rules of the group naming `agent` (substring match), else of the `*` group."""
        groups: list[tuple[list[str], list[Rule]]] = []
        agents: list[str] = []
        rules: list[Rule] = []
        last_was_agent = False
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].strip()
            key, sep, value = line.partition(":")
            if not sep:
                continue
            key, value = key.strip().lower(), value.strip()
            if key == "user-agent":
                if not last_was_agent:
                    agents, rules = [], []
                    groups.append((agents, rules))
                agents.append(value.lower())
                last_was_agent = True
                continue
            last_was_agent = False
            if key in ("allow", "disallow") and value:
                rules.append(Rule(key == "allow", value))
        agent = agent.lower()
        named = [r for names, r in groups if any(n != "*" and n in agent for n in names)]
        star = [r for names, r in groups if "*" in names]
        return cls((named or star or [[]])[0])

    def allowed(self, path_and_query: str) -> bool:
        best: Rule | None = None
        for rule in self.rules:
            if rule.regex().match(path_and_query) and (
                best is None
                or rule.length > best.length
                or (rule.length == best.length and rule.allow)
            ):
                best = rule
        return best is None or best.allow
