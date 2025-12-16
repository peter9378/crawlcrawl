import requests
import time
import sys

def test_api():
    url = "http://localhost:8000/search/suggestions"
    params = {"keyword": "속건조"}
    
    print(f"Testing API endpoint: {url} with params: {params}")
    
    max_retries = 30
    for i in range(max_retries):
        try:
            print(f"Attempt {i+1}...")
            response = requests.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("Server is up!")
                break
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            continue
    else:
        print("Server failed to start in time.")
        sys.exit(1)

    try:
        start_time = time.time()
        response = requests.get(url, params=params)
        duration = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Duration: {duration:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            suggestions = data.get("suggestions", [])
            print(f"Suggestions count: {len(suggestions)}")
            print(f"Suggestions: {suggestions}")
            if len(suggestions) > 0:
                print("SUCCESS: Suggestions returned.")
            else:
                print("WARNING: No suggestions returned.")
        else:
            print(f"FAILURE: API returned error: {response.text}")
            sys.exit(1)
            
    except Exception as e:
        print(f"FAILURE: Exception during request: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    test_api()
