from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class Metric:
    label: str
    value: Any
    help: str | None = None


def section(title: str, help_text: str = "") -> None:
    st.subheader(title, help=help_text or None)


def empty_state(message: str) -> None:
    st.info(message)


def metric_row(items: Sequence[Metric | tuple[str, Any]]) -> None:
    metrics = [item if isinstance(item, Metric) else Metric(*item) for item in items]
    for column, metric in zip(st.columns(len(metrics)), metrics, strict=True):
        column.metric(metric.label, metric.value, help=metric.help)
