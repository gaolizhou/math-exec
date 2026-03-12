# 🧮 Math Practice Sheet Generator

小数四则运算练习题生成器 — 支持 Web 在线操作和命令行两种使用方式。

自动生成适合小学生的数学练习卷，包含加减法和乘法题目，PDF 排版美观，每题留有充足的草稿空间。

## ✨ 功能特性

- **在线预览** — 在网页上实时预览生成的题目，支持翻页浏览
- **参数配置** — 滑块调节页数、加减法/乘法题目数量
- **PDF 下载** — 一键生成并下载美观排版的 PDF 练习卷
- **换一批** — 对当前页重新随机生成题目
- **美化排版** — 彩色圆形题号、渐变标题栏、充足草稿空间

## 📋 题型说明

每页最多 20 道题（10 行 × 2 列）：

| 题型 | 默认数量 | 说明 |
|------|---------|------|
| **加减法** | 16 题 | 3 位有效数字的小数（如 `3.57 + 42.1 =`），减法保证结果非负 |
| **乘法** | 4 题 | 2 位有效数字的小数（如 `3.5 × 2.1 =`） |

每行留有 2.5cm 的竖式计算空间。

---

## 🚀 部署指南

### 环境要求

- **Python** 3.8+
- **pip** 包管理器

### 方式一：Web 应用部署（推荐）

#### 1. 克隆项目

```bash
git clone <仓库地址>
cd math-exec
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

> 依赖包：`flask>=2.3.0`、`reportlab>=4.0`

#### 3. 启动服务

```bash
python app.py
```

服务将在 `http://0.0.0.0:5000` 启动。

#### 4. 访问页面

打开浏览器访问：

```
http://localhost:5000
```

即可在网页上配置参数、预览题目、下载 PDF。

#### 生产环境部署（可选）

推荐使用 **Gunicorn** 部署：

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

或使用 **Docker**：

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

```bash
docker build -t math-practice .
docker run -p 5000:5000 math-practice
```

### 方式二：命令行使用

```bash
python math_sheet_gen.py [选项]
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-n`, `--pages` | 总页数 | 5 |
| `-s`, `--start` | 起始页码 | 1 |
| `-o`, `--output` | 输出文件名 | `math_exercises_v2.pdf` |

#### 示例

```bash
# 默认生成 5 页
python math_sheet_gen.py

# 生成 10 页，从第 6 页开始
python math_sheet_gen.py -n 10 -s 6

# 指定输出文件名
python math_sheet_gen.py -o homework.pdf
```

---

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 前端页面 |
| `POST` | `/api/preview` | 生成题目预览（JSON） |
| `POST` | `/api/download` | 生成并下载 PDF |
| `POST` | `/api/regenerate` | 重新生成单页题目 |

### 请求参数示例

```json
{
  "pages": 3,
  "add_sub_count": 16,
  "mul_count": 4,
  "start_page": 1,
  "filename": "math_practice.pdf"
}
```

---

## 📁 项目结构

```
├── app.py              # Flask Web 后端
├── templates/
│   └── index.html      # 前端页面
├── math_sheet_gen.py   # 命令行版本
├── requirements.txt    # Python 依赖
└── README.md           # 本文件
```
