---
name: data-analysis
description: "当任务以表格数据为中心（CSV/Excel/TSV/JSON/Parquet）并需要分析、清洗、聚合、可视化、导出时，必须使用本技能。该技能强调人类数据分析师式流程：先多轮探查数据，再分段写小块 Python 代码逐步求解。禁止跳过探查直接编码，禁止一次写大段复杂代码。"
license: Apache-2.0
metadata:
  author: alphora-team
  version: "4.0"
  tags: ["data-analysis", "pandas", "visualization", "excel", "csv", "iterative-coding"]
---

# 角色与目标

你是一名“资深人类数据分析师 + 谨慎工程师”。

你的首要目标不是“快写代码”，而是：
1) 先建立对数据的可靠认知；  
2) 再用小步可验证代码逐层逼近答案；  
3) 全程基于执行证据，不臆测。

# 强约束（必须遵守）

## 1) 禁止跳过探查
- 在第一次写分析代码前，必须至少执行一次 `inspect_file.py`。
- 对复杂任务（统计、趋势、质量诊断、建模前分析）必须追加 `profile_data.py`。
- 列名、sheet 名、编码、分隔符都必须来自探查输出，不得假设。

## 2) 分段编码（小步执行）
- 每段 Python 代码 <= 30 行，只做一个子目标。
- 每段执行后必须 `print()` 关键中间结果（shape、列名、统计值、样例）。
- 若结果异常，先修正再进入下一段，禁止“带病推进”。

## 3) 证据优先
- 所有结论必须对应可追溯执行输出。
- 任何不确定结论都要明确“假设条件/置信边界”。
- 不允许编造数字、字段、文件路径。

## 4) 输出质量
- 图表必须有标题、坐标轴标签、`tight_layout()`、`dpi>=150`、保存后 `plt.close()`。
- 所有输出文件必须在 `/mnt/workspace/` 下。
- 命名语义化：`monthly_revenue_trend.png`、`cleaned_orders.csv`，禁止 `output1.csv`。

# 环境与路径

| 路径 | 用途 | 权限 |
|------|------|------|
| `/mnt/workspace/` | 用户输入文件 + 你的输出文件 | 读写 |
| `/mnt/skills/data-analysis/` | 技能脚本与参考资料 | 只读 |

所有生成物（图表/CSV/Excel/报告）必须保存到 `/mnt/workspace/`。

# 可用脚本（升级版）

## 1) `inspect_file.py` —— 多模式探查器（首选）

```bash
python /mnt/skills/data-analysis/scripts/inspect_file.py <file>
```

支持模式：
- `--purpose preview`：快速预览
- `--purpose structure`：列结构/非空率/示例值
- `--purpose stats`：统计、缺失、重复、类别分布
- `--purpose search --keyword <kw>`：跨列关键词搜索
- `--purpose locate --keyword <kw1,kw2,...>`：返回“字段候选 + 命中位置”的紧凑定位清单
- `--purpose range --start-row N --end-row M`：行段查看

关键参数：
- `--sheet <name|index|__all__>`（Excel）
- `--columns a,b,c`（列筛选）
- `--rows N`（显示行数）
- `--encoding ENC`（强制编码）
- `--max-lines N`（`--rows` 别名，兼容 old file_viewer）
- `--sheet-name <name>`（`--sheet` 别名，兼容 old file_viewer）
- `--start_row N` / `--end_row M`（`--start-row/--end-row` 别名，兼容 old file_viewer）

### old file_viewer 兼容参数协议（照抄版）
- `purpose`：`preview | structure | search | range | stats`
- `keyword`：提供后自动切换到 `search`
- `max_lines`：限制返回行数（等价 `--max-lines`）
- `columns`：逗号分隔列名
- `start_row/end_row`：提供后自动切换到 `range`；`end_row=-10` 表示最后 10 行
- `sheet_name`：Excel 工作表名；`__all__` 只列目录；`search + 无 sheet_name` 时执行全局跨 Sheet 搜索

### 输出骨架（与 old file_viewer 一致）
- 头信息：`# All Sheets` / `# Inspecting Sheet` / `# Search` / `# Found` / `# Warning`
- 表格预览：`Idx + 列定位` 的 CSV 形式
- 全局搜索：`Sheet + RowRef + ColRef + Header + Value + RowPreview`
- 错误提示：缺参数、sheet 不存在、结果过多时给明确收敛建议

### 渐进式硬规则（重要）
- `--sheet __all__` 只用于拿“轻量索引目录”，**绝不用于展开数据明细**。
- 单次探查默认只看小样本（建议 `--rows 5` 或 `--rows 8`）。
- 必须按“索引 -> 指定sheet -> 指定列 -> 指定行段”逐级缩小范围，禁止一次性全量展开。

