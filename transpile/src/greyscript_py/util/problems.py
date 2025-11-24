"""Collect errors."""

import importlib.resources
import json
from collections.abc import Iterable, Sequence
from typing import NamedTuple, Literal

from .jdata import DictJsonData, JsonData
from .source import Source

__all__ = ("ProblemLevel", "ConvertProblem", "Problems", "ProblemMessages")

ProblemLevel = Literal["error", "warning", "informative"]


class ConvertProblem(NamedTuple):
    """General top-level record of a problem with a conversion."""

    level: ProblemLevel
    message_id: str
    source: Source
    parameters: DictJsonData


class Problems:
    """Collection of errors."""

    def __init__(self) -> None:
        self._problems: list[ConvertProblem] = []

    def add_from(self, problems: "Problems") -> None:
        """Add all the problems from the collection."""
        self._problems.extend(problems._problems)

    def add_err(
        self, __source: Source, __message_id: str, /, **kwargs: JsonData
    ) -> None:
        """Add an error."""
        self._problems.append(
            ConvertProblem(
                level="error",
                message_id=__message_id,
                source=__source,
                parameters=kwargs,
            )
        )

    def add_warn(
        self, __source: Source, __message_id: str, /, **kwargs: JsonData
    ) -> None:
        """Add a warning."""
        self._problems.append(
            ConvertProblem(
                level="warning",
                message_id=__message_id,
                source=__source,
                parameters=kwargs,
            )
        )

    def add_info(self, __source: Source, __message_id: str, **kwargs: JsonData) -> None:
        """Add an informative message."""
        self._problems.append(
            ConvertProblem(
                level="informative",
                message_id=__message_id,
                source=__source,
                parameters=kwargs,
            )
        )

    @property
    def all(self) -> Sequence[ConvertProblem]:
        """Get all the contained problems."""
        return self._problems

    @property
    def errors(self) -> Iterable[ConvertProblem]:
        """Get all the contained errors."""
        return filter(
            lambda x: x.level == "error",
            self._problems,
        )

    def __repr__(self) -> str:
        return repr(self._problems)


class ProblemMessages:
    """Catalog of problem messages."""

    def __init__(self, data: DictJsonData) -> None:
        self.data = data

    def format(self, problem: ConvertProblem) -> str:
        """Format the problem into a printable string."""
        params = dict(problem.parameters)
        msg = self.data.get(problem.message_id, {})
        if not isinstance(msg, dict):
            raise RuntimeError(
                f"message catalog has incorrect format: {problem.message_id}"
            )
        sub = msg.get("subject", f"[{problem.message_id}]")
        if not isinstance(sub, str):
            raise RuntimeError(
                f"message catalog has incorrect format: {problem.message_id}.subject"
            )
        desc = msg.get("details", "[unknown message]")
        if not isinstance(desc, str):
            raise RuntimeError(
                f"message catalog has incorrect format: {problem.message_id}.details"
            )
        msg_params = msg.get("params", {})
        if not isinstance(msg_params, dict):
            raise RuntimeError(
                f"message catalog has incorrect format: {problem.message_id}.params"
            )
        for key, val in msg_params.items():
            if key not in params:
                if isinstance(val, dict) and "default" in val:
                    params[key] = val["default"]
                else:
                    params[key] = "(not set)"
        sub = sub.format(**params)
        desc = desc.format(**params)
        return f"{problem.source} [{problem.level}] {sub}.  {desc}"

    @staticmethod
    def load_messages() -> "ProblemMessages":
        """Load the message catalog."""
        inp_file = importlib.resources.files(__package__) / "problem_messages.json"
        with inp_file.open("rb") as f:
            return ProblemMessages(json.load(f))
