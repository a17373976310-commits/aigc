import sys
import os
from fastapi.testclient import TestClient

# Add current directory to path so we can import backend.main
sys.path.append(os.getcwd())

try:
    from backend.main import app
except ImportError:
    # Try adding the parent directory if running from backend/
    sys.path.append(os.path.join(os.getcwd(), '..'))
    from backend.main import app

client = TestClient(app)

def test_index():
    response = client.get("/")
    assert response.status_code == 200
    # Check if it returns the html content (rough check)
    assert "<!DOCTYPE html>" in response.text

def test_history_endpoint():
    response = client.get("/api/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_optimize_prompt_free_mode():
    # Mocking the OpenAI/Gemini call might be needed if we don't want to hit real API
    # But for now let's just see if the endpoint accepts the request.
    # We expect it might fail with API key error or network if not configured, 
    # but we want to check if the route exists and handles params.
    
    # If we don't have a key, it might return error, but status code might be 200 with error message 
    # or 500 depending on implementation.
    # main.py catches exceptions and returns {"status": "error", ...} or 500.
    
    response = client.post(
        "/api/optimize-prompt",
        data={"mode": "free", "prompt": "test prompt"}
    )
    # We accept 200 (success or handled error)
    assert response.status_code == 200
    json_resp = response.json()
    print("Optimize Prompt Response:", json_resp)
    # If API key is missing/invalid, it might be error status
    if json_resp.get("status") == "error":
        print("Got expected error (likely API key/network):", json_resp["message"])
    else:
        assert "optimized_prompt" in json_resp

def test_generate_endpoint_structure():
    # Just testing parameter handling
    # We won't actually generate an image to save cost/time, 
    # but we can check if it validates inputs.
    
    response = client.post(
        "/api/generate",
        data={} # Missing prompt
    )
    # FastAPI validation error for missing field
    assert response.status_code == 422 

if __name__ == "__main__":
    print("Running tests...")
    try:
        test_index()
        print("✓ Index endpoint passed")
        test_history_endpoint()
        print("✓ History endpoint passed")
        test_generate_endpoint_structure()
        print("✓ Generate endpoint structure passed")
        test_optimize_prompt_free_mode()
        print("✓ Optimize prompt endpoint passed (connectivity check)")
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
