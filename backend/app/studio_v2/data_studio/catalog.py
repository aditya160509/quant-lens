from __future__ import annotations

"""
Data Catalog, Custom Upload, Freshness Monitor (F6.6, F6.9-F6.10).

Searchable source catalog with quality tracking. Bounded CSV, JSON, and
Parquet upload with schema validation and atomic owner-scoped storage.
Daily freshness status board with amber/red alerts.
"""

import csv
import hashlib
import io
import json
import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, Iterator, List, Optional

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..shared import data_loader


@dataclass
class SourceEntry:
    name: str
    source_type: str
    coverage_universe: str = ""
    date_range: str = ""
    update_frequency: str = ""
    last_successful_update: Optional[str] = None
    quality_issues: List[str] = None
    access_expression: str = ""
    path: Optional[str] = None
    freshness_slo_trading_days: int = 1
    def __post_init__(self) -> None:
        if self.quality_issues is None: self.quality_issues = []
    def to_dict(self) -> dict: return asdict(self)


@dataclass
class UploadResult:
    success: bool
    source_name: str
    fields: List[str]
    validation_report: dict
    storage_key: Optional[str] = None
    format: Optional[str] = None
    size_bytes: int = 0
    checksum_sha256: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    governance: Optional[dict] = None
    error: Optional[str] = None


class UploadValidationError(ValueError):
    """Raised when an uploaded dataset is unsafe or violates its schema contract."""


class UploadTooLargeError(UploadValidationError):
    """Raised before parsing when an upload exceeds the configured byte ceiling."""


class UploadQuotaExceededError(UploadValidationError):
    """Raised before publication when the owner's storage quota would be exceeded."""


@dataclass
class FreshnessStatus:
    source_name: str
    last_update: Optional[str]
    lag_trading_days: Optional[int]
    status: str
    error: Optional[str] = None
    data_as_of: Optional[str] = None
    freshness_slo_trading_days: int = 1
    slo_breached: bool = False


class DataCatalog:
    def __init__(self) -> None:
        self.sources: Dict[str, SourceEntry] = {}
        self._seed()

    def _seed(self) -> None:
        self.register_source("market_universe", "OHLCV", {"coverage_universe": "4,158 tickers", "date_range": "1996-present", "update_frequency": "daily", "access_expression": "get_ohlcv(ticker, start, end)", "path": str(data_loader.UNIVERSE_PATH), "freshness_slo_trading_days": 1})
        self.register_source("category7_macro", "macro", {"coverage_universe": "21 macro series", "date_range": "1990-present", "update_frequency": "daily", "access_expression": "get_macro(series_name, start, end)", "path": str(data_loader.CATEGORY7_PATH), "freshness_slo_trading_days": 2})
        self.register_source("ff3", "factor", {"coverage_universe": "US factors", "date_range": "", "update_frequency": "daily", "access_expression": "get_factor_returns('ff3')", "path": str(data_loader.FF3_PATH), "freshness_slo_trading_days": 2})
        self.register_source("ff5", "factor", {"coverage_universe": "US factors", "date_range": "", "update_frequency": "daily", "access_expression": "get_factor_returns('ff5')", "path": str(data_loader.FF5_PATH if data_loader.FF5_PATH.exists() else data_loader.FF5_PATH.with_suffix(".csv")), "freshness_slo_trading_days": 2})
        self.register_source("momentum", "factor", {"coverage_universe": "US momentum", "date_range": "", "update_frequency": "daily", "access_expression": "get_factor_returns('momentum')", "path": str(data_loader.MOM_PATH if data_loader.MOM_PATH.exists() else data_loader.MOM_PATH.with_suffix(".csv")), "freshness_slo_trading_days": 2})
        self.register_source("fundamentals", "reference", {"coverage_universe": "4,158 tickers", "date_range": "", "update_frequency": "quarterly", "access_expression": "get_market_cap(ticker, date)", "path": str(data_loader.FUNDAMENTALS_PATH), "freshness_slo_trading_days": 70})
        for asset_class, slo in (("crypto", 1), ("fx", 2), ("futures", 2)):
            self.register_source(asset_class, "multi_asset", {"coverage_universe": asset_class, "date_range": "", "update_frequency": "daily", "access_expression": f"get_returns(..., asset_class='{asset_class}')", "path": str(data_loader.CANONICAL_PATH / f"{asset_class}_daily.parquet"), "freshness_slo_trading_days": slo})

    def register_source(self, name: str, source_type: str, metadata: dict) -> None:
        self.sources[name] = SourceEntry(name, source_type, **{key: value for key, value in metadata.items() if key in {field for field in SourceEntry.__dataclass_fields__ if field != "name" and field != "source_type"}})

    def get_catalog(self, filters: Optional[dict] = None) -> List[SourceEntry]:
        filters = filters or {}; entries = list(self.sources.values())
        return [entry for entry in entries if all(str(getattr(entry, key, "")).lower() == str(value).lower() for key, value in filters.items() if hasattr(entry, key))]

    def search_catalog(self, query: str) -> List[SourceEntry]:
        needle = str(query or "").lower(); return [entry for entry in self.sources.values() if needle in str(entry.to_dict()).lower()]

    def get_source_quality(self, name: str) -> dict:
        entry = self.sources[name]; path = Path(entry.path) if entry.path else None; issues = list(entry.quality_issues); exists = bool(path and path.exists()); return {"source": name, "exists": exists, "issues": issues + ([] if exists else [f"file not found: {entry.path}"]), "rows": len(data_loader.get_all_tickers()) if name == "market_universe" and exists else None}

    def get_coverage_summary(self) -> pd.DataFrame:
        return pd.DataFrame([entry.to_dict() for entry in self.sources.values()])

    def get_data_access_expression(self, source_name: str) -> str:
        return self.sources[source_name].access_expression


