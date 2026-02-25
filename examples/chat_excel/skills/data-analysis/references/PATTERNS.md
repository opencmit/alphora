# 常用代码模式速查

遇到不确定的 pandas / matplotlib 写法时查阅本文件。

---

## 1. 文件读写

### 读取 CSV

```python
import pandas as pd

# 基本读取
df = pd.read_csv('data.csv')

# 指定编码
df = pd.read_csv('data.csv', encoding='gbk')

# 指定分隔符
df = pd.read_csv('data.tsv', sep='\t')

# 只读前 N 行（大文件安全预览）
df = pd.read_csv('data.csv', nrows=1000)

# 指定列类型
df = pd.read_csv('data.csv', dtype={'id': str, 'amount': float})

# 解析日期列
df = pd.read_csv('data.csv', parse_dates=['date'])
```

### 读取 Excel

```python
# 读取第一个 sheet
df = pd.read_excel('data.xlsx', engine='openpyxl')

# 读取指定 sheet
df = pd.read_excel('data.xlsx', sheet_name='Sheet2')

# 读取所有 sheets 为字典
dfs = pd.read_excel('data.xlsx', sheet_name=None)
for name, df in dfs.items():
    print(f"Sheet '{name}': {df.shape}")
```

### 保存文件

```python
# CSV（Excel 兼容的 UTF-8 BOM）
df.to_csv('output.csv', index=False, encoding='utf-8-sig')

# Excel 多 sheet
with pd.ExcelWriter('report.xlsx', engine='openpyxl') as writer:
    df_summary.to_excel(writer, sheet_name='汇总', index=False)
    df_detail.to_excel(writer, sheet_name='明细', index=False)

# JSON
df.to_json('output.json', orient='records', force_ascii=False, indent=2)
```

---

## 2. 数据探查

```python
# 基本信息
print(df.shape)
print(df.dtypes)
print(df.describe())
print(df.info())

# 缺失值
print(df.isnull().sum())
print(df.isnull().mean() * 100)  # 缺失百分比

# 唯一值
print(df.nunique())

# 各列前几个值
for col in df.columns:
    print(f"{col}: {df[col].head(3).tolist()}")

# 重复行
print(f"Duplicate rows: {df.duplicated().sum()}")
```

---

## 3. 数据清洗

### 缺失值处理

```python
# 删除含缺失值的行
df_clean = df.dropna()

# 删除特定列为空的行
df_clean = df.dropna(subset=['重要列'])

# 用均值填充
df['col'] = df['col'].fillna(df['col'].mean())

# 用中位数填充
df['col'] = df['col'].fillna(df['col'].median())

# 用前值填充（时间序列常用）
df['col'] = df['col'].ffill()
```

### 类型转换

```python
# 数值转换（无法转换的变为 NaN）
df['col'] = pd.to_numeric(df['col'], errors='coerce')

# 日期转换
df['date'] = pd.to_datetime(df['date'], format='mixed')
df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')

# 字符串清理
df['col'] = df['col'].str.strip()
df['col'] = df['col'].str.replace(',', '', regex=False)
```

### 去重

```python
# 完全重复
df = df.drop_duplicates()

# 按特定列去重（保留第一条）
df = df.drop_duplicates(subset=['id'], keep='first')
```

### 列名清理

```python
# 去除空格
df.columns = df.columns.str.strip()

# 重命名
df = df.rename(columns={'旧名': '新名', 'old': 'new'})
```

---

## 4. 分组聚合

```python
# 基本分组
result = df.groupby('category')['revenue'].sum().reset_index()

# 多指标聚合
result = df.groupby('category').agg(
    total_revenue=('revenue', 'sum'),
    avg_revenue=('revenue', 'mean'),
    count=('revenue', 'count'),
).reset_index()

# 多维度分组
result = df.groupby(['year', 'category'])['revenue'].sum().reset_index()

# 透视表
pivot = df.pivot_table(
    index='month',
    columns='product',
    values='revenue',
    aggfunc='sum',
    fill_value=0
)
```

---

## 5. 排序与筛选

