#!/usr/bin/env python3
"""
AI Compliance Consultant — Detailed Diagnostics
Checks backend configuration and tests full pipeline.
"""

import httpx
import sys
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "https://ai-verify.onrender.com")

def test_endpoint(method, path, **kwargs):
    """Test an endpoint and return status + response."""
    try:
        resp = httpx.request(method, f"{BACKEND_URL}{path}", timeout=30, **kwargs)
        return resp.status_code, resp.text[:500] if resp.text else ""
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 70)
    print(f"AI Compliance Consultant — Diagnostics")
    print(f"Backend: {BACKEND_URL}")
    print("=" * 70)
    
    # 1. Health check
    print("\n[1] Health endpoint...")
    status, body = test_endpoint("GET", "/health")
    if status == 200:
        print(f"✅ /health: {status} - {body}")
    else:
        print(f"❌ /health: {status} - {body}")
        return 1
    
    # 2. Submit test form
    print("\n[2] Submit form...")
    test_data = {
        "company": "Test Firma GmbH",
        "url": "https://example.com",
        "description": "Testunternehmen",
    }
    status, body = test_endpoint("POST", "/submit", data=test_data)
    if status == 200 and "id" in body:
        import json
        data = json.loads(body)
        sub_id = data.get("id")
        print(f"✅ /submit: {status} - ID: {sub_id}")
    else:
        print(f"❌ /submit: {status} - {body}")
        return 1
    
    # 3. Wait and check status
    print("\n[3] Polling status (30s)...")
    import time
    time.sleep(30)
    status, body = test_endpoint("GET", f"/report/{sub_id}")
    if status == 200:
        if "status" in body:
            import json
            data = json.loads(body)
            report_status = data.get("status")
            print(f"Status: {report_status}")
            if report_status == "completed":
                print("✅ Report completed!")
                return 0
            elif report_status == "failed":
                print("❌ Report FAILED")
                print("\nPossible causes:")
                print("  - OLLAMA_API_BASE not set on Render")
                print("  - OLLAMA_MODEL not configured")
                print("  - DATABASE_URL missing or invalid")
                print("  - LLM API unreachable")
                print("\nCheck Render dashboard → Environment Variables")
                return 1
            else:
                print(f"⏳ Still processing: {report_status}")
                return 1
        else:
            print(f"✅ Report file returned ({len(body)} bytes)")
            return 0
    else:
        print(f"❌ /report: {status} - {body}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
