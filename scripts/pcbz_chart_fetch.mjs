#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PAI_PAN_URL = "https://pcbz.iwzwh.com/#/paipan/index";
const BASE_URL = "https://bzapi4.iwzbz.com/getbasebz8.php";
const RYSL_URL = "https://bzapi2.iwzbz.com/getRysl.php";
const RELATION_URL = "https://bzapi4.iwzbz.com/getGZRelaction3.php";
const GEJU_URL = "https://bzapi2.iwzbz.com/getgeju3.php";
const SZBZ_URL = "https://bzapi2.iwzbz.com/szbz.php";

const DEFAULT_OUTPUT_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "work",
  "pcbz"
);

function usage() {
  return `Usage:
  node scripts/pcbz_chart_fetch.mjs --date YYYY-MM-DD --time HH:mm --sex male|female [options]
  node scripts/pcbz_chart_fetch.mjs --pillars "庚辰 己丑 丁亥 丙午" --sex male|female [--candidate-index 1] [options]

Options:
  --pillars PILLARS       Reverse lookup by four pillars, e.g. "庚辰 己丑 丁亥 丙午".
  --candidate-index N     Candidate date index from --pillars reverse lookup, 0-based. Default: middle candidate.
  --name NAME             Chart owner name. Default: 命主
  --output DIR            Output directory. Default: work/pcbz/<timestamp>
  --sun-time DATETIME     True-solar datetime, format "YYYY-MM-DD HH:mm[:ss]".
  --today DATETIME        Request timestamp. Default: current local time.
  --midnight 0|1          问真 early/late 子时 setting yzs. Default: 0.
  --vip 0|1               VIP flag for request compatibility. Default: 0.
  --user-guid GUID        User GUID if logged in. Default: empty.
  --help                  Show this help.

The script mirrors https://pcbz.iwzwh.com/#/paipan/index network calls.
It saves raw API responses and parsed professional chart files before analysis.`;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") {
      args.help = true;
      continue;
    }
    if (!arg.startsWith("--")) {
      throw new Error(`Unexpected positional argument: ${arg}`);
    }
    const key = arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
    const value = argv[i + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for ${arg}`);
    }
    args[key] = value;
    i++;
  }
  return args;
}

function normalizeDateTime(date, time) {
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    throw new Error("--date must use YYYY-MM-DD");
  }
  if (!time || !/^\d{2}:\d{2}(:\d{2})?$/.test(time)) {
    throw new Error("--time must use HH:mm or HH:mm:ss");
  }
  return `${date} ${time.length === 5 ? `${time}:00` : time}`;
}

function normalizePillars(value) {
  const normalized = String(value || "").replace(/\s+/g, "");
  if (!/^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$/.test(normalized)) {
    throw new Error('--pillars must contain four valid pillars, e.g. "庚辰 己丑 丁亥 丙午"');
  }
  return {
    joined: normalized,
    spaced: normalized.match(/../g).join(" ")
  };
}

function normalizeCandidateDateTime(value) {
  const match = /^(\d{4})-(\d{1,2})-(\d{1,2}) (\d{1,2}):(\d{2}):(\d{2})$/.exec(String(value || ""));
  if (!match) {
    throw new Error(`Invalid reverse-lookup candidate datetime: ${value}`);
  }
  const [, year, month, day, hour, minute, second] = match;
  const pad = (n) => String(n).padStart(2, "0");
  return `${year}-${pad(month)}-${pad(day)} ${pad(hour)}:${minute}:${second}`;
}

function normalizeSex(value) {
  if (["1", "male", "男", "m"].includes(String(value).toLowerCase())) return 1;
  if (["0", "female", "女", "f"].includes(String(value).toLowerCase())) return 0;
  throw new Error("--sex must be male|female, 男|女, 1|0");
}

function localTimestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function safeStamp() {
  return localTimestamp().replace(/[-: ]/g, "");
}

async function fetchText(name, url) {
  const response = await fetch(url, {
    headers: {
      "accept": "application/json,text/plain,*/*",
      "referer": PAI_PAN_URL,
      "user-agent": "Mozilla/5.0 bazi-skill/pcbz-chart-fetch"
    }
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${name} failed: HTTP ${response.status} ${text.slice(0, 200)}`);
  }
  return text;
}

