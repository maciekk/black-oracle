#!/bin/bash
bold() { printf "\033[1m%s\033[0m" "$*"; }

chat_history="[]"

trap 'echo; echo "Goodbye."; exit 0' INT

while true; do
    echo
    printf "%s " "$(bold Question:)"
    read -r question

    [[ "$question" == "quit" ]] && echo "Goodbye." && exit 0
    [[ -z "$question" ]] && continue

    echo
    echo "Querying..."

    body=$(python3 -c "
import json, sys
q = sys.argv[1]
h = json.loads(sys.argv[2])
print(json.dumps({'question': q, 'chat_history': h}))
" "$question" "$chat_history")

    response=$(curl -s -X POST "http://localhost:8000/chat" \
        -H "Content-Type: application/json" \
        -d "$body")

    echo
    echo "$response" \
        | python3 -c '
import json, sys
data = json.load(sys.stdin)
print(data.get("answer", str(data)))
' | glow

    printf "%s " "$(bold 'Show sources? [y/N]')"
    read -r show_sources
    if [[ "$show_sources" == "y" || "$show_sources" == "Y" ]]; then
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
' | glow
    fi

    answer=$(echo "$response" | python3 -c '
import json, sys
data = json.load(sys.stdin)
print(data.get("answer", ""))
')

    chat_history=$(python3 -c "
import json, sys
h = json.loads(sys.argv[1])
h.append([sys.argv[2], sys.argv[3]])
print(json.dumps(h))
" "$chat_history" "$question" "$answer")

done
