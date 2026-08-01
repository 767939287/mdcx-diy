@echo off
cd /d "%~dp0.."
uv run python scripts\cover_backfill_gui.py
