"""AST-based export of Studio strategies into portable Python packages."""

from __future__ import annotations

import ast
import io
import textwrap
import zipfile
from typing import Any


_PLATFORM_ROOTS = {"quant360", "studio_v2", "app"}
_PORTABLE_IMPORTS = {"numpy", "pandas"}


class StandaloneExporter:
    @staticmethod
    def _import_root(node: ast.Import | ast.ImportFrom) -> str:
        if isinstance(node, ast.Import):
            return node.names[0].name.split(".")[0]
        return (node.module or "").split(".")[0]

    def transform(self, source_code: str) -> str:
        tree = ast.parse(source_code)
        functions = {
            node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        target_name = "generate_signals" if "generate_signals" in functions else "generate_signal"
        if target_name not in functions:
            raise ValueError("strategy must define generate_signals() or generate_signal()")

        required = {target_name}
        pending = [target_name]
        while pending:
            name = pending.pop()
            for node in ast.walk(functions[name]):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    candidate = node.func.id
                    if candidate in functions and candidate not in required:
                        required.add(candidate)
                        pending.append(candidate)

        body: list[ast.stmt] = []
        imported_names: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                root = self._import_root(node)
                if root in _PLATFORM_ROOTS:
                    continue
                if root not in _PORTABLE_IMPORTS:
                    raise ValueError(f"non-portable dependency '{root}' must be removed before export")
                body.append(node)
                for alias in node.names:
                    imported_names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in required:
                body.append(node)
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                body.append(node)

        exported = ast.Module(body=body, type_ignores=[])
        ast.fix_missing_locations(exported)
        source = ast.unparse(exported).strip() + "\n"
        reparsed = ast.parse(source)
        platform_names = {
            node.id for node in ast.walk(reparsed)
            if isinstance(node, ast.Name) and node.id in _PLATFORM_ROOTS
        }
        if platform_names:
            raise ValueError(f"platform references remain after export: {sorted(platform_names)}")
        return source

    def build_zip(
        self,
        strategy_name: str,
        source_code: str,
        default_config: dict[str, Any] | None = None,
    ) -> bytes:
        standalone = self.transform(source_code)
        requirements = "numpy>=1.24\npandas>=2.0\n"
        readme = textwrap.dedent(
            f"""
            # {strategy_name}

            This package was exported from Quant360 Studio V2.

            ## Input contract

            `generate_signals(ohlcv, config)` expects a pandas DataFrame indexed
            by timestamp with one price column per instrument. The function
            returns a DataFrame of portfolio weights aligned to the same index
            and columns.

            Default configuration:

            ```json
            {default_config or {}}
            ```

            Install dependencies with `pip install -r requirements.txt`.
            """
        ).strip() + "\n"
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("strategy_module.py", standalone)
            bundle.writestr("requirements.txt", requirements)
            bundle.writestr("README.md", readme)
        return archive.getvalue()
