"""Private continuation codec. Never expose checkpoint payloads in API responses."""

import base64
from dataclasses import fields

from google.genai import types

from forge.model_router.base import ModelResult, ToolExchange


def pack(value):
    if isinstance(value, bytes):
        return {"__forge_bytes__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {k: pack(v) for k, v in value.items()}
    if isinstance(value, list):
        return [pack(v) for v in value]
    return value


def unpack(value):
    if isinstance(value, dict):
        if set(value) == {"__forge_bytes__"}:
            return base64.b64decode(value["__forge_bytes__"], validate=True)
        return {k: unpack(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unpack(v) for v in value]
    return value


def save_result(result):
    data = {f.name: getattr(result, f.name) for f in fields(result) if f.name != "provider_content"}
    data["provider_content"] = (
        pack(result.provider_content.model_dump(mode="python", exclude_none=True))
        if result.provider_content is not None
        else None
    )
    return data


def load_result(data):
    data = dict(data)
    if data["provider_content"] is not None:
        data["provider_content"] = types.Content.model_validate(unpack(data["provider_content"]))
    return ModelResult(**data)


def save_exchanges(exchanges):
    return [{"response": save_result(x.response), "results": x.results} for x in exchanges]


def load_exchanges(data):
    return [ToolExchange(response=load_result(x["response"]), results=x["results"]) for x in data]
