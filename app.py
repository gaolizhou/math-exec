import random
import io
import json
import math
from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm, mm
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.lib import colors

app = Flask(__name__)

# ========================
# 题目生成逻辑（保留原有逻辑）
# ========================

def get_random_3_digit_str():
    if random.choice([True, False]):
        val = random.randint(100, 999) / 100.0
        return f"{val:.2f}"
    else:
        val = random.randint(100, 999) / 10.0
        return f"{val:.1f}"

def get_random_2_digit_str():
    val = random.randint(10, 99) / 10.0
    return f"{val:.1f}"

def get_add_sub_problem():
    a_str = get_random_3_digit_str()
    b_str = get_random_3_digit_str()
    a_val = float(a_str)
    b_val = float(b_str)
    operator = random.choice(['+', '-'])
    if operator == '-':
        if a_val < b_val:
            a_str, b_str = b_str, a_str
    return {"text": f"{a_str} {operator} {b_str} =", "type": "add_sub"}

def get_mul_problem():
    a_str = get_random_2_digit_str()
    b_str = get_random_2_digit_str()
    return {"text": f"{a_str} × {b_str} =", "type": "mul"}

def generate_problems(add_sub_count=16, mul_count=4):
    problems = []
    for _ in range(add_sub_count):
        problems.append(get_add_sub_problem())
    for _ in range(mul_count):
        problems.append(get_mul_problem())
    return problems

def generate_page_data(num_pages, add_sub_count=16, mul_count=4):
    pages = []
    for i in range(num_pages):
        problems = generate_problems(add_sub_count, mul_count)
        pages.append({
            "page_num": i + 1,
            "problems": problems
        })
    return pages

# ========================
# PDF 生成（美化版）
# ========================

# 主题色
PDF_PRIMARY = HexColor('#6366f1')
PDF_PRIMARY_DARK = HexColor('#4f46e5')
PDF_PRIMARY_LIGHT = HexColor('#c7d2fe')
PDF_SUCCESS = HexColor('#10b981')
PDF_WARNING = HexColor('#f59e0b')
PDF_WARNING_LIGHT = HexColor('#fef3c7')
PDF_PURPLE_BG = HexColor('#eef2ff')
PDF_ORANGE_BG = HexColor('#fff7ed')
PDF_GRAY = HexColor('#64748b')
PDF_GRAY_LIGHT = HexColor('#f1f5f9')
PDF_GRAY_BORDER = HexColor('#e2e8f0')
PDF_TEXT = HexColor('#1e293b')
PDF_TEXT_SEC = HexColor('#475569')


def draw_rounded_rect(c, x, y, w, h, r, fill_color=None, stroke_color=None, stroke_width=0.5):
    """绘制圆角矩形"""
    p = c.beginPath()
    p.moveTo(x + r, y)
    p.lineTo(x + w - r, y)
    p.arcTo(x + w - r, y, x + w, y + r, r)
    p.lineTo(x + w, y + h - r)
    p.arcTo(x + w, y + h - r, x + w - r, y + h, r)
    p.lineTo(x + r, y + h)
    p.arcTo(x + r, y + h, x, y + h - r, r)
    p.lineTo(x, y + r)
    p.arcTo(x, y + r, x + r, y, r)
    p.close()
    if fill_color:
        c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(stroke_width)
    if fill_color and stroke_color:
        c.drawPath(p, fill=1, stroke=1)
    elif fill_color:
        c.drawPath(p, fill=1, stroke=0)
    elif stroke_color:
        c.drawPath(p, fill=0, stroke=1)


def draw_circle(c, cx, cy, r, fill_color):
    """绘制填充圆"""
    c.setFillColor(fill_color)
    c.circle(cx, cy, r, fill=1, stroke=0)


