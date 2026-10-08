"""Compatibility facade for the authoritative per-feature declarations."""

from ..registry import contract_for as contract_for, feature_manifest


def all_contracts():
    return feature_manifest()
