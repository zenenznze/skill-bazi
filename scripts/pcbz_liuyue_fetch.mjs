#!/usr/bin/env node

import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const INDEX_URL = "https://pcbz.iwzwh.com/";
const PAI_PAN_URL = "https://pcbz.iwzwh.com/#/paipan/index";
const SHENSHA_URL = "https://bzapi2.iwzbz.com/getliunianshensha5.php";
const DEFAULT_OUTPUT_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "work",
  "pcbz"
);

const TIAN_GAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"];
const STEM_META = {
  甲: { element: "木", yang: true },
  乙: { element: "木", yang: false },
  丙: { element: "火", yang: true },
  丁: { element: "火", yang: false },
  戊: { element: "土", yang: true },
  己: { element: "土", yang: false },
  庚: { element: "金", yang: true },
  辛: { element: "金", yang: false },
  壬: { element: "水", yang: true },
  癸: { element: "水", yang: false }
};
const GENERATES = { 木: "火", 火: "土", 土: "金", 金: "水", 水: "木" };
const CONTROLS = { 木: "土", 土: "水", 水: "火", 火: "金", 金: "木" };
const BRANCH_PRIMARY_STEM = {
  子: "癸",
  丑: "己",
  寅: "甲",
  卯: "乙",
  辰: "戊",
  巳: "丙",
  午: "丁",
  未: "己",
  申: "庚",
  酉: "辛",
  戌: "戊",
  亥: "壬"
};

function usage() {
  return `Usage:
  node scripts/pcbz_liuyue_fetch.mjs --year YYYY --chart-json path/to/chart.json [options]
  node scripts/pcbz_liuyue_fetch.mjs --year YYYY --bz 辛巳庚寅丁巳癸卯 --sex female --day-stem 丁 [options]

Options:
  --year YYYY                 Flow year to generate, e.g. 2026.
  --chart-json FILE           Existing WenZhen chart.json. Preferred source for bz, sex, day stem, vip, user guid.
  --bz BAZI                   Eight-character chart string for shensha calls, e.g. 辛巳庚寅丁巳癸卯.
  --sex male|female|1|0       Sex for shensha calls. WenZhen uses 1=male, 0=female.
  --day-stem STEM             Day stem for ten-god labels. Auto-read from --chart-json when available.
  --output DIR                Output directory. Default: chart dir/liuyue-YYYY, or work/pcbz/liuyue-<timestamp>.
  --gregorian-month YYYY-MM   Calendar month to split by flow-month boundaries, e.g. 2026-07.
  --month M                   Shorthand for --gregorian-month YYYY-M, using --year.
  --date DATETIME             Locate active flow month for a date, YYYY-MM-DD[ HH:mm[:ss]].
  --vip 0|1                   VIP flag for shensha request. Default: chart input or 0.
  --user-guid GUID            User GUID for shensha request. Default: chart input or empty.
  --source-map-url URL        Override WenZhen app source map URL.
  --no-shensha                Do not call getliunianshensha5.php.
  --strict-shensha            Fail if a shensha request fails.
  --help                      Show this help.

The script mirrors WenZhen frontend flow-month generation:
  getYueGan(year, month) + ly_zhi + _JieQiData.
WenZhen has no dedicated API that directly returns the 12 flow-month pillars.`;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") {
      args.help = true;
      continue;
    }
    if (arg === "--no-shensha") {
      args.noShensha = true;
      continue;
    }
    if (arg === "--strict-shensha") {
      args.strictShensha = true;
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

function localTimestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function safeStamp() {
  return localTimestamp().replace(/[-: ]/g, "");
}

function sha256(text) {
  return crypto.createHash("sha256").update(text).digest("hex");
}

function pad2(value) {
  return String(value).padStart(2, "0");
}

function normalizeYear(value) {
  const year = Number(value);
  if (!Number.isInteger(year) || year < 1801 || year > 2098) {
    throw new Error("--year must be an integer between 1801 and 2098");
  }
  return year;
}

function normalizeSex(value) {
  if (value == null || value === "") return null;
  if (["1", "male", "男", "m"].includes(String(value).toLowerCase())) return 1;
  if (["0", "female", "女", "f"].includes(String(value).toLowerCase())) return 0;
  throw new Error("--sex must be male|female, 男|女, 1|0");
}

function normalizeBazi(value) {
  if (value == null || value === "") return "";
  const normalized = String(value).replace(/\s+/g, "");
  if (!/^[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥][甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]$/.test(normalized)) {
    throw new Error("--bz must contain four valid pillars, e.g. 辛巳庚寅丁巳癸卯");
  }
  return normalized;
}

function normalizeDayStem(value) {
  if (value == null || value === "") return "";
  if (!TIAN_GAN.includes(value)) {
    throw new Error("--day-stem must be one of 甲乙丙丁戊己庚辛壬癸");
  }
  return value;
}

function normalizeGregorianMonth(args, flowYear) {
  if (args.gregorianMonth) {
    const match = /^(\d{4})-(\d{1,2})$/.exec(args.gregorianMonth);
    if (!match) throw new Error("--gregorian-month must use YYYY-MM");
    const month = Number(match[2]);
    if (month < 1 || month > 12) throw new Error("--gregorian-month month must be 1-12");
    return `${match[1]}-${pad2(month)}`;
  }
  if (args.month) {
    const month = Number(args.month);
    if (!Number.isInteger(month) || month < 1 || month > 12) {
      throw new Error("--month must be an integer from 1 to 12");
    }
    return `${flowYear}-${pad2(month)}`;
  }
  return "";
}

function normalizeDateTime(value) {
  if (!value) return "";
  const text = String(value).trim();
  const match = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$/.exec(text);
  if (!match) throw new Error("--date must use YYYY-MM-DD or YYYY-MM-DD HH:mm[:ss]");
  const [, year, month, day, hour = "0", minute = "0", second = "0"] = match;
  return `${year}-${pad2(month)}-${pad2(day)} ${pad2(hour)}:${minute}:${second}`;
}

function parseNaiveEpoch(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(value);
  if (!match) throw new Error(`Invalid datetime: ${value}`);
  const [, year, month, day, hour, minute, second] = match.map(Number);
  return Date.UTC(year, month - 1, day, hour, minute, second);
}

function compareDateTime(a, b) {
  return parseNaiveEpoch(a) - parseNaiveEpoch(b);
}

function addGregorianMonths(year, month, count) {
  const d = new Date(Date.UTC(year, month - 1 + count, 1, 0, 0, 0));
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1 };
}

