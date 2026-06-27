#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generate a local structured bazi chart with lunar_python.

This is the fallback chart generator for the bazi skill pack. It is deliberately
separate from the WenZhen API fetcher: when WenZhen is available, prefer
pcbz_chart_fetch.mjs. When it is unavailable, this script creates a traceable
local chart.json/chart.md with the fields needed by later analysis skills.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from local_bazi_reverse_lookup import reverse_lookup


DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "work" / "local-bazi"


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


def local_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_stamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def normalize_sex(value: str) -> int:
    normalized = str(value).lower()
    if normalized in {"1", "male", "m", "男"}:
        return 1
    if normalized in {"0", "female", "f", "女"}:
        return 0
    raise argparse.ArgumentTypeError("--sex must be male|female, 男|女, 1|0")


def normalize_datetime(date: str | None, time: str | None) -> str:
    if not date or not time:
        raise ValueError("--date and --time are required when --pillars is not provided")
    if not re_date(date):
        raise ValueError("--date must use YYYY-MM-DD")
    if not re_time(time):
        raise ValueError("--time must use HH:mm or HH:mm:ss")
    return f"{date} {time if len(time) == 8 else time + ':00'}"


def normalize_standalone_datetime(value: str) -> str:
    value = value.strip()
    if not re_datetime(value):
        raise ValueError('datetime must use "YYYY-MM-DD HH:mm" or "YYYY-MM-DD HH:mm:ss"')
    return value if len(value) == 19 else f"{value}:00"


def re_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def re_time(value: str) -> bool:
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            pass
    return False


def re_datetime(value: str) -> bool:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            pass
    return False


def parse_dt(value: str) -> datetime:
    return datetime.strptime(normalize_standalone_datetime(value), "%Y-%m-%d %H:%M:%S")


def format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def format_date(value: datetime) -> str:
    return value.strftime("%Y-%m-%d")


def add_years(value: datetime, years: int) -> datetime:
    try:
        return value.replace(year=value.year + years)
    except ValueError:
        return value.replace(year=value.year + years, day=28)


