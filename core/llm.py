"""
Shared LLM factory. Controls which provider is used across all agents.

Set LLM_PROVIDER in .env to switch:
  LLM_PROVIDER=anthropic   — uses ANTHROPIC_API_KEY
  LLM_PROVIDER=bedrock     (default) — uses AWS credentials or Bedrock API key

Bedrock auth options:
  - Standard IAM:       AWS_ACCESS_KEY_ID (AKIA...) + AWS_SECRET_ACCESS_KEY
  - Bedrock API key:    AWS_SECRET_ACCESS_KEY=ABSK... (AWS_ACCESS_KEY_ID can be anything)
"""
import os
import boto3
from dotenv import load_dotenv

load_dotenv()

_PROVIDER        = os.getenv("LLM_PROVIDER", "bedrock").lower().strip()
_ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-6")
_BEDROCK_MODEL   = os.getenv("BEDROCK_MODEL",   "amazon.nova-pro-v1:0")
_REGION          = os.getenv("AWS_REGION", "us-east-1")


def _make_bedrock_client():
    """Return a boto3 bedrock-runtime client, supporting both IAM and API key auth."""
    secret = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()

    # Bedrock API key — bearer token (starts with ABSK or bedrock-api-key prefix)
    if secret.startswith("ABSK") or os.getenv("AWS_ACCESS_KEY_ID", "").startswith("BedrockAPIKey"):
        import requests as _req

        class _BedrockBearerSession:
            """Minimal shim so ChatBedrockConverse can call .converse()."""
            def __init__(self, token, region, model):
                self._token  = token
                self._region = region
                self._model  = model
                self._base   = f"https://bedrock-runtime.{region}.amazonaws.com"

            def converse(self, modelId, messages, **kwargs):
                url = f"{self._base}/model/{modelId}/converse"
                body = {"messages": messages, **kwargs}
                resp = _req.post(
                    url,
                    json=body,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                return resp.json()

        return _BedrockBearerSession(secret, _REGION, _BEDROCK_MODEL)

    # Standard IAM credentials
    kwargs = {"region_name": _REGION}
    access = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    if access and secret:
        kwargs["aws_access_key_id"]     = access
        kwargs["aws_secret_access_key"] = secret
    return boto3.client("bedrock-runtime", **kwargs)


def get_llm(**kwargs):
    """Return a configured LLM. Provider selected by LLM_PROVIDER env var."""
    if _PROVIDER == "bedrock":
        from langchain_aws import ChatBedrockConverse
        return ChatBedrockConverse(
            model=_BEDROCK_MODEL,
            region_name=_REGION,
            client=_make_bedrock_client(),
            **kwargs,
        )
    else:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=_ANTHROPIC_MODEL, **kwargs)
