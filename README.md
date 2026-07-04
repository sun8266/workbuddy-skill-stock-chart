# 📈 Stock Normalized Chart Skill

> WorkBuddy AI 助手技能包 — 输入股票名称或代码，自动生成 A 股个股归一化走势图

## ✨ 功能介绍

本技能可根据用户输入的**股票名称或代码**，自动获取过去一年（天数可自定义）的三项关键数据：

| 数据线 | 说明 |
|--------|------|
| 🔴 **个股收盘价**（前复权） | 真实价格走势 |
| 🟠 **PE(TTM)** | 动态市盈率估值变化 |
| 🟢 **申万二级行业指数** | 所属行业整体走势 |

三条曲线均以**首日 = 1.0** 进行归一化，方便直观比较个股相对行业的强弱，以及股价与估值的联动关系。

### 输出效果

生成一张**交互式 HTML 图表**（基于 Plotly），支持：
- 鼠标悬停查看精确数值
- 缩放、平移时间区间
- 切换显示/隐藏某条曲线
- 中文标签，红涨绿跌（符合中国市场惯例）

---

## 🚀 安装方法

### 方式一：从 GitHub 安装（推荐）

在 WorkBuddy 对话中输入：

```
安装 skill，地址是 https://github.com/sun8266/workbuddy-skill-stock-chart
```

### 方式二：手动安装

1. 下载本仓库的 ZIP 压缩包并解压
2. 将 `stock-normalized-chart` 文件夹复制到 WorkBuddy 的 skills 目录：
   - 用户级：`~/.workbuddy/skills/`
   - 项目级：`<你的项目>/.workbuddy/skills/`
3. 重启 WorkBuddy 或重新加载技能列表

---

## 📖 使用方法

安装完成后，在 WorkBuddy 对话中直接输入：

```
帮我生成贵州茅台的归一化走势图
```

或带上股票代码：

```
@skill:stock-normalized-chart 600519
```

### 参数说明

| 输入格式 | 示例 | 说明 |
|----------|------|------|
| 6位股票代码 | `600519`、`000001`、`300750` | 自动识别沪深北交易所 |
| 中文股票名称 | `贵州茅台`、`平安银行`、`宁德时代` | 模糊匹配 |
| 自定义天数 | `--days 180` | 默认365天 |

---

## 📊 生成示例

### 示例一：贵州茅台（600519）

```
@skill:stock-normalized-chart 贵州茅台
```

生成文件：`guizhoumaotai_normalized_chart.html`

- 收盘价归一化曲线（红色）
- PE(TTM) 归一化曲线（橙色）
- 申万二级行业「白酒II」指数归一化曲线（绿色）

### 示例二：平安银行（000001）

```
@skill:stock-normalized-chart 平安银行 --days 180
```

- 回溯180天数据
- 行业指数：申万二级「股份制银行II」

### 示例三：宁德时代（300750）

```
@skill:stock-normalized-chart 300750
```

- 行业指数：申万二级「电池II」

---

## 🔧 技术实现

### 数据来源

| 数据项 | AKShare 接口 | 数据来源 |
|--------|-------------|----------|
| 个股收盘价 | `stock_zh_a_daily` | 新浪财经（前复权） |
| PE(TTM) | `stock_zh_valuation_baidu` | 百度股市通 |
| 申万行业指数 | `index_hist_sw` | 申万宏源 |

### 归一化方法

所有数据除以各自首个交易日的数值，使三条曲线均从 1.0 起步：

```
归一化值 = 当日数值 / 首个交易日数值
```

这样可以直观比较：
- 曲线 > 1.0 → 相对起点上涨
- 曲线 < 1.0 → 相对起点下跌
- 个股线跑赢行业线 → 个股强于行业

### 行业归属查找

采用**三策略降级**方案（应对 AKShare 接口频繁变动）：
1. **首选**：`stock_industry_clf_hist_sw()` 获取行业代码，查内置映射表（覆盖 ~60 个常见二级行业）
2. **备选**：通过个股信息接口获取行业名称，按名称匹配
3. **降级**：若全部失败，自动跳过行业指数线，仅展示收盘价 + PE TTM 双线图

---

## 📦 依赖

脚本内置自动依赖检测，首次运行时会自动安装：

```
akshare >= 1.12.0
pandas >= 2.0.0
urllib3 >= 2.0.0
```

> **注意**：AKShare 需要访问外部数据源，执行时请允许网络权限。

---

## ⚠️ 注意事项

- AKShare 依赖公开数据源，接口可能因源站变更而暂时失效，建议关注 [AKShare 官方仓库](https://github.com/akfamily/akshare) 获取更新
- 部分东方财富系列接口连接不稳定，脚本已尽量规避依赖这些接口
- 批量查询时建议在请求间加延迟，避免被源站限流
- 生成的 HTML 文件名含中文时，部分预览面板可能无法加载，建议使用英文输出路径

---

## 📄 许可证

MIT License — 自由使用、修改和分发。

---

## 🙏 致谢

- [AKShare](https://github.com/akfamily/akshare) — 开源财经数据接口库
- [Plotly](https://plotly.com/) — 交互式图表库
- [WorkBuddy](https://www.workbuddy.cn/) — AI 助手平台

---

## 📮 反馈与贡献

- 问题反馈：欢迎在 [GitHub Issues](https://github.com/sun8266/workbuddy-skill-stock-chart/issues) 提交 bug 或功能建议
- 代码贡献：Fork 本仓库，提交 Pull Request
- 技能分享：本技能已上传至 ClaWHub，可在 WorkBuddy 技能市场中搜索安装

---

*Made with ❤️ for Chinese A-share investors*
