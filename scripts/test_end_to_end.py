"""End-to-End Integration Test for Ghana Law Companion.

Tests FastAPI Core Service and NestJS BFF Client & API Gateway together.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
FASTAPI_PORT = 8000
NESTJS_PORT = 3000

# Set environment variables for test execution
os.environ["FASTAPI_URL"] = f"http://127.0.0.1:{FASTAPI_PORT}"
os.environ["API_KEY"] = os.getenv(
    "API_KEY",
    "9b87aaf8645c488a21174f21a0ab693da30a71b4b258de9af3a0b96cabe6d148",
)
os.environ["VECTOR_STORE_BACKEND"] = "local"


def wait_for_url(url: str, timeout: float = 30.0, name: str = "service") -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TestRunner"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def run_tests() -> int:
    print("=" * 70)
    print(">>> STARTING GHANA LAW COMPANION END-TO-END INTEGRATION TEST")
    print("=" * 70)

    fastapi_proc = None
    nestjs_proc = None
    exit_code = 0

    try:
        # 1. Start FastAPI Service
        print(f"\n[1/5] Starting FastAPI backend on port {FASTAPI_PORT}...")
        fastapi_cmd = [
            "uv",
            "run",
            "uvicorn",
            "src.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(FASTAPI_PORT),
        ]
        fastapi_proc = subprocess.Popen(
            fastapi_cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        if not wait_for_url(
            f"http://127.0.0.1:{FASTAPI_PORT}/health/live",
            timeout=25.0,
            name="FastAPI",
        ):
            print("[FAIL] FastAPI failed to start within timeout.")
            return 1
        print("[OK] FastAPI is healthy at /health/live")

        # 2. Start NestJS BFF
        print(f"\n[2/5] Starting NestJS BFF on port {NESTJS_PORT}...")
        nestjs_cmd = ["node", "dist/main.js"]
        nestjs_proc = subprocess.Popen(
            nestjs_cmd,
            cwd=str(ROOT / "nestjs"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env={**os.environ, "PORT": str(NESTJS_PORT)},
        )

        if not wait_for_url(
            f"http://127.0.0.1:{NESTJS_PORT}/api/health/live",
            timeout=25.0,
            name="NestJS BFF",
        ):
            print("[FAIL] NestJS BFF failed to start within timeout.")
            return 1
        print("[OK] NestJS BFF is healthy at /api/health/live")

        # 3. Test Static Assets Serving (Modern Client)
        print("\n[3/5] Verifying Modern Web Client Delivery...")
        
        # Test index.html
        req = urllib.request.Request(f"http://127.0.0.1:{NESTJS_PORT}/")
        with urllib.request.urlopen(req) as resp:
            html = resp.read().decode("utf-8")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "Ghana Law Companion" in html, "index.html missing brand title"
            assert "Constitutional Analysis" in html, "index.html missing UI sections"
            print("   [OK] index.html delivered correctly (Status: 200)")

        # Test app.css
        req = urllib.request.Request(f"http://127.0.0.1:{NESTJS_PORT}/app.css")
        with urllib.request.urlopen(req) as resp:
            css = resp.read().decode("utf-8")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "--gold-primary" in css, "app.css missing CSS theme variables"
            print("   [OK] app.css delivered correctly (Status: 200)")

        # Test app.js
        req = urllib.request.Request(f"http://127.0.0.1:{NESTJS_PORT}/app.js")
        with urllib.request.urlopen(req) as resp:
            js = resp.read().decode("utf-8")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert "CONSTITUTION_CHAPTERS" in js, "app.js missing chapter data"
            print("   [OK] app.js delivered correctly (Status: 200)")

        # 4. Test BFF Connectivity Status Endpoint
        print("\n[4/5] Testing System Status Probes...")
        req = urllib.request.Request(f"http://127.0.0.1:{NESTJS_PORT}/api/health/status")
        with urllib.request.urlopen(req) as resp:
            status_data = json.loads(resp.read().decode("utf-8"))
            print(f"   [OK] Health Status: {status_data}")
            assert status_data.get("bff") == "ok"
            assert status_data.get("fastApi") == "ok"

        # 5. Test Live Constitutional Query through NestJS Gateway
        print("\n[5/5] Executing Live Constitutional RAG Query via NestJS BFF...")
        test_payload = {
            "query": "What are the valid constitutional reasons for restricting a person's personal liberty?",
            "chapter": "5",
        }
        query_req = urllib.request.Request(
            f"http://127.0.0.1:{NESTJS_PORT}/api/query",
            data=json.dumps(test_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(query_req, timeout=45.0) as resp:
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            result = json.loads(resp.read().decode("utf-8"))

            answer_obj = result.get("answer", {})
            answer_text = answer_obj.get("answer", "")
            citations = answer_obj.get("citations", [])
            sources = result.get("sources", [])
            timing = result.get("timing", {})

            print(f"\n   Request ID: {result.get('request_id')}")
            print(f"   Timings: Retrieval={timing.get('retrieval_ms')}ms | Generation={timing.get('generation_ms')}ms | Total={timing.get('total_ms')}ms")
            print(f"   Verified Citations: {citations}")
            print(f"   Sources Returned: {len(sources)} chunks")
            print(f"   Answer Preview:\n      {answer_text[:180]}...")

            assert len(answer_text) > 20, "Answer text was unexpectedly short"
            assert len(citations) > 0, "No citations returned"
            assert any("14" in c for c in citations), "Article 14 should be cited for personal liberty"
            assert len(sources) > 0, "No sources returned"
            print("\n   [OK] Full Query & Grounded Citation Verification PASSED!")

    except Exception as exc:
        print(f"\n[FAIL] TEST FAILED: {exc}")
        import traceback
        traceback.print_exc()
        exit_code = 1
    finally:
        print("\n[Cleaning up processes...]")
        if nestjs_proc:
            nestjs_proc.terminate()
            try:
                nestjs_proc.wait(timeout=3)
            except Exception:
                nestjs_proc.kill()
        if fastapi_proc:
            fastapi_proc.terminate()
            try:
                fastapi_proc.wait(timeout=3)
            except Exception:
                fastapi_proc.kill()

    print("=" * 70)
    if exit_code == 0:
        print("ALL END-TO-END INTEGRATION TESTS PASSED SUCCESSFULLY!")
    else:
        print("INTEGRATION TESTS FAILED.")
    print("=" * 70)
    return exit_code


if __name__ == "__main__":
    sys.exit(run_tests())