def draw_header_bar(c, width, height, page_num):
    """绘制页面顶部装饰标题栏"""
    bar_height = 42
    bar_y = height - bar_height - 12

    # 主标题栏背景
    draw_rounded_rect(c, 20, bar_y, width - 40, bar_height, 8, fill_color=PDF_PRIMARY)

    # 左侧装饰小圆点
    for i, alpha in enumerate([0.3, 0.2, 0.15]):
        dot_color = Color(1, 1, 1, alpha)
        c.setFillColor(dot_color)
        c.circle(45 + i * 18, bar_y + bar_height / 2, 4, fill=1, stroke=0)

    # 标题文字
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(100, bar_y + 14, "Math Practice Sheet")

    # 副标题 emoji 用文字替代
    c.setFont("Helvetica", 8.5)
    c.setFillColor(Color(1, 1, 1, 0.8))
    c.drawString(100, bar_y + 3, "Decimal Arithmetic Exercises")

    # 右侧页码标签
    page_label = f"Page {page_num}"
    label_w = 70
    label_x = width - 20 - label_w - 10
    label_y = bar_y + (bar_height - 22) / 2
    # 白色半透明背景
    c.setFillColor(Color(1, 1, 1, 0.2))
    draw_rounded_rect(c, label_x, label_y, label_w, 22, 11, fill_color=Color(1, 1, 1, 0.2))
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 10)
    text_w = c.stringWidth(page_label, "Helvetica-Bold", 10)
    c.drawString(label_x + (label_w - text_w) / 2, label_y + 6.5, page_label)


def draw_info_bar(c, width, height, add_sub_count, mul_count):
    """绘制标题栏下方的信息条"""
    info_y = height - 72
    bar_w = width - 50

    # 浅灰背景条
    draw_rounded_rect(c, 25, info_y, bar_w, 20, 5, fill_color=PDF_GRAY_LIGHT)

    c.setFont("Helvetica", 7.5)
    c.setFillColor(PDF_GRAY)
    total = add_sub_count + mul_count
    info_text = f"Total: {total} problems per page  |  Addition/Subtraction: {add_sub_count}  |  Multiplication: {mul_count}"
    c.drawString(35, info_y + 6, info_text)

    # 右侧小标签
    tag_x = width - 115
    # 加减法标签
    draw_rounded_rect(c, tag_x, info_y + 3, 36, 14, 7, fill_color=PDF_PRIMARY)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(tag_x + 5, info_y + 7, "+  -")

    # 乘法标签
    draw_rounded_rect(c, tag_x + 42, info_y + 3, 36, 14, 7, fill_color=PDF_WARNING)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(tag_x + 52, info_y + 7, "x")


def draw_problem_item(c, x, y, idx, problem_text, problem_type):
    """绘制单个题目（保留宽松间距用于草稿）"""
    # 圆形题号
    circle_r = 10
    circle_cx = x
    circle_cy = y
    num_color = PDF_PRIMARY if problem_type != 'mul' else PDF_WARNING
    draw_circle(c, circle_cx, circle_cy, circle_r, num_color)

    # 题号文字
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8.5)
    num_str = str(idx)
    num_w = c.stringWidth(num_str, "Helvetica-Bold", 8.5)
    c.drawString(circle_cx - num_w / 2, circle_cy - 3, num_str)

    # 题目文本
    c.setFillColor(PDF_TEXT)
    c.setFont("Helvetica", 14)
    c.drawString(x + 18, y - 4, problem_text)


def draw_footer(c, width, page_num, total_pages):
    """绘制页脚"""
    footer_y = 18

    # 分隔线
    c.setStrokeColor(PDF_GRAY_BORDER)
    c.setLineWidth(0.5)
    c.line(25, footer_y + 16, width - 25, footer_y + 16)

    c.setFont("Helvetica", 7)
    c.setFillColor(PDF_GRAY)
    c.drawString(25, footer_y + 3, "Math Practice Sheet Generator")

    # 中间装饰
    c.setFillColor(PDF_PRIMARY)
    mid_x = width / 2
    for dx in [-8, 0, 8]:
        c.circle(mid_x + dx, footer_y + 8, 1.5, fill=1, stroke=0)

    # 右侧页码
    c.setFillColor(PDF_GRAY)
    c.setFont("Helvetica", 7)
    page_info = f"{page_num} / {total_pages}"
    pw = c.stringWidth(page_info, "Helvetica", 7)
    c.drawString(width - 25 - pw, footer_y + 3, page_info)


