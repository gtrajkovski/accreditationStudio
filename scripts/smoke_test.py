#!/usr/bin/env python3
"""AccreditAI Smoke Test Script.

Verifies all major features are accessible after deployment.

Usage:
    python scripts/smoke_test.py [base_url]

Examples:
    python scripts/smoke_test.py
    python scripts/smoke_test.py http://localhost:5003
"""

import sys
import json
import urllib.request
import urllib.error


def test_endpoint(base_url: str, path: str, method: str = "GET", expected_status: int = 200) -> tuple:
    """Test an endpoint and return (success, message)."""
    url = f"{base_url}{path}"
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.getcode()
            if status == expected_status:
                return True, f"OK ({status})"
            return False, f"Unexpected status: {status} (expected {expected_status})"
    except urllib.error.HTTPError as e:
        if e.code == expected_status:
            return True, f"OK ({e.code})"
        return False, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Connection error: {e.reason}"
    except Exception as e:
        return False, f"Error: {e}"


def run_smoke_tests(base_url: str) -> bool:
    """Run all smoke tests and return overall success."""
    print(f"\nAccreditAI Smoke Test")
    print(f"{'=' * 50}")
    print(f"Base URL: {base_url}\n")

    tests = [
        # Health check
        ("/api/health", "GET", 200, "Health endpoint"),

        # Page routes
        ("/", "GET", 200, "Root redirect"),
        ("/dashboard", "GET", 200, "Dashboard"),
        ("/institutions", "GET", 200, "Institutions list"),
        ("/chat", "GET", 200, "Chat page"),
        ("/settings", "GET", 200, "Settings page"),
        ("/work-queue", "GET", 200, "Work queue"),
        ("/portfolios", "GET", 200, "Portfolios list"),

        # API endpoints (32 blueprints)
        ("/api/institutions", "GET", 200, "Institutions API"),
        ("/api/standards", "GET", 200, "Standards API"),
        ("/api/documents/types", "GET", 200, "Document types API"),
        ("/api/settings", "GET", 200, "Settings API"),
    ]

    passed = 0
    failed = 0

    for path, method, expected, description in tests:
        success, message = test_endpoint(base_url, path, method, expected)
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {description}")
        print(f"         {method} {path} -> {message}")

        if success:
            passed += 1
        else:
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("\nAll smoke tests passed!")
        return True
    else:
        print(f"\n{failed} test(s) failed. Check the application logs.")
        return False


def main():
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5003"

    # Remove trailing slash
    base_url = base_url.rstrip("/")

    # First check if server is reachable
    print(f"Checking server at {base_url}...")
    success, message = test_endpoint(base_url, "/api/health")
    if not success:
        print(f"Server not reachable: {message}")
        print("\nMake sure the application is running:")
        print("  python app.py")
        sys.exit(1)

    # Run smoke tests
    all_passed = run_smoke_tests(base_url)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
