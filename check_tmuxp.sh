#!/bin/bash

session="trading-algo"
venv_path="./venv/bin/activate"  # Path to your virtual environment
script_path="src/main.py"  # Path to your Python script


# Check if the tmux session exists
if ! tmux has-session -t $session 2>/dev/null; then
    echo "Creating new tmux session: $session"
    tmux new-session -d -s $session  # Create a new detached session
    tmux send-keys -t $session "source $venv_path" C-m  # Activate the virtual environment
    tmux send-keys -t $session "watchmedo auto-restart --directory=./src --pattern='*.py' --recursive -- python -u $script_path" C-m  # Run the Python script
else
    echo "Attaching to existing tmux session: $session"
fi

# Attach to the tmux session
tmux attach-session -t $session