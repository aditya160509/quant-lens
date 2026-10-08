"""Authoritative declarations, strict controls and feature envelope regressions."""
import ast
from pathlib import Path

import pytest
from app.services.volatility_v2.registry import contract_for, feature_manifest, prepare_payload


def test_all_actual_response_outputs_are_declared():
    root = Path(__file__).parents[1] / 'app/services/volatility_v2/features'
    for contract in feature_manifest():
        keys = [field['key'] for field in contract['inputs']]
        assert len(keys) == len(set(keys))
        assert all({'label', 'type', 'group', 'default', 'help'} <= set(field) for field in contract['inputs'])
        declared = {(output['source'], output['key']) for output in contract['outputs']}
        assert declared
        tree = ast.parse((root / f"feature_{contract['id']}.py").read_text())
        actual = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'response':
                for keyword in node.keywords:
                    if keyword.arg in {'charts', 'tables'} and isinstance(keyword.value, ast.Dict):
                        actual.update((keyword.arg, key.value) for key in keyword.value.keys if isinstance(key, ast.Constant))
        assert actual == declared
        assert all(output['render'] in {'line', 'heatmap', 'table'} for output in contract['outputs'])


def test_strict_controls_reject_ignored_flags_and_invalid_values():
    for payload in [{'rolling_window': 0}, {'rolling_window': 2.5}, {'include_hourly_variation': 'maybe'},
                    {'annualization': float('nan')}, {'made_up': 1}]:
        with pytest.raises((ValueError, TypeError)):
            prepare_payload('01', payload)
    assert prepare_payload('09', {'gross_exposure_cap': '1.5', 'cash_rate_annual': '.02', 'breach_threshold': '.15'}) == {
        'gross_exposure_cap': 1.5, 'cash_rate_annual': .02, 'breach_threshold': .15}
    assert prepare_payload('03', {'forecast_horizons': '1,5', 'volatility_estimator': 'cc'}) == {'horizons': [1, 5], 'estimator': 'cc'}
    with pytest.raises(ValueError, match='Conflicting'):
        prepare_payload('01', {'rolling_window': 21, 'window_days': 42})
    copied = contract_for('01')
    copied['inputs'].clear()
    assert contract_for('01')['inputs']
