# math-exec

小数四则运算练习题 PDF 生成器，自动生成适合小学生的数学练习卷。

## 题型

每页 20 道题（10 行 × 2 列）：

- **加减法** 16 题 — 3 位有效数字的小数（如 `3.57 + 42.1 =`），减法保证结果非负
- **乘法** 4 题 — 2 位有效数字的小数（如 `3.5 × 2.1 =`）

每行留有竖式计算空间。

## 安装

```bash
pip install reportlab
```

## 使用

```bash
python math_sheet_gen.py [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-n`, `--pages` | 总页数 | 5 |
| `-s`, `--start` | 起始页码 | 1 |
| `-o`, `--output` | 输出文件名 | `math_exercises_v2.pdf` |

### 示例

```bash
# 默认生成 5 页，从第 1 页开始
python math_sheet_gen.py

# 生成 10 页，从第 6 页开始
python math_sheet_gen.py -n 10 -s 6

# 指定输出文件名
python math_sheet_gen.py -o homework.pdf
```
