#!/bin/bash

# Start Ollama in the background
echo "Starting Ollama..."
ollama serve &
OLLAMA_PID=$!

# Optional: Wait for Ollama to boot
sleep 5

# Pull model (idempotent)
echo "Pulling TinyDolphin model..."
ollama pull tinydolphin

# Start Streamlit in the foreground
echo "Launching Streamlit app..."
streamlit run app/main.py --server.address=0.0.0.0 --server.port=8501 &

STREAMLIT_PID=$!

# Wait on Streamlit (keeps container alive)
wait $STREAMLIT_PID

# Clean up on exit (optional)
kill $OLLAMA_PID