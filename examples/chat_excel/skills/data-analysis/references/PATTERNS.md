# pandas / matplotlib Quick Reference

Consult this file when unsure about specific syntax. For chart creation and file I/O basics, see the main SKILL.md instructions first.

---

## File I/O

```python
import pandas as pd

# CSV with encoding fallback
try:
    df = pd.read_csv('data.csv')
except UnicodeDecodeError:
    df = pd.read_csv('data.csv', encoding='gbk')

# CSV: specify separator, dtypes, date parsing
df = pd.read_csv('data.tsv', sep='\t', dtype={'id': str}, parse_dates=['date'])

# Large file safe preview
df = pd.read_csv('data.csv', nrows=1000)

# Excel: specific sheet, all sheets
df = pd.read_excel('data.xlsx', sheet_name='Sheet2', engine='openpyxl')
dfs = pd.read_excel('data.xlsx', sheet_name=None)  # dict of DataFrames

# JSON / Parquet
df = pd.read_json('data.json')
df = pd.read_parquet('data.parquet')

# Save CSV (Excel-compatible)
df.to_csv('output.csv', index=False, encoding='utf-8-sig')

# Save multi-sheet Excel
with pd.ExcelWriter('report.xlsx', engine='openpyxl') as writer:
    df1.to_excel(writer, sheet_name='Summary', index=False)
    df2.to_excel(writer, sheet_name='Detail', index=False)
```

---

## Data Inspection

```python
df.shape                          # (rows, cols)
df.dtypes                         # column types
df.describe()                     # numeric summary
df.info()                         # memory, non-null counts
df.isnull().sum()                 # missing count per column
df.isnull().mean() * 100          # missing percentage
df.nunique()                      # unique values per column
df.duplicated().sum()             # duplicate row count
```

---

## Cleaning

```python
# Missing values
df_clean = df.dropna(subset=['key_column'])
df['col'] = df['col'].fillna(df['col'].mean())
df['col'] = df['col'].ffill()

# Type conversion
df['col'] = pd.to_numeric(df['col'], errors='coerce')
df['date'] = pd.to_datetime(df['date'], format='mixed')

# String cleaning
df['col'] = df['col'].str.strip()
df.columns = df.columns.str.strip()
df = df.rename(columns={'old': 'new'})

# Deduplication
df = df.drop_duplicates(subset=['id'], keep='first')
```

---

## Grouping and Aggregation

```python
# Single metric
result = df.groupby('category')['revenue'].sum().reset_index()

# Multiple metrics
result = df.groupby('category').agg(
    total=('revenue', 'sum'),
    avg=('revenue', 'mean'),
    count=('revenue', 'count'),
).reset_index()

# Multi-dimension grouping
result = df.groupby(['year', 'category'])['revenue'].sum().reset_index()

# Pivot table
pivot = df.pivot_table(index='month', columns='product', values='revenue',
                       aggfunc='sum', fill_value=0)
```

---

## Filtering and Sorting

```python
# Filter
filtered = df[df['revenue'] > 10000]
filtered = df[(df['year'] == 2024) & (df['category'] == 'A')]
filtered = df[df['category'].isin(['A', 'B', 'C'])]
filtered = df[df['name'].str.contains('keyword', na=False)]

# Sort and rank
df_sorted = df.sort_values('revenue', ascending=False)
top10 = df.nlargest(10, 'revenue')
```

---

## Derived Columns

```python
df['profit_rate'] = df['profit'] / df['revenue'] * 100
df['mom'] = df['revenue'].pct_change() * 100          # month-over-month
df['yoy'] = df['revenue'].pct_change(12) * 100        # year-over-year
df['cumsum'] = df['revenue'].cumsum()
df['rank'] = df['revenue'].rank(ascending=False)
df['level'] = pd.cut(df['score'], bins=[0, 60, 80, 100], labels=['Low', 'Mid', 'High'])
```

---

## Multi-Table Operations

```python
merged = pd.merge(df1, df2, on='id', how='left')
merged = pd.merge(df1, df2, left_on='user_id', right_on='id')
combined = pd.concat([df1, df2], ignore_index=True)
```

---

## Visualization Patterns

### Multi-subplot Layout

```python
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
axes[0].bar(df['cat'], df['val1'])
axes[0].set_title('Metric A')
axes[1].plot(df['cat'], df['val2'], marker='o')
axes[1].set_title('Metric B')
plt.suptitle('Combined Analysis', fontsize=14)
plt.tight_layout()
plt.savefig('/mnt/workspace/subplots.png', dpi=150, bbox_inches='tight')
plt.close()
```

### Correlation Heatmap (no seaborn)

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
ax.set_title('Correlation Matrix')
plt.tight_layout()
plt.savefig('/mnt/workspace/heatmap.png', dpi=150, bbox_inches='tight')
plt.close()
```

### Stacked Bar Chart

```python
pivot = df.pivot_table(index='month', columns='category', values='revenue', aggfunc='sum', fill_value=0)
pivot.plot(kind='bar', stacked=True, figsize=(10, 6))
plt.title('Revenue by Category (Stacked)')
plt.xlabel('Month')
plt.ylabel('Revenue')
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig('/mnt/workspace/stacked_bar.png', dpi=150, bbox_inches='tight')
plt.close()
```

---

## Output Formatting

```python
# Display control
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.float_format', '{:.2f}'.format)

# Formatted printing
print(f"Total: {total:,.2f}")       # 1,234,567.89
print(f"Growth: {rate:.1f}%")       # 15.3%
```
