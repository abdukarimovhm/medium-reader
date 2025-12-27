#!/bin/bash
# Wrapper script for medium-read that activates conda environment
# This allows using medium-read from anywhere without manually activating conda

# Find conda installation - try common locations
if [ -f "$HOME/miniforge3/etc/profile.d/conda.sh" ]; then
    CONDA_BASE="$HOME/miniforge3"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    CONDA_BASE="$HOME/anaconda3"
elif [ -f "$HOME/conda/etc/profile.d/conda.sh" ]; then
    CONDA_BASE="$HOME/conda"
elif [ -f "/opt/homebrew/Caskroom/miniforge/base/etc/profile.d/conda.sh" ]; then
    CONDA_BASE="/opt/homebrew/Caskroom/miniforge/base"
else
    echo "Error: Could not find conda installation" >&2
    echo "Please ensure conda is installed or update the CONDA_BASE path in this script" >&2
    exit 1
fi

# Initialize conda
source "$CONDA_BASE/etc/profile.d/conda.sh"

# Activate the medium-reader environment
conda activate medium-reader

# Run the actual command with all arguments
exec medium-read "$@"

