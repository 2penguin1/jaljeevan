from pydantic import BaseModel, ValidationError

from app.core.exceptions import ExternalServiceError
from app.integrations.ports import LLMResult


class BedrockNovaClient:
    """Adapter over Amazon Nova on Bedrock via the Converse API.

    Nova is Amazon's own model: billed to the AWS account (credits apply) with no Marketplace subscription,
    so it works on free-plan accounts where Claude is blocked. Structured output = a forced tool call whose
    input schema is our JSON schema; the input is re-validated with the Pydantic schema.
    """

    TOOL_NAME = "submit_result"
    _RETRYABLE = {"ThrottlingException", "ServiceUnavailableException", "InternalServerException",
                  "ModelNotReadyException", "ModelTimeoutException"}

    def __init__(self, region: str, model: str, profile: str | None = None, client=None):
        if client is None:
            import boto3
            client = boto3.Session(profile_name=profile, region_name=region).client("bedrock-runtime")
        self.client = client
        self.model = model

    @property
    def provider(self) -> str:
        return f"bedrock:{self.model}"

    def parse(self, *, system: str, user: str, schema: type[BaseModel], max_tokens: int) -> LLMResult:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            resp = self.client.converse(
                modelId=self.model, system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0},
                toolConfig={"tools": [{"toolSpec": {"name": self.TOOL_NAME,
                                                    "description": "Return the classification result.",
                                                    "inputSchema": {"json": schema.model_json_schema()}}}],
                            "toolChoice": {"tool": {"name": self.TOOL_NAME}}})
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "ClientError")
            raise ExternalServiceError("bedrock-nova", code, retryable=code in self._RETRYABLE) from None
        except BotoCoreError as exc:
            raise ExternalServiceError("bedrock-nova", type(exc).__name__) from None
        raw = resp.get("usage") or {}
        usage = {"input_tokens": raw.get("inputTokens", 0), "output_tokens": raw.get("outputTokens", 0),
                 "cache_read_input_tokens": 0}
        if resp.get("stopReason") == "content_filtered":
            return LLMResult(parsed=None, usage=usage, refused=True, provider=self.provider)
        blocks = ((resp.get("output") or {}).get("message") or {}).get("content") or []
        tool_input = next((b["toolUse"].get("input") for b in blocks
                           if "toolUse" in b and b["toolUse"].get("name") == self.TOOL_NAME), None)
        try:
            parsed = schema.model_validate(tool_input) if tool_input is not None else None
        except ValidationError:
            parsed = None
        return LLMResult(parsed=parsed, usage=usage, provider=self.provider)
