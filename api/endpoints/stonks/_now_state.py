"""Shared in-memory state for the currently displayed stock/cycle."""

_current: dict = {"symbol": None, "cycle_key": None}
