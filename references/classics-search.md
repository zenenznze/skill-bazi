# 古籍检索指南

## 原典梯队

### 第一梯队（必须先搜）

| 书名 | 本地引用 | 主要用途 | 常搜关键词 |
|------|----------|----------|------------|
| 《滴天髓》 | `references/classics-originals/raw/滴天髓.txt` | 日主气质、五行根本、总论句 | 庚金、辛金、官、杀、伤官、印、财 |
| 《滴天髓阐微》 | `references/classics-originals/raw/滴天髓阐微.txt` | 任铁樵纠偏、反对机械套格局/刑害 | 伤官、刑、冲、喜忌、生克 |
| 《穷通宝鉴》 | `references/classics-originals/raw/穷通宝鉴.txt` | 月令、调候、病药、时令对日主的影响 | 四月庚金、五月庚金、三夏庚金、冬金、秋木 |
| 《渊海子平》 | `references/classics-originals/raw/渊海子平.txt` | 十神原始语义（财官印食伤比劫古典定义） | 劫财、伤官、财、官、印 |
| 《三命通会》 | `references/classics-originals/raw/三命通会.txt` | 组合、刑冲会合、性情与应象描述 | 寅巳申、互相刑、会合 |

### 第二梯队（补充搜）

| 书名 | 本地引用 | 用途 |
|------|----------|------|
| 《子平真诠》 | 未纳入本地全文，需联网逐条核对 | 补格局、用神、病药视角 |
| 《神峰通考》 | `references/classics-originals/raw/神峰通考.txt` | 补传统断语与经验句 |
| 《穷通宝鉴》相关注本 | 先查 `references/classics-originals/raw/穷通宝鉴.txt`，注本需另行核对 | 补月令判断的现代解释 |

## 搜索模式

### 模式 A：精确定位（已知大致原句）

```
site:zh.wikisource.org "庚金带煞，刚强为最"
site:zh.wikisource.org "四月庚金，长生于巳"
site:zh.wikisource.org "财者，人之所欲，方令弟兄见之，多有争竞"
site:zh.wikisource.org "刑之义无所取"
site:zh.wikisource.org "英华发外，多主聪明"
```

### 模式 B：书名 + 关键词（只知主题）

```
site:zh.wikisource.org 穷通宝鉴 庚金 巳月
site:zh.wikisource.org 三命通会 寅巳申 刑
site:zh.wikisource.org 滴天髓阐微 刑 生克
site:zh.wikisource.org 渊海子平 劫财 争竞
```

### 模式 C：反向找异议（防止只搜到支持自己结论的材料）

```
site:zh.wikisource.org 滴天髓阐微 刑之义无所取
site:zh.wikisource.org 任铁樵 刑 害 生克
site:zh.wikisource.org 三命通会 寅巳申 互相刑
```

## 搜索顺序（强制）

0. **先查本地原文** → `references/classics-originals/raw/`，已纳入的书直接查对应中文文件名。
1. **再找原句** → 确认原文是否存在
2. **再找整本书或所在章节** → 还原上下文，避免断章取义
3. **再找相反意见或纠偏意见** → 确认古人内部是否有不同看法
4. **最后才做综合推断**

## 搜索目标

不是"搜到一句就赢"，而是：
1. 确认这句话**真存在**
2. 确认它在原书里**是什么意思**
3. 确认它和**当前命盘是否匹配**
4. 确认有没有**更强的解释变量**

## 推荐检索站点

- **本地原文库**（`references/classics-originals/raw/`）— 已抓取原文，优先使用；需要核版、缺卷或异文时再回维基文库
- **维基文库**（zh.wikisource.org）— 原文全文，用于复核本地文本和补未纳入书目
- **中国哲学书电子化计划**（ctext.org）— 古籍全文检索备选
- 现代文章仅作补充，必须标注为"二手分析"，不能压过原典

## 引用规则

- 回答中注明出处："《书名·篇章》原文：…"
- 二手解释单独标注，与原典明确区分
- 每条引用说明：支持到哪一步，哪一步开始是现代推论
