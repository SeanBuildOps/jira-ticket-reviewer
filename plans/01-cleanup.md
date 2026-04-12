# Phase 1 — Cleanup

**Branch:** `phase/1-cleanup`
**Status:** Complete — pending merge to `main` via PR

---

## Goal

Remove everything belonging to the old hardcoded design and stub the README so the repo is clean before any new code is introduced.

---

## What Gets Deleted

| File | Reason |
|------|--------|
| `recommend-tickets.py` | The old hardcoded priority + expertise scorer — replaced entirely by the microkernel |
| `recommend-tickets.md` | Documentation for the deleted script |
| `config/expertise.example.json` | Example config for the deleted script's expertise-matching logic |

---

## What Gets Updated

**`README.md`** — stripped to a stub containing only:
- Project name
- One-line description of the new direction
- "See `plans/` for architecture"

The stub must contain **no references** to priority scoring, expertise matching, or the old `recommend-tickets.py` script.

---

## What Stays Untouched

| Path | Notes |
|------|-------|
| `.gitignore` | Keep as-is |
| `cache/` | Keep directory (may be git-ignored contents) |
| `config/` | Keep directory, now empty after expertise.example.json removal |
| `plans/` | Keep — was created in Phase 0 |
| `CHANGELOG.txt` | Keep — created in Phase 0 |

---

## Verification Checklist

- [ ] `recommend-tickets.py` does not exist
- [ ] `recommend-tickets.md` does not exist
- [ ] `config/expertise.example.json` does not exist
- [ ] `README.md` contains no references to priority scoring, expertise matching, or the old script
- [ ] `git status` clean (all changes committed on branch)
- [ ] Code review passes (no critical/blocker issues)
- [ ] **User approves → Phase 2 begins**
