#!/usr/bin/env bash

# Source bashrc
source $HOME/.bashrc

# Activate the environment
source activate deleutri

# Run the script
python metric.py $@
