"""Build workspace state kept in the kv table: version tags and lock, branches, local history, snippets, share links, editing lease, find and replace, zip projects."""

from __future__ import annotations

import difflib
import io
import json
import re
import secrets
import time
import zipfile

from . import store
from .spec import Strategy

LEASE_SECONDS = 60
HISTORY_DAYS = 7
MAX_SNAPSHOTS = 200
MAX_SNIPPETS = 200


class Refused(ValueError):
    """A request the workspace will not do; the API turns it into a 4xx with the message."""

    def __init__(self, message: str, status: int = 422, **extra):
        super().__init__(message)
        self.status, self.extra = status, extra


def _spec(sid: str, version: int | None = None) -> Strategy:
    return Strategy(**store.get(sid, version)["spec"])


def _with_files(spec: Strategy, files: dict[str, str]) -> Strategy:
    files = dict(files)
    return Strategy(**{**spec.model_dump(), "code": files.pop("main.py", ""), "files": files})


# --- version tags and the live lock (B-126) ---------------------------------


def label_version(sid: str, version: int, name: str | None, tags: list[str] | None) -> dict:
    store.get(sid, version)
    labels = store.kv_get(f"labels:{sid}", {})
    entry = labels.get(str(version), {"name": "", "tags": []})
    if name is not None:
        entry["name"] = name.strip()[:80]
    if tags is not None:
        entry["tags"] = list(dict.fromkeys(t.strip()[:30] for t in tags if t.strip()))[:10]
    labels[str(version)] = entry
    store.kv_set(f"labels:{sid}", labels)
    return {"version": version, **entry}


def set_lock(sid: str, version: int | None) -> dict:
    """Lock the version a live deployment runs; saving over it is refused until it is unlocked."""
    if version is not None:
        store.get(sid, version)
    store.kv_set(f"lock:{sid}", version)
    return {"locked_version": version}


def locked_version(sid: str) -> int | None:
    return store.kv_get(f"lock:{sid}")


def timeline(sid: str) -> list[dict]:
    """Each version with its name, tags, lock and the latest backtest summary."""
    saved = store.get(sid)
    labels, lock = store.kv_get(f"labels:{sid}", {}), locked_version(sid)
    out = []
    for row in saved["versions"]:
        v = row["version"]
        run = saved["runs_by_version"].get(v) or {}
        out.append({**row, **labels.get(str(v), {"name": "", "tags": []}), "locked": v == lock,
                    "sharpe": run.get("sharpe"), "total_return": run.get("total_return"), "spark": run.get("spark") or []})
    return out


# --- branches: compare and merge (B-128) ------------------------------------


def _origin(sid: str) -> tuple[str, int] | None:
    for row in store.actor_log(sid):
        if row["action"] == "branch":
            return row["detail"]["from"], row["detail"]["version"]
    return None


def compare(sid_a: str, sid_b: str) -> dict:
    a, b = _spec(sid_a).project_files(), _spec(sid_b).project_files()
    diffs = {n: "".join(difflib.unified_diff(a.get(n, "").splitlines(True), b.get(n, "").splitlines(True), fromfile=f"{sid_a}/{n}", tofile=f"{sid_b}/{n}"))
             for n in sorted(set(a) | set(b)) if a.get(n) != b.get(n)}
    runs = {sid: (store.get(sid)["runs_by_version"].get(store.get(sid)["latest"]) or {}) for sid in (sid_a, sid_b)}
    return {"a": sid_a, "b": sid_b, "diffs": diffs, "runs": runs}


def merge(target: str, source: str, resolution: str | None = None, actor: str = "human") -> dict:
    """Three-way, file by file, against the version the source branched from. A file both sides changed is a conflict unless `resolution` is "ours" or "theirs"."""
    origin = _origin(source)
    if origin is None or origin[0] != target:
        raise Refused(f"{source} was not branched from {target}.", 422, hint="Merge a branch back into the strategy it came from.")
    base = _spec(origin[0], origin[1]).project_files()
    ours, theirs = _spec(target).project_files(), _spec(source).project_files()
    merged, conflicts = {}, []
    for name in sorted(set(base) | set(ours) | set(theirs)):
        b, o, t = base.get(name), ours.get(name), theirs.get(name)
        if o == t or t == b:
            pick = o
        elif o == b:
            pick = t
        elif resolution in ("ours", "theirs"):
            pick = o if resolution == "ours" else t
        else:
            conflicts.append(name)
            continue
        if pick is not None:
            merged[name] = pick
    if conflicts:
        raise Refused("Both branches changed the same files.", 409, conflicts=conflicts, hint='Retry with resolution "ours" or "theirs".')
    if "main.py" not in merged:
        merged["main.py"] = ours.get("main.py", "")
    saved = store.save_version(target, _with_files(_spec(target), merged), actor)
    store.log(actor, "merge", target, {"from": source})
    return {"version": saved["version"], "files": sorted(merged)}


