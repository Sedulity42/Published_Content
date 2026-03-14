#!/usr/bin/env python3
"""
Content publication tool for Published_Content.

Usage:
    python3 scripts/publish.py status    - Show what's staged, published, and needs attention
    python3 scripts/publish.py publish   - Sync staged content to projects/ and update index.html
"""

import json
import os
import shutil
import sys
import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = REPO_ROOT / "_source"
PROJECTS_DIR = REPO_ROOT / "projects"
CONFIG_PATH = REPO_ROOT / "publish-config.json"
INDEX_PATH = REPO_ROOT / "index.html"

# Markers in index.html where project cards are injected
GRID_START = "<!-- BEGIN_PROJECT_GRID -->"
GRID_END = "<!-- END_PROJECT_GRID -->"


def load_config():
    if not CONFIG_PATH.exists():
        print(f"Error: {CONFIG_PATH} not found")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        return json.load(f)


def has_real_content(directory):
    """Check if a directory has files beyond .gitkeep."""
    if not directory.is_dir():
        return False
    for item in directory.rglob("*"):
        if item.is_file() and item.name != ".gitkeep":
            return True
    return False


def file_count(directory):
    """Count real files in a directory."""
    if not directory.is_dir():
        return 0
    return sum(1 for f in directory.rglob("*") if f.is_file() and f.name != ".gitkeep")


