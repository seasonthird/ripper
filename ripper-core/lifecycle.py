"""Durable claim identity and revision metadata, independent of the index."""

from __future__ import annotations

import hashlib
import json


LIFECYCLE_FIELDS = {"revision", "created_at", "updated_at"}


def content(claim: dict) -> str:
    return json.dumps({k: v for k, v in claim.items() if k not in LIFECYCLE_FIELDS},
                      ensure_ascii=False, sort_keys=True)


def prepare_analysis(analysis: dict, previous: dict, project_id: str, timestamp: str) -> dict:
    """Reuse explicit identities; only reuse legacy titles when unambiguous.

    Changed titles without an explicit ID/key are new claims: guessing a
    semantic match would silently merge independent engineering results.
    """
    old_claims = previous.get("claims", []) or []
    by_id = {str(c["id"]): c for c in old_claims if isinstance(c, dict) and c.get("id")}
    by_key = {str(c["identity_key"]): c for c in old_claims if isinstance(c, dict) and c.get("identity_key")}
    titles: dict[str, list[dict]] = {}
    for c in old_claims:
        if isinstance(c, dict):
            titles.setdefault(str(c.get("title", "")), []).append(c)
    result = []
    seen: set[str] = set()
    for raw in analysis.get("claims", []) or []:
        if not isinstance(raw, dict):
            raise ValueError("claims must contain objects")
        claim = dict(raw)
        if not claim.get("title"):
            raise ValueError("claim title is required")
        old = by_id.get(str(claim.get("id", ""))) or by_key.get(str(claim.get("identity_key", "")))
        if not old and not claim.get("id") and not claim.get("identity_key"):
            matches = titles.get(str(claim["title"]), [])
            old = matches[0] if len(matches) == 1 else None
        key = claim.get("identity_key") or (old or {}).get("identity_key")
        claim_id = claim.get("id") or (old or {}).get("id")
        if not claim_id:
            basis = str(key) if key else str(claim["title"]) + "\0" + str(claim.get("statement", ""))
            claim_id = "claim_" + hashlib.sha256((project_id + "\0" + basis).encode()).hexdigest()[:16]
        claim["id"] = str(claim_id)
        if key:
            claim["identity_key"] = str(key)
        if claim["id"] in seen:
            raise ValueError("duplicate claim identity: " + claim["id"])
        seen.add(claim["id"])
        old = old or by_id.get(claim["id"])
        if old and "confirmations" not in claim and "confirmation_questions" not in claim:
            for field in ("confirmations", "confirmation_questions"):
                if field in old:
                    claim[field] = old[field]
        if old:
            for field in ("production_status", "disclosure_level", "realization_status"):
                if field not in claim and field in old:
                    claim[field] = old[field]
            old_entries = old.get("confirmation_questions", old.get("confirmations", [])) or []
            old_entries = {str(e.get("question") or e.get("text")): e for e in old_entries if isinstance(e, dict)}
            for field in ("confirmation_questions", "confirmations"):
                if field in claim:
                    entries = []
                    for entry in claim[field] or []:
                        entry = dict(entry) if isinstance(entry, dict) else {"question": str(entry)}
                        question = str(entry.get("question") or entry.get("text") or "")
                        entries.append({**old_entries.get(question, {}), **entry})
                    claim[field] = entries
        changed = not old or content(claim) != content(old)
        claim["revision"] = int((old or {}).get("revision", 1)) + int(changed) if old else 1
        claim["created_at"] = (old or {}).get("created_at") or timestamp
        claim["updated_at"] = timestamp if changed else old.get("updated_at", timestamp)
        result.append(claim)
    return {**analysis, "project_id": project_id, "claims": result}