def create_math_pdf_bytes(pages_data, start_page=1):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    total_pages = len(pages_data)

    # 沿用原始布局参数 — 充足的草稿空间
    margin_top = 2 * cm
    col_1_x = 2.5 * cm       # 第一列起始X（题号圆心位置）
    col_2_x = 11.5 * cm      # 第二列起始X
    line_height = 2.5 * cm   # 每题间距，留出竖式计算空间

    for page_data in pages_data:
        page_num = page_data["page_num"] + start_page - 1
        problems = page_data["problems"]

        # 页面背景 — 纯白
        c.setFillColor(white)
        c.rect(0, 0, width, height, fill=1, stroke=0)

        # 细边框装饰
        draw_rounded_rect(c, 14, 10, width - 28, height - 20, 10,
                          stroke_color=PDF_GRAY_BORDER, stroke_width=0.3)

        # 顶部标题栏
        draw_header_bar(c, width, height, page_num)

        # 信息栏
        add_sub_count = sum(1 for p in problems if p.get("type") != "mul")
        mul_count = sum(1 for p in problems if p.get("type") == "mul")
        draw_info_bar(c, width, height, add_sub_count, mul_count)

        # 题目起始 Y 坐标（标题栏 + 信息栏之后）
        start_y = height - margin_top - 42 - 20 - 8  # header(42) + info(20) + gap

        current_y = start_y

        # 两列排列 (10行 × 2列 = 最多20题)
        num_rows = math.ceil(len(problems) / 2)

        for row in range(num_rows):
            idx_left = row * 2
            idx_right = row * 2 + 1

            # 每行之间画淡色分隔虚线（帮助对齐草稿区域）
            if row > 0:
                sep_y = current_y + line_height * 0.65
                c.setStrokeColor(HexColor('#eff1f5'))
                c.setLineWidth(0.3)
                c.setDash(2, 4)
                c.line(col_1_x - 12, sep_y, width - 1.5 * cm, sep_y)
                c.setDash()

            # 左列
            if idx_left < len(problems):
                prob = problems[idx_left]
                draw_problem_item(
                    c, col_1_x, current_y,
                    idx_left + 1, prob["text"], prob.get("type", "add_sub")
                )

            # 右列
            if idx_right < len(problems):
                prob = problems[idx_right]
                draw_problem_item(
                    c, col_2_x, current_y,
                    idx_right + 1, prob["text"], prob.get("type", "add_sub")
                )

            current_y -= line_height

        # 页脚
        draw_footer(c, width, page_num, start_page + total_pages - 1)

        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# ========================
# Web 路由
# ========================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/preview', methods=['POST'])
def preview():
    data = request.json or {}
    num_pages = min(max(int(data.get('pages', 1)), 1), 50)
    add_sub = min(max(int(data.get('add_sub_count', 16)), 0), 20)
    mul = min(max(int(data.get('mul_count', 4)), 0), 20)

    if add_sub + mul > 20:
        mul = 20 - add_sub

    pages = generate_page_data(num_pages, add_sub, mul)
    return jsonify({"pages": pages})

@app.route('/api/download', methods=['POST'])
def download():
    data = request.json or {}
    num_pages = min(max(int(data.get('pages', 5)), 1), 50)
    start_page = max(int(data.get('start_page', 1)), 1)
    add_sub = min(max(int(data.get('add_sub_count', 16)), 0), 20)
    mul = min(max(int(data.get('mul_count', 4)), 0), 20)
    filename = data.get('filename', 'math_exercises.pdf')

    if add_sub + mul > 20:
        mul = 20 - add_sub

    pages = generate_page_data(num_pages, add_sub, mul)
    pdf_buffer = create_math_pdf_bytes(pages, start_page)

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/regenerate', methods=['POST'])
def regenerate_single():
    data = request.json or {}
    add_sub = min(max(int(data.get('add_sub_count', 16)), 0), 20)
    mul = min(max(int(data.get('mul_count', 4)), 0), 20)
    problems = generate_problems(add_sub, mul)
    return jsonify({"problems": problems})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)