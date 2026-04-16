from __future__ import annotations

import json
import sys
from urllib import error, request


def _request_json(url: str, method: str = "GET", payload: dict | None = None, timeout: int = 10) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    req = request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"请求失败 {method} {url}，status={exc.code}，body={body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"网络请求失败 {method} {url}: {exc}") from exc
    return json.loads(body)


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

    print(f"[smoke] base_url={base_url}")

    health_json = _request_json(f"{base_url}/health", timeout=10)
    print("[smoke] /health:", json.dumps(health_json, ensure_ascii=False))

    models_json = _request_json(f"{base_url}/models", timeout=10)
    print("[smoke] /models:", json.dumps(models_json, ensure_ascii=False))

    test_cases = [
        ("multiple_choice", "单选题：下列选项中正确的是 A.1 B.2 C.3 D.4"),
        ("fill_blank", "填空题：地球是____星。"),
        ("calculation", "计算：2x+3=7，求x。"),
        ("proof", "证明：若a>b且b>c，则a>c。"),
    ]
    for expected_type, question_text in test_cases:
        payload = {
            "text": question_text,
            "user_id": "smoke_user",
            "preferred_model": "mock-primary",
        }
        first = _request_json(f"{base_url}/solve", method="POST", payload=payload, timeout=20)
        print(f"[smoke] /solve first [{expected_type}]:", json.dumps(first, ensure_ascii=False))
        validation = first.get("validation", {})
        if expected_type == "multiple_choice" and first.get("question_type") != "multiple_choice":
            raise RuntimeError("选择题识别失败")
        if expected_type == "fill_blank" and first.get("question_type") != "fill_blank":
            raise RuntimeError("填空题识别失败")
        if expected_type == "calculation" and first.get("question_type") != "calculation":
            raise RuntimeError("计算题识别失败")
        if expected_type == "proof" and first.get("question_type") != "proof":
            raise RuntimeError("证明题识别失败")
        if "method" not in validation or "equivalence_score" not in validation:
            raise RuntimeError("validation 字段不完整，缺少 method/equivalence_score")
        if not isinstance(first.get("agent_outputs", []), list) or not first.get("agent_outputs"):
            raise RuntimeError("首次请求未返回 agent_outputs")

        second = _request_json(f"{base_url}/solve", method="POST", payload=payload, timeout=20)
        print(f"[smoke] /solve second [{expected_type}]:", json.dumps(second, ensure_ascii=False))
        if second.get("cache_hit") is not True:
            raise RuntimeError(f"题型 {expected_type} 第二次请求未命中缓存")
        if not isinstance(second.get("agent_outputs", []), list) or not second.get("agent_outputs"):
            raise RuntimeError("缓存命中后未返回 agent_outputs，可观测性不符合预期")

    print("[smoke] done: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
