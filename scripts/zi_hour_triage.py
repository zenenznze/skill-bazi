#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Triage near-zi-hour bazi cases before chart generation.

This helper does not replace the WenZhen chart fetcher. It turns a recorded
birth time, optional birthplace/longitude, and DST context into a reproducible
candidate plan for bazi-dingpan.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent.parent / "work" / "zi-hour"
EAST_8_CENTRAL_LONGITUDE = 120.0

BRANCHES = [
    ("子", 23, 1),
    ("丑", 1, 3),
    ("寅", 3, 5),
    ("卯", 5, 7),
    ("辰", 7, 9),
    ("巳", 9, 11),
    ("午", 11, 13),
    ("未", 13, 15),
    ("申", 15, 17),
    ("酉", 17, 19),
    ("戌", 19, 21),
    ("亥", 21, 23),
]

KNOWN_LONGITUDES = {
    "北京": 116.4074,
    "天津": 117.2000,
    "上海": 121.4737,
    "重庆": 106.5516,
    "成都": 104.0665,
    "四川成都": 104.0665,
    "四川": 104.0,
    "广州": 113.2644,
    "广东广州": 113.2644,
    "深圳": 114.0579,
    "杭州": 120.1551,
    "南京": 118.7969,
    "武汉": 114.3054,
    "西安": 108.9398,
    "郑州": 113.6254,
    "济南": 117.1201,
    "青岛": 120.3826,
    "沈阳": 123.4315,
    "哈尔滨": 126.6424,
    "长春": 125.3235,
    "呼和浩特": 111.7492,
    "太原": 112.5489,
    "石家庄": 114.5149,
    "南昌": 115.8582,
    "福州": 119.2965,
    "厦门": 118.0894,
    "合肥": 117.2272,
    "长沙": 112.9388,
    "南宁": 108.3669,
    "贵阳": 106.6302,
    "昆明": 102.8332,
    "拉萨": 91.1322,
    "西藏拉萨": 91.1322,
    "乌鲁木齐": 87.6168,
    "新疆乌鲁木齐": 87.6168,
    "喀什": 75.9898,
    "兰州": 103.8343,
    "银川": 106.2309,
    "西宁": 101.7782,
    "海口": 110.1983,
    "三亚": 109.5119,
    "香港": 114.1694,
    "澳门": 113.5439,
    "台北": 121.5654,
}

CHINA_DST_RANGES = [
    (date(1986, 5, 4), date(1986, 9, 14)),
    (date(1987, 4, 12), date(1987, 9, 13)),
    (date(1988, 4, 10), date(1988, 9, 11)),
    (date(1989, 4, 16), date(1989, 9, 17)),
    (date(1990, 4, 15), date(1990, 9, 16)),
    (date(1991, 4, 14), date(1991, 9, 15)),
]


@dataclass
class TimeView:
    key: str
    label: str
    datetime: str
    branch: str
    zi_segment: str
    is_zi: bool
    minutes_to_zi_start: int
    minutes_to_zi_end: int
    note: str


@dataclass
class ChartCandidate:
    key: str
    label: str
    beijing_datetime: str
    datetime: str
    yzs: str
    output: str
    reason: str
    command: list[str]


