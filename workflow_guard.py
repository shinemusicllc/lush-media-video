"""Workflow normalization guards shared by web and Telegram submissions."""

from __future__ import annotations

import logging
from typing import Any

import config

logger = logging.getLogger("workflow_guard")


def enforce_locked_diffusion_models(workflow: dict[str, Any]) -> int:
    """Force high/low UNETLoader model names to the configured locked models."""
    changed = 0
    for node in _iter_nodes(workflow):
        if not _is_unet_loader(node):
            continue

        inputs = node.get("inputs")
        if isinstance(inputs, dict):
            current = inputs.get("unet_name")
            locked = _locked_model_for_name(current)
            if locked and current != locked:
                inputs["unet_name"] = locked
                changed += 1
            continue

        widgets = node.get("widgets_values")
        if isinstance(widgets, list) and widgets:
            locked = _locked_model_for_name(widgets[0])
            if locked and widgets[0] != locked:
                widgets[0] = locked
                changed += 1

    return changed


def _iter_nodes(workflow: dict[str, Any]):
    nodes = workflow.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if isinstance(node, dict):
                yield node

    for node in workflow.values():
        if isinstance(node, dict):
            yield node


def _is_unet_loader(node: dict[str, Any]) -> bool:
    return node.get("class_type") == "UNETLoader" or node.get("type") == "UNETLoader"


def _locked_model_for_name(value: Any) -> str | None:
    name = str(value or "").lower()
    if "high_noise" in name or "a14b-high" in name or "high_fp8" in name:
        return config.LOCKED_HIGH_DIFFUSION_MODEL
    if "low_noise" in name or "a14b-low" in name or "low_fp8" in name:
        return config.LOCKED_LOW_DIFFUSION_MODEL
    return None