async function fetchText(name, url) {
  const response = await fetch(url, {
    headers: {
      accept: "application/json,text/plain,*/*",
      referer: PAI_PAN_URL,
      "user-agent": "Mozilla/5.0 bazi-skill/pcbz-liuyue-fetch"
    }
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`${name} failed: HTTP ${response.status} ${text.slice(0, 200)}`);
  }
  return text;
}

async function resolveSourceMap(args) {
  let indexUrl = INDEX_URL;
  let appJsUrl = "";
  let sourceMapUrl = args.sourceMapUrl || "";
  let appJsSha256 = "";
  let indexSha256 = "";

  if (!sourceMapUrl) {
    const indexText = await fetchText("WenZhen index", indexUrl);
    indexSha256 = sha256(indexText);
    const appMatches = [...indexText.matchAll(/src="([^"]*static\/js\/app\.[^"]+\.js)"/g)];
    if (!appMatches.length) {
      throw new Error("Unable to find WenZhen app JS in index page");
    }
    appJsUrl = new URL(appMatches[appMatches.length - 1][1], indexUrl).href;
    const appText = await fetchText("WenZhen app JS", appJsUrl);
    appJsSha256 = sha256(appText);
    const sourceMapMatch = /\/\/# sourceMappingURL=([^\s]+)/.exec(appText);
    if (!sourceMapMatch) {
      throw new Error("Unable to find sourceMappingURL in WenZhen app JS");
    }
    sourceMapUrl = new URL(sourceMapMatch[1], appJsUrl).href;
  }

  const sourceMapText = await fetchText("WenZhen app source map", sourceMapUrl);
  const sourceMap = JSON.parse(sourceMapText);
  return {
    indexUrl,
    appJsUrl,
    sourceMapUrl,
    fetchedAt: localTimestamp(),
    indexSha256,
    appJsSha256,
    sourceMapSha256: sha256(sourceMapText),
    sourceMap
  };
}

function findSource(sourceMap, suffix) {
  const index = sourceMap.sources.findIndex((source) => source.endsWith(suffix));
  if (index < 0 || !sourceMap.sourcesContent?.[index]) {
    throw new Error(`Unable to find ${suffix} in WenZhen source map`);
  }
  return {
    index,
    name: sourceMap.sources[index],
    content: sourceMap.sourcesContent[index]
  };
}