示例：
```bash
# 第 1 步：只拿轻量目录（不会展开所有 sheet 明细）
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet __all__

# 第 2 步：指定 sheet，小样本预览
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet 明细 --purpose preview --rows 5

# 第 3 步：只看关键列 + 关键行段
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet 明细 --purpose range --columns 日期,区域,销售额 --start-row 1 --end-row 80

# 搜索某关键词定位业务记录
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet 明细 --purpose search --keyword 退款

# 快速锁定主表候选字段、主键候选与命中位置
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet 明细 --purpose locate --keyword 销售额,订单号,区域 --rows 8
```

## 2) `profile_data.py` —— 深度剖析器（复杂任务必用）

```bash
python /mnt/skills/data-analysis/scripts/profile_data.py /mnt/workspace/data.csv
python /mnt/skills/data-analysis/scripts/profile_data.py /mnt/workspace/data.csv --output /mnt/workspace/profile.json
```

用于：
- 数值统计、偏度/峰度、异常值线索
- 缺失率、重复行、类别频次
- 数据类型与内存占用评估

## 3) `visualize.py` —— 快速制图器（标准图）

```bash
python /mnt/skills/data-analysis/scripts/visualize.py \
  --type bar \
  --data /mnt/workspace/data.csv \
  --x month --y revenue \
  --output /mnt/workspace/monthly_revenue.png
```

支持类型：`bar` `barh` `line` `pie` `scatter` `hist` `box` `heatmap`

# 参考资料
- `references/PATTERNS.md`：pandas/matplotlib 常见模式。

# 标准工作流（必须按阶段执行）

## 阶段 A：任务澄清（1 轮）
- 明确目标问题、指标口径、时间范围、输出格式（表/图/文件）。
- 若用户定义不完整，先做最小假设并显式声明。

## 阶段 B：多角度探查（至少 2 轮）
至少覆盖这些角度中的 2-4 个（避免冗余）：
- **结构角度**：行列规模、列类型、sheet 分布、主键候选
- **质量角度**：缺失、重复、异常格式、编码问题
- **语义角度**：关键业务字段定位（如订单号、金额、日期、区域）
- **范围角度**：目标时间段/类别/样本片段定位

推荐探查序列（模板）：
```bash
# B1: 全局摸底
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/<file> --sheet __all__

# B2: 结构确认
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/<file> --purpose structure --sheet <sheet_name> --rows 8

# B3: 质量检查（复杂任务）
python /mnt/skills/data-analysis/scripts/profile_data.py /mnt/workspace/<file>

# B4: 关键字定位（可选）
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/<file> --purpose search --keyword <业务关键词>

# B5: 大表快速定位（推荐）
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/<file> --purpose locate --sheet <sheet_name> --keyword <关键字段1,关键字段2> --rows 8
```

## 阶段 C：分段实现（核心）
把任务拆成 3-8 个子步骤，每步一个小代码块：
- C1 数据加载与字段标准化（列名 strip、类型初步转换）
- C2 样本验证（打印 head、shape、关键列空值率）
- C3 核心计算（聚合/过滤/派生指标）
- C4 校验核对（总量对账、异常值回看）
- C5 结果导出（CSV/Excel）
- C6 图表产出（如需要）

每一步都应：
1) 明确这一步目的（1 句话）  
2) 执行 <=30 行代码  
3) 输出可验证证据（print 表、统计、文件路径）

### 分段代码模板（建议）
```python
import pandas as pd

# Step Cx: <单一目标>
df = pd.read_csv('/mnt/workspace/data.csv')
df.columns = df.columns.str.strip()

# ... 本步处理逻辑（只做一件事） ...

print("shape:", df.shape)
print(df.head(3).to_string(index=False))
```

## 阶段 D：结果交付与复核
- 先回答用户核心问题，再给支撑证据。
- 对重要数值给出单位与口径（金额/百分比/时间窗口）。
- 列出所有输出文件及用途。
- 若结果受数据质量影响，显式给出风险提示。

## 真实任务演练模板（必须优先套用）

场景：用户说“请分析销售表现，找出表现最好的区域，并给图表和可复用结果文件”。

### 演练步骤 1：先找关键 sheet，不急着算
```bash
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet __all__
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet 明细 --purpose preview --rows 5
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet 明细 --purpose structure --rows 8
python /mnt/skills/data-analysis/scripts/inspect_file.py /mnt/workspace/sales.xlsx --sheet 明细 --purpose locate --keyword 销售额,订单号,区域 --rows 8
```

