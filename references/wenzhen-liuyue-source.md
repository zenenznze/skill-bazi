# 问真流月来源说明

本文件记录 `scripts/pcbz_liuyue_fetch.mjs` 的数据来源。处理问真流月变化、脚本失效或前端改版时再读。

## 当前来源

- 页面入口：`https://pcbz.iwzwh.com/#/paipan/index`
- 首页脚本：`https://pcbz.iwzwh.com/static/js/app.<hash>.js`
- source map：从 app bundle 末尾的 `sourceMappingURL` 解析。
- 流月源码：
  - `src/views/paipan-result/utils.js`
  - `src/views/paipan-result/static.js`
  - `src/static/index.js`
  - `src/api/bazi.js`

## 关键逻辑

问真没有直接返回 12 个流月干支的后端接口。前端生成逻辑是：

```js
ly_zhi = ['寅','卯','辰','巳','午','未','申','酉','戌','亥','子','丑']

function getYueGan(year, month) {
  const TianGan = ['甲','乙','丙','丁','戊','己','庚','辛','壬','癸']
  const initnum = 1801 * 12 + 1
  const newnum = year * 12 + month
  return TianGan[(newnum - initnum + 6) % 10]
}
```

每个流月的起点使用 `_JieQiData` 中的下一节气：

- 第 1 个流月 `寅` 起于当年 2 月立春。
- 第 5 个流月 `午` 起于当年 6 月芒种。
- 第 6 个流月 `未` 起于当年 7 月小暑。
- 第 12 个流月 `丑` 起于次年 1 月小寒。

神煞只作为低优先级附录，接口是：

```text
getliunianshensha5.php?ln=<流月干支>&bz=<八字>&sex=<性别>&vip=<vip>&userguid=<guid>
```

## 已知校验

2026 年 7 月按问真节气表切分为：

- `2026-07-01 00:00:00` 至 `2026-07-07 09:56:40` 前：`甲午`。
- `2026-07-07 09:56:40` 至 `2026-08-01 00:00:00` 前：`乙未`。

命主为丁火时，`甲午` 天干为正印、午主气丁为比肩；`乙未` 天干为偏印、未主气己为食神。

## 维护原则

- 先让脚本重新抓 source map 和 hash，不手抄全年节气表。
- 如果 source map 不可用，报告失败来源；不要静默改用本地库。
- 本地 `lunar_python` 只能做排盘兜底，不能替代问真流月证据。
