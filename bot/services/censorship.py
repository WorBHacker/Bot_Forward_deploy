import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import aiohttp

from bot.config import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Public exception
# --------------------------------------------------------------------------

class CensorshipError(Exception):
    """
    Raised when a censorship check cannot be completed (network failure,
    unexpected API response, model crash, etc.).

    The caller MUST treat this as "unknown safety" and route the post to
    manual review — never auto-approve on a CensorshipError.
    """


# --------------------------------------------------------------------------
# Sightengine response helpers
# --------------------------------------------------------------------------

def _scalar(obj: object, key: str, *, fallback: float = 0.0) -> float:
    """Return a float from obj[key]; safe against non-dict, nested dict, None."""
    if not isinstance(obj, dict):
        return fallback
    value = obj.get(key, fallback)
    if isinstance(value, (int, float)):
        return float(value)
    return fallback


def _max_leaf(obj: object) -> float:
    """
    Recursively return the maximum float leaf value in any Sightengine field.

      0.9                                  → 0.9
      {"prob": 0.9}                        → 0.9
      {"classes": {"firearms": 0.99, ...}} → 0.99
      {"prob": 0.5, "classes": {...}}      → max(0.5, max(classes values))
    """
    if isinstance(obj, (int, float)):
        return float(obj)
    if not isinstance(obj, dict):
        return 0.0
    best = 0.0
    for v in obj.values():
        candidate = _max_leaf(v)
        if candidate > best:
            best = candidate
    return best


# --------------------------------------------------------------------------
# Result dataclass
# --------------------------------------------------------------------------

@dataclass
class CensorshipResult:
    is_safe: bool
    reason: Optional[str] = None
    scores: Optional[dict] = None


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------

class CensorshipService:
    """
    Two-stage content moderation:
      1. Text / caption  → detoxify (multilingual, GPU).
      2. Photo / video   → Sightengine REST API.

    On any failure raises CensorshipError.
    Never returns is_safe=True on an error path.
    """

    def __init__(self) -> None:
        self._model = None
        self._model_lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    async def check_text(self, text: str) -> CensorshipResult:
        if not text or not text.strip():
            return CensorshipResult(is_safe=True)

        model = await self._get_model()
        loop = asyncio.get_running_loop()

        try:
            scores: dict = await loop.run_in_executor(None, model.predict, text)
        except Exception as exc:
            raise CensorshipError(f"detoxify prediction failed: {exc}") from exc

        threshold = settings.toxicity_threshold
        violations = {k: round(v, 4) for k, v in scores.items() if v > threshold}

        if violations:
            reason = "Toxic content: " + ", ".join(
                f"{k}={v}" for k, v in violations.items()
            )
            return CensorshipResult(is_safe=False, reason=reason, scores=scores)

        return CensorshipResult(is_safe=True, scores=scores)

    async def check_image_url(self, file_url: str) -> CensorshipResult:
        if not settings.sightengine_api_user:
            return CensorshipResult(is_safe=True)
        return await self._sightengine_check(file_url, "image")

    async def check_video_url(self, file_url: str) -> CensorshipResult:
        if not settings.sightengine_api_user:
            return CensorshipResult(is_safe=True)
        return await self._sightengine_check(file_url, "video")

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    async def _get_model(self):
        async with self._model_lock:
            if self._model is None:
                loop = asyncio.get_running_loop()
                self._model = await loop.run_in_executor(None, self._load_model)
                logger.info("detoxify model loaded")
        return self._model

    @staticmethod
    def _load_model():
        try:
            import torch
            from detoxify import Detoxify

            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading detoxify on device=%s", device)
            return Detoxify("multilingual", device=device)
        except Exception as exc:
            logger.exception("Could not load detoxify model")
            raise CensorshipError(f"Could not load detoxify model: {exc}") from exc

    async def _sightengine_check(self, file_url: str, media_type: str) -> CensorshipResult:
        params = {
            "url": file_url,
            "models": "nudity-2.0,wad",
            "api_user": settings.sightengine_api_user,
            "api_secret": settings.sightengine_api_secret,
        }
        endpoint = (
            "https://api.sightengine.com/1.0/check.json"
            if media_type == "image"
            else "https://api.sightengine.com/1.0/video/check-sync.json"
        )

        # --- Network request -------------------------------------------
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20)
            ) as session:
                async with session.get(endpoint, params=params) as resp:
                    data = await resp.json()
        except Exception as exc:
            raise CensorshipError(
                f"Sightengine network error ({media_type}): {exc}"
            ) from exc

        # --- API-level error -------------------------------------------
        if data.get("status") != "success":
            raise CensorshipError(
                f"Sightengine returned non-success: {data.get('error', data)}"
            )

        # --- Parse scores ----------------------------------------------
        threshold = settings.nsfw_threshold
        violations: list[str] = []

        try:
            # nudity-2.0: all fields checked — explicit + suggestive (family/children groups)
            nudity = data.get("nudity", {})

            # Explicit content
            for field in ("sexual_activity", "sexual_display", "erotica"):
                score = _scalar(nudity, field)
                if score > threshold:
                    violations.append(f"nudity:{field}({score:.2f})")

            # Suggestive content (bikini, cleavage, lingerie, miniskirt, etc.)
            suggestive_score = _scalar(nudity, "suggestive")
            if suggestive_score > threshold:
                violations.append(f"nudity:suggestive({suggestive_score:.2f})")

            # Suggestive sub-classes — most granular detection
            suggestive_classes_score = _max_leaf(nudity.get("suggestive_classes", {}))
            if suggestive_classes_score > threshold:
                violations.append(f"nudity:suggestive_class({suggestive_classes_score:.2f})")

            # weapon: {"classes": {"firearms": 0.99, ...}}
            weapon_score = _max_leaf(data.get("weapon", {}))
            if weapon_score > threshold:
                violations.append(f"weapon({weapon_score:.2f})")

            # violence: {"prob": 0.9, "classes": {...}}
            violence = data.get("violence", {})
            violence_score = _scalar(violence, "prob", fallback=_max_leaf(violence))
            if violence_score > threshold:
                violations.append(f"violence({violence_score:.2f})")

            # alcohol / drugs: {"prob": ...}
            for category in ("alcohol", "drugs"):
                cat_data = data.get(category, {})
                cat_score = _scalar(cat_data, "prob", fallback=_max_leaf(cat_data))
                if cat_score > threshold:
                    violations.append(f"{category}({cat_score:.2f})")

        except Exception as exc:
            raise CensorshipError(
                f"Failed to parse Sightengine response: {exc}"
            ) from exc

        if violations:
            return CensorshipResult(
                is_safe=False,
                reason="NSFW media: " + ", ".join(violations),
                scores=data,
            )

        return CensorshipResult(is_safe=True, scores=data)