def dir_fingerprint(directory):
    """Create a fingerprint of a directory's contents for comparison."""
    if not directory.is_dir():
        return None
    h = hashlib.md5()
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            rel = path.relative_to(directory)
            h.update(str(rel).encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def find_entry_file(directory):
    """Try to identify the main HTML entry file in a project directory."""
    if not directory.is_dir():
        return None
    # Priority order for entry file detection
    candidates = ["index.html", "index.htm"]
    for c in candidates:
        if (directory / c).exists():
            return c
    # Fall back to any HTML file at the root level
    html_files = [f.name for f in directory.iterdir() if f.is_file() and f.suffix in (".html", ".htm")]
    if len(html_files) == 1:
        return html_files[0]
    if html_files:
        return html_files[0]  # pick first alphabetically
    return None


def scan_source():
    """Scan _source/ for all project directories with content."""
    if not SOURCE_DIR.is_dir():
        return {}
    results = {}
    for item in sorted(SOURCE_DIR.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            results[item.name] = {
                "has_content": has_real_content(item),
                "file_count": file_count(item),
                "entry": find_entry_file(item),
                "path": item,
            }
    return results


def scan_published():
    """Scan projects/ for published project directories (not standalone HTML files)."""
    if not PROJECTS_DIR.is_dir():
        return {}
    results = {}
    for item in sorted(PROJECTS_DIR.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            results[item.name] = {
                "has_content": has_real_content(item),
                "file_count": file_count(item),
                "entry": find_entry_file(item),
                "path": item,
            }
    return results


def check_index_has_card(project_name):
    """Check if the index.html has a project card linking to this project."""
    if not INDEX_PATH.exists():
        return False
    content = INDEX_PATH.read_text()
    return f'projects/{project_name}/' in content or f'projects/{project_name}.html' in content


# ── Status command ────────────────────────────────────────────────────

def cmd_status():
    config = load_config()
    configured = {p["source"]: p for p in config["projects"]}
    staged = scan_source()
    published = scan_published()

    all_names = sorted(set(list(configured.keys()) + list(staged.keys()) + list(published.keys())))

    if not all_names:
        print("No projects found anywhere. Drop project files into _source/<project-name>/ to get started.")
        return

    print("=" * 70)
    print("  CONTENT STATUS REPORT")
    print("=" * 70)
    print()

    needs_attention = []

    for name in all_names:
        in_config = name in configured
        in_source = name in staged and staged[name]["has_content"]
        in_published = name in published and published[name]["has_content"]
        on_index = check_index_has_card(name)

        # Determine sync status
        if in_source and in_published:
            src_fp = dir_fingerprint(staged[name]["path"])
            pub_fp = dir_fingerprint(published[name]["path"])
            in_sync = src_fp == pub_fp
        else:
            in_sync = False

        # Print project status
        print(f"  Project: {name}")
        print(f"    Config:    {'yes' if in_config else 'NO  -- not in publish-config.json'}")
        print(f"    Staged:    {'yes (' + str(staged[name]['file_count']) + ' files)' if in_source else 'no  -- _source/' + name + '/ is empty'}")
        print(f"    Published: {'yes (' + str(published[name]['file_count']) + ' files)' if in_published else 'no'}")
        if in_source and in_published:
            print(f"    In sync:   {'yes' if in_sync else 'NO  -- source has changes not yet published'}")
        print(f"    On index:  {'yes' if on_index else 'NO  -- no card on index page'}")

        # Detect entry file
        if in_source:
            entry = staged[name].get("entry")
            if entry:
                print(f"    Entry:     {entry}")
            else:
                print(f"    Entry:     NONE DETECTED -- no HTML file found in source")

        # Identify actions needed
        actions = []
        if in_source and not in_config:
            actions.append("Add to publish-config.json")
        if in_source and not in_published:
            actions.append("Run 'publish' to deploy to projects/")
        if in_source and in_published and not in_sync:
            actions.append("Run 'publish' to sync latest changes")
        if in_config and in_published and not on_index:
            actions.append("Run 'publish' to add card to index page")
        if in_config and not in_source:
            actions.append("Drop source files into _source/" + name + "/")

        if actions:
            needs_attention.append((name, actions))
            print(f"    Actions:   {'; '.join(actions)}")

        print()

    # Summary
    print("-" * 70)
    if needs_attention:
        print(f"  {len(needs_attention)} project(s) need attention:")
        for name, actions in needs_attention:
            for action in actions:
                print(f"    - {name}: {action}")
    else:
        print("  All projects are up to date.")
    print()


# ── Publish command ───────────────────────────────────────────────────

def sync_project(source_dir, target_dir):
    """Sync files from source to target, mirroring deletions."""
    if target_dir.exists():
        # Remove files in target that aren't in source
        for item in list(target_dir.rglob("*")):
            if item.is_file() and item.name != ".gitkeep":
                rel = item.relative_to(target_dir)
                if not (source_dir / rel).exists():
                    item.unlink()
                    print(f"    removed: {rel}")
        # Clean empty directories
        for item in sorted(target_dir.rglob("*"), reverse=True):
            if item.is_dir() and not any(item.iterdir()):
                item.rmdir()

    target_dir.mkdir(parents=True, exist_ok=True)

    # Copy files from source to target
    copied = 0
    for src_file in source_dir.rglob("*"):
        if src_file.is_file() and src_file.name != ".gitkeep":
            rel = src_file.relative_to(source_dir)
            dst_file = target_dir / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            # Only copy if changed
            if dst_file.exists() and dst_file.read_bytes() == src_file.read_bytes():
                continue

            shutil.copy2(src_file, dst_file)
            copied += 1
            print(f"    copied: {rel}")

    return copied


def generate_project_card(project_config):
    """Generate an HTML project card from config metadata."""
    meta = project_config["metadata"]
    target = project_config["target"]
    entry = project_config["entry"]
    title = meta["title"]
    desc = meta["description"]
    tags = meta["tags"]
    status = meta.get("status", "In Progress").capitalize()

    tags_html = "\n".join(f'                                <span class="tag">{tag}</span>' for tag in tags)

    return f"""                    <a href="projects/{target}/{entry}" class="project-card" data-animate>
                        <div class="project-card-body">
                            <h3 class="project-card-title">{title}</h3>
                            <p class="project-card-desc">{desc}</p>
                            <div class="project-card-tags">
{tags_html}
                            </div>
                        </div>
                        <span class="project-card-status">{status}</span>
                    </a>"""


def update_index(config):
    """Regenerate the project grid in index.html from publish-config.json."""
    if not INDEX_PATH.exists():
        print("  Warning: index.html not found, skipping index update")
        return False

    content = INDEX_PATH.read_text()

    if GRID_START not in content or GRID_END not in content:
        print(f"  Warning: index.html missing grid markers ({GRID_START} / {GRID_END})")
        print("  Skipping index update. Add the markers around the project-grid content.")
        return False

    # Build new project cards for all configured projects that have published content
    cards = []
    for project in config["projects"]:
        target_dir = PROJECTS_DIR / project["target"]
        if has_real_content(target_dir):
            cards.append(generate_project_card(project))

    if not cards:
        print("  No published projects to show on index page.")
        return False

    cards_html = "\n\n".join(cards)
    new_grid = f"""{GRID_START}

{cards_html}

                    <!-- To add a new project: add it to publish-config.json, stage in _source/, and run publish -->

                    {GRID_END}"""

    # Replace content between markers
    start_idx = content.index(GRID_START)
    end_idx = content.index(GRID_END) + len(GRID_END)
    new_content = content[:start_idx] + new_grid + content[end_idx:]

    if new_content != content:
        INDEX_PATH.write_text(new_content)
        print("  Updated index.html project grid")
        return True
    else:
        print("  Index.html already up to date")
        return False


def cmd_publish():
    config = load_config()
    configured = {p["source"]: p for p in config["projects"]}
    staged = scan_source()

    # Detect new content in _source/ not yet in config
    unconfigured = []
    for name, info in staged.items():
        if info["has_content"] and name not in configured:
            unconfigured.append((name, info))

    if unconfigured:
        print("=" * 70)
        print("  NEW CONTENT DETECTED (not yet in publish-config.json)")
        print("=" * 70)
        for name, info in unconfigured:
            entry = info.get("entry", "unknown")
            print(f"\n  _source/{name}/")
            print(f"    Files: {info['file_count']}")
            print(f"    Entry: {entry or 'NONE -- no HTML found'}")
            print(f"    Action needed: Add this project to publish-config.json")
            print(f"    Example config entry:")
            print(f'    {{')
            print(f'      "source": "{name}",')
            print(f'      "target": "{name}",')
            print(f'      "entry": "{entry or "index.html"}",')
            print(f'      "metadata": {{')
            print(f'        "title": "{name.replace("-", " ").title()}",')
            print(f'        "description": "TODO: Add project description",')
            print(f'        "tags": ["TODO"],')
            print(f'        "status": "completed"')
            print(f'      }}')
            print(f'    }}')
        print()

    # Publish configured projects that have staged content
    any_published = False
    print("=" * 70)
    print("  PUBLISHING")
    print("=" * 70)

    for project in config["projects"]:
        name = project["source"]
        src_dir = SOURCE_DIR / name
        tgt_dir = PROJECTS_DIR / project["target"]

        print(f"\n  {name}:")

        if not has_real_content(src_dir):
            print(f"    SKIP -- no content in _source/{name}/")
            continue

        # Verify entry file exists
        entry = project["entry"]
        if not (src_dir / entry).exists():
            print(f"    WARNING -- entry file '{entry}' not found in source")
            detected = find_entry_file(src_dir)
            if detected:
                print(f"    Detected '{detected}' -- consider updating publish-config.json")

        copied = sync_project(src_dir, tgt_dir)
        if copied > 0:
            print(f"    Published {copied} file(s) to projects/{project['target']}/")
            any_published = True
        else:
            print(f"    Already in sync")

    # Update index.html
    print()
    print("-" * 70)
    print("  UPDATING INDEX")
    print("-" * 70)
    update_index(config)

    # Final status
    print()
    print("-" * 70)
    if any_published:
        print("  Done. Review changes and commit when ready.")
    else:
        print("  Nothing new to publish.")
    if unconfigured:
        print(f"  Reminder: {len(unconfigured)} project(s) in _source/ need to be added to publish-config.json")
    print()


# ── Main ──────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    if command == "status":
        cmd_status()
    elif command == "publish":
        cmd_publish()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
