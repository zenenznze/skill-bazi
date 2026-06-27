# 八字技能包概览

本仓库已按 `dbs` 风格重构为 umbrella skill 包：根级 `SKILL.md` 是主入口，`skills/` 下每个目录是一项可独立触发的子技能。

## 子技能映射

| 子技能 | 来源 | 职责 |
|---|---|---|
| 根级 `SKILL.md` | 原根级主控 | 主入口、主控、路由 |
| `skills/bazi-dingpan/` | 原排盘模块 + 子时定盘扩展 | 定盘、排盘、节气、真太阳时、子时换日、四柱反推 |
| `skills/bazi-geju/` | 格局取法模块 | 月令、天透地藏、四见、三合三会、建禄羊刃、顺逆用 |
| `skills/bazi-mingju/` | 原正统子平模块 | 命局总论、原局结构、旺衰承载、调候病药、十神宫位 |
| `skills/bazi-dayun/` | 大运理解模块 | 大运主旋律、换运状态、十神运势和流年微调 |
| `skills/bazi-liunian/` | 原前事验盘模块 + 原年份验盘模块 | 前事反推、年份验盘、年表反证 |
| `skills/bazi-shiye/` | 原职业模块 | 职业方向、平台、岗位选择 |
| `skills/bazi-qinmi/` | 原关系模块的亲密部分 | 恋爱、伴侣、婚姻和长期亲密关系 |
| `skills/bazi-jiating/` | 从原关系模块拆分 | 父母宫、原生家庭模板、早年关系气候和家庭责任 |
| `skills/bazi-renji/` | 原现实分析模块 | 普通人际、边界感、冲突模式、合作同类关系 |
| `skills/bazi-jiankang/` | 原根级模块二 | 健康体质、病位、岁运触发 |
| `references/analysis-governance.md` | 原总控规范模块 | 多模块链路、证据规范、输出规范 |

## 共享参考资料

- `references/complex-case-method-notes.md`：复杂盘复核、用神分层、年表反证。
- `references/analysis-governance.md`：完整链路、证据、验盘和输出规范。
- `references/hour-branch-deep-analysis.md`：时支深层分析。
- `references/zi-hour-method-notes.md`：子时定盘、真太阳时、早晚子时和前事核验方法。
- `references/momtest-validation-questions.md`：Mom Test 式验盘提问规范，避免用候选盘画像诱导当事人。
- `references/classics-search.md`：古籍原文检索指南。
- `references/translation-examples.md`：古籍术语到现实结构语言的翻译示例。

## 设计原则

- `bazi` 主入口只做主控和路由，不再承载具体专题正文。
- 子技能按任务场景独立触发，避免一次加载全部八字知识。
- 完整链路默认是：定盘 -> 格局 -> 命局 -> 大运 -> 流年 -> 现实用途专题。
- 子时属于定盘内部专项；前事验盘属于流年验证链路。
- 专题技能保留原有方法论内容，结构迁移不改写核心断法。