# --- local history (B-130) ---------------------------------------------------


def snapshot(sid: str, spec: dict, now: float | None = None, minimum_gap: float = 30.0) -> bool:
    """Keep an autosave for 7 days. Skips an unchanged file set and anything closer than `minimum_gap` seconds to the last one."""
    now = time.time() if now is None else now
    files = Strategy(**spec).project_files()
    rows = [r for r in store.kv_get(f"history:{sid}", []) if r["at"] > now - HISTORY_DAYS * 86400]
    if rows and (rows[-1]["files"] == files or now - rows[-1]["at"] < minimum_gap):
        store.kv_set(f"history:{sid}", rows)
        return False
    rows.append({"at": now, "files": files})
    store.kv_set(f"history:{sid}", rows[-MAX_SNAPSHOTS:])
    return True


def history(sid: str, now: float | None = None) -> list[dict]:
    now = time.time() if now is None else now
    return [r for r in store.kv_get(f"history:{sid}", []) if r["at"] > now - HISTORY_DAYS * 86400][::-1]


# --- user snippets (B-95, B-141) ---------------------------------------------


def snippets() -> list[dict]:
    return store.kv_get("snippets", [])


def save_snippet(name: str, prefix: str, body: str, description: str = "", snippet_id: str | None = None) -> dict:
    rows = snippets()
    if snippet_id is None and len(rows) >= MAX_SNIPPETS:
        raise Refused(f"At most {MAX_SNIPPETS} snippets.")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,31}", prefix):
        raise Refused("A snippet prefix is a word of up to 32 letters, digits or underscores.")
    row = {"id": snippet_id or secrets.token_hex(4), "name": name.strip()[:80], "prefix": prefix, "body": body[:20_000], "description": description[:300]}
    if snippet_id and not any(r["id"] == snippet_id for r in rows):
        raise KeyError(f"Unknown snippet {snippet_id}")
    rows = [row if r["id"] == row["id"] else r for r in rows] if snippet_id else [*rows, row]
    store.kv_set("snippets", rows)
    return row


def delete_snippet(snippet_id: str) -> None:
    rows = snippets()
    if not any(r["id"] == snippet_id for r in rows):
        raise KeyError(f"Unknown snippet {snippet_id}")
    store.kv_set("snippets", [r for r in rows if r["id"] != snippet_id])


# --- read-only share links and forks (B-131) ---------------------------------


def share(sid: str, version: int | None = None) -> dict:
    saved = store.get(sid, version)
    token = secrets.token_urlsafe(12)
    store.kv_set(f"share:{token}", {"strategy_id": sid, "version": saved["version"], "created": time.time()})
    return {"token": token, "version": saved["version"]}


def _shared(token: str) -> dict:
    row = store.kv_get(f"share:{token}")
    if not row:
        raise KeyError("This share link does not exist or was revoked.")
    return row


def revoke_share(token: str) -> None:
    _shared(token)
    store.kv_set(f"share:{token}", None)


def read_share(token: str) -> dict:
    row = _shared(token)
    saved = store.get(row["strategy_id"], row["version"])
    return {"name": saved["name"], "version": row["version"], "read_only": True, "files": Strategy(**saved["spec"]).project_files()}


def fork_share(token: str, actor: str = "human") -> dict:
    row = _shared(token)
    saved = store.get(row["strategy_id"], row["version"])
    return store.create(Strategy(**{**saved["spec"], "name": f"{saved['name']} fork"}), actor)


# --- single editing session (B-14, B-132) ------------------------------------


