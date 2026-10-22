#!/bin/sh
uv run python -m pipeline "$@" 2>&1 | tee last-step.log