function extractBalanced(source, openIndex, openChar, closeChar) {
  let depth = 0;
  let quote = "";
  let escaped = false;
  for (let i = openIndex; i < source.length; i++) {
    const ch = source[i];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (ch === "\\") {
        escaped = true;
      } else if (ch === quote) {
        quote = "";
      }
      continue;
    }
    if (ch === "'" || ch === '"' || ch === "`") {
      quote = ch;
      continue;
    }
    if (ch === openChar) depth++;
    if (ch === closeChar) depth--;
    if (depth === 0) return source.slice(openIndex, i + 1);
  }
  throw new Error(`Unbalanced ${openChar}${closeChar} block`);
}

function extractConstBlock(source, name, openChar, closeChar) {
  const marker = `export const ${name}`;
  const markerIndex = source.indexOf(marker);
  if (markerIndex < 0) throw new Error(`Unable to find ${name}`);
  const openIndex = source.indexOf(openChar, markerIndex);
  if (openIndex < 0) throw new Error(`Unable to find ${openChar} for ${name}`);
  return extractBalanced(source, openIndex, openChar, closeChar);
}

function parseLyZhi(source) {
  const block = extractConstBlock(source, "ly_zhi", "[", "]");
  const values = [...block.matchAll(/'([^']+)'/g)].map((match) => match[1]);
  if (values.join("") !== "寅卯辰巳午未申酉戌亥子丑") {
    throw new Error(`Unexpected ly_zhi sequence: ${values.join(" ")}`);
  }
  return values;
}

