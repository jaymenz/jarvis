"""
JARVIS Obsidian Vault Access — READ + CREATE ONLY.

Reads and creates notes in the local Obsidian vault using the filesystem.
No Obsidian app API needed — vault is just a folder of markdown files.
CANNOT edit or delete existing notes (safety).
"""

import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger("jarvis.obsidian")

VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT", str(Path.home() / "Documents" / "Vault" / "jarvis")))


def _get_vault() -> Path:
    """Return vault path, warn if missing."""
    if not VAULT_PATH.exists():
        log.warning(f"Obsidian vault not found at {VAULT_PATH}")
    return VAULT_PATH


def get_recent_notes(count: int = 10) -> list[dict]:
    """Get most recently modified notes from the vault."""
    vault = _get_vault()
    if not vault.exists():
        return []
    try:
        md_files = list(vault.rglob("*.md"))
        md_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        notes = []
        for f in md_files[:count]:
            rel = f.relative_to(vault)
            folder = str(rel.parent) if rel.parent != Path(".") else ""
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            notes.append({
                "title": f.stem,
                "folder": folder,
                "modified": mtime,
                "path": str(f),
            })
        return notes
    except Exception as e:
        log.warning(f"get_recent_notes error: {e}")
        return []


def read_note(title_match: str) -> dict | None:
    """Read a note by title (partial, case-insensitive match). Returns title + body."""
    vault = _get_vault()
    if not vault.exists():
        return None
    try:
        query = title_match.lower()
        candidates = []
        for f in vault.rglob("*.md"):
            if query in f.stem.lower():
                candidates.append(f)
        if not candidates:
            return None
        # Prefer exact match, otherwise most recently modified
        exact = [f for f in candidates if f.stem.lower() == query]
        target = exact[0] if exact else sorted(candidates, key=lambda f: f.stat().st_mtime, reverse=True)[0]
        body = target.read_text(encoding="utf-8")
        if len(body) > 3000:
            body = body[:3000]
        rel = target.relative_to(vault)
        folder = str(rel.parent) if rel.parent != Path(".") else ""
        return {
            "title": target.stem,
            "body": body,
            "folder": folder,
            "path": str(target),
        }
    except Exception as e:
        log.warning(f"read_note error: {e}")
        return None


def search_notes(query: str, count: int = 5) -> list[dict]:
    """Search notes by title or content (case-insensitive)."""
    vault = _get_vault()
    if not vault.exists():
        return []
    try:
        q = query.lower()
        results = []
        for f in vault.rglob("*.md"):
            title_match = q in f.stem.lower()
            body_match = False
            snippet = ""
            try:
                content = f.read_text(encoding="utf-8")
                if q in content.lower():
                    body_match = True
                    # Extract a short snippet around the match
                    idx = content.lower().find(q)
                    start = max(0, idx - 60)
                    end = min(len(content), idx + 120)
                    snippet = content[start:end].replace("\n", " ").strip()
            except Exception:
                pass
            if title_match or body_match:
                rel = f.relative_to(vault)
                folder = str(rel.parent) if rel.parent != Path(".") else ""
                mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
                results.append({
                    "title": f.stem,
                    "folder": folder,
                    "modified": mtime,
                    "snippet": snippet,
                    "title_match": title_match,
                })
        # Sort: title matches first, then by recency
        results.sort(key=lambda r: (not r["title_match"], r["modified"]), reverse=False)
        return results[:count]
    except Exception as e:
        log.warning(f"search_notes error: {e}")
        return []


def create_note(title: str, body: str, folder: str = "", tags: list[str] | None = None) -> bool:
    """Create a new markdown note in the vault.

    Adds YAML frontmatter with date and tags.
    Supports [[wikilinks]] in body — just include them naturally.
    Will NOT overwrite an existing note.
    """
    vault = _get_vault()
    if not vault.exists():
        log.warning(f"Vault not found, cannot create note: {VAULT_PATH}")
        return False
    try:
        target_dir = vault / folder if folder else vault
        target_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_title = "".join(c if c.isalnum() or c in " -_" else " " for c in title).strip()
        file_path = target_dir / f"{safe_title}.md"

        if file_path.exists():
            log.warning(f"Note already exists: {file_path}")
            return False

        date_str = datetime.now().strftime("%Y-%m-%d")
        tag_list = "\n".join(f"  - {t}" for t in (tags or []))
        frontmatter = f"---\ndate: {date_str}\n"
        if tag_list:
            frontmatter += f"tags:\n{tag_list}\n"
        frontmatter += "---\n\n"

        file_path.write_text(frontmatter + body, encoding="utf-8")
        log.info(f"Obsidian note created: {file_path}")
        return True
    except Exception as e:
        log.warning(f"create_note error: {e}")
        return False


def format_recent_for_context(count: int = 8) -> str:
    """Format recent Obsidian notes for LLM system prompt context."""
    notes = get_recent_notes(count)
    if not notes:
        return "No Obsidian notes found."
    lines = []
    for n in notes:
        folder_part = f" [{n['folder']}]" if n["folder"] else ""
        lines.append(f"- {n['title']}{folder_part} (modified {n['modified']})")
    return "\n".join(lines)