def acquire_lease(sid: str, session: str, take_over: bool = False, now: float | None = None) -> dict:
    store.get(sid)
    now = time.time() if now is None else now
    held = store.kv_get(f"lease:{sid}")
    if held and held["expires"] > now and held["session"] != session and not take_over:
        raise Refused("Another editing session holds this strategy.", 409, held_by=held["session"], since=held["since"], expires=held["expires"],
                      hint="Take over, or open it read-only.")
    since = held["since"] if held and held["session"] == session and held["expires"] > now else now
    lease = {"session": session, "since": since, "expires": now + LEASE_SECONDS}
    store.kv_set(f"lease:{sid}", lease)
    return {**lease, "taken_over": bool(held and held["session"] != session and held["expires"] > now)}


def release_lease(sid: str, session: str) -> None:
    held = store.kv_get(f"lease:{sid}")
    if held and held["session"] == session:
        store.kv_set(f"lease:{sid}", None)


def check_writer(sid: str, session: str | None, now: float | None = None) -> None:
    """Raise a 409 when a different live session holds the lease. No lease means anyone may write."""
    now = time.time() if now is None else now
    held = store.kv_get(f"lease:{sid}")
    if held and held["expires"] > now and held["session"] != session:
        raise Refused("Another editing session holds this strategy.", 409, held_by=held["session"], expires=held["expires"],
                      hint="Send X-Studio-Session with the session that holds the lease, or take it over.")


# --- find and replace across the project (B-23) ------------------------------


def find_replace(sid: str, query: str, replacement: str | None = None, *, regex: bool = False, match_case: bool = False, whole_word: bool = False,
                 base_version: int | None = None, actor: str = "human") -> dict:
    """Matches with their line and column. With `replacement`, saves one new version holding every change."""
    pattern = query if regex else re.escape(query)
    if whole_word:
        pattern = rf"\b(?:{pattern})\b"
    try:
        found = re.compile(pattern, 0 if match_case else re.IGNORECASE)
    except re.error as exc:
        raise Refused(f"Not a valid pattern: {exc}") from exc
    saved = store.get(sid)
    if replacement is not None and base_version is not None and base_version != saved["version"]:
        raise Refused(f"Strategy is at version {saved['version']}. Reload before replacing.", 409)
    spec = Strategy(**saved["spec"])
    files = spec.project_files()
    matches, changed = [], {}
    for name, source in files.items():
        for number, line in enumerate(source.splitlines(), 1):
            matches += [{"file": name, "line": number, "column": m.start() + 1, "text": line[:300]} for m in found.finditer(line) if m.end() > m.start()]
        if replacement is not None:
            new = found.sub(lambda _m: replacement, source)
            if new != source:
                changed[name] = new
    out = {"matches": matches, "count": len(matches), "files": sorted({m["file"] for m in matches})}
    if replacement is not None and changed:
        out["version"] = store.save_version(sid, _with_files(spec, {**files, **changed}), actor)["version"]
    return out


# --- projects as zip files (B-94) --------------------------------------------


def export_zip(sid: str, version: int | None = None) -> bytes:
    saved = store.get(sid, version)
    spec = Strategy(**saved["spec"])
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, source in spec.project_files().items():
            z.writestr(name, source)
        z.writestr("studio.json", json.dumps({"name": saved["name"], "version": saved["version"], "symbols_note": "params and settings live in the strategy spec"}, indent=2))
    return buffer.getvalue()


def import_zip(raw: bytes, name: str | None = None, actor: str = "human") -> dict:
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise Refused("That is not a zip file.") from exc
    files: dict[str, str] = {}
    with z:
        infos = [i for i in z.infolist() if not i.is_dir() and i.filename != "studio.json"]
        if len(infos) > 50:
            raise Refused("A project holds at most 50 files.")
        for info in infos:
            if info.file_size > 200_000 or "/" in info.filename or info.filename.startswith("."):
                raise Refused(f"{info.filename}: files must sit at the top level and stay under 200 KB.")
            try:
                files[info.filename] = z.read(info).decode("utf-8")
            except UnicodeDecodeError as exc:
                raise Refused(f"{info.filename} is not UTF-8 text.") from exc
    if "main.py" not in files:
        raise Refused("The zip needs a main.py at its top level.")
    try:
        spec = _with_files(Strategy(name=name or "Imported project"), files)
    except ValueError as exc:
        raise Refused(str(exc)) from exc
    return store.create(spec, actor)