def normalize_pillars(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    items: list[str] = []
    for value in values:
        items.extend(str(value).split())
    if len(items) != 4:
        raise ValueError('--pillars must contain four pillars, e.g. --pillars "庚辰 戊寅 己酉 辛未"')
    for item in items:
        if len(item) != 2:
            raise ValueError(f"invalid pillar: {item}")
    return items


@dataclass
class ResolvedInput:
    datetime: str
    reverse_lookup: dict[str, Any] | None


def resolve_input(args: argparse.Namespace) -> ResolvedInput:
    pillars = normalize_pillars(args.pillars)
    if not pillars:
        return ResolvedInput(datetime=normalize_datetime(args.date, args.time), reverse_lookup=None)

    candidates = reverse_lookup(pillars, args.start, args.end, verify=True)
    if not candidates:
        raise ValueError(f"No Gregorian candidates found for pillars: {' '.join(pillars)}")
    candidate_index = len(candidates) // 2 if args.candidate_index is None else int(args.candidate_index)
    if candidate_index < 0 or candidate_index >= len(candidates):
        raise ValueError(f"--candidate-index must be between 0 and {len(candidates) - 1}")
    selected = candidates[candidate_index]
    return ResolvedInput(
        datetime=selected.datetime,
        reverse_lookup={
            "requestedPillars": {"spaced": " ".join(pillars), "joined": "".join(pillars)},
            "candidates": [asdict(candidate) for candidate in candidates],
            "selectedIndex": candidate_index,
            "selectedDatetime": selected.datetime,
            "selectionMode": "default-middle" if args.candidate_index is None else "explicit",
            "range": {"start": args.start, "end": args.end},
            "engine": "sxtwl.siZhu2Year",
        },
    )


def call(obj: Any, method: str, default: Any = "") -> Any:
    if not hasattr(obj, method):
        return default
    try:
        return getattr(obj, method)()
    except Exception:
        return default


def jq_info(lunar: Any, prev: bool) -> dict[str, str]:
    jq = lunar.getPrevJieQi(True) if prev else lunar.getNextJieQi(True)
    return {"name": str(jq), "datetime": jq.getSolar().toYmdHms()}


def pillar_data(eight: Any, prefix: str, label: str) -> dict[str, Any]:
    gan = call(eight, f"get{prefix}Gan")
    zhi = call(eight, f"get{prefix}Zhi")
    return {
        "label": label,
        "pillar": f"{gan}{zhi}",
        "stem": gan,
        "branch": zhi,
        "stemStar": call(eight, f"get{prefix}ShiShenGan"),
        "hiddenStems": call(eight, f"get{prefix}HideGan", []),
        "hiddenStemStars": call(eight, f"get{prefix}ShiShenZhi", []),
        "nayin": call(eight, f"get{prefix}NaYin"),
    }


def build_dayun_periods(yun: Any, first_start: datetime) -> list[dict[str, Any]]:
    periods = []
    dayuns = yun.getDaYun()[1:]
    for offset, dayun in enumerate(dayuns):
        start = add_years(first_start, offset * 10)
        next_start = add_years(first_start, (offset + 1) * 10)
        end = next_start - timedelta(seconds=1)
        liunian = []
        for item in dayun.getLiuNian():
            liunian.append(
                {
                    "year": item.getYear(),
                    "age": item.getAge(),
                    "ganzhi": item.getGanZhi(),
                }
            )
        periods.append(
            {
                "index": dayun.getIndex(),
                "pillar": dayun.getGanZhi(),
                "startAge": dayun.getStartAge(),
                "endAge": dayun.getEndAge(),
                "startYear": dayun.getStartYear(),
                "endYear": dayun.getEndYear(),
                "startDate": format_date(start),
                "endDate": format_date(end),
                "yearRange": f"{dayun.getStartYear()}-{dayun.getEndYear()}",
                "ageRange": f"{dayun.getStartAge()}-{dayun.getEndAge()}岁",
                "xun": dayun.getXun(),
                "xunKong": dayun.getXunKong(),
                "years": liunian,
            }
        )
    return periods


def hidden_text(branch: str, stems: list[str], stars: list[str]) -> str:
    if not stems:
        return ""
    parts = [f"{stem}{stars[index] if index < len(stars) else ''}" for index, stem in enumerate(stems)]
    return f"{branch}藏{'、'.join(parts)}"


def render_core_table(pillars: list[dict[str, Any]]) -> str:
    rows = [
        "| 柱位 | 干支 | 天干十神 | 地支藏干十神 |",
        "|---|---|---|---|",
    ]
    for item in pillars:
        rows.append(
            f"| {item['label']} | {item['pillar']} | {item['stem']}{item['stemStar']} | "
            f"{hidden_text(item['branch'], item['hiddenStems'], item['hiddenStemStars'])} |"
        )
    return "\n".join(rows)


def render_dayun_table(periods: list[dict[str, Any]]) -> str:
    if not periods:
        return "- 无"
    rows = [
        "| 序 | 大运 | 起止日期 | 公历年份 | 年龄段 |",
        "|---|---|---|---|---|",
    ]
    for item in periods:
        rows.append(
            f"| {item['index']} | {item['pillar']} | {item['startDate']} 至 {item['endDate']} | "
            f"{item['yearRange']} | {item['ageRange']} |"
        )
    return "\n".join(rows)


def render_liunian(periods: list[dict[str, Any]]) -> str:
    if not periods:
        return "- 无"
    lines = []
    for item in periods:
        years = "、".join(f"{year['year']} {year['ganzhi']}" for year in item["years"])
        lines.append(f"- {item['pillar']}（{item['yearRange']}）：{years}")
    return "\n".join(lines)


def render_raw_table(pillars: list[dict[str, Any]]) -> str:
    labels = [item["label"] for item in pillars]
    rows = [
        f"| 日期 | {' | '.join(labels)} |",
        f"|---|{'|'.join('---' for _ in labels)}|",
        f"| 干支 | {' | '.join(item['pillar'] for item in pillars)} |",
        f"| 主星 | {' | '.join(item['stemStar'] for item in pillars)} |",
        f"| 天干 | {' | '.join(item['stem'] for item in pillars)} |",
        f"| 地支 | {' | '.join(item['branch'] for item in pillars)} |",
        f"| 藏干 | {' | '.join(' '.join(item['hiddenStems']) for item in pillars)} |",
        f"| 副星 | {' | '.join(' '.join(item['hiddenStemStars']) for item in pillars)} |",
        f"| 纳音 | {' | '.join(item['nayin'] for item in pillars)} |",
    ]
    return "\n".join(rows)


def render_markdown(parsed: dict[str, Any]) -> str:
    input_data = parsed["input"]
    pillars = parsed["analysisCore"]["pillarsList"]
    dayun_periods = parsed["analysisCore"]["dayunPeriods"]
    source_title = "本地八字排盘底稿"
    if input_data.get("sourceMode") == "fallback":
        source_title = "本地八字排盘底稿（问真失败兜底）"

    reverse = input_data.get("reverseLookup")
    reverse_block = ""
    if reverse:
        candidates = "；".join(
            f"{index}. {candidate['datetime']}" for index, candidate in enumerate(reverse["candidates"])
        )
        reverse_block = f"""- 输入四柱：{reverse['requestedPillars']['spaced']}
- 候选公历：{candidates}
- 采用候选：{reverse['selectedIndex']}. {reverse['selectedDatetime']}
- 候选选择：{'未指定候选，默认采用中间候选。' if reverse['selectionMode'] == 'default-middle' else '调用方显式指定候选编号。'}"""

    fallback_reason = ""
    if input_data.get("fallbackReason"):
        fallback_reason = f"\n- 问真失败原因：{input_data['fallbackReason']}"

    prev_jq = parsed["solarTerms"]["previous"]
    next_jq = parsed["solarTerms"]["next"]
    traditional = parsed["traditional"]
    qiyun = parsed["analysisCore"]["qiyun"]

    return f"""# {source_title}

## 来源

- 排盘来源：本地 `lunar_python` 结构化排盘
- 四柱反推来源：本地 `sxtwl.siZhu2Year`（仅四柱入口时使用）
- 采集方式：本地库计算，非问真接口响应
- 采集时间：{parsed['fetchedAt']}
- 原始数据文件：{parsed['rawFile']}
- 边界说明：本地底稿不包含问真 raw、人元司令接口、问真格局接口；若问真恢复可用，应优先补跑问真专业细盘。{fallback_reason}

## 输入

- 姓名：{input_data['name']}
- 性别：{'男' if input_data['sex'] == 1 else '女'}
- 排盘方式：{'四柱反推公历后排盘' if reverse else '公历出生时间排盘'}
{reverse_block}
- 北京时间：{input_data['datetime']}
- 排盘采用时间：{input_data['sunTime']}
- 子时设置：本地库默认口径；若涉及早晚子时争议，必须另列候选盘验证。

## 基本信息

- 公历：{parsed['solar']['datetime']}
- 农历：{parsed['lunar']['text']}
- 四柱：{parsed['pillars']['spaced']}
- 前一节气：{prev_jq['name']}：{prev_jq['datetime']}
- 后一节气：{next_jq['name']}：{next_jq['datetime']}
- 节气区间：{prev_jq['name']}后、{next_jq['name']}前
- 起运时间：{qiyun['startSolar']}
- 起运差：出生后约 {qiyun['startYear']} 年 {qiyun['startMonth']} 个月 {qiyun['startDay']} 天 {qiyun['startHour']} 时
- 命宫：{traditional['mingGong']}
- 胎元：{traditional['taiYuan']}
- 身宫：{traditional['shenGong']}
- 胎息：{traditional['taiXi']}

## 后续分析必读

### 四柱十神核心表

{render_core_table(pillars)}

### 起运与大运年份表

{render_dayun_table(dayun_periods)}

### 流年索引

{render_liunian(dayun_periods)}

## 低优先级附录

### 传统细盘补充

- 胎息：{traditional['taiXi']}（{traditional['taiXiNaYin']}）
- 胎元：{traditional['taiYuan']}（{traditional['taiYuanNaYin']}）
- 命宫：{traditional['mingGong']}（{traditional['mingGongNaYin']}）
- 身宫：{traditional['shenGong']}（{traditional['shenGongNaYin']}）

### 本地原始排盘表

{render_raw_table(pillars)}

## 后续分析要求

后续验盘、正统子平、关系、健康、事业等分析，必须优先引用“后续分析必读”中的四柱十神、藏干十神、大运年份和流年索引；低优先级附录只作辅助，不作为主证。若问真接口恢复可用，应补跑问真专业细盘并以问真底稿作为优先来源。
"""


def build_chart(args: argparse.Namespace) -> dict[str, Any]:
    Solar = require_module("lunar_python").Solar
    resolved = resolve_input(args)
    sun_time = normalize_standalone_datetime(args.sun_time) if args.sun_time else resolved.datetime
    dt = parse_dt(sun_time)

    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    lunar = solar.getLunar()
    eight = lunar.getEightChar()
    yun = eight.getYun(args.sex == 1)
    first_start = parse_dt(yun.getStartSolar().toYmdHms())

    pillars = [
        pillar_data(eight, "Year", "年柱"),
        pillar_data(eight, "Month", "月柱"),
        pillar_data(eight, "Day", "日柱"),
        pillar_data(eight, "Time", "时柱"),
    ]
    spaced = " ".join(item["pillar"] for item in pillars)
    joined = "".join(item["pillar"] for item in pillars)
    dayun_periods = build_dayun_periods(yun, first_start)

    parsed = {
        "source": "local-lunar-python",
        "sourcePriority": "fallback-after-wenzhen",
        "fetchedAt": local_timestamp(),
        "rawFile": "",
        "input": {
            "name": args.name,
            "sex": args.sex,
            "datetime": resolved.datetime,
            "sunTime": sun_time,
            "sourceMode": args.source_mode,
            "fallbackReason": args.fallback_reason,
            "midnight": args.midnight,
            "reverseLookup": resolved.reverse_lookup,
        },
        "solar": {
            "datetime": solar.toYmdHms(),
            "full": solar.toFullString(),
        },
        "lunar": {
            "text": f"{lunar.getYearInGanZhi()}年 {lunar.getMonthInChinese()}月{lunar.getDayInChinese()} {eight.getTimeZhi()}时",
            "simple": lunar.toString(),
            "full": lunar.toFullString(),
        },
        "solarTerms": {
            "previous": jq_info(lunar, True),
            "next": jq_info(lunar, False),
        },
        "pillars": {
            "year": pillars[0]["pillar"],
            "month": pillars[1]["pillar"],
            "day": pillars[2]["pillar"],
            "hour": pillars[3]["pillar"],
            "joined": joined,
            "spaced": spaced,
        },
        "traditional": {
            "mingGong": call(eight, "getMingGong"),
            "mingGongNaYin": call(eight, "getMingGongNaYin"),
            "taiYuan": call(eight, "getTaiYuan"),
            "taiYuanNaYin": call(eight, "getTaiYuanNaYin"),
            "shenGong": call(eight, "getShenGong"),
            "shenGongNaYin": call(eight, "getShenGongNaYin"),
            "taiXi": call(eight, "getTaiXi"),
            "taiXiNaYin": call(eight, "getTaiXiNaYin"),
        },
        "analysisCore": {
            "pillarsList": pillars,
            "pillars": {
                "year": pillars[0],
                "month": pillars[1],
                "day": pillars[2],
                "hour": pillars[3],
            },
            "qiyun": {
                "startYear": yun.getStartYear(),
                "startMonth": yun.getStartMonth(),
                "startDay": yun.getStartDay(),
                "startHour": yun.getStartHour(),
                "startSolar": yun.getStartSolar().toYmdHms(),
                "startAge": dayun_periods[0]["startAge"] if dayun_periods else None,
            },
            "dayunPeriods": dayun_periods,
        },
    }
    return parsed


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate local bazi chart files using lunar_python, for WenZhen fallback."
    )
    parser.add_argument("--date", help="Gregorian date, YYYY-MM-DD")
    parser.add_argument("--time", help="Gregorian time, HH:mm or HH:mm:ss")
    parser.add_argument("--pillars", nargs="+", help='Four pillars, e.g. --pillars "庚辰 戊寅 己酉 辛未"')
    parser.add_argument("--candidate-index", type=int, help="Candidate index from --pillars reverse lookup")
    parser.add_argument("--start", type=int, default=1850, help="Reverse lookup start year")
    parser.add_argument("--end", type=int, default=2030, help="Reverse lookup end year")
    parser.add_argument("--sex", required=True, type=normalize_sex, help="male|female, 男|女, 1|0")
    parser.add_argument("--name", default="命主", help="Chart owner name")
    parser.add_argument("--output", help="Output directory. Default: work/local-bazi/<timestamp>")
    parser.add_argument("--sun-time", help='True-solar datetime, "YYYY-MM-DD HH:mm[:ss]"')
    parser.add_argument("--source-mode", choices=["local", "fallback"], default="local")
    parser.add_argument("--fallback-reason", default="")
    parser.add_argument("--midnight", default="default", help="Compatibility field; local engine uses its default")
    parser.add_argument("--today", help="Accepted for compatibility with pcbz_chart_fetch.mjs; ignored")
    parser.add_argument("--vip", help="Accepted for compatibility with pcbz_chart_fetch.mjs; ignored")
    parser.add_argument("--user-guid", help="Accepted for compatibility with pcbz_chart_fetch.mjs; ignored")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    output_dir = Path(args.output or (DEFAULT_OUTPUT_ROOT / safe_stamp())).resolve()
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    parsed = build_chart(args)
    raw_file = raw_dir / "local_lunar_python.json"
    parsed["rawFile"] = str(raw_file)
    chart_json = output_dir / "chart.json"
    chart_md = output_dir / "chart.md"

    raw_payload = {
        "source": parsed["source"],
        "input": parsed["input"],
        "solar": parsed["solar"],
        "lunar": parsed["lunar"],
        "solarTerms": parsed["solarTerms"],
        "pillars": parsed["pillars"],
        "traditional": parsed["traditional"],
        "analysisCore": parsed["analysisCore"],
    }
    raw_file.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf8")
    chart_json.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf8")
    chart_md.write_text(render_markdown(parsed), encoding="utf8")

    print(
        json.dumps(
            {
                "outputDir": str(output_dir),
                "chartJson": str(chart_json),
                "chartMd": str(chart_md),
                "source": parsed["source"],
                "pillars": parsed["pillars"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
