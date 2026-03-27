#!/bin/bash
bold() { printf "\033[1m%s\033[0m" "$*"; }

echo
printf "%s " "$(bold Question:)"
read -r question

echo
echo "Querying..."

json_question=$(printf '%s' "$question" \
    | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

response=$(curl -s -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d "{\"question\": $json_question}")

echo
echo "$response" \
    | python3 -c '
import json, sys
data = json.load(sys.stdin)
print(data.get("answer", str(data)))
' \
    | glow

echo "$response" \
    | python3 -c '
import json, sys
data = json.load(sys.stdin)
sources = data.get("sources", [])
if sources:
    print("---\n\n**Sources:**\n")
    for i, s in enumerate(sources, 1):
        path = s.get("metadata", {}).get("source", "unknown")
        preview = s.get("content", "").strip()
        print(f"{i}. `{path}`\n\n{preview}\n")
' \
    | glow
