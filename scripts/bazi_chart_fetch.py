#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""WenZhen-first chart fetcher with local fallback.

Default behavior:
1. Try scripts/pcbz_chart_fetch.mjs for WenZhen professional chart files.
2. If it fails, run scripts/local_bazi_chart_fetch.py and mark the chart as a
   local fallback.

Use --source wenzhen or --source local to force either path.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PCBZ_SCRIPT = SCRIPT_DIR / "pcbz_chart_fetch.mjs"
LOCAL_SCRIPT = SCRIPT_DIR / "local_bazi_chart_fetch.py"


def parse_wrapper_args(argv: list[str]) -> tuple[str, list[str]]:
    parser = argparse.ArgumentParser(
        description="Fetch bazi chart files. Default: WenZhen first, local lunar_python fallback."
    )
    parser.add_argument("--source", choices=["auto", "wenzhen", "local"], default="auto")
    args, rest = parser.parse_known_args(argv)
    return args.source, rest


def run_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(cmd, text=True, capture_output=True, check=False)
    except OSError as error:
        return subprocess.CompletedProcess(cmd, 127, "", str(error))


def print_completed(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def local_args(rest: list[str], fallback_reason: str | None) -> list[str]:
    args = list(rest)
    if fallback_reason:
        args.extend(["--source-mode", "fallback", "--fallback-reason", fallback_reason])
    else:
        args.extend(["--source-mode", "local"])
    return args


def main() -> None:
    source, rest = parse_wrapper_args(sys.argv[1:])

    if source == "local":
        result = run_command([sys.executable, str(LOCAL_SCRIPT), *local_args(rest, None)])
        print_completed(result)
        raise SystemExit(result.returncode)

    wenzhen_result = run_command(["node", str(PCBZ_SCRIPT), *rest])
    if wenzhen_result.returncode == 0:
        print_completed(wenzhen_result)
        return

    if source == "wenzhen":
        print_completed(wenzhen_result)
        raise SystemExit(wenzhen_result.returncode)

    reason = " ".join(
        part.strip()
        for part in [wenzhen_result.stderr, wenzhen_result.stdout]
        if part and part.strip()
    )
    if len(reason) > 1000:
        reason = reason[:1000] + "..."
    print("WenZhen fetch failed; falling back to local lunar_python chart.", file=sys.stderr)
    if reason:
        print(reason, file=sys.stderr)
    local_result = run_command([sys.executable, str(LOCAL_SCRIPT), *local_args(rest, reason)])
    print_completed(local_result)
    raise SystemExit(local_result.returncode)


if __name__ == "__main__":
    main()
