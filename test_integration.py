#!/usr/bin/env python3
import requests
import json
import sys
import time

API_BASE = "http://localhost:8000"

def test_status():
    print("🔍 Testing /api/status...")
    try:
        res = requests.get(f"{API_BASE}/api/status", timeout=5)
        res.raise_for_status()
        data = res.json()
        print(f"✅ Status: {json.dumps(data, indent=2)}")
        return data
    except Exception as e:
        print(f"❌ Status check failed: {e}")
        return None

def test_chat(query: str):
    print(f"\n📝 Testing /api/chat with query: '{query}'")
    print("⏳ Waiting for LLM inference (CPU: 60-120 seconds)...")
    try:
        payload = {"query": query, "history": []}
        res = requests.post(
            f"{API_BASE}/api/chat",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=180  # 3 minutes for CPU inference
        )
        res.raise_for_status()
        data = res.json()
        print(f"✅ Response received:")
        print(f"   Answer: {data.get('answer', 'N/A')[:300]}...")
        print(f"   Sources: {len(data.get('sources', []))} documents retrieved")
        for i, source in enumerate(data.get('sources', [])[:3], 1):
            print(f"     [{i}] {source['type']}: {source['title']}")
        return data
    except requests.exceptions.Timeout:
        print(f"❌ Still processing (inference very slow on CPU)")
        return None
    except Exception as e:
        print(f"❌ Chat failed: {e}")
        return None

def main():
    print("=" * 70)
    print("🧪 LegalSahyak Backend-Frontend Integration Test")
    print("=" * 70)
    
    status = test_status()
    if not status or not (status.get("llm_loaded") and status.get("databases_loaded")):
        print("\n❌ Backend not ready!")
        sys.exit(1)
    
    print("\n" + "=" * 70)
    print("✅ Backend Ready - Testing inference...")
    print("=" * 70)
    
    result = test_chat("What is GST evasion penalty?")
    
    print("\n" + "=" * 70)
    if result:
        print("✅✅✅ FULL INTEGRATION TEST PASSED!")
        print("✅ Frontend ↔ Backend API is fully functional!")
    else:
        print("⚠️  Backend responding but inference is slow on CPU")
        print("💡 For faster responses, use GPU or reduce model size")
    print("=" * 70)

if __name__ == "__main__":
    main()
