#!/bin/bash

session="trading-algo"
script_path="bot.py"  # Path to your Python script


# Check if the tmux session exists
if ! tmux has-session -t $session 2>/dev/null; then
    echo "Creating new tmux session: $session"
    tmux new-session -d -s $session  # Create a new detached session
    tmux send-keys -t $session "poetry shell" C-m
    sleep 5  # Wait for poetry shell to activate
    # Check if poetry shell is active before proceeding
    tmux send-keys -t $session "if [ -n \"\$POETRY_ACTIVE\" ]; then watchmedo auto-restart --directory=./src --pattern='*.py' --recursive -- python -u $script_path; fi" C-m
else
    echo "Attaching to existing tmux session: $session"
fi

# Attach to the tmux session
tmux attach-session -t $session