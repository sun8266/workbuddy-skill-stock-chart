---
name: stock-normalized-chart
description: >-
  A股个股归一化走势图生成器。输入股票名称或代码，自动生成过去一年（可自定义天数）的
  收盘价、PE(TTM)、申万二级行业指数三条归一化曲线（首日=1.0）的交互式HTML点线图。
  当用户提到"股票走势""归一化图表""股价vs行业""PE走势对比""个股图表"等需求时触发此技能。
  适用于个股与行业走势对比分析、估值变化可视化、相对强弱分析等场景。
agent_created: true
---

# Stock Normalized Chart

## Overview

此技能根据用户输入的股票名称或代码，自动获取过去一段时间内的三项数据——个股收盘价（前复权）、PE(TTM)、所属申万二级行业指数收盘价——将三者归一化到首日=1.0，生成一张交互式HTML点线图，便于直观比较个股股价、估值与行业整体的相对走势。

## When to Use

- 用户提供股票名称或代码，要求生成走势图/对比图
- 用户想比较个股与行业的相对强弱
- 用户想看股价与PE的联动关系
- 用户提到"归一化""点线图""股价vs行业"等关键词

## Prerequisites

- 脚本内置自动依赖检测：首次运行时如缺少 `akshare`、`pandas`、`urllib3`，会自动 `pip install`
- 执行脚本时需使用 `dangerouslyDisableSandbox: true`（AKShare 需访问外部数据源）
- Python 路径：使用当前环境的 Python 解释器（WorkBuddy 管理环境路径为 `~/.workbuddy/binaries/python/envs/default/Scripts/python.exe`，其他环境使用系统 `python` 即可）

## Workflow

### Step 1: Run the Script

直接执行 bundled 脚本，将用户输入的股票名称或代码作为参数传入：

```bash
# WorkBuddy 管理环境
~/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
  ~/.workbuddy/skills/stock-normalized-chart/scripts/generate_stock_chart.py \
  <股票代码或名称> [--days <天数>] [--output <输出路径>]

# 或使用系统 Python（需已安装 akshare、pandas）
python \
  ~/.workbuddy/skills/stock-normalized-chart/scripts/generate_stock_chart.py \
  <股票代码或名称> [--days <天数>] [--output <输出路径>]
```

**必须设置 `dangerouslyDisableSandbox: true`**，否则网络请求会被沙箱阻断。

#### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `stock`（必填） | 6位股票代码或中文名称 | `600519`、`贵州茅台`、`000001` |
| `--days` | 回溯天数，默认365 | `--days 180` |
| `--output` | 输出HTML路径，默认当前目录 | `--output /path/to/chart.html` |

#### 使用示例

```bash
# 按代码查询，默认一年
python generate_stock_chart.py 600519

# 按名称查询，半年数据
python generate_stock_chart.py 贵州茅台 --days 180

# 指定输出路径
python generate_stock_chart.py 000001 --output /home/user/pingan_chart.html
```

### Step 2: Present the Result

脚本执行完成后，使用 `present_files` 工具展示生成的 HTML 文件，HTML 会在预览面板中自动渲染。

**注意**：如果生成的 HTML 文件名包含中文字符，预览面板可能无法加载。建议用 `--output` 指定纯英文路径，或生成后 `cp` 到英文名再 present。

## Data Sources

| 数据 | AKShare 接口 | 数据源 | 备注 |
|------|-------------|--------|------|
| 个股收盘价 | `ak.stock_zh_a_daily(symbol='sh600519', adjust='qfq')` | 新浪财经 | 前复权，symbol需带交易所前缀(sh/sz/bj) |
| PE(TTM) | `ak.stock_zh_valuation_baidu(symbol='600519', indicator='市盈率(TTM)', period='近一年')` | 百度股市通 | symbol为纯6位代码 |
| 申万行业指数 | `ak.index_hist_sw(symbol='801783', period='day')` | 申万宏源 | 需先查个股所属申万二级行业 |

## Key Implementation Details

### SSL 补丁
脚本顶部内置 SSL 补丁（`ssl._create_default_https_context = ssl._create_unverified_context` + `requests` verify=False），因为部分 AKShare 数据源（如申万宏源）存在证书问题。

### 股票代码解析
- 6开头 → 沪市（前缀 `sh`）
- 0/3开头 → 深市（前缀 `sz`）
- 8/4开头 → 北交所（前缀 `bj`）
- 输入名称时，通过 `ak.stock_info_a_code_name()` 反查代码（轻量级，只返回code+name，不会像 `stock_zh_a_spot_em()` 那样拉全市场行情导致超时）

### 申万行业归属查找（三策略降级）
1. **策略1（首选）**：`ak.stock_industry_clf_hist_sw()` 获取个股 industry_code，取前4位作为二级行业代码，查内置 `SW_INDUSTRY_MAP` 映射表（覆盖~60个常见二级行业）得到 SW 指数代码
2. **策略2（备选）**：`ak.stock_individual_info_em()` 获取行业名 → `ak.index_realtime_sw(symbol='二级行业')` 按名称匹配
3. **策略3（最后手段）**：遍历所有 SW 指数成分股反查（很慢，通常跳过）
4. **降级**：若全部失败，跳过行业指数线，仅展示收盘价 + PE TTM 两条线

### SW_INDUSTRY_MAP 映射表
脚本内置了 `stock_industry_clf_hist_sw` 返回的 industry_code（前4位）到 `index_realtime_sw` 指数代码的映射表，覆盖银行、证券、保险、白酒、家电、汽车、医药、电子、化工、钢铁、有色、电力设备、建筑、地产、交运、计算机、传媒、军工等~60个二级行业。这是因为 `sw_index_second_info()` 和 `sw_index_third_cons()` 等 AKShare 接口经常因源站页面结构变更而失效，映射表是更可靠的方案。

### 归一化方法
所有三组数据除以各自首个交易日的值，使三条线均从1.0起点。

### Y轴范围自动计算
Y轴范围根据实际数据的最大值和最小值自动留出余量（上限+10%，下限-5%），确保所有数据点完整显示。

### 图表样式
- 红色线（#E63946）：个股收盘价，圆形标记
- 橙色线（#FF8C00）：PE(TTM)，菱形标记
- 绿色线（#2A9D8F）：申万行业指数，圆形标记
- 涨跌颜色遵循中国市场惯例：涨为红，跌为绿

### 优雅降级
当 SW 行业数据无法获取时，图表自动降级为双线（收盘价 + PE TTM），不影响核心功能。

## Resources

### scripts/
- `generate_stock_chart.py` — 主脚本，接收股票代码/名称，自动获取数据、归一化、生成HTML图表

## Notes

- AKShare 依赖公开数据源，接口偶尔可能因源站变更而失效，需关注 AKShare 版本更新
- 东方财富(eastmoney)系列接口（`stock_individual_info_em`、`stock_zh_a_spot_em`、`stock_board_industry_*`）经常出现连接超时，脚本已尽量避免依赖这些接口
- 申万系列接口（`sw_index_second_info`、`sw_index_third_cons`）经常因页面结构变更返回 None，脚本使用 `stock_industry_clf_hist_sw` + 映射表替代
- 批量查询多家公司时，建议在请求间加 `time.sleep(2)` 避免被源站限流
- 脚本内置 3 次重试机制，每次间隔 5 秒
