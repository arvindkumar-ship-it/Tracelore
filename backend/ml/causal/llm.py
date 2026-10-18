import asyncio
import json
import logging
from typing import Any

from pydantic import ValidationError

from backend.common.metrics import GROUNDING_FAILURES
from backend.common.settings import Settings

from .evidence import EvidenceBundle
from .grounding import RootCauseReport, check, rules_report

logger = logging.getLogger(__name__)
SYSTEM_PROMPT = (
    "You are a debugging analyst. You receive a JSON evidence bundle produced by "
    "deterministic analysis. Choose root_cause_node ONLY from the candidates list. "
    "Cite evidence only by its id. Every number you mention must come from a cited "
    "evidence item. If the evidence does not clearly support one candidate, set "
    "insufficient_evidence=true and explain why. Never invent services, metrics, "
    "events or timings. Output JSON matching the schema, nothing else."
)


async def explain(
    bundle: EvidenceBundle, settings: Settings, completion: Any = None
) -> tuple[RootCauseReport, str]:
    if not settings.llm_enabled or not settings.openai_api_key.get_secret_value():
        return rules_report(bundle), "rules"
    if completion is None:
        from litellm import acompletion

        completion = acompletion
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": bundle.model_dump_json()},
    ]
    for attempt in range(3):
        try:
            response = await completion(
                model=settings.llm_model,
                api_key=settings.openai_api_key.get_secret_value(),
                messages=messages,
                temperature=0,
                max_tokens=800,
                timeout=30,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "root_cause",
                        "schema": RootCauseReport.model_json_schema(),
                    },
                },
            )
            report = RootCauseReport.model_validate_json(response.choices[0].message.content)
            if not check(report, bundle):
                return report, "llm"
            GROUNDING_FAILURES.inc()
            return rules_report(bundle), "rules"
        except (ValidationError, json.JSONDecodeError, TypeError) as error:
            if attempt > 0:
                break
            messages.append(
                {
                    "role": "user",
                    "content": f"Return valid schema JSON. Validation type: {type(error).__name__}",
                }
            )
        except Exception as error:
            logger.warning(
                "llm_unavailable error_type=%s attempt=%s", type(error).__name__, attempt
            )
            await asyncio.sleep(min(2**attempt, 4))
    return rules_report(bundle), "rules"
