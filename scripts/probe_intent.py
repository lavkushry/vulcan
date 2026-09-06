#!/usr/bin/env python3
"""
Project Vulcan: Intent Resolution Single-Session Probe
Validates:
1. Valid query with slot extraction ("renew ssl cert on f5-edge-01.pnc.com in prod for 90 days")
2. Out-of-catalog nonsense refusal ("xyzzy unknown token sequence 12345")
3. Adversarial hallucination refusal ("teleport quantum flux capacitor bake pie")
4. Twin disambiguation with delta_sim ("renew ssl cert on f5 vip")
"""
import argparse
import json
import urllib.request
import urllib.error
import sys

def run_probe(base_url: str, api_token: str = ""):
    url = f"{base_url.rstrip('/')}/api/v1/intent/resolve"
    headers = {"Content-Type": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    probes = [
        {
            "name": "1. Valid Intent & Slot Extraction",
            "prompt": "renew ssl cert on f5-edge-01.pnc.com in prod for 90 days with vip 10.200.1.50",
            "ambient_params": {"requester": "eng.alice", "environment": "PROD"}
        },
        {
            "name": "2. Out-of-Catalog Nonsense Refusal",
            "prompt": "xyzzy unknown token sequence 12345",
            "ambient_params": {}
        },
        {
            "name": "3. Adversarial Sci-Fi Refusal",
            "prompt": "teleport quantum flux capacitor bake pie",
            "ambient_params": {}
        },
        {
            "name": "4. Ambiguous Twin Playbook Disambiguation",
            "prompt": "renew ssl certificate on f5 big-ip vip",
            "ambient_params": {}
        }
    ]

    results = []
    print(f"=== Probing {url} ===")

    for p in probes:
        print(f"\n--- Running Probe: {p['name']} ---")
        print(f"Query: \"{p['prompt']}\"")
        payload = json.dumps({"text": p["prompt"], "ambient_params": p["ambient_params"]}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.getcode()
                body = json.loads(resp.read().decode("utf-8"))
                result_entry = {
                    "name": p["name"],
                    "query": p["prompt"],
                    "http_status": status_code,
                    "response": body
                }
                results.append(result_entry)
                print(f"HTTP Status: {status_code}")
                print(f"Resolved Status: {body.get('status')}")
                print(f"Playbook: {body.get('playbook_identifier')}")
                print(f"Parameters: {body.get('parameters')}")
                print(f"Reason: {body.get('reason')}")
                if body.get("disambiguation"):
                    print(f"Disambiguation: {body.get('disambiguation')}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8")
            print(f"HTTP Error {e.code}: {err_body}")
            results.append({
                "name": p["name"],
                "query": p["prompt"],
                "http_status": e.code,
                "error": err_body
            })
        except Exception as e:
            print(f"Connection Error: {e}")
            results.append({
                "name": p["name"],
                "query": p["prompt"],
                "error": str(e)
            })

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vulcan Intent Resolution Probe")
    parser.add_argument("--url", type=str, default="http://localhost:8000", help="Base URL of vulcan backend")
    parser.add_argument("--token", type=str, default="", help="API Bearer Token if auth enabled")
    parser.add_argument("--output", type=str, default="", help="Save JSON output path")
    args = parser.parse_args()

    results = run_probe(args.url, args.token)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nSaved probe results to {args.output}")
