"""Google Gemini（AI Studio）呼叫的共用工具：建立 client、要求模型回傳符合 JSON Schema 的結果。"""
import json
import os
from dataclasses import dataclass

import httpx2
from google import genai
from google.genai import errors, types

# Interactions API 的錯誤不是 errors.APIError，而是下面這組（SDK 尚未公開匯出）。
from google.genai._gaos.errors import GenAiError, NoResponseError
from google.genai._gaos.lib.compat_errors import APIConnectionError, GeminiNextGenAPIClientError

# 可在網頁「設定」切換的模型（皆有免費額度）。
MODELS = {
    "gemini-3.5-flash-lite": "Flash-Lite：最快，適合免費版",
    "gemini-3.6-flash": "3.6 Flash：穩定版，速度與品質平衡",
    "gemini-3.8-flash": "3.8 Flash：最聰明，但較慢",
}
_env_model = os.environ.get("GEMINI_MODEL", "")
DEFAULT_MODEL = _env_model if _env_model in MODELS else "gemini-3.5-flash-lite"
MODEL = DEFAULT_MODEL  # 舊名稱，保留相容

# SDK 預設「沒有逾時」且失敗會重試 4 次，免費版一慢就會卡住很久。
# 改成：每次最多等 90 秒、最多重試 1 次；超過就改用規則式備案。
TIMEOUT_MS = 90_000
ATTEMPTS = 2


class AIError(Exception):
    pass


@dataclass
class GeminiClient:
    client: genai.Client
    model: str


def make_client(api_key: str | None = None, model: str | None = None) -> GeminiClient | None:
    """優先用傳入的 Key，其次是環境變數 GEMINI_API_KEY / GOOGLE_API_KEY；都沒有就回傳 None（改用規則式）。"""
    key = (api_key or "").strip() or env_key()
    if not key:
        return None
    http_options = types.HttpOptions(timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=ATTEMPTS))
    return GeminiClient(genai.Client(api_key=key, http_options=http_options), resolve_model(model))


def resolve_model(model: str | None) -> str:
    return model if model in MODELS else DEFAULT_MODEL


def env_key() -> str:
    return os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")


def call_json(gc: GeminiClient, system: str, user: str | list[dict], schema: dict, effort: str = "low") -> dict:
    """送出一次請求，回傳解析後的 JSON。任何失敗都轉成 AIError，讓呼叫端改用規則式備案。"""
    try:
        try:
            interaction = _create(gc, system, user, schema, {"thinking_level": effort})
        except GeminiNextGenAPIClientError as e:
            # 有些模型不接受 thinking_level，拿掉後再試一次
            if getattr(e, "status_code", None) == 400 and "thinking" in str(e).lower():
                interaction = _create(gc, system, user, schema, {})
            else:
                raise
    except (APIConnectionError, httpx2.HTTPError, NoResponseError) as e:  # 含逾時
        if "timeout" in type(e).__name__.lower() or "timed out" in str(e).lower():
            raise AIError(f"Gemini 超過 {TIMEOUT_MS // 1000} 秒沒有回應（免費版忙碌中），請稍後再試或換更快的模型") from e
        raise AIError(f"連不上 Gemini（請檢查網路）：{e}") from e
    except GeminiNextGenAPIClientError as e:
        raise AIError(_friendly(getattr(e, "status_code", None), str(e), gc.model)) from e
    except GenAiError as e:
        raise AIError(_friendly(e.status_code, f"{e.message} {e.body}", gc.model)) from e
    except errors.APIError as e:
        raise AIError(_friendly(e.code, str(e), gc.model)) from e
    except Exception as e:  # 其他未預期的 SDK 例外
        raise AIError(f"Gemini 呼叫失敗：{str(e)[:300]}") from e

    if interaction.status == "incomplete":
        raise AIError("回應超出長度上限")
    if interaction.status != "completed":
        raise AIError(f"Gemini 沒有完成回應（狀態：{interaction.status}）")
    text = interaction.output_text
    if not text:
        raise AIError("Gemini 沒有回傳內容（可能被安全過濾擋下）")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIError("Gemini 回傳的格式不正確") from e


def _create(gc: GeminiClient, system: str, user: str, schema: dict, thinking: dict):
    return gc.client.interactions.create(
        model=gc.model,
        system_instruction=system,
        input=user,
        generation_config={**thinking, "max_output_tokens": 16000},
        response_format={"type": "text", "mime_type": "application/json", "schema": schema},
        store=False,  # 不在 Google 端保存這次的請求與回應
    )


def _friendly(code: int | None, detail: str, model: str) -> str:
    low = detail.lower()
    if code == 401:
        return "API Key 無效或已停用，請到 Google AI Studio 確認"
    if code == 403:
        if "api key" in low or "api_key" in low or "credential" in low:
            return "API Key 無效或受限制，請到 Google AI Studio 確認"
        return "此 API Key 沒有存取 Gemini API 的權限，請檢查金鑰所屬專案與 API 設定"
    if code == 400 and ("api key" in low or "api_key" in low):
        return "API Key 無效，請到 Google AI Studio 確認"
    if code == 404 or (code == 400 and "model" in low and ("not found" in low or "not supported" in low)):
        return f"目前無法使用模型 {model}，請在「設定」換一個模型"
    if code == 429:
        return f"{model} 已達免費額度的使用上限，請稍後再試或在「設定」換一個模型"
    if code is not None and code >= 500:
        return f"Gemini 伺服器暫時異常（HTTP {code}）；已自動重試，通常不是 API Key 問題，請稍後再試"
    return f"Gemini 呼叫失敗（{code}）：{detail[:300]}"
