"""Backend manifest and import boundaries for the frontend handoff."""
import importlib
import json
import pytest
from app.services.screener_v2.registry import feature_manifest


def test_all_eight_manifests_have_typed_inputs_and_resolvable_outputs():
    manifest = feature_manifest()
    assert [feature['id'] for feature in manifest] == [f'{i:02d}' for i in range(1, 9)]
    for feature in manifest:
        inputs = feature['inputs']
        assert len({item['key'] for item in inputs}) == len(inputs)
        assert all({'key', 'type', 'label', 'group', 'help', 'default'} <= item.keys() for item in inputs)
        assert all({'key', 'source', 'render', 'primary', 'label'} <= output.keys() for output in feature['outputs'])
        assert any(output['primary'] for output in feature['outputs'])
    json.dumps(manifest, allow_nan=False)


def test_retired_monolith_and_empty_packages_are_not_importable():
    for module in ['analytics', 'schemas', 'utils']:
        name = f'app.services.screener_v2.{module}' if module != 'analytics' else 'app.services.screener_v2.core.analytics'
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(name)
