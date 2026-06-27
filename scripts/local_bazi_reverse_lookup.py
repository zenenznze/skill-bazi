#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Local four-pillar reverse lookup helper.

This intentionally mirrors only the small, useful path from
https://github.com/china-testing/bazi:

- direct four-pillar reverse lookup calls sxtwl.siZhu2Year(...)
- optional Gregorian verification calls lunar_python Solar.getLunar().getEightChar()

It is a candidate finder, not a replacement for the WenZhen professional chart
fetcher used by the bazi skill pack.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass


GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"


@dataclass
class Candidate:
    datetime: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    pillars: str | None = None
    lunar: str | None = None


def parse_pillar(value: str) -> str:
    value = value.strip()
    if len(value) != 2 or value[0] not in GAN or value[1] not in ZHI:
        raise argparse.ArgumentTypeError(f"invalid pillar: {value}")
    return value


def require_module(name: str):
    try:
        return __import__(name)
    except ModuleNotFoundError:
        print(
            f"Missing dependency: {name}. Install with `pip install sxtwl lunar_python` "
            "or run via `uv run --with sxtwl --with lunar_python ...`.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def gz(value: str):
    sxtwl = require_module("sxtwl")
    return sxtwl.GZ(GAN.index(value[0]), ZHI.index(value[1]))


def eight_char_from_solar(year: int, month: int, day: int, hour: int, minute: int, second: int) -> tuple[str, str]:
    Solar = require_module("lunar_python").Solar
    lunar = Solar.fromYmdHms(year, month, day, hour, minute, second).getLunar()
    eight = lunar.getEightChar()
    pillars = " ".join(
        [
            f"{eight.getYearGan()}{eight.getYearZhi()}",
            f"{eight.getMonthGan()}{eight.getMonthZhi()}",
            f"{eight.getDayGan()}{eight.getDayZhi()}",
            f"{eight.getTimeGan()}{eight.getTimeZhi()}",
        ]
    )
    lunar_text = f"{lunar.getYearInGanZhi()}年 {lunar.getMonthInChinese()}月{lunar.getDayInChinese()} {eight.getTimeZhi()}时"
    return pillars, lunar_text


def reverse_lookup(pillars: list[str], start: int, end: int, verify: bool) -> list[Candidate]:
    sxtwl = require_module("sxtwl")
    jds = sxtwl.siZhu2Year(gz(pillars[0]), gz(pillars[1]), gz(pillars[2]), gz(pillars[3]), start, end)
    candidates = []
    for jd in jds:
        t = sxtwl.JD2DD(jd)
        year = int(t.Y)
        month = int(t.M)
        day = int(t.D)
        hour = int(t.h)
        minute = int(t.m)
        second = int(round(t.s))
        if second == 60:
            second = 0
            minute += 1
        candidate = Candidate(
            datetime=f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}",
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
        )
        if verify:
            candidate.pillars, candidate.lunar = eight_char_from_solar(year, month, day, hour, minute, second)
        candidates.append(candidate)
    return candidates


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reverse lookup Gregorian birth candidates from four pillars using sxtwl.siZhu2Year."
    )
    parser.add_argument("pillars", nargs=4, type=parse_pillar, help="four pillars: year month day hour")
    parser.add_argument("--start", type=int, default=1850, help="start Gregorian year, default: 1850")
    parser.add_argument("--end", type=int, default=2030, help="end Gregorian year, default: 2030")
    parser.add_argument("--verify", action="store_true", help="also verify each candidate with lunar_python")
    args = parser.parse_args()

    candidates = reverse_lookup(args.pillars, args.start, args.end, args.verify)
    print(
        json.dumps(
            {
                "source": "china-testing/bazi key path: sxtwl.siZhu2Year; lunar_python verification",
                "inputPillars": " ".join(args.pillars),
                "range": {"start": args.start, "end": args.end},
                "count": len(candidates),
                "candidates": [asdict(candidate) for candidate in candidates],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
