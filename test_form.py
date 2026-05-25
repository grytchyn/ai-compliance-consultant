#!/usr/bin/env python3
"""
AI Compliance Consultant — Automated Form Test
Submits a real German EE company and verifies report generation.
"""

import time
import sys
import httpx

BACKEND_URL = "https://ai-compliance-consultant.onrender.com"

# Test companies (rotate)
TEST_COMPANIES = [
    {
        "company": "Conrad Electronic SE",
        "url": "https://www.conrad.de",
        "description": "Online-Händler für Elektronik und Technik",
        "email": "test@example.com"
    },
    {
        "company": "MediaMarkt Deutschland",
        "url": "https://www.mediamarkt.de",
        "description": "Elektronik-Fachmarkt für Unterhaltungselektronik",
        "email": "test@example.com"
    },
    {
        "company": "Saturn Electro-Handels GmbH",
        "url": "https://www.saturn.de",
        "description": "Einzelhändler für Elektrogeräte und Elektronik",
        "email": "test@example.com"
    }
]

def get_backend_url():
    """Use environment variable if set, otherwise default."""
    import os
    return os.environ.get("BACKEND_URL", BACKEND_URL)

def health_check():
    """Check if backend is healthy."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/health", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                return True, "Backend healthy"
        return False, f"Health check failed: {resp.status_code}"
    except Exception as e:
        return False, f"Health check error: {e}"

def submit_form(company_data):
    """Submit form and return submission ID."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/submit",
            data=company_data,
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            if "id" in data and data.get("status") == "processing":
                return True, data["id"]
        return False, f"Submission failed: {resp.status_code} - {resp.text}"
    except Exception as e:
        return False, f"Submission error: {e}"

def poll_report(sub_id, max_wait=300):
    """Poll report status until completed or timeout."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            resp = httpx.get(f"{BACKEND_URL}/report/{sub_id}", timeout=30)
            if resp.status_code == 200:
                # Check if it's a file (completed) or JSON (status)
                content_type = resp.headers.get("content-type", "")
                if "text/markdown" in content_type or resp.content.startswith(b"#"):
                    return True, "Report generated successfully", len(resp.content)
                data = resp.json()
                status = data.get("status")
                if status == "completed":
                    return True, "Report completed", 0
                elif status == "failed":
                    return False, "Report generation failed", 0
            elif resp.status_code == 404:
                return False, "Report not found", 0
            else:
                data = resp.json()
                status = data.get("status", "unknown")
                print(f"  Status: {status} (waiting...)")
        except Exception as e:
            print(f"  Poll error: {e}")
        time.sleep(10)
    return False, f"Timeout after {max_wait}s", 0

def main():
    import random
    backend = get_backend_url()
    print(f"Testing backend: {backend}")
    print("=" * 60)
    
    # Step 1: Health check
    print("\n[1/3] Health check...")
    ok, msg = health_check()
    if not ok:
        print(f"❌ FAIL: {msg}")
        sys.exit(1)
    print(f"✅ PASS: {msg}")
    
    # Step 2: Submit form
    print("\n[2/3] Submitting form...")
    company = random.choice(TEST_COMPANIES)
    print(f"Company: {company['company']}")
    print(f"URL: {company['url']}")
    ok, result = submit_form(company)
    if not ok:
        print(f"❌ FAIL: {result}")
        sys.exit(1)
    sub_id = result
    print(f"✅ PASS: Submission ID = {sub_id}")
    
    # Step 3: Poll for report
    print("\n[3/3] Waiting for report (max 5 min)...")
    ok, msg, size = poll_report(sub_id)
    if not ok:
        print(f"❌ FAIL: {msg}")
        sys.exit(1)
    print(f"✅ PASS: {msg} ({size} bytes)")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED")
    sys.exit(0)

if __name__ == "__main__":
    main()