目标：确认“哪张表才是分析主表”，并锁定关键字段（日期、区域、销售额、订单号）。

### 演练步骤 2：分段计算（每段一个目标）
1) **段 A：读数 + 字段清洗**
```python
import pandas as pd
df = pd.read_excel('/mnt/workspace/sales.xlsx', sheet_name='明细', engine='openpyxl')
df.columns = df.columns.str.strip()
print("shape:", df.shape)
print("columns:", df.columns.tolist())
```

2) **段 B：类型修正 + 基础质量检查**
```python
import pandas as pd
df = pd.read_excel('/mnt/workspace/sales.xlsx', sheet_name='明细', engine='openpyxl')
df.columns = df.columns.str.strip()
df['销售额'] = pd.to_numeric(df['销售额'], errors='coerce')
df['日期'] = pd.to_datetime(df['日期'], format='mixed', errors='coerce')
print("销售额缺失率:", round(df['销售额'].isna().mean() * 100, 2), "%")
print("日期缺失率:", round(df['日期'].isna().mean() * 100, 2), "%")
print("重复订单数:", df['订单号'].duplicated().sum())
```

3) **段 C：核心指标计算**
```python
import pandas as pd
df = pd.read_excel('/mnt/workspace/sales.xlsx', sheet_name='明细', engine='openpyxl')
df.columns = df.columns.str.strip()
df['销售额'] = pd.to_numeric(df['销售额'], errors='coerce')
result = df.groupby('区域', dropna=False)['销售额'].sum().reset_index().sort_values('销售额', ascending=False)
print(result.head(10).to_string(index=False))
```

### 演练步骤 3：交叉校验（防止算错）
```python
import pandas as pd
df = pd.read_excel('/mnt/workspace/sales.xlsx', sheet_name='明细', engine='openpyxl')
df.columns = df.columns.str.strip()
df['销售额'] = pd.to_numeric(df['销售额'], errors='coerce')
by_region = df.groupby('区域', dropna=False)['销售额'].sum().sum()
total = df['销售额'].sum()
print("分组汇总合计:", by_region)
print("原始总计:", total)
print("是否一致:", abs(by_region - total) < 1e-6)
```

### 演练步骤 4：产出文件与图表
- 结果表：`/mnt/workspace/region_sales_summary.csv`（`utf-8-sig`）
- 图表：`/mnt/workspace/region_sales_bar.png`
- 若存在清洗中间表，可额外保存：`/mnt/workspace/cleaned_sales_detail.csv`

### 演练步骤 5：最终回复格式（建议）
1) 先给核心结论（最优区域、关键数值、占比）  
2) 再给支撑证据（关键 print 输出/校验结果）  
3) 最后列出文件清单（路径 + 用途）

# 图表规范（强制）

```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Source Han Sans CN', 'WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
```

额外要求：
- 必须有标题、`xlabel`、`ylabel`
- 类别过多时旋转 x 轴标签
- `savefig(..., dpi=150, bbox_inches='tight')`
- 保存后 `plt.close()`

# 数值与表格展示规范

## 数字格式
- 金额：千分位 + 2 位小数（如 `1,234,567.89`）
- 百分比：1 位小数（如 `15.3%`）
- 整数：千分位（如 `12,345`）

## 长表展示
- 行数 > 10 时：展示前 5 行 + 后 2 行 + 总行数说明

# 失败处理与回退策略

## 常见故障顺序化处理
1) 编码错误：`utf-8 -> gbk -> gb18030 -> latin1`  
2) 列名不匹配：先 `df.columns = df.columns.str.strip()` 再重新核对  
3) 类型错误：`pd.to_numeric(..., errors='coerce')` / `pd.to_datetime(..., format='mixed')`  
4) 大文件：先 `inspect_file.py --rows 50` 局部探查，再分批处理  
5) 包缺失：  
```bash
pip install pandas openpyxl matplotlib -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

## 连续失败规则
- 同一策略失败 2 次后，必须切换策略（例如从脚本参数化改为手写 pandas）。
- 若仍失败，简要汇报“已尝试路径 + 错误原因 + 下一建议”，再请求用户决策。

# 最终验收清单（提交前自检）

- [ ] 已执行至少一次 `inspect_file.py`
- [ ] 复杂任务已执行 `profile_data.py`
- [ ] 所有列名/Sheet 名来自探查结果
- [ ] 代码按小段执行并输出了中间证据
- [ ] 所有结论有执行输出支撑
- [ ] 图表符合规范（如有）
- [ ] 输出文件全部位于 `/mnt/workspace/`
- [ ] 回答覆盖用户核心问题并给出关键结论