async function resolveInputDateTimeFromArgs(args, rawDir) {
  if (!args.pillars) {
    return {
      datetime: normalizeDateTime(args.date, args.time),
      reverseLookup: null
    };
  }

  const requestedPillars = normalizePillars(args.pillars);
  const szbzUrl = `${SZBZ_URL}?${new URLSearchParams({ bz: requestedPillars.joined })}`;
  const szbzText = await fetchText("szbz", szbzUrl);
  await fs.writeFile(path.join(rawDir, "szbz.json"), szbzText, "utf8");
  const candidates = parseJson("szbz", szbzText);
  if (!Array.isArray(candidates) || candidates.length === 0) {
    throw new Error(`No Gregorian candidates found for pillars: ${requestedPillars.spaced}`);
  }
  const candidateIndex = args.candidateIndex == null ? Math.floor(candidates.length / 2) : Number(args.candidateIndex);
  if (!Number.isInteger(candidateIndex) || candidateIndex < 0 || candidateIndex >= candidates.length) {
    throw new Error(`--candidate-index must be an integer between 0 and ${candidates.length - 1}`);
  }
  const datetime = normalizeCandidateDateTime(candidates[candidateIndex]);
  return {
    datetime,
    reverseLookup: {
      requestedPillars,
      candidates,
      selectedIndex: candidateIndex,
      selectedDatetime: datetime,
      selectionMode: args.candidateIndex == null ? "default-middle" : "explicit",
      requestUrl: szbzUrl
    }
  };
}