```python
# 排序
df_sorted = df.sort_values('revenue', ascending=False)
df_sorted = df.sort_values(['year', 'month'])

# Top N
top10 = df.nlargest(10, 'revenue')

# 条件筛选
filtered = df[df['revenue'] > 10000]
filtered = df[(df['year'] == 2024) & (df['category'] == 'A')]
filtered = df[df['category'].isin(['A', 'B', 'C'])]

# 字符串包含
filtered = df[df['name'].str.contains('关键词', na=False)]
```

---

## 6. 计算与派生

```python
# 新增列
df['profit_rate'] = df['profit'] / df['revenue'] * 100

# 同比/环比
df['mom'] = df['revenue'].pct_change() * 100  # 环比
df['yoy'] = df['revenue'].pct_change(12) * 100  # 同比（月度数据）

# 累计
df['cumsum'] = df['revenue'].cumsum()

# 排名
df['rank'] = df['revenue'].rank(ascending=False)

# 分箱
df['level'] = pd.cut(df['score'], bins=[0, 60, 80, 100], labels=['低', '中', '高'])
```

---

## 7. 多表操作

```python
# 内连接
merged = pd.merge(df1, df2, on='id', how='inner')

# 左连接
merged = pd.merge(df1, df2, on='id', how='left')

# 不同列名连接
merged = pd.merge(df1, df2, left_on='user_id', right_on='id')

# 纵向拼接
combined = pd.concat([df1, df2], ignore_index=True)
```

---

## 8. 可视化

### 基本设置

```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Source Han Sans CN', 'WenQuanYi Micro Hei', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
```

### 柱状图

```python
fig, ax = plt.subplots(figsize=(10, 6))
ax.bar(df['category'], df['revenue'])
ax.set_xlabel('类别')
ax.set_ylabel('销售额')
ax.set_title('各类别销售额')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('bar.png', dpi=150, bbox_inches='tight')
plt.close()
```

### 折线图

```python
fig, ax = plt.subplots(figsize=(10, 6))
ax.plot(df['month'], df['revenue'], marker='o', label='销售额')
ax.set_xlabel('月份')
ax.set_ylabel('金额')
ax.set_title('月度销售趋势')
ax.legend()
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('line.png', dpi=150, bbox_inches='tight')
plt.close()
```

### 饼图

```python
fig, ax = plt.subplots(figsize=(8, 8))
ax.pie(df['value'], labels=df['label'], autopct='%1.1f%%', startangle=90)
ax.set_title('占比分布')
plt.tight_layout()
plt.savefig('pie.png', dpi=150, bbox_inches='tight')
plt.close()
```

### 多子图

```python
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

axes[0].bar(df['cat'], df['val1'])
axes[0].set_title('指标一')

axes[1].plot(df['cat'], df['val2'], marker='o')
axes[1].set_title('指标二')

plt.suptitle('综合分析', fontsize=14)
plt.tight_layout()
plt.savefig('subplots.png', dpi=150, bbox_inches='tight')
plt.close()
```

### 热力图（不依赖 seaborn）

```python
import numpy as np

corr = df.select_dtypes(include=[np.number]).corr()
fig, ax = plt.subplots(figsize=(8, 6))
im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1)
fig.colorbar(im)
ax.set_xticks(range(len(corr.columns)))
ax.set_yticks(range(len(corr.columns)))
ax.set_xticklabels(corr.columns, rotation=45, ha='right')
ax.set_yticklabels(corr.columns)
for i in range(len(corr)):
    for j in range(len(corr)):
        ax.text(j, i, f'{corr.iloc[i,j]:.2f}', ha='center', va='center', fontsize=8)
ax.set_title('相关系数矩阵')
plt.tight_layout()
plt.savefig('heatmap.png', dpi=150, bbox_inches='tight')
plt.close()
```

---

## 9. 格式化输出

```python
# 大数字千分位
print(f"总收入: {total:,.2f}")

# 百分比
print(f"增长率: {rate:.1f}%")

# DataFrame 展示控制
pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 20)
pd.set_option('display.width', 200)
pd.set_option('display.float_format', '{:.2f}'.format)
```
