"""config/api.py — 所有 JSON API 共用的小工具（為什麼不用 DRF？見 README「為什麼用純 Django view」）

  api_ok(data)                 → 200 JSON（中文不轉成 \\uXXXX）
  api_error(status, code, 中文原因, **額外欄位) → 4xx JSON：{"ok": false, "error": code, "reason": "..."}
  read_json(request)           → 解析 POST/DELETE 的 JSON body（也接受表單欄位）
"""
import json

from django.http import JsonResponse

JSON_OPTS = {"ensure_ascii": False}


def api_ok(data, status=200):
    return JsonResponse(data, status=status, safe=False, json_dumps_params=JSON_OPTS)


def api_error(status, code, reason, **extra):
    body = {"ok": False, "error": code, "reason": reason}
    body.update(extra)
    return JsonResponse(body, status=status, json_dumps_params=JSON_OPTS)


def read_json(request):
    if request.body and request.content_type == "application/json":
        try:
            data = json.loads(request.body.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (ValueError, UnicodeDecodeError):
            return {}
    return request.POST.dict() if request.method == "POST" else {}


def int_or_none(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
