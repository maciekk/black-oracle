#!/bin/sh
curl -X POST "http://localhost:8000/ask" \
     -H "Content-Type: application/json" \
     -d '{"question": "Based on my documents, what are the top three recurring themes in my kettlebell training?"}'