class CustomDataUploader:
    """Validate and atomically publish bounded, owner-scoped tabular uploads."""

    SUPPORTED_EXTENSIONS = frozenset({".csv", ".json", ".parquet"})
    DEFAULT_MAX_FILE_BYTES = 25 * 1024 * 1024
    DEFAULT_OWNER_QUOTA_BYTES = 250 * 1024 * 1024
    DEFAULT_MAX_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
    DEFAULT_MAX_ROWS = 1_000_000
    DEFAULT_MAX_COLUMNS = 256
    DEFAULT_RETENTION_DAYS = 90
    MIN_RETENTION_DAYS = 1
    MAX_RETENTION_DAYS = 3650
    _EICAR_SIGNATURE = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
    _FORBIDDEN_FILE_MAGIC = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe")
    _OWNER_WRITE_LOCK = Lock()
    _NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,99}$")
    _TICKER_PATTERN = re.compile(r"^[A-Z0-9^=./:_-]{1,40}$")

    def __init__(
        self,
        catalog: Optional[DataCatalog] = None,
        output_dir: Optional[str] = None,
        *,
        max_file_bytes: Optional[int] = None,
        owner_quota_bytes: Optional[int] = None,
        max_uncompressed_bytes: Optional[int] = None,
        max_rows: Optional[int] = None,
        max_columns: Optional[int] = None,
    ) -> None:
        self.catalog = catalog or DataCatalog()
        configured_dir = output_dir or os.getenv("STUDIO_V2_CUSTOM_UPLOAD_DIR")
        self.output_dir = Path(
            configured_dir or (Path(data_loader.UNIVERSE_PATH).parent / "custom")
        )
        self.max_file_bytes = self._positive_limit(
            max_file_bytes,
            "STUDIO_V2_CUSTOM_UPLOAD_MAX_BYTES",
            self.DEFAULT_MAX_FILE_BYTES,
        )
        self.owner_quota_bytes = self._positive_limit(
            owner_quota_bytes,
            "STUDIO_V2_CUSTOM_UPLOAD_QUOTA_BYTES",
            self.DEFAULT_OWNER_QUOTA_BYTES,
        )
        self.max_uncompressed_bytes = self._positive_limit(
            max_uncompressed_bytes,
            "STUDIO_V2_CUSTOM_UPLOAD_MAX_UNCOMPRESSED_BYTES",
            self.DEFAULT_MAX_UNCOMPRESSED_BYTES,
        )
        self.max_rows = self._positive_limit(
            max_rows, "STUDIO_V2_CUSTOM_UPLOAD_MAX_ROWS", self.DEFAULT_MAX_ROWS
        )
        self.max_columns = self._positive_limit(
            max_columns,
            "STUDIO_V2_CUSTOM_UPLOAD_MAX_COLUMNS",
            self.DEFAULT_MAX_COLUMNS,
        )
        self.registered_fields: set[str] = set()

    @classmethod
    def _retention_days(cls, value: Optional[int]) -> int:
        configured = value if value is not None else os.getenv(
            "STUDIO_V2_CUSTOM_UPLOAD_RETENTION_DAYS", str(cls.DEFAULT_RETENTION_DAYS)
        )
        try:
            days = int(configured)
        except (TypeError, ValueError) as exc:
            raise UploadValidationError("retention_days must be an integer") from exc
        if not cls.MIN_RETENTION_DAYS <= days <= cls.MAX_RETENTION_DAYS:
            raise UploadValidationError(
                f"retention_days must be between {cls.MIN_RETENTION_DAYS} and {cls.MAX_RETENTION_DAYS}"
            )
        return days

    @classmethod
    def _scan_content(cls, content: bytes) -> dict:
        """Run the built-in bounded content scan and disclose its exact coverage."""
        upper = content.upper()
        if cls._EICAR_SIGNATURE in upper:
            raise UploadValidationError("upload rejected by malware content scan")
        if any(content.startswith(magic) for magic in cls._FORBIDDEN_FILE_MAGIC):
            raise UploadValidationError("executable content is not permitted in data uploads")
        return {
            "status": "passed",
            "engine": "builtin-content-policy-v1",
            "scope": "EICAR test signature and executable file-magic rejection; schema decoder validation",
            "scanned_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _metadata_path(dataset_path: Path) -> Path:
        return dataset_path.with_suffix(".metadata.json")

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(payload, sort_keys=True, indent=2), encoding="utf-8")
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def list_uploads(self, owner_id: str) -> list[dict]:
        owner_dir = self._owner_directory(owner_id)
        self.delete_expired(owner_id)
        records = []
        for path in sorted(owner_dir.glob("*.metadata.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            dataset_path = owner_dir / str(record.get("dataset_file", ""))
            if dataset_path.is_file() and not dataset_path.is_symlink():
                records.append({key: value for key, value in record.items() if key != "dataset_file"})
        return records

    def delete_upload(self, owner_id: str, upload_id: str) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", str(upload_id or "")):
            raise UploadValidationError("invalid upload id")
        owner_dir = self._owner_directory(owner_id)
        metadata_path = owner_dir / f"{upload_id}.metadata.json"
        dataset_path = owner_dir / f"{upload_id}.parquet"
        if metadata_path.is_symlink() or dataset_path.is_symlink():
            raise UploadValidationError("upload path cannot be a symlink")
        existed = metadata_path.exists() or dataset_path.exists()
        metadata_path.unlink(missing_ok=True)
        dataset_path.unlink(missing_ok=True)
        return existed

    def delete_expired(self, owner_id: str, *, now: Optional[datetime] = None) -> int:
        owner_dir = self._owner_directory(owner_id)
        reference = now or datetime.now(timezone.utc)
        removed = 0
        for path in list(owner_dir.glob("*.metadata.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
                expires_at = datetime.fromisoformat(str(record["expires_at"]).replace("Z", "+00:00"))
            except (KeyError, OSError, ValueError, json.JSONDecodeError):
                continue
            if expires_at <= reference and self.delete_upload(owner_id, str(record.get("upload_id", ""))):
                removed += 1
        return removed

    @staticmethod
    def _positive_limit(value: Optional[int], environment: str, default: int) -> int:
        configured = value if value is not None else os.getenv(environment, str(default))
        try:
            parsed = int(configured)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{environment} must be an integer") from exc
        if parsed <= 0:
            raise ValueError(f"{environment} must be positive")
        return parsed

    @staticmethod
    def _safe_filename(filename: str) -> tuple[str, str]:
        value = str(filename or "")
        if (
            not value
            or len(value) > 255
            or "\x00" in value
            or "/" in value
            or "\\" in value
            or value in {".", ".."}
            or ".." in Path(value).stem
        ):
            raise UploadValidationError("unsafe upload filename")
        suffix = Path(value).suffix.lower()
        if suffix not in CustomDataUploader.SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(CustomDataUploader.SUPPORTED_EXTENSIONS))
            raise UploadValidationError(f"unsupported upload format; expected one of {supported}")
        return value, suffix

    @classmethod
    def _safe_source_name(cls, source_name: str) -> str:
        value = str(source_name or "").strip()
        if (
            not cls._NAME_PATTERN.fullmatch(value)
            or value in {".", ".."}
            or ".." in value
        ):
            raise UploadValidationError(
                "dataset name must be 1-100 safe letters, numbers, spaces, dots, dashes, or underscores"
            )
        return value

    @staticmethod
    def _owner_key(owner_id: str) -> str:
        value = str(owner_id or "").strip()
        if not value:
            raise UploadValidationError("authenticated owner id is required")
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]

    def _owner_directory(self, owner_id: str) -> Path:
        root = self.output_dir.resolve()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        owner_dir = root / self._owner_key(owner_id)
        resolved = owner_dir.resolve()
        if root not in resolved.parents:
            raise UploadValidationError("owner storage path escapes the upload root")
        owner_dir.mkdir(parents=False, exist_ok=True, mode=0o700)
        if owner_dir.is_symlink():
            raise UploadValidationError("owner storage directory cannot be a symlink")
        return owner_dir

    @staticmethod
    def _storage_usage(owner_dir: Path) -> int:
        total = 0
        for path in owner_dir.iterdir():
            if path.name.startswith(".") or path.is_symlink() or not path.is_file():
                continue
            total += path.stat().st_size
        return total

    @staticmethod
    @contextmanager
    def _quota_lock(owner_dir: Path) -> Iterator[None]:
        lock_path = owner_dir / ".upload-quota.lock"
        with lock_path.open("a+b") as handle:
            try:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except ImportError:  # pragma: no cover - Windows fallback
                fcntl = None
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _is_formula_text(value: object) -> bool:
        if not isinstance(value, str):
            return False
        stripped = value.lstrip()
        if not stripped:
            return False
        if stripped[0] in {"=", "+", "@"}:
            return True
        if stripped[0] != "-":
            return False
        try:
            float(stripped.replace(",", ""))
            return False
        except ValueError:
            return True

    def _reject_formula_cells(self, frame: pd.DataFrame) -> None:
        for column in frame.select_dtypes(include=["object", "string"]).columns:
            values = frame[column].dropna()
            if values.map(self._is_formula_text).any():
                raise UploadValidationError(
                    f"spreadsheet formula-like value detected in column {column!r}"
                )

    def _read_parquet(self, content: bytes) -> pd.DataFrame:
        if len(content) < 8 or content[:4] != b"PAR1" or content[-4:] != b"PAR1":
            raise UploadValidationError("invalid Parquet magic bytes")
        try:
            parquet = pq.ParquetFile(io.BytesIO(content))
        except (OSError, ValueError, pa.ArrowException) as exc:
            raise UploadValidationError(f"invalid Parquet file: {exc}") from exc
        if parquet.metadata.num_rows > self.max_rows:
            raise UploadValidationError(f"dataset exceeds the {self.max_rows:,}-row limit")
        if parquet.metadata.num_columns > self.max_columns:
            raise UploadValidationError(
                f"dataset exceeds the {self.max_columns:,}-column limit"
            )
        uncompressed = sum(
            parquet.metadata.row_group(group).column(column).total_uncompressed_size
            for group in range(parquet.metadata.num_row_groups)
            for column in range(parquet.metadata.num_columns)
        )
        if uncompressed > self.max_uncompressed_bytes:
            raise UploadTooLargeError(
                "Parquet expands beyond the configured uncompressed-size limit"
            )
        nested = [
            field.name
            for field in parquet.schema_arrow
            if pa.types.is_nested(field.type) or pa.types.is_binary(field.type)
        ]
        if nested:
            raise UploadValidationError(
                f"nested or binary Parquet columns are not supported: {nested}"
            )
        try:
            return parquet.read().to_pandas()
        except (OSError, ValueError, pa.ArrowException) as exc:
            raise UploadValidationError(f"could not decode Parquet data: {exc}") from exc

    def _read_frame(self, content: bytes, suffix: str) -> pd.DataFrame:
        if suffix == ".parquet":
            return self._read_parquet(content)
        if suffix == ".json":
            def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise UploadValidationError(f"duplicate JSON key: {key!r}")
                    result[key] = value
                return result

            try:
                payload = json.loads(
                    content.decode("utf-8-sig"),
                    object_pairs_hook=reject_duplicate_keys,
                )
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise UploadValidationError(f"invalid UTF-8 JSON: {exc}") from exc
            if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
                raise UploadValidationError("JSON uploads must be an array of row objects")
            if len(payload) > self.max_rows:
                raise UploadValidationError(f"dataset exceeds the {self.max_rows:,}-row limit")
            if any(
                isinstance(value, (dict, list))
                for row in payload
                for value in row.values()
            ):
                raise UploadValidationError("nested JSON values are not supported")
            return pd.DataFrame.from_records(payload)
        if b"\x00" in content:
            raise UploadValidationError("CSV uploads cannot contain NUL bytes")
        try:
            text = content.decode("utf-8-sig")
            reader = csv.reader(io.StringIO(text))
            header = next(reader)
            if len({column.casefold() for column in header}) != len(header):
                raise UploadValidationError("CSV column names must be unique ignoring case")
            for row_number, row in enumerate(reader, start=1):
                if row_number > self.max_rows:
                    raise UploadValidationError(
                        f"dataset exceeds the {self.max_rows:,}-row limit"
                    )
                if len(row) > self.max_columns:
                    raise UploadValidationError(
                        f"dataset exceeds the {self.max_columns:,}-column limit"
                    )
                if any(self._is_formula_text(value) for value in row):
                    raise UploadValidationError(
                        f"spreadsheet formula-like value detected in CSV row {row_number + 1}"
                    )
            return pd.read_csv(
                io.StringIO(text),
                nrows=self.max_rows + 1,
                low_memory=False,
            )
        except StopIteration as exc:
            raise UploadValidationError("CSV upload has no header row") from exc
        except (UnicodeDecodeError, csv.Error, pd.errors.ParserError) as exc:
            raise UploadValidationError(f"invalid UTF-8 CSV: {exc}") from exc

    def _validate_frame(
        self, frame: pd.DataFrame, *, date_column: str, symbol_column: str
    ) -> pd.DataFrame:
        if frame.empty or frame.dropna(how="all").empty:
            raise UploadValidationError("upload contains no usable rows")
        if len(frame) > self.max_rows:
            raise UploadValidationError(f"dataset exceeds the {self.max_rows:,}-row limit")
        if len(frame.columns) > self.max_columns:
            raise UploadValidationError(
                f"dataset exceeds the {self.max_columns:,}-column limit"
            )
        columns = [str(column) for column in frame.columns]
        if any(
            not column
            or len(column) > 128
            or column != column.strip()
            or any(ord(character) < 32 for character in column)
            for column in columns
        ):
            raise UploadValidationError("column names must be non-empty, trimmed, and printable")
        if len({column.casefold() for column in columns}) != len(columns):
            raise UploadValidationError("column names must be unique ignoring case")
        if not date_column or not symbol_column or date_column == symbol_column:
            raise UploadValidationError("date and symbol columns must be distinct")
        missing = [column for column in (date_column, symbol_column) if column not in columns]
        if missing:
            raise UploadValidationError(f"missing required schema columns: {missing}")
        self._reject_formula_cells(frame)
        normalized = frame.copy()
        dates = pd.to_datetime(normalized[date_column], errors="coerce", utc=True)
        if dates.isna().any():
            count = int(dates.isna().sum())
            raise UploadValidationError(f"date column contains {count} missing or invalid values")
        normalized[date_column] = dates.dt.tz_convert(None)
        symbols = normalized[symbol_column].astype("string").str.strip().str.upper()
        invalid_symbols = (
            symbols.isna()
            | ~symbols.str.fullmatch(self._TICKER_PATTERN, na=False)
            | symbols.str.contains("..", regex=False, na=False)
        )
        if invalid_symbols.any():
            raise UploadValidationError(
                f"symbol column contains {int(invalid_symbols.sum())} missing or invalid values"
            )
        normalized[symbol_column] = symbols
        if normalized.duplicated([date_column, symbol_column]).any():
            raise UploadValidationError("duplicate date-symbol observations are not allowed")
        value_columns = [column for column in columns if column not in {date_column, symbol_column}]
        if not value_columns:
            raise UploadValidationError("at least one data value column is required")
        numeric = normalized[value_columns].select_dtypes(include=[np.number])
        if numeric.empty:
            raise UploadValidationError("at least one numeric data value column is required")
        if np.isinf(numeric.to_numpy(dtype=float, copy=False)).any():
            raise UploadValidationError("numeric data values must be finite")
        return normalized.sort_values([date_column, symbol_column], kind="stable").reset_index(drop=True)

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def auto_detect_date_format(self, df: pd.DataFrame) -> str:
        column = next((name for name in df.columns if str(name).lower() in {"date", "datetime", "timestamp", "time"}), None)
        if column is None: raise ValueError("CSV has no date column; expected date, datetime, or timestamp")
        sample = df[column].dropna().astype(str).iloc[0] if df[column].notna().any() else ""
        if sample.count("-") == 2 and len(sample.split("-")[0]) == 4: return "%Y-%m-%d"
        return "month-first"

    def align_to_trading_calendar(self, df: pd.DataFrame, date_col: str) -> pd.DataFrame:
        out = df.copy(); out[date_col] = pd.to_datetime(out[date_col], errors="coerce"); out = out.dropna(subset=[date_col]); ticker_col = next((column for column in out.columns if str(column).lower() in {"ticker", "symbol"}), None)
        if ticker_col is None:
            calendar = pd.date_range(out[date_col].min(), out[date_col].max(), freq="B"); return out.set_index(date_col).reindex(calendar).rename_axis(date_col).reset_index()
        aligned = []
        for ticker, group in out.groupby(ticker_col, dropna=False):
            calendar = pd.date_range(group[date_col].min(), group[date_col].max(), freq="B"); part = group.set_index(date_col).reindex(calendar).rename_axis(date_col).reset_index(); part[ticker_col] = ticker; aligned.append(part)
        return pd.concat(aligned, ignore_index=True) if aligned else out.iloc[0:0].copy()

    def forward_fill_gaps(self, df: pd.DataFrame, max_fill_days: int = 1) -> pd.DataFrame:
        if max_fill_days < 0 or max_fill_days > 5: raise ValueError("max_fill_days must be between 0 and 5")
        out = df.copy(); date_col = next((c for c in out.columns if str(c).lower() in {"date", "datetime", "timestamp"}), None); ticker_col = next((c for c in out.columns if str(c).lower() in {"ticker", "symbol"}), None)
        if date_col is None: return out
        if ticker_col and ticker_col in out:
            out = out.sort_values([ticker_col, date_col]); numeric = out.select_dtypes(include=[np.number]).columns; out[numeric] = out.groupby(ticker_col)[numeric].ffill(limit=max_fill_days)
        else:
            numeric = out.select_dtypes(include=[np.number]).columns; out[numeric] = out[numeric].ffill(limit=max_fill_days)
        return out

    def register_custom_field(self, field_name: str, source_name: str, metadata: dict) -> None:
        base, number = str(field_name), 1
        name = base
        while name in self.registered_fields: number += 1; name = f"{base}_{number}"
        self.registered_fields.add(name); self.catalog.register_source(source_name, "custom", {**metadata, "access_expression": f"custom.{name}"})

    def generate_validation_report(
        self,
        df: pd.DataFrame,
        date_column: Optional[str] = None,
        symbol_column: Optional[str] = None,
    ) -> dict:
        date_col = date_column or next(
            (
                column
                for column in df.columns
                if str(column).lower() in {"date", "datetime", "timestamp"}
            ),
            None,
        )
        ticker_col = symbol_column or next(
            (
                column
                for column in df.columns
                if str(column).lower() in {"ticker", "symbol"}
            ),
            None,
        )
        numeric = df.select_dtypes(include=[np.number])
        return {
            "rows": len(df),
            "date_coverage": (
                [str(df[date_col].min()), str(df[date_col].max())]
                if date_col and not df.empty
                else []
            ),
            "ticker_coverage": int(df[ticker_col].nunique()) if ticker_col else None,
            "missing_fraction": (
                float(df.isna().mean().mean()) if len(df.columns) else 1.0
            ),
            "value_distribution": (
                numeric.describe().replace({np.nan: None}).to_dict()
                if not numeric.empty
                else {}
            ),
            "numeric_fields": list(numeric.columns),
        }

    def upload(
        self,
        file_content: bytes,
        filename: str,
        *,
        source_name: str,
        date_column: str,
        symbol_column: str,
        owner_id: str,
        license_status: str = "user-provided",
        permitted_use_attested: bool = False,
        retention_days: Optional[int] = None,
    ) -> UploadResult:
        """Validate an upload and publish normalized Parquet with an atomic rename."""
        _, suffix = self._safe_filename(filename)
        safe_source = self._safe_source_name(source_name)
        if len(file_content) > self.max_file_bytes:
            raise UploadTooLargeError(
                f"upload exceeds the {self.max_file_bytes:,}-byte file limit"
            )
        if not file_content:
            raise UploadValidationError("upload is empty")
        if not permitted_use_attested:
            raise UploadValidationError("permitted-use attestation is required")
        license_value = str(license_status or "").strip()
        if not self._NAME_PATTERN.fullmatch(license_value):
            raise UploadValidationError("license status must be a safe 1-100 character label")
        retention = self._retention_days(retention_days)
        scan = self._scan_content(file_content)
        date_name = str(date_column or "").strip()
        symbol_name = str(symbol_column or "").strip()
        frame = self._validate_frame(
            self._read_frame(file_content, suffix),
            date_column=date_name,
            symbol_column=symbol_name,
        )
        report = self.generate_validation_report(frame, date_name, symbol_name)
        owner_dir = self._owner_directory(owner_id)
        slug = re.sub(r"[^A-Za-z0-9_-]+", "_", safe_source).strip("_")[:64] or "dataset"
        upload_id = f"{slug}_{uuid.uuid4().hex}"
        final_path = owner_dir / f"{upload_id}.parquet"
        temporary_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=owner_dir,
                prefix=".upload-",
                suffix=".parquet.tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
            frame.to_parquet(temporary_path, index=False, compression="zstd")
            with temporary_path.open("rb") as handle:
                os.fsync(handle.fileno())
            # Compression happens outside the short quota critical section so
            # independent users do not block each other's file conversion.
            with self._OWNER_WRITE_LOCK, self._quota_lock(owner_dir):
                published_size = temporary_path.stat().st_size
                current_usage = self._storage_usage(owner_dir)
                if current_usage + published_size > self.owner_quota_bytes:
                    raise UploadQuotaExceededError(
                        f"upload would exceed the {self.owner_quota_bytes:,}-byte owner quota"
                    )
                os.chmod(temporary_path, 0o600)
                os.replace(temporary_path, final_path)
                temporary_path = None
                try:
                    directory_handle = os.open(owner_dir, os.O_RDONLY)
                    try:
                        os.fsync(directory_handle)
                    finally:
                        os.close(directory_handle)
                except OSError:
                    pass
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        numeric_fields = [
            str(column)
            for column in frame.select_dtypes(include=[np.number]).columns
            if str(column) not in {date_name, symbol_name}
        ]
        storage_key = final_path.relative_to(self.output_dir.resolve()).as_posix()
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(days=retention)
        governance = {
            "visibility": "private-owner-only",
            "license_status": license_value,
            "permitted_use_attested": True,
            "retention_days": retention,
            "deletion_policy": "owner may delete immediately; expired uploads are removed during owner upload inventory access",
            "malware_scan": scan,
        }
        self._write_json_atomic(
            self._metadata_path(final_path),
            {
                "upload_id": upload_id,
                "dataset_file": final_path.name,
                "source_name": safe_source,
                "storage_key": storage_key,
                "created_at": created_at.isoformat(),
                "expires_at": expires_at.isoformat(),
                "governance": governance,
            },
        )
        self.register_custom_field(
            slug,
            safe_source,
            {
                "coverage_universe": str(report.get("ticker_coverage", "")),
                "date_range": str(report.get("date_coverage", "")),
                "path": str(final_path),
            },
        )
        return UploadResult(
            success=True,
            source_name=safe_source,
            fields=[f"custom.{column}" for column in numeric_fields],
            validation_report=report,
            storage_key=storage_key,
            format="parquet",
            size_bytes=final_path.stat().st_size,
            checksum_sha256=self._checksum(final_path),
            created_at=created_at.isoformat(),
            expires_at=expires_at.isoformat(),
            governance=governance,
        )

    def upload_csv(self, file_content: bytes, filename: str) -> UploadResult:
        """Backward-compatible CSV helper using the same hardened upload pipeline."""
        source_name = Path(str(filename or "dataset")).stem
        try:
            return self.upload(
                file_content,
                filename,
                source_name=source_name,
                date_column="date",
                symbol_column="ticker",
                owner_id="legacy",
                permitted_use_attested=True,
            )
        except UploadValidationError as exc:
            return UploadResult(False, source_name, [], {}, error=str(exc))


class DataFreshnessMonitor:
    def __init__(self, catalog: Optional[DataCatalog] = None) -> None: self.catalog, self._statuses, self._alerts = catalog or DataCatalog(), {}, []
    @staticmethod
    def _data_as_of(path: Path) -> Optional[pd.Timestamp]:
        if path.suffix.lower() != ".parquet": return None
        try:
            import pyarrow.parquet as pq
            parquet = pq.ParquetFile(path); names = parquet.schema.names
            date_index = next((index for index, name in enumerate(names) if str(name).lower() in {"date", "datetime", "timestamp"}), None)
            if date_index is None: return None
            maxima = []
            for group in range(parquet.metadata.num_row_groups):
                stats = parquet.metadata.row_group(group).column(date_index).statistics
                if stats is not None and stats.has_min_max: maxima.append(pd.Timestamp(stats.max))
            return max(maxima) if maxima else None
        except (OSError, ValueError, TypeError): return None
    def check_source(self, source_name: str) -> FreshnessStatus:
        entry = self.catalog.sources[source_name]; path = Path(entry.path) if entry.path else None
        slo = max(0, int(entry.freshness_slo_trading_days))
        if not path or not path.exists(): status = FreshnessStatus(source_name, None, None, "failed", f"source file not found: {entry.path}", freshness_slo_trading_days=slo, slo_breached=True)
        else:
            stamp_dt = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc); stamp = stamp_dt.isoformat(); as_of = self._data_as_of(path); reference_date = as_of.date() if as_of is not None else stamp_dt.date(); today = pd.Timestamp.utcnow().date(); lag = max(0, int(np.busday_count(reference_date, today))); breached = lag > slo; state = "current" if not breached else "stale"; status = FreshnessStatus(source_name, stamp, lag, state, data_as_of=as_of.isoformat() if as_of is not None else None, freshness_slo_trading_days=slo, slo_breached=breached)
        self._statuses[source_name] = status
        if status.status != "current": self._alerts.append(asdict(status))
        return status
    def check_all_sources(self) -> Dict[str, FreshnessStatus]: return {name: self.check_source(name) for name in self.catalog.sources}
    def get_freshness_board(self) -> pd.DataFrame:
        if not self._statuses: self.check_all_sources()
        return pd.DataFrame([asdict(status) for status in self._statuses.values()])
    def get_run_metadata_tag(self) -> dict: return {name: asdict(status) for name, status in self._statuses.items()}
    def get_alerts(self) -> List[dict]: return list(self._alerts)
    def record_backtest_freshness(self, run_id: str) -> None: self._statuses.setdefault(run_id, FreshnessStatus(run_id, datetime.now(timezone.utc).isoformat(), 0, "recorded"))
