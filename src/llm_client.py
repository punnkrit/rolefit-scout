from __future__ import annotations

import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .config import AppConfig

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


def structured_response(
    config: AppConfig,
    output_model: type[T],
    system_prompt: str,
    user_prompt: str,
) -> T:
    if not config.openai_api_key:
        raise LLMError("OPENAI_API_KEY is missing.")

    client = OpenAI(api_key=config.openai_api_key)
    schema = _strict_json_schema(output_model.model_json_schema())
    last_error: Exception | None = None
    prompt = user_prompt

    for attempt in range(2):
        try:
            response = client.responses.create(
                model=config.openai_model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": output_model.__name__,
                        "schema": schema,
                        "strict": True,
                    }
                },
            )
            raw_text = getattr(response, "output_text", None) or _extract_output_text(response)
            data = json.loads(raw_text)
            return output_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError, Exception) as exc:
            last_error = exc
            prompt = (
                f"{user_prompt}\n\nThe previous response failed validation with this error:\n"
                f"{exc}\n\nReturn only JSON matching this schema:\n{json.dumps(schema)}"
            )
            if attempt == 1:
                break
    raise LLMError(f"OpenAI response failed validation: {last_error}") from last_error


def _extract_output_text(response: object) -> str:
    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", None)
            if text:
                chunks.append(text)
    if not chunks:
        raise LLMError("OpenAI response did not contain output text.")
    return "\n".join(chunks)


def _strict_json_schema(schema: dict) -> dict:
    """Adapt Pydantic JSON Schema for OpenAI strict structured outputs."""
    schema = json.loads(json.dumps(schema))

    def visit(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node:
                properties = node.get("properties", {})
                node["additionalProperties"] = False
                node["required"] = list(properties.keys())
            node.pop("default", None)
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(schema)
    return schema