def parse_dt(date_text: str, time_text: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(f"{date_text} {time_text}", fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError("--date/--time must use YYYY-MM-DD and HH:mm[:ss]")


def fmt_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def safe_stamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def resolve_longitude(birthplace: str | None, longitude: float | None) -> tuple[float | None, str]:
    if longitude is not None:
        return longitude, "explicit"
    if not birthplace:
        return None, "missing"
    normalized = "".join(str(birthplace).split())
    matches = [key for key in KNOWN_LONGITUDES if key in normalized]
    if not matches:
        return None, "unresolved"
    key = max(matches, key=len)
    return KNOWN_LONGITUDES[key], f"matched:{key}"


def in_china_dst(value: datetime) -> bool:
    d = value.date()
    return any(start <= d <= end for start, end in CHINA_DST_RANGES)


def branch_for(value: datetime) -> str:
    hour = value.hour
    if hour == 23 or hour == 0:
        return "子"
    for branch, start, end in BRANCHES[1:]:
        if start <= hour < end:
            return branch
    raise ValueError(f"cannot resolve branch for hour {hour}")


def zi_segment(value: datetime) -> str:
    if branch_for(value) != "子":
        return "非子时"
    if value.hour == 23:
        return "夜子/晚子，传统口径多按当日夜论；部分软件会按次日子初换日"
    return "早子/子正后，通常按公历当日早论"


def minute_of_day(value: datetime) -> int:
    return value.hour * 60 + value.minute


def distance_to_minute(value: datetime, target: int) -> int:
    current = minute_of_day(value)
    return min((current - target) % 1440, (target - current) % 1440)


def build_time_view(key: str, label: str, value: datetime, note: str) -> TimeView:
    return TimeView(
        key=key,
        label=label,
        datetime=fmt_dt(value),
        branch=branch_for(value),
        zi_segment=zi_segment(value),
        is_zi=branch_for(value) == "子",
        minutes_to_zi_start=distance_to_minute(value, 23 * 60),
        minutes_to_zi_end=distance_to_minute(value, 60),
        note=note,
    )


def output_slug(text: str) -> str:
    allowed = []
    for char in text.lower():
        if char.isalnum() or char in {"-", "_"}:
            allowed.append(char)
        elif char.isspace():
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    return slug or "candidate"


def chart_command(args: argparse.Namespace, beijing_dt_text: str, sun_dt_text: str, yzs: str, output: str) -> list[str]:
    dt = datetime.strptime(beijing_dt_text, "%Y-%m-%d %H:%M:%S")
    return [
        "python3",
        "scripts/bazi_chart_fetch.py",
        "--source",
        "auto",
        "--date",
        dt.strftime("%Y-%m-%d"),
        "--time",
        dt.strftime("%H:%M"),
        "--sex",
        args.sex,
        "--name",
        args.name,
        "--sun-time",
        sun_dt_text,
        "--midnight",
        yzs,
        "--output",
        output,
    ]


def add_candidate(
    candidates: list[ChartCandidate],
    seen: set[tuple[str, str]],
    args: argparse.Namespace,
    base_output: Path,
    beijing_view: TimeView,
    view: TimeView,
    yzs: str,
    reason: str,
) -> None:
    identity = (view.datetime, yzs)
    if identity in seen:
        return
    seen.add(identity)
    key = f"{view.key}-yzs{yzs}"
    output = str(base_output / output_slug(key))
    candidates.append(
        ChartCandidate(
            key=key,
            label=f"{view.label} / yzs={yzs}",
            beijing_datetime=beijing_view.datetime,
            datetime=view.datetime,
            yzs=yzs,
            output=output,
            reason=reason,
            command=chart_command(args, beijing_view.datetime, view.datetime, yzs, output),
        )
    )


def build_candidates(
    args: argparse.Namespace,
    output_dir: Path,
    views: list[TimeView],
    boundary_window: int,
) -> list[ChartCandidate]:
    candidates: list[ChartCandidate] = []
    seen: set[tuple[str, str]] = set()
    chart_root = output_dir / "charts"

    recorded_view = next(view for view in views if view.key == "recorded-clock")
    standard_view = next(view for view in views if view.key == "standard-beijing")
    if standard_view.is_zi:
        add_candidate(candidates, seen, args, chart_root, standard_view, standard_view, "0", "北京时间落子时，以问真原生口径排盘。")
    else:
        add_candidate(candidates, seen, args, chart_root, standard_view, standard_view, "0", "北京时间未落子时，作为基础盘。")

    if args.dst == "auto" and recorded_view.datetime != standard_view.datetime:
        if recorded_view.is_zi:
            add_candidate(candidates, seen, args, chart_root, recorded_view, recorded_view, "0", "日期落在夏令时实行期；若记录时间已被转述为标准北京时间，保留未减一小时的子时口径。")
        elif recorded_view.branch != standard_view.branch or recorded_view.minutes_to_zi_start <= boundary_window or recorded_view.minutes_to_zi_end <= boundary_window:
            add_candidate(candidates, seen, args, chart_root, recorded_view, recorded_view, "0", "日期落在夏令时实行期；保留未减一小时的记录时间候选以待核验。")

    solar_views = [view for view in views if view.key in {"longitude-solar", "recorded-longitude-solar"}]
    for view in solar_views:
        beijing_base = recorded_view if view.key == "recorded-longitude-solar" else standard_view
        boundary_sensitive = (
            view.is_zi
            or beijing_base.is_zi
            or view.branch != beijing_base.branch
            or view.minutes_to_zi_start <= boundary_window
            or view.minutes_to_zi_end <= boundary_window
        )
        if not boundary_sensitive:
            continue
        if view.is_zi:
            add_candidate(candidates, seen, args, chart_root, beijing_base, view, "0", "经度校正后落子时，以问真原生口径排盘。")
        else:
            add_candidate(
                candidates,
                seen,
                args,
                chart_root,
                beijing_base,
                view,
                "0",
                "经度校正后不在子时，优先作为真太阳时方向的正式候选。",
            )

    return candidates


def shell_line(command: list[str]) -> str:
    parts = []
    for part in command:
        if any(ch.isspace() for ch in part) or any(ord(ch) > 127 for ch in part):
            escaped = part.replace('"', '\\"')
            parts.append(f'"{escaped}"')
        else:
            parts.append(part)
    return " ".join(parts)


def render_markdown(report: dict[str, Any]) -> str:
    input_data = report["input"]
    location = report["location"]
    correction = report["correction"]
    views = report["timeViews"]
    candidates = report["chartCandidates"]
    risk = report["risk"]

    time_rows = [
        "| 口径 | 时间 | 时辰 | 子时段 | 说明 |",
        "|---|---|---|---|---|",
    ]
    for item in views:
        time_rows.append(
            f"| {item['label']} | {item['datetime']} | {item['branch']} | {item['ziSegment']} | {item['note']} |"
        )

    candidate_rows = [
        "| 候选 | 北京时间 | 排盘采用时间 | yzs | 输出目录 | 理由 |",
        "|---|---|---|---|---|---|",
    ]
    for item in candidates:
        candidate_rows.append(
            f"| {item['label']} | {item['beijingDatetime']} | {item['datetime']} | {item['yzs']} | `{item['output']}` | {item['reason']} |"
        )

    commands = "\n".join(shell_line(item["command"]) for item in candidates) or "# 无需生成候选盘"

    return f"""# 子时定盘分诊报告

## 输入

- 姓名：{input_data['name']}
- 性别：{input_data['sex']}
- 记录时间：{input_data['recordedDatetime']}
- 出生地：{input_data.get('birthplace') or '未提供'}
- 经度：{location.get('longitude') if location.get('longitude') is not None else '未解析'}（{location['source']}）
- 夏令时处理：{correction['dstMode']}；{correction['dstNote']}

## 时间换算

- 东八区中央经线：{correction['centralLongitude']}E
- 经度差：{correction['longitudeDeltaDegrees'] if correction['longitudeDeltaDegrees'] is not None else '未知'} 度
- 经度折算：{correction['longitudeOffsetMinutes'] if correction['longitudeOffsetMinutes'] is not None else '未知'} 分钟

{chr(10).join(time_rows)}

## 风险判断

- 风险等级：{risk['level']}
- 核心争议：{risk['summary']}
- 处理原则：先分清“是否入子时”和“入子时后是否换日”；如果经度校正后已经退回亥时，早晚子时争议不作为正式主线。

## 候选盘计划

{chr(10).join(candidate_rows)}

### 建议执行命令

```bash
{commands}
```

## Mom Test 式前事核验问题

开场建议：我们先不判断你是什么性格，也不让你配合任何结论。我只是帮你整理一份事实时间线，用来核对出生时间边界。你尽量说真实发生过的事：时间、地点、谁在场、发生了什么、后来怎么处理。如果某一年没事，直接说无。

### 出生时间证据

1. 这个出生时间是从哪里来的？出生证明、医院记录、户口材料、家人口述，还是后来听说的？
2. 家里有没有人对出生时间有过不同说法？原话大概怎么说，比如“晚上”“快 23 点”“夜里”“吃完饭后”。
3. 有没有可能是四舍五入、记错日期、夏令时、地方时间、医院或家里钟表本身不准，或后来补登记？

### 事实采集

1. 从小学到现在，最记得清楚的 5 个年份或年龄段是什么？每个年份发生了什么？
2. 小学、初中、高中、大学或工作阶段，有没有换学校、搬家、换城市、休学、转专业、换方向？分别是哪一年？
3. 家里做重大决定时，印象最深的一次是什么？谁先提出来，谁反对，谁最后拍板？
4. 你和父母或长辈在升学、花钱、作息、交友、搬家等事情上，印象最深的一次沟通是什么？当时各自怎么说，后来怎么收场？
5. 学业上最明显的一次上升或下滑发生在什么时候？当时老师、家庭、身体或环境有什么变化？
6. 过去有没有某一年身体、睡眠、情绪或精力状态和前后明显不一样？那一年具体发生了什么？
7. 第一段或影响最大的关系发生在什么时候？怎么开始，期间有什么转折，后来怎么变化？
8. 有没有哪一年你明显换了一种圈子、生活方式、目标或工作方向？那一年实际发生了什么？

### 年份核对表

年份表只用于补时间线，不暗示某年一定有事。没有明显事件就写“无”。

| 年份 | 当年是否有具体事件 | 事件经过 | 大概月份 | 影响持续多久 | 可佐证记录 |
|---|---|---|---|---|---|
| 2008 |  |  |  |  |  |
| 2009 |  |  |  |  |  |
| 2010 |  |  |  |  |  |
| 2011 |  |  |  |  |  |
| 2012 |  |  |  |  |  |
| 2013 |  |  |  |  |  |
| 2014 |  |  |  |  |  |
| 2015 |  |  |  |  |  |
| 2016 |  |  |  |  |  |
| 2017 |  |  |  |  |  |
| 2018 |  |  |  |  |  |
| 2019 |  |  |  |  |  |
| 2020 |  |  |  |  |  |
| 2021 |  |  |  |  |  |
| 2022 |  |  |  |  |  |
| 2023 |  |  |  |  |  |
| 2024 |  |  |  |  |  |
| 2025 |  |  |  |  |  |

### 追问模板

- 当时具体发生了什么？
- 这件事是谁先提出来的？
- 对方原话或大概原话是什么？
- 你当时做了什么，不是怎么想？
- 后来结果是什么？
- 这件事影响了多久？
- 有没有成绩、证书、医院记录、聊天记录、搬家记录、入学或工作时间可以佐证？

### 禁止问法

- 不问“你是不是某种性格”。
- 不问“你更像哪张候选盘”。
- 不问“某年是不是发生了某类事”。
- 不把候选盘的画像、十神、格局、喜忌讲给当事人后再让对方反馈。

## 使用边界

- 本报告只生成可追溯的候选盘计划，不替代 `chart.md` 专业细盘。
- 后续必须运行候选盘命令，读取每个候选目录的 `chart.md` 和 `raw/` 后再分析。
- 子时争议未压缩前，不输出吓人式结论；如果现实核验耦合度过低，应标记为无法可靠定盘。
"""


def normalize_key_names(obj: Any) -> Any:
    if isinstance(obj, list):
        return [normalize_key_names(item) for item in obj]
    if isinstance(obj, dict):
        return {
            {
                "zi_segment": "ziSegment",
                "is_zi": "isZi",
                "beijing_datetime": "beijingDatetime",
                "minutes_to_zi_start": "minutesToZiStart",
                "minutes_to_zi_end": "minutesToZiEnd",
            }.get(key, key): normalize_key_names(value)
            for key, value in obj.items()
        }
    return obj


def build_report(args: argparse.Namespace, output_dir: Path) -> dict[str, Any]:
    recorded = parse_dt(args.date, args.time)
    dst_active = in_china_dst(recorded)
    should_apply_dst = args.dst == "yes" or (args.dst == "auto" and dst_active)
    standard = recorded - timedelta(hours=1) if should_apply_dst else recorded
    longitude, longitude_source = resolve_longitude(args.birthplace, args.longitude)

    views = [
        build_time_view(
            "recorded-clock",
            "记录钟表时间",
            recorded,
            "用户或出生记录给出的原始时间。",
        ),
        build_time_view(
            "standard-beijing",
            "北京时间/标准时",
            standard,
            "已按夏令时设置校正后，用于正式排盘的北京时间。",
        ),
    ]

    longitude_delta = None
    longitude_offset_minutes = None
    if longitude is not None:
        longitude_delta = longitude - args.central_longitude
        longitude_offset_minutes = int(round(longitude_delta * 4))
        solar = standard + timedelta(minutes=longitude_offset_minutes)
        views.append(
            build_time_view(
                "longitude-solar",
                "经度校正太阳时",
                solar,
                "按经度差每度约 4 分钟校正；用于判断是否仍在子时边界。",
            )
        )
        if should_apply_dst and args.dst == "auto":
            recorded_solar = recorded + timedelta(minutes=longitude_offset_minutes)
            views.append(
                build_time_view(
                    "recorded-longitude-solar",
                    "未校正夏令时的经度太阳时",
                    recorded_solar,
                    "夏令时日期的备选口径：若输入时间已是标准北京时间，则用该时间再做经度校正。",
                )
            )

    candidates = build_candidates(args, output_dir, views, args.boundary_window_minutes)
    any_zi = any(view.is_zi for view in views)
    branch_changed = len({view.branch for view in views if view.key in {"standard-beijing", "longitude-solar"}}) > 1
    near_zi = any(
        view.minutes_to_zi_start <= args.boundary_window_minutes
        or view.minutes_to_zi_end <= args.boundary_window_minutes
        for view in views
    )

    if branch_changed and any(view.key == "longitude-solar" and not view.is_zi for view in views):
        risk_level = "high-but-compressible"
        summary = "北京时间与经度校正后时辰不同，应优先用真太阳时方向压缩候选。"
    elif any_zi:
        risk_level = "high"
        summary = "至少一个时间口径落在子时，必须生成早晚子时/换日候选盘后再验盘。"
    elif near_zi:
        risk_level = "medium"
        summary = "未直接落子时，但接近子时边界；出生地或分钟误差可能改变时柱。"
    else:
        risk_level = "low"
        summary = "当前信息未触发明显子时换日争议。"

    dst_note = "不在已知中国夏令时日期内。"
    if dst_active and args.dst == "auto":
        dst_note = "日期落在中国夏令时实行期，已自动把记录钟表时间减 1 小时作为标准北京时间；仍需向当事人确认记录口径。"
    elif dst_active and args.dst == "no":
        dst_note = "日期落在中国夏令时实行期，但调用方指定不校正；建议保留夏令时候选。"
    elif args.dst == "yes":
        dst_note = "调用方指定按夏令时校正，记录钟表时间已减 1 小时。"

    report = {
        "source": "bazi zi-hour triage",
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input": {
            "name": args.name,
            "sex": args.sex,
            "recordedDatetime": fmt_dt(recorded),
            "birthplace": args.birthplace,
        },
        "location": {
            "longitude": longitude,
            "source": longitude_source,
        },
        "correction": {
            "centralLongitude": args.central_longitude,
            "longitudeDeltaDegrees": None if longitude_delta is None else round(longitude_delta, 4),
            "longitudeOffsetMinutes": longitude_offset_minutes,
            "dstMode": args.dst,
            "dstActiveByDate": dst_active,
            "dstApplied": should_apply_dst,
            "dstNote": dst_note,
        },
        "timeViews": [asdict(view) for view in views],
        "risk": {
            "level": risk_level,
            "summary": summary,
            "boundaryWindowMinutes": args.boundary_window_minutes,
        },
        "chartCandidates": [asdict(candidate) for candidate in candidates],
    }
    return normalize_key_names(report)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a reproducible triage report for near-zi-hour bazi chart calibration."
    )
    parser.add_argument("--date", required=True, help="Recorded Gregorian date, YYYY-MM-DD")
    parser.add_argument("--time", required=True, help="Recorded time, HH:mm or HH:mm:ss")
    parser.add_argument("--sex", required=True, choices=["male", "female", "男", "女", "1", "0"], help="sex for chart commands")
    parser.add_argument("--name", default="命主", help="Chart owner name")
    parser.add_argument("--birthplace", help="Birthplace text, used for built-in longitude lookup")
    parser.add_argument("--longitude", type=float, help="Birthplace longitude, east positive; overrides birthplace lookup")
    parser.add_argument("--central-longitude", type=float, default=EAST_8_CENTRAL_LONGITUDE)
    parser.add_argument("--dst", choices=["auto", "yes", "no"], default="auto", help="China DST handling for 1986-1991")
    parser.add_argument("--boundary-window-minutes", type=int, default=75)
    parser.add_argument("--output", help="Output directory. Default: work/zi-hour/<timestamp>")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args(sys.argv[1:])
    output_dir = Path(args.output or (DEFAULT_OUTPUT_ROOT / safe_stamp())).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    report = build_report(args, output_dir)
    report_json = output_dir / "zi_hour_report.json"
    report_md = output_dir / "zi_hour_report.md"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    report_md.write_text(render_markdown(report), encoding="utf8")
    print(
        json.dumps(
            {
                "outputDir": str(output_dir),
                "reportJson": str(report_json),
                "reportMd": str(report_md),
                "risk": report["risk"],
                "chartCandidateCount": len(report["chartCandidates"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
