"""Shared operations for displaying validated filters in Qt controls."""

from PySide6.QtCore import Qt


def set_checked_items(items, selected):
    selected = set(selected or [])
    for value, item in items.items():
        item.setCheckState(
            Qt.CheckState.Checked if value in selected else Qt.CheckState.Unchecked
        )


def set_range_inputs(minimum_input, maximum_input, value, *, date_values=False):
    if value is None or isinstance(value, list):
        return
    for control, bound in ((minimum_input, value.minimum), (maximum_input, value.maximum)):
        if bound is not None:
            control.setText(bound.strftime("%m-%d-%Y") if date_values else f"{bound:g}")