function parseJieQiData(source) {
  const block = extractConstBlock(source, "_JieQiData", "{", "}");
  const data = {};
  const yearRegex = /(\d{4})\s*:\s*{/g;
  let match;
  while ((match = yearRegex.exec(block))) {
    const year = match[1];
    const openIndex = block.indexOf("{", match.index);
    const yearBlock = extractBalanced(block, openIndex, "{", "}");
    const months = {};
    for (const monthMatch of yearBlock.matchAll(/(\d{1,2})\s*:\s*\['([^']+)'\s*,\s*'(\d{1,2})'\s*,\s*'(\d{2}:\d{2}:\d{2})'\]/g)) {
      months[monthMatch[1]] = [monthMatch[2], monthMatch[3], monthMatch[4]];
    }
    if (Object.keys(months).length === 12) {
      data[year] = months;
    }
    yearRegex.lastIndex = openIndex + yearBlock.length;
  }
  if (!Object.keys(data).length) throw new Error("Unable to parse _JieQiData");
  return data;
}

function getYueGan(year, month) {
  const initnum = 1801 * 12 + 1;
  const newnum = year * 12 + month;
  if (newnum >= initnum) {
    const index = (newnum - initnum + 6) % 10;
    return TIAN_GAN[index];
  }
  return "";
}

function getTenGod(dayStem, otherStem) {
  if (!dayStem || !otherStem) return "";
  const day = STEM_META[dayStem];
  const other = STEM_META[otherStem];
  if (!day || !other) return "";
  const samePolarity = day.yang === other.yang;
  if (day.element === other.element) return samePolarity ? "比肩" : "劫财";
  if (GENERATES[day.element] === other.element) return samePolarity ? "食神" : "伤官";
  if (CONTROLS[day.element] === other.element) return samePolarity ? "偏财" : "正财";
  if (CONTROLS[other.element] === day.element) return samePolarity ? "七杀" : "正官";
  if (GENERATES[other.element] === day.element) return samePolarity ? "偏印" : "正印";
  return "";
}

function flowMonthStart(jieQiData, flowYear, flowMonthIndex) {
  let termYear = flowYear;
  let termMonth = flowMonthIndex + 1;
  if (termMonth === 13) {
    termYear += 1;
    termMonth = 1;
  }
  const entry = jieQiData[String(termYear)]?.[String(termMonth)];
  if (!entry) {
    throw new Error(`Missing WenZhen _JieQiData for ${termYear}-${termMonth}`);
  }
  const [termName, day, time] = entry;
  const date = `${termYear}-${pad2(termMonth)}-${pad2(day)}`;
  return {
    termYear,
    termMonth,
    termName,
    date,
    time,
    dateTime: `${date} ${time}`
  };
}

function buildFlowMonths({ year, jieQiData, lyZhi, dayStem }) {
  const months = [];
  for (let yue = 1; yue <= 12; yue++) {
    const stem = getYueGan(year, yue);
    const branch = lyZhi[yue - 1];
    const start = flowMonthStart(jieQiData, year, yue);
    const nextStart = yue === 12
      ? flowMonthStart(jieQiData, year + 1, 1)
      : flowMonthStart(jieQiData, year, yue + 1);
    const branchPrimaryStem = BRANCH_PRIMARY_STEM[branch] || "";
    months.push({
      index: yue,
      pillar: `${stem}${branch}`,
      stem,
      branch,
      startTerm: start.termName,
      startDateTime: start.dateTime,
      endExclusiveDateTime: nextStart.dateTime,
      stemTenGod: getTenGod(dayStem, stem),
      branchPrimaryStem,
      branchPrimaryTenGod: getTenGod(dayStem, branchPrimaryStem)
    });
  }
  return months;
}

function findActiveMonth(months, datetime) {
  if (!datetime) return null;
  return months.find((month) => (
    compareDateTime(month.startDateTime, datetime) <= 0
    && compareDateTime(datetime, month.endExclusiveDateTime) < 0
  )) || null;
}

function buildGregorianMonthSegments(months, gregorianMonth) {
  if (!gregorianMonth) return [];
  const [yearText, monthText] = gregorianMonth.split("-");
  const year = Number(yearText);
  const month = Number(monthText);
  const next = addGregorianMonths(year, month, 1);
  const calendarStart = `${year}-${pad2(month)}-01 00:00:00`;
  const calendarEnd = `${next.year}-${pad2(next.month)}-01 00:00:00`;
  return months
    .filter((item) => compareDateTime(item.startDateTime, calendarEnd) < 0 && compareDateTime(item.endExclusiveDateTime, calendarStart) > 0)
    .map((item) => ({
      startDateTime: compareDateTime(item.startDateTime, calendarStart) > 0 ? item.startDateTime : calendarStart,
      endExclusiveDateTime: compareDateTime(item.endExclusiveDateTime, calendarEnd) < 0 ? item.endExclusiveDateTime : calendarEnd,
      pillar: item.pillar,
      monthIndex: item.index,
      stemTenGod: item.stemTenGod,
      branchPrimaryTenGod: item.branchPrimaryTenGod
    }));
}

async function readChartJson(chartJsonPath) {
  if (!chartJsonPath) return {};
  const file = path.resolve(chartJsonPath);
  const chart = JSON.parse(await fs.readFile(file, "utf8"));
  const joined = chart.pillars?.joined || [
    chart.base?.bz?.[0], chart.base?.bz?.[1],
    chart.base?.bz?.[2], chart.base?.bz?.[3],
    chart.base?.bz?.[4], chart.base?.bz?.[5],
    chart.base?.bz?.[6], chart.base?.bz?.[7]
  ].filter(Boolean).join("");
  return {
    file,
    chart,
    chartDir: path.dirname(file),
    name: chart.input?.name || "",
    sex: chart.input?.sex,
    bazi: joined,
    spacedBazi: chart.pillars?.spaced || joined.match(/../g)?.join(" ") || joined,
    dayStem: chart.base?.bz?.[4] || chart.analysisCore?.pillars?.day?.stem || "",
    vip: chart.input?.vip,
    userGuid: chart.input?.userGuid,
    source: chart.source || ""
  };
}

function shenshaSummary(parsed) {
  const flatten = (value) => {
    if (Array.isArray(value)) return value.flatMap(flatten);
    if (value == null || value === "") return [];
    if (typeof value === "object") return [];
    return [String(value)];
  };
  if (Array.isArray(parsed)) return flatten(parsed).join("、");
  if (parsed && typeof parsed === "object") {
    if (Array.isArray(parsed.data)) return flatten(parsed.data).join("、");
    if (typeof parsed.data === "string") return parsed.data;
    if (Array.isArray(parsed.shensha)) return flatten(parsed.shensha).join("、");
  }
  return "";
}

async function fetchShenShaForMonths(months, input, rawDir, strict) {
  if (!input.bazi || input.sex == null) return;
  for (const month of months) {
    const params = new URLSearchParams({
      ln: month.pillar,
      bz: input.bazi,
      sex: String(input.sex),
      vip: String(input.vip ?? "0"),
      userguid: input.userGuid || ""
    });
    const url = `${SHENSHA_URL}?${params}`;
    const file = path.join(rawDir, `getliunianshensha5-${pad2(month.index)}-${month.pillar}.json`);
    month.shenshaRequestUrl = url;
    try {
      const text = await fetchText(`getliunianshensha5 ${month.pillar}`, url);
      await fs.writeFile(file, text, "utf8");
      month.shenshaRawFile = file;
      const parsed = JSON.parse(text);
      month.shensha = parsed;
      month.shenshaSummary = shenshaSummary(parsed);
    } catch (error) {
      month.shenshaError = error.message;
      await fs.writeFile(`${file}.error.txt`, error.stack || error.message, "utf8");
      if (strict) throw error;
    }
  }
}

function renderMarkdown(result) {
  const shenshaNote = result.input.fetchShensha
    ? "- 神煞接口：`getliunianshensha5.php`，按每个流月干支逐月请求；原始响应见 `raw/`。"
    : "- 神煞接口：本次未请求。";
  const activeText = result.activeDate
    ? (result.activeMonth
      ? `- ${result.activeDate} 所在流月：${result.activeMonth.pillar}（${result.activeMonth.startDateTime} 至 ${result.activeMonth.endExclusiveDateTime} 前）`
      : `- ${result.activeDate} 不在 ${result.year} 流月范围内。`)
    : "- 未指定具体日期。";
  const segmentText = result.gregorianMonth
    ? renderSegments(result.gregorianMonth, result.gregorianMonthSegments)
    : "未指定公历月份。";
  const monthRows = result.months.map((month) => `| ${month.index} | ${month.pillar} | ${month.startTerm} | ${month.startDateTime} | ${month.endExclusiveDateTime} 前 | ${month.stemTenGod || ""} | ${month.branchPrimaryStem || ""}${month.branchPrimaryTenGod || ""} | ${month.shenshaSummary || month.shenshaError || ""} |`);
  return `# 问真流月表

## 来源

- 排盘入口：${PAI_PAN_URL}
- 流月干支来源：问真网页版前端 source map 中的 \`src/views/paipan-result/utils.js\`、\`src/views/paipan-result/static.js\`、\`src/static/index.js\`。
- 生成方式：问真前端没有单独返回 12 个流月干支的 API；本文件按前端 \`getYueGan(year, month)\`、\`ly_zhi\` 和 \`_JieQiData\` 生成。
${shenshaNote}
- 来源记录：${result.rawSourceFile}

## 输入

- 流年：${result.year}
- 命主：${result.input.name || ""}
- 八字：${result.input.spacedBazi || result.input.bazi || ""}
- 日干：${result.input.dayStem || ""}
- 性别：${result.input.sex === 1 ? "男" : result.input.sex === 0 ? "女" : ""}
- 排盘底稿：${result.input.chartJson || ""}

## ${result.year} 流月表

| 序 | 流月 | 起始节气 | 起始时间 | 结束前 | 天干十神 | 月支主气十神 | 神煞/状态 |
|---|---|---|---|---|---|---|---|
${monthRows.join("\n")}

## 日期定位

${activeText}

## 公历月份切分

${segmentText}

## 后续分析要求

- 月份级分析必须引用本文件的节气边界，不能把整个公历月直接当成单一流月。
- 如果同一公历月跨两个流月，先分段判断，再合并现实结论。
- 本文件只提供问真兼容的流月证据，不替代 \`chart.md\`、大运和流年主线。
`;
}

function renderSegments(label, segments) {
  if (!segments.length) return `${label} 未落入本流年范围。`;
  return [
    `公历 ${label} 覆盖：`,
    "",
    "| 日期区间 | 流月 | 天干十神 | 月支主气十神 |",
    "|---|---|---|---|",
    ...segments.map((segment) => `| ${segment.startDateTime} 至 ${segment.endExclusiveDateTime} 前 | ${segment.pillar} | ${segment.stemTenGod || ""} | ${segment.branchPrimaryTenGod || ""} |`)
  ].join("\n");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log(usage());
    return;
  }

  const year = normalizeYear(args.year);
  const chartInfo = await readChartJson(args.chartJson);
  const bazi = normalizeBazi(args.bz || chartInfo.bazi || "");
  const sex = normalizeSex(args.sex ?? chartInfo.sex);
  const dayStem = normalizeDayStem(args.dayStem || chartInfo.dayStem);
  const gregorianMonth = normalizeGregorianMonth(args, year);
  const activeDate = normalizeDateTime(args.date || "");
  const outputDir = path.resolve(
    args.output
    || (chartInfo.chartDir ? path.join(chartInfo.chartDir, `liuyue-${year}`) : path.join(DEFAULT_OUTPUT_ROOT, `liuyue-${safeStamp()}`))
  );
  const rawDir = path.join(outputDir, "raw");
  await fs.mkdir(rawDir, { recursive: true });

  const sourceMapInfo = await resolveSourceMap(args);
  const sourceMap = sourceMapInfo.sourceMap;
  const staticSource = findSource(sourceMap, "./src/views/paipan-result/static.js");
  const utilsSource = findSource(sourceMap, "./src/views/paipan-result/utils.js");
  const rootStaticSource = findSource(sourceMap, "./src/static/index.js");
  const apiSource = findSource(sourceMap, "./src/api/bazi.js");

  const jieQiData = parseJieQiData(staticSource.content);
  const lyZhi = parseLyZhi(rootStaticSource.content);
  const months = buildFlowMonths({ year, jieQiData, lyZhi, dayStem });
  const fetchShensha = !args.noShensha && !!bazi && sex != null;
  await fetchShenShaForMonths(months, {
    bazi,
    sex,
    vip: args.vip ?? chartInfo.vip ?? "0",
    userGuid: args.userGuid ?? chartInfo.userGuid ?? ""
  }, rawDir, !!args.strictShensha);

  const rawSourceFile = path.join(rawDir, "wenzhen-liuyue-source.json");
  const result = {
    source: PAI_PAN_URL,
    fetchedAt: localTimestamp(),
    rawDir,
    rawSourceFile,
    year,
    gregorianMonth,
    activeDate,
    input: {
      name: chartInfo.name || "",
      chartJson: chartInfo.file || "",
      chartSource: chartInfo.source || "",
      bazi,
      spacedBazi: chartInfo.spacedBazi || bazi.match(/../g)?.join(" ") || bazi,
      sex,
      dayStem,
      vip: args.vip ?? chartInfo.vip ?? "0",
      userGuid: args.userGuid ?? chartInfo.userGuid ?? "",
      fetchShensha
    },
    provenance: {
      indexUrl: sourceMapInfo.indexUrl,
      appJsUrl: sourceMapInfo.appJsUrl,
      sourceMapUrl: sourceMapInfo.sourceMapUrl,
      fetchedAt: sourceMapInfo.fetchedAt,
      indexSha256: sourceMapInfo.indexSha256,
      appJsSha256: sourceMapInfo.appJsSha256,
      sourceMapSha256: sourceMapInfo.sourceMapSha256,
      sources: {
        api: apiSource.name,
        rootStatic: rootStaticSource.name,
        paipanStatic: staticSource.name,
        utils: utilsSource.name
      },
      algorithm: {
        monthStem: "getYueGan(year, month): TianGan[(year * 12 + month - (1801 * 12 + 1) + 6) % 10]",
        monthBranches: lyZhi,
        monthStart: "flow month yue starts at _JieQiData[termYear][yue + 1], wrapping yue=12 to next year's 小寒",
        shenshaEndpoint: "getliunianshensha5.php?ln=${pillar}&bz=${bazi}&sex=${sex}&vip=${vip}&userguid=${userguid}"
      }
    },
    months,
    activeMonth: findActiveMonth(months, activeDate),
    gregorianMonthSegments: buildGregorianMonthSegments(months, gregorianMonth)
  };

  await fs.writeFile(rawSourceFile, JSON.stringify({
    provenance: result.provenance,
    jieQiDataUsed: {
      [year]: jieQiData[String(year)],
      [year + 1]: jieQiData[String(year + 1)]
    }
  }, null, 2), "utf8");

  const liuyueJson = path.join(outputDir, "liuyue.json");
  const liuyueMd = path.join(outputDir, "liuyue.md");
  await fs.writeFile(liuyueJson, JSON.stringify(result, null, 2), "utf8");
  await fs.writeFile(liuyueMd, renderMarkdown(result), "utf8");

  console.log(JSON.stringify({
    outputDir,
    liuyueJson,
    liuyueMd,
    year,
    activeMonth: result.activeMonth ? result.activeMonth.pillar : null,
    gregorianMonth,
    gregorianMonthSegments: result.gregorianMonthSegments
  }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
