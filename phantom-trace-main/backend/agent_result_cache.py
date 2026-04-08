import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BASE_DIR = Path(__file__).resolve().parent
CACHE_DB_PATH = BASE_DIR / "agent_results_cache.sqlite3"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(CACHE_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_cache() -> None:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                user_message TEXT NOT NULL,
                raw_response TEXT NOT NULL,
                parsed_response TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_results_thread_id ON agent_results(thread_id, created_at)"
        )


initialize_cache()


def _ensure_cache_ready() -> None:
    initialize_cache()


def _normalize_agent_name(agent_name: str) -> str:
    return agent_name.strip().lower()


def _split_response_lines(raw_response: str) -> List[str]:
    return [line.strip() for line in raw_response.splitlines() if line.strip()]


def _extract_findings(lines: Iterable[str]) -> List[str]:
    findings: List[str] = []
    for line in lines:
        cleaned = re.sub(r"^[-*•]+\s*", "", line)
        cleaned = re.sub(r"^\d+[).:-]?\s*", "", cleaned)
        if cleaned and cleaned not in findings:
            findings.append(cleaned)
    return findings


def parse_agent_response(raw_response: str) -> Dict[str, Any]:
    lines = _split_response_lines(raw_response)
    findings = _extract_findings(lines)

    sections: Dict[str, List[str]] = {}
    current_section: Optional[str] = None

    for line in lines:
        heading_match = re.match(r"^([A-Za-z][A-Za-z0-9 /_-]{1,60}):$", line)
        if heading_match:
            current_section = heading_match.group(1).strip().lower()
            sections.setdefault(current_section, [])
            continue

        if current_section:
            sections[current_section].append(line)

    summary = findings[0] if findings else (lines[0] if lines else raw_response.strip())

    return {
        "summary": summary,
        "findings": findings,
        "sections": sections,
        "line_count": len(lines),
    }


def store_agent_result(
    *,
    thread_id: str,
    agent_name: str,
    user_message: str,
    raw_response: str,
) -> Dict[str, Any]:
    _ensure_cache_ready()
    parsed_response = parse_agent_response(raw_response)
    record = {
        "thread_id": thread_id,
        "agent_name": _normalize_agent_name(agent_name),
        "user_message": user_message.strip(),
        "raw_response": raw_response.strip(),
        "parsed_response": parsed_response,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO agent_results (
                thread_id, agent_name, user_message, raw_response, parsed_response, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record["thread_id"],
                record["agent_name"],
                record["user_message"],
                record["raw_response"],
                json.dumps(record["parsed_response"]),
                record["created_at"],
            ),
        )

    return record


def get_cached_agent_results(thread_id: str) -> List[Dict[str, Any]]:
    _ensure_cache_ready()
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT thread_id, agent_name, user_message, raw_response, parsed_response, created_at
            FROM agent_results
            WHERE thread_id = ?
            ORDER BY datetime(created_at) ASC, id ASC
            """,
            (thread_id,),
        ).fetchall()

    results: List[Dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "thread_id": row["thread_id"],
                "agent_name": row["agent_name"],
                "user_message": row["user_message"],
                "raw_response": row["raw_response"],
                "parsed_response": json.loads(row["parsed_response"]),
                "created_at": row["created_at"],
            }
        )
    return results


def combine_cached_agent_results(thread_id: str) -> Dict[str, Any]:
    _ensure_cache_ready()
    cached_results = get_cached_agent_results(thread_id)
    combined_by_agent: Dict[str, Dict[str, Any]] = {}
    ordered_findings: List[Dict[str, Any]] = []

    for result in cached_results:
        agent_name = result["agent_name"]
        parsed = result["parsed_response"]
        combined_by_agent[agent_name] = {
            "latest_user_message": result["user_message"],
            "raw_response": result["raw_response"],
            "parsed_response": parsed,
            "created_at": result["created_at"],
        }
        ordered_findings.append(
            {
                "agent_name": agent_name,
                "summary": parsed.get("summary", ""),
                "findings": parsed.get("findings", []),
                "created_at": result["created_at"],
            }
        )

    total_findings = sum(len(item.get("findings", [])) for item in ordered_findings)
    latest_context = ordered_findings[-1]["summary"] if ordered_findings else "No cached specialist findings were found."

    return {
        "thread_id": thread_id,
        "total_agents": len(combined_by_agent),
        "total_findings": total_findings,
        "latest_context": latest_context,
        "by_agent": combined_by_agent,
        "ordered_findings": ordered_findings,
    }


def build_explainer_context(thread_id: str, user_message: str) -> str:
    combined_results = combine_cached_agent_results(thread_id)
    if not combined_results["by_agent"]:
        return user_message.strip()

    formatted_agents: List[str] = []
    for agent_name, payload in combined_results["by_agent"].items():
        parsed = payload["parsed_response"]
        findings = parsed.get("findings", [])
        finding_lines = "\n".join(f"  - {finding}" for finding in findings[:10]) or "  - No parsed findings captured"
        formatted_agents.append(
            "\n".join(
                [
                    f"{agent_name}:",
                    f"  summary: {parsed.get('summary', '')}",
                    "  findings:",
                    finding_lines,
                    f"  source_message: {payload['latest_user_message']}",
                ]
            )
        )

    cache_block = "\n\n".join(formatted_agents)
    return (
        "Use the cached specialist findings below as primary context before answering.\n\n"
        f"Thread ID: {thread_id}\n"
        f"Cached specialist findings:\n{cache_block}\n\n"
        f"User request:\n{user_message.strip()}"
    )
