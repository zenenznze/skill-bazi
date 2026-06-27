# bazi skill pack

这是一个中文八字命理 umbrella skill 包，结构参考 `dbs`：`skills/bazi/` 是主入口，其他 `skills/bazi-*` 是可独立触发的子技能。

## 必装入口

- `bazi`：主入口。负责判断用户意图并路由到具体子技能。

## 子技能

- `bazi-dingpan`：定盘，包含排盘、节气、真太阳时、子时换日、四柱反推和候选盘生成。
- `bazi-geju`：格局取法、天透地藏、四见、三合三会、建禄羊刃、顺逆用和格局时效。
- `bazi-mingju`：命局总论，在格局之后整合原局、旺衰承载、调候病药、用神喜忌、十神宫位。
- `bazi-dayun`：大运主旋律、换运状态、十神运势和流年微调。
- `bazi-liunian`：流年与验盘，包含前事反推、年份验盘、年表反证。
- `bazi-shiye`：职业方向、平台、岗位选择。
- `bazi-qinmi`：恋爱、伴侣、婚姻和长期亲密关系。
- `bazi-jiating`：父母宫、原生家庭模板、早年关系气候和家庭责任。
- `bazi-renji`：普通人际、边界感、冲突模式、合作同类关系和现实互动困惑。
- `bazi-jiankang`：健康体质、病位、岁运触发。

## 典籍原文库

本技能包现在带有一组“只含原文、不含白话译文”的典籍参考，入口在
`references/classics-originals/README.md`。需要查原句时，优先检索：

```bash
rg "关键词" references/classics-originals/raw
```

已纳入本地原文：

- 《滴天髓》
- 《滴天髓阐微》
- 《渊海子平》
- 《三命通会》
- 《穷通宝鉴》
- 《神峰通考》

未纳入全文：

- 《子平真诠》：未找到可直接镜像的维基文库完整原文页；需要引用时联网逐条核对原句。
- 《千里命稿》：近现代韦千里著作，仍可能受版权保护；不纳入本地全文。

本地原文不是唯一底本。若不同来源有异文，输出时必须说明采用哪个来源。

## 排盘脚本

`bazi-dingpan` 采用“问真优先、本地兜底”的排盘策略。默认先尝试问真八字网页版接口；
如果问真不可访问，再用本地 `sxtwl` / `lunar_python` 生成结构化底稿，并在 `chart.md` 中明确标注为本地来源。
任何分析前都必须先有 `chart.md` 排盘底稿；只给四柱/八字文本不算已排盘，仍必须先反推候选并排盘落盘。
用户未提供出生地时，不追问真太阳时，直接按北京时间生成底稿并说明未做经度修正。

默认入口：

```bash
python3 scripts/bazi_chart_fetch.py --source auto --date YYYY-MM-DD --time HH:mm --sex male|female --name 命主 --output work/pcbz/<case-id>
```

不想安装本地依赖时，可用 `uv` 临时运行本地兜底依赖：

```bash
uv run --with sxtwl --with lunar_python python3 scripts/bazi_chart_fetch.py --source auto --date YYYY-MM-DD --time HH:mm --sex male|female --name 命主 --output work/pcbz/<case-id>
```

只跑问真专业细盘：

```bash
node scripts/pcbz_chart_fetch.mjs --date YYYY-MM-DD --time HH:mm --sex male|female --name 命主 --output work/pcbz/<case-id>
```

只跑本地结构化底稿：

```bash
python3 scripts/local_bazi_chart_fetch.py --date YYYY-MM-DD --time HH:mm --sex male|female --name 命主 --output work/local-bazi/<case-id>
```

已知四柱时，先走问真网页“四柱”反推候选公历日期，再生成专业细盘。未指定候选编号时，默认采用中间候选：

```bash
python3 scripts/bazi_chart_fetch.py --source auto --pillars "庚辰 己丑 丁亥 丙午" --sex male --name 命主 --output work/pcbz/<case-id>
```

问真路径下，多个候选日期会写入 `raw/szbz.json` 和 `chart.md` 输入区，并写明当前采用候选与选择方式。
本地路径下，候选日期会写入 `raw/local_lunar_python.json`、`chart.json` 和 `chart.md`。
用户明确指定或纠正候选时，使用 `--candidate-index N` 重跑。
四柱反推只用于定位候选公历日期和时辰，不承诺分钟级精度；问真和本地反推如果落在同一天、同一时辰，
即视为反推一致。后续需要精确起运时，必须使用用户提供的真实出生分钟重新按公历起盘。

如果问真“四柱”反推不可用，或需要本地交叉校验候选日期，可使用
`china-testing/bazi` 关键路径封装的本地候选脚本：

```bash
python3 scripts/local_bazi_reverse_lookup.py --start 1850 --end 2030 --verify 庚辰 戊寅 己酉 辛未
```

不想安装到系统环境时，可临时运行：

```bash
uv run --with sxtwl --with lunar_python python3 scripts/local_bazi_reverse_lookup.py --start 1850 --end 2030 --verify 庚辰 戊寅 己酉 辛未
```

依赖：

```bash
pip install sxtwl lunar_python
```

该脚本只做本地候选反推：四柱反推调用 `sxtwl.siZhu2Year(...)`，公历复核调用
`lunar_python` 的 `Solar.fromYmdHms(...).getLunar().getEightChar()`。它本身不生成排盘底稿；
要生成本地 `chart.md`，使用 `scripts/local_bazi_chart_fetch.py` 或统一入口 `scripts/bazi_chart_fetch.py --source auto`。

