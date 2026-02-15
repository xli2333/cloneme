from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

from ..config import settings

logger = logging.getLogger("doppelganger.wecom_client")


class WeComApiError(RuntimeError):
    pass


class WeComClient:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token = ""
        self._expires_at = 0.0
        self._base = "https://qyapi.weixin.qq.com"
        self._opener = self._build_opener()

    def _build_opener(self):
        proxy = settings.wecom_proxy_url.strip()
        if not proxy:
            return urllib.request.build_opener()
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        logger.info("wecom proxy enabled")
        return urllib.request.build_opener(handler)

    def _get_json(self, url: str) -> dict[str, Any]:
        with self._opener.open(url, timeout=8) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self._opener.open(req, timeout=8) as resp:  # nosec B310
            return json.loads(resp.read().decode("utf-8"))

    def get_access_token(self, force_refresh: bool = False) -> str:
        if not settings.wecom_corp_id or not settings.wecom_secret:
            raise WeComApiError("WECOM_CORP_ID or WECOM_SECRET is empty")

        now = time.time()
        with self._lock:
            if (not force_refresh) and self._token and now < self._expires_at - 300:
                return self._token

            query = urllib.parse.urlencode(
                {
                    "corpid": settings.wecom_corp_id,
                    "corpsecret": settings.wecom_secret,
                }
            )
            data = self._get_json(f"{self._base}/cgi-bin/gettoken?{query}")
            if int(data.get("errcode", -1)) != 0:
                raise WeComApiError(f"gettoken failed: {data}")

            self._token = str(data.get("access_token", "")).strip()
            if not self._token:
                raise WeComApiError("empty access_token")

            expires_in = int(data.get("expires_in", 7200))
            self._expires_at = now + max(300, expires_in)
            return self._token

    def send_text_message(self, touser: str, content: str) -> dict[str, Any]:
        if not settings.wecom_agent_id:
            raise WeComApiError("WECOM_AGENT_ID is empty")
        text = content.strip()
        if not touser.strip() or not text:
            raise WeComApiError("touser or content is empty")

        payload = {
            "touser": touser.strip(),
            "msgtype": "text",
            "agentid": settings.wecom_agent_id,
            "text": {"content": text[:1800]},
            "safe": 0,
            "enable_duplicate_check": 1,
            "duplicate_check_interval": 1800,
        }

        token = self.get_access_token()
        data = self._send_with_token(payload, token)
        errcode = int(data.get("errcode", -1))
        if errcode in {40014, 42001, 42007}:
            logger.info("access_token expired, retry once")
            token = self.get_access_token(force_refresh=True)
            data = self._send_with_token(payload, token)
            errcode = int(data.get("errcode", -1))

        if errcode != 0:
            raise WeComApiError(f"message/send failed: {data}")
        return data

    def _send_with_token(self, payload: dict[str, Any], token: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"access_token": token})
        url = f"{self._base}/cgi-bin/message/send?{query}"
        return self._post_json(url, payload)


wecom_client = WeComClient()