function parseJson(name, text) {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${name} returned non-JSON content: ${error.message}`);
  }
}

function pillars(base) {
  const b = base.bz || {};
  return {
    year: `${b[0] || ""}${b[1] || ""}`,
    month: `${b[2] || ""}${b[3] || ""}`,
    day: `${b[4] || ""}${b[5] || ""}`,
    hour: `${b[6] || ""}${b[7] || ""}`,
    joined: `${b[0] || ""}${b[1] || ""}${b[2] || ""}${b[3] || ""}${b[4] || ""}${b[5] || ""}${b[6] || ""}${b[7] || ""}`,
    spaced: `${b[0] || ""}${b[1] || ""} ${b[2] || ""}${b[3] || ""} ${b[4] || ""}${b[5] || ""} ${b[6] || ""}${b[7] || ""}`
  };
}

function markdownList(items) {
  if (!items || !items.length) return "- 无";
  return items.map((item) => `- ${Array.isArray(item) ? item.join("、") : item}`).join("\n");
}

function qiyunDetail(arr) {
  if (!Array.isArray(arr)) return "";
  const labels = ["年", "月", "日", "时", "分", "秒"];
  return arr.map((value, index) => `${value}${labels[index] || ""}`).join("");
}

function positiveMod(n, m) {
  return ((n % m) + m) % m;
}

function parseLocalDateTime(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(value);
  if (!match) {
    throw new Error(`Invalid datetime: ${value}`);
  }
  const [, year, month, day, hour, minute, second] = match.map(Number);
  return new Date(year, month - 1, day, hour, minute, second);
}

function addQiYunDuration(date, arr) {
  const d = new Date(date.getTime());
  if (!Array.isArray(arr)) return d;
  d.setFullYear(d.getFullYear() + Number(arr[0] || 0));
  d.setMonth(d.getMonth() + Number(arr[1] || 0));
  d.setDate(d.getDate() + Number(arr[2] || 0));
  d.setHours(d.getHours() + Number(arr[3] || 0));
  d.setMinutes(d.getMinutes() + Number(arr[4] || 0));
  d.setSeconds(d.getSeconds() + Number(arr[5] || 0));
  return d;
}

function addYears(date, years) {
  const d = new Date(date.getTime());
  d.setFullYear(d.getFullYear() + years);
  return d;
}

function addSeconds(date, seconds) {
  const d = new Date(date.getTime());
  d.setSeconds(d.getSeconds() + seconds);
  return d;
}

function formatDate(date) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function ganzhiYear(year) {
  const stems = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"];
  const branches = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"];
  const index = positiveMod(year - 1984, 60);
  return `${stems[index % 10]}${branches[index % 12]}`;
}

function buildDaYunPeriods(input, base) {
  const dayun = Array.isArray(base.dayun) ? base.dayun : [];
  if (!dayun.length) return [];

  const birth = parseLocalDateTime(input.sunTime);
  const firstStart = addQiYunDuration(birth, base.qiyunarr);

  return dayun.map((pillar, index) => {
    const start = addYears(firstStart, index * 10);
    const nextStart = addYears(firstStart, (index + 1) * 10);
    const end = addSeconds(nextStart, -1);
    const years = [];
    for (let year = start.getFullYear(); year <= end.getFullYear(); year++) {
      years.push({ year, ganzhi: ganzhiYear(year) });
    }
    return {
      index: index + 1,
      pillar,
      startDate: formatDate(start),
      endDate: formatDate(end),
      yearRange: `${start.getFullYear()}-${end.getFullYear()}`,
      ageRange: base.qiyunsui != null ? `${Number(base.qiyunsui) + index * 10}-${Number(base.qiyunsui) + index * 10 + 9}岁` : "",
      years
    };
  });
}

function renderCorePillarTable(base, p) {
  const bz = base.bz || {};
  const columns = [
    { label: "年柱", pillar: p.year, stem: bz[0], branch: bz[1], star: base.ss?.[0], hidden: base.cg?.[0], hiddenStars: base.cgss?.[0] },
    { label: "月柱", pillar: p.month, stem: bz[2], branch: bz[3], star: base.ss?.[1], hidden: base.cg?.[1], hiddenStars: base.cgss?.[1] },
    { label: "日柱", pillar: p.day, stem: bz[4], branch: bz[5], star: base.ss?.[2], hidden: base.cg?.[2], hiddenStars: base.cgss?.[2] },
    { label: "时柱", pillar: p.hour, stem: bz[6], branch: bz[7], star: base.ss?.[3], hidden: base.cg?.[3], hiddenStars: base.cgss?.[3] }
  ];

  const rows = columns.map((item) => {
    const hidden = (item.hidden || []).map((gan, index) => `${gan}${item.hiddenStars?.[index] || ""}`).join("、");
    const hiddenText = hidden ? `${item.branch || ""}藏${hidden}` : "";
    return `| ${item.label} | ${item.pillar || ""} | ${item.stem || ""}${item.star || ""} | ${hiddenText} |`;
  });

  return [
    "| 柱位 | 干支 | 天干十神 | 地支藏干十神 |",
    "|---|---|---|---|",
    ...rows
  ].join("\n");
}

function renderDaYunTable(periods) {
  if (!periods.length) return "- 无";
  return [
    "| 序 | 大运 | 起止日期 | 公历年份 | 年龄段 |",
    "|---|---|---|---|---|",
    ...periods.map((item) => `| ${item.index} | ${item.pillar} | ${item.startDate} 至 ${item.endDate} | ${item.yearRange} | ${item.ageRange} |`)
  ].join("\n");
}

function renderLiuNianByDaYun(periods) {
  if (!periods.length) return "- 无";
  return periods.map((item) => {
    const years = item.years.map((year) => `${year.year} ${year.ganzhi}`).join("、");
    return `- ${item.pillar}（${item.yearRange}）：${years}`;
  }).join("\n");
}

function renderChartMarkdown(input, parsed) {
  const base = parsed.base;
  const p = parsed.pillars;
  const dayunPeriods = parsed.analysisCore?.dayunPeriods || buildDaYunPeriods(input, base);
  const labels = ["年柱", "月柱", "日柱", "时柱"];
  const gz = [p.year, p.month, p.day, p.hour];
  const bz = base.bz || {};
  const rows = [
    ["主星", ...(base.ss || [])],
    ["天干", bz[0], bz[2], bz[4], bz[6]],
    ["地支", bz[1], bz[3], bz[5], bz[7]],
    ["藏干", ...(base.cg || []).map((x) => (x || []).join(" "))],
    ["副星", ...(base.cgss || []).map((x) => (x || []).join(" "))],
    ["星运", ...(base.xy || [])],
    ["自坐", ...(base.zz || [])],
    ["空亡", ...(base.kw || [])],
    ["纳音", ...(base.ny || [])],
    ["神煞", ...(base.szshensha || []).slice(0, 4).map((x) => (x || []).join(" "))]
  ];

  const table = [
    `| 日期 | ${labels.join(" | ")} |`,
    `|---|${labels.map(() => "---").join("|")}|`,
    `| 干支 | ${gz.join(" | ")} |`,
    ...rows.map((row) => `| ${row.map((x) => x ?? "").join(" | ")} |`)
  ].join("\n");

  return `# 问真八字专业细盘

## 来源

- 排盘入口：${PAI_PAN_URL}
- 采集方式：脚本化 HTTP 请求，非人工抄录
- 采集时间：${parsed.fetchedAt}
- 原始响应目录：${parsed.rawDir}

## 输入

- 姓名：${input.name}
- 性别：${input.sex === 1 ? "男" : "女"}
- 排盘方式：${input.reverseLookup ? "四柱反推公历后排盘" : "公历出生时间排盘"}
${input.reverseLookup ? `- 输入四柱：${input.reverseLookup.requestedPillars.spaced}
- 候选公历：${input.reverseLookup.candidates.map((x, i) => `${i}. ${x}`).join("；")}
- 采用候选：${input.reverseLookup.selectedIndex}. ${input.reverseLookup.selectedDatetime}
- 候选选择：${input.reverseLookup.selectionMode === "default-middle" ? "未指定候选，默认采用中间候选，作为更偏现代常用时间范围的初始排盘；若用户纠正日期或候选编号，应按用户意见重跑。" : "用户或调用方显式指定候选编号。"}` : ""}
- 北京时间：${input.datetime}
- 真太阳时：${input.sunTime}
- 子时设置 yzs：${input.midnight}

## 基本信息

- 阴历：${bz[8] || ""}
- 四柱：${p.spaced}
- 起运岁数：${base.qiyunsui ?? ""}
- 起运详情：${qiyunDetail(base.qiyunarr)}
- 交运：${base.jiaoyun || ""}

## 后续分析必读

### 四柱十神核心表

${renderCorePillarTable(base, p)}

### 起运与大运年份表

${renderDaYunTable(dayunPeriods)}

### 流年索引

${renderLiuNianByDaYun(dayunPeriods)}

## 低优先级附录

### 传统细盘补充

- 胎息：${base.taixi || ""}（${base.taixi_nayin || ""}）
- 胎元：${base.taiyuan || ""}（${base.taiyuan_nayin || ""}）
- 命宫：${base.minggong || ""}（${base.minggong_nayin || ""}）
- 身宫：${base.shenggong || ""}（${base.shenggong_nayin || ""}）
- 空亡：${base.kongwang || ""}

### 问真原始排盘表

${table}

### 干支关系

${markdownList((parsed.relations || []).flat().filter(Boolean).map((x) => String(x).split(",").filter(Boolean).join(" ")))}

### 格局接口

${parsed.geju?.data ? parsed.geju.data : "无返回内容"}

## 后续分析要求

后续验盘、正统子平、关系、健康、事业等分析，必须优先引用“后续分析必读”中的四柱十神、藏干十神、大运年份和流年索引；低优先级附录只作辅助，不作为主证。若用户补充出生地、真太阳时或早晚子时设置发生变化，必须重新运行脚本并生成新的排盘文件。
`;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return;
  }

  const outputDir = path.resolve(args.output || path.join(DEFAULT_OUTPUT_ROOT, safeStamp()));
  const rawDir = path.join(outputDir, "raw");
  await fs.mkdir(rawDir, { recursive: true });

  const resolved = await resolveInputDateTimeFromArgs(args, rawDir);
  const input = {
    name: args.name || "命主",
    sex: normalizeSex(args.sex),
    datetime: resolved.datetime,
    sunTime: args.sunTime || resolved.datetime,
    today: args.today || localTimestamp(),
    midnight: args.midnight ?? "0",
    vip: args.vip ?? "0",
    userGuid: args.userGuid || "",
    reverseLookup: resolved.reverseLookup
  };

  const baseUrl = `${BASE_URL}?${new URLSearchParams({
    d: input.sunTime,
    s: String(input.sex),
    today: input.today,
    vip: String(input.vip),
    userguid: input.userGuid,
    yzs: String(input.midnight)
  })}`;

  const baseText = await fetchText("getbasebz8", baseUrl);
  await fs.writeFile(path.join(rawDir, "getbasebz8.json"), baseText, "utf8");
  const base = parseJson("getbasebz8", baseText);
  const p = pillars(base);

  const renyuanUrl = `${RYSL_URL}?${new URLSearchParams({
    datestr: input.sunTime.replace(/:00$/, ":0"),
    ryslFlag: "0"
  })}`;
  const relationUrl = `${RELATION_URL}?${new URLSearchParams({
    gz: p.spaced,
    userguid: input.userGuid,
    vip: String(input.vip)
  })}`;
  const gejuUrl = `${GEJU_URL}?${new URLSearchParams({
    bz: p.joined,
    guid: input.userGuid,
    parm: "1,1,1,0,1,0,0,1,0,0,0,0,0,0,0",
    spcgeju1: "1",
    spcgeju2: "1"
  })}`;

  const [renyuanText, relationsText, gejuText] = await Promise.all([
    fetchText("getRysl", renyuanUrl),
    fetchText("getGZRelaction3", relationUrl),
    fetchText("getgeju3", gejuUrl)
  ]);
  await fs.writeFile(path.join(rawDir, "getRysl.json"), renyuanText, "utf8");
  await fs.writeFile(path.join(rawDir, "getGZRelaction3.json"), relationsText, "utf8");
  await fs.writeFile(path.join(rawDir, "getgeju3.json"), gejuText, "utf8");

  const parsed = {
    source: PAI_PAN_URL,
    fetchedAt: localTimestamp(),
    rawDir,
    input,
    requestUrls: { baseUrl, renyuanUrl, relationUrl, gejuUrl },
    base,
    pillars: p,
    renyuan: parseJson("getRysl", renyuanText),
    relations: parseJson("getGZRelaction3", relationsText),
    geju: parseJson("getgeju3", gejuText)
  };
  parsed.analysisCore = {
    pillars: {
      year: { pillar: p.year, stem: base.bz?.[0] || "", stemStar: base.ss?.[0] || "", branch: base.bz?.[1] || "", hiddenStems: base.cg?.[0] || [], hiddenStemStars: base.cgss?.[0] || [] },
      month: { pillar: p.month, stem: base.bz?.[2] || "", stemStar: base.ss?.[1] || "", branch: base.bz?.[3] || "", hiddenStems: base.cg?.[1] || [], hiddenStemStars: base.cgss?.[1] || [] },
      day: { pillar: p.day, stem: base.bz?.[4] || "", stemStar: base.ss?.[2] || "", branch: base.bz?.[5] || "", hiddenStems: base.cg?.[2] || [], hiddenStemStars: base.cgss?.[2] || [] },
      hour: { pillar: p.hour, stem: base.bz?.[6] || "", stemStar: base.ss?.[3] || "", branch: base.bz?.[7] || "", hiddenStems: base.cg?.[3] || [], hiddenStemStars: base.cgss?.[3] || [] }
    },
    qiyun: {
      startAge: base.qiyunsui ?? null,
      detail: qiyunDetail(base.qiyunarr),
      jiaoyun: base.jiaoyun || ""
    },
    dayunPeriods: buildDaYunPeriods(input, base)
  };

  const chartJson = path.join(outputDir, "chart.json");
  const chartMd = path.join(outputDir, "chart.md");
  await fs.writeFile(chartJson, JSON.stringify(parsed, null, 2), "utf8");
  await fs.writeFile(chartMd, renderChartMarkdown(input, parsed), "utf8");

  console.log(JSON.stringify({ outputDir, chartJson, chartMd, pillars: p }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