问真脚本会保存 `raw/` 原始接口响应、`chart.json` 结构化数据和 `chart.md` 专业细盘底稿。
本地脚本会保存 `raw/local_lunar_python.json`、`chart.json` 和 `chart.md` 结构化底稿，但不包含问真 raw、
人元司令接口和问真格局接口。后续验盘与分析必须先读取这些文件。

`chart.md` 会把后续分析最需要的主证放在前面：

- 四柱天干十神、地支藏干十神。
- 起运岁数、起运详情、交运信息。
- 每步大运的公历起止日期、年份段和年龄段。
- 按大运分组的流年索引，包含每个公历年份对应的干支。

十神使用自然读法，例如“辛劫财”“巳藏丙七杀、庚比肩、戊偏印”，不使用等号。神煞、纳音、胎元、命宫、身宫等传统细盘信息保留在低优先级附录或 `raw/` 中，只作辅助参考。

## 子时分诊脚本

23 点前后出生、早晚子时、真太阳时可能跨时辰，或 1986-1991 年中国夏令时可能影响记录时间时，先使用 `bazi-dingpan` 内部的子时分诊流程生成候选盘计划：

```bash
python3 scripts/zi_hour_triage.py --date YYYY-MM-DD --time HH:mm --sex male|female --name 命主 --birthplace 四川成都 --output work/zi-hour/<case-id>
```

若知道精确经度，优先传入 `--longitude`：

```bash
python3 scripts/zi_hour_triage.py --date YYYY-MM-DD --time HH:mm --sex male|female --name 命主 --longitude 104.0665 --output work/zi-hour/<case-id>
```

脚本会生成 `zi_hour_report.md` 和 `zi_hour_report.json`，列出记录时间、标准北京时间、经度校正太阳时、风险等级、候选盘命令和前事核验问题。候选盘命令仍调用 `scripts/bazi_chart_fetch.py --source auto`，每个候选必须生成自己的 `chart.md` 后再分析。

子时专项的原则是：先分清“是否入子时”和“入子时后是否换日”。若出生地偏西导致真太阳时退回亥时，早晚子时换日争议通常应降级，优先验证亥时盘是否更贴近现实。

前事核验问题必须按 Mom Test 式事实采集来写：问过去的具体经历、年份、原话和可佐证记录，不把候选盘画像或“你是不是……”式判断喂给当事人。具体规范见 `references/momtest-validation-questions.md`。

## 更新记录

### 2.0 - 2026-06-28

- 架构更新：子技能统一改为中文拼音入口，并按“定盘 -> 格局 -> 命局 -> 大运 -> 流年”的命理主链路重排。
- 合并旧 `/bazi-zi-hour` 到 `/bazi-dingpan`，子时不再作为独立入口，而是定盘内部专项。
- 合并旧 `/bazi-retro-validation` 到 `/bazi-liunian`，前事验盘与年份反证统一为流年验盘链路。
- 将旧 `/bazi-orthodox` 改为 `/bazi-mingju`，明确命局总论承接格局，不能把旺衰置于格局之前。
- 将现实用途拆为 `/bazi-shiye`、`/bazi-qinmi`、`/bazi-jiating`、`/bazi-renji`、`/bazi-jiankang`。

### 1.7 - 2026-06-27

- 新增 `/bazi-geju` 子技能，用于按用户提供的梁湘润式取格参考，逐项处理月令、天透地藏、四见、三合三会、建禄羊刃、顺逆用和格局时效。
- 新增 `references/geju/user-provided-geju-method.md`，沉淀用户提供的格局取法参考。
- 新增格局模块验收测试样例；公开版不包含个人案例文件。

### 1.6 - 2026-06-24

- 新增 `/bazi-dayun` 子技能，用于解释十年大运主旋律、换运交接期、十神大运现实走法和流年微调。
- 更新主入口路由，把“当前大运/换运状态/阶段自我定位”从完整全盘和年份验盘中拆成独立模块。

### 1.5 - 2026-06-22

- 新增 `references/momtest-validation-questions.md`，把 Mom Test 式事实访谈方法改造成八字定盘/验盘提问规范。
- 更新 `/bazi-dingpan` 和 `/bazi-liunian`，要求待核问题先采集事实，再后台比较候选盘解释力。
- 更新 `scripts/zi_hour_triage.py`，自动报告中的前事核验问题改为非诱导式事实访谈表。

### 1.4 - 2026-06-22

- 新增 `/bazi-dingpan` 子技能，用于 23 点前后、早晚子时、真太阳时、夏令时和出生时间可信度分诊。
- 新增 `scripts/zi_hour_triage.py`，生成可追溯的子时分诊报告和候选盘命令。
- 新增 `references/zi-hour-method-notes.md`，沉淀子时案例的方法原则和输出边界。

### 1.3 - 2026-06-22

- 新增 `references/classics-originals/` 原文库索引和 `raw/` 原文文件。
- 从维基文库整理并纳入《滴天髓》《滴天髓阐微》《渊海子平》《三命通会》《穷通宝鉴》《神峰通考》。
- 更新 `references/classics-search.md`，典籍检索顺序改为先查本地原文，再联网核对上下文。
- 未纳入《子平真诠》全文：未找到可直接镜像的维基文库完整原文页。
- 未纳入《千里命稿》全文：近现代著作存在版权风险。
