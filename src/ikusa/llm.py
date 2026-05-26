"""LLM triage client.

Dual-provider design: Ollama (self-hosted, matches the product narrative) is
the default; OpenAI is available as a fallback for development convenience.

The triage step takes parser-emitted Finding objects, sends them to the LLM
along with the CRA Annex I lookup, and parses the response back into
TriagedFinding objects. Findings the LLM did not address get a placeholder
triage so the downstream pipeline can still render them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import httpx
from jinja2 import Template

from ikusa.cra import CraMapper
from ikusa.models import Finding, MasvsCategory, TriagedFinding

_PROMPTS_DIR = Path(__file__).parent / "prompts"
_SYSTEM_PROMPT = (_PROMPTS_DIR / "triage_system.txt").read_text()
_USER_TEMPLATE = Template((_PROMPTS_DIR / "triage_user.txt.j2").read_text())

_PLACEHOLDER_EXPLANATION = "[sin triaje LLM]"
_PLACEHOLDER_REMEDIATION = "Revisar manualmente."


class LLMTriageClient:
    def __init__(
        self,
        provider: Literal["ollama", "openai"],
        model: str,
        api_key: str | None = None,
        ollama_url: str = "http://localhost:11434",
        timeout: float = 600.0,
    ) -> None:
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._ollama_url = ollama_url
        self._timeout = timeout
        self._cra = CraMapper.load_default()

    async def triage(
        self,
        findings: list[Finding],
        app_name: str,
        package_name: str,
    ) -> list[TriagedFinding]:
        if not findings:
            return []
        payload = await self._chat_json(
            system=_SYSTEM_PROMPT,
            user=self._render_user(findings, app_name, package_name),
        )
        payload = self._coerce_to_dict(payload)
        return self._merge(findings, payload)

    def _render_user(
        self,
        findings: list[Finding],
        app_name: str,
        package_name: str,
    ) -> str:
        cra_lookup = {cat.value: self._cra.articles_for(cat) for cat in MasvsCategory}
        return _USER_TEMPLATE.render(
            app_name=app_name,
            package_name=package_name,
            findings=findings,
            cra_lookup=cra_lookup,
        )

    async def _chat_json(self, system: str, user: str) -> Any:
        if self._provider == "ollama":
            return await self._ollama(system, user)
        return await self._openai(system, user)

    async def _ollama(self, system: str, user: str) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.1},
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    async def _openai(self, system: str, user: str) -> Any:
        # Imported lazily so projects without an OPENAI_API_KEY can still
        # use the Ollama path without crashing on import.
        from openai import AsyncOpenAI  # type: ignore[import-not-found]

        client = AsyncOpenAI(api_key=self._api_key)
        response = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        return response.choices[0].message.content or "{}"

    @staticmethod
    def _coerce_to_dict(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _merge(
        self,
        findings: list[Finding],
        payload: dict[str, Any],
    ) -> list[TriagedFinding]:
        by_id = {f.id: f for f in findings}
        triaged: list[TriagedFinding] = []
        seen: set[str] = set()

        for entry in payload.get("triaged", []) or []:
            if not isinstance(entry, dict):
                continue
            fid = entry.get("id")
            base = by_id.get(fid)
            if base is None:
                continue  # hallucinated id -> ignore
            seen.add(fid)
            triaged.append(
                TriagedFinding(
                    **base.model_dump(),
                    priority=self._clamp_priority(entry.get("priority", 3)),
                    explanation=str(entry.get("explanation") or _PLACEHOLDER_EXPLANATION),
                    remediation=str(entry.get("remediation") or _PLACEHOLDER_REMEDIATION),
                    cra_articles=list(entry.get("cra_articles") or []),
                )
            )

        for finding in findings:
            if finding.id in seen:
                continue
            triaged.append(
                TriagedFinding(
                    **finding.model_dump(),
                    priority=3,
                    explanation=_PLACEHOLDER_EXPLANATION,
                    remediation=_PLACEHOLDER_REMEDIATION,
                    cra_articles=[],
                )
            )

        triaged.sort(key=lambda t: (t.priority, -t.severity._order))
        return triaged

    @staticmethod
    def _clamp_priority(raw: Any) -> int:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return 3
        return max(1, min(3, value))
