import random
import io
import json
from flask import Flask, render_template, request, jsonify, send_file
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

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
# PDF 生成
# ========================

def create_math_pdf_bytes(pages_data, start_page=1):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    margin_top = 2 * cm
    col_1_x = 2.5 * cm
    col_2_x = 11.5 * cm
    start_y = height - margin_top
    line_height = 2.5 * cm

    for page_data in pages_data:
        page_num = page_data["page_num"] + start_page - 1
        problems = page_data["problems"]

        c.setFont("Helvetica-Bold", 12)
        c.drawString(width / 2 - 2 * cm, height - 1 * cm, f"Page {page_num}")
        c.setFont("Helvetica", 14)

        current_y = start_y
        for row in range(10):
            idx_left = row * 2
            idx_right = row * 2 + 1

            if idx_left < len(problems):
                c.drawString(col_1_x - 1 * cm, current_y, f"{idx_left + 1}.")
                c.drawString(col_1_x, current_y, problems[idx_left]["text"])

            if idx_right < len(problems):
                c.drawString(col_2_x - 1 * cm, current_y, f"{idx_right + 1}.")
                c.drawString(col_2_x, current_y, problems[idx_right]["text"])

            current_y -= line_height

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
