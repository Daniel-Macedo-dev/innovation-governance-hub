from typing import Any

import streamlit as st


def section(title: str, help_text: str = "") -> None:
    st.subheader(title, help=help_text or None)


def empty_state(message: str) -> None:
    st.info(message)


def metric_row(items: list[tuple[str, Any]]) -> None:
    for column, (label, value) in zip(st.columns(len(items)), items, strict=True):
        column.metric(label, value)
