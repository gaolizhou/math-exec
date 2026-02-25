import random
import argparse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

def get_random_3_digit_str():
    """
    生成总位数为3位的小数数字字符串
    包含两种情况：
    1. X.XX (1位整数 + 2位小数)
    2. XX.X (2位整数 + 1位小数)
    """
    if random.choice([True, False]):
        # 模式：X.XX (范围 0.01 ~ 9.99，但为了像题目，我们用1.00~9.99或者包含0)
        # 逻辑：生成 100-999 的整数，除以 100
        val = random.randint(100, 999) / 100.0
        return f"{val:.2f}"
    else:
        # 模式：XX.X (范围 10.0 ~ 99.9)
        # 逻辑：生成 100-999 的整数，除以 10
        val = random.randint(100, 999) / 10.0
        return f"{val:.1f}"

def get_random_2_digit_str():
    """
    生成总位数为2位的小数数字字符串
    模式：X.X (1位整数 + 1位小数)
    """
    # 逻辑：生成 10-99 的整数，除以 10
    # 范围：1.0 ~ 9.9
    val = random.randint(10, 99) / 10.0
    return f"{val:.1f}"

def get_add_sub_problem():
    """
    生成加减法题目
    要求：参与运算的数字总位数为3位
    """
    a_str = get_random_3_digit_str()
    b_str = get_random_3_digit_str()
    
    # 转换为浮点数用于比较大小
    a_val = float(a_str)
    b_val = float(b_str)
    
    operator = random.choice(['+', '-'])
    
    # 如果是减法，确保大减小
    if operator == '-':
        if a_val < b_val:
            a_str, b_str = b_str, a_str
            
    return f"{a_str} {operator} {b_str} ="

def get_mul_problem():
    """
    生成乘法题目
    要求：参与运算的数字总位数为2位 (例如 3.5 x 2.1)
    """
    a_str = get_random_2_digit_str()
    b_str = get_random_2_digit_str()
    
    return f"{a_str} × {b_str} ="

def create_math_pdf(filename, num_pages, start_page=1):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    
    # 字体设置
    c.setFont("Helvetica", 14) # 稍微调大一点字体，方便看清小数点
    
    # 布局配置
    margin_top = 2 * cm
    col_1_x = 2.5 * cm       # 第一列起始X坐标 (稍微右移一点)
    col_2_x = 11.5 * cm      # 第二列起始X坐标
    start_y = height - margin_top
    line_height = 2.5 * cm   # 留出竖式计算空间
    
    print(f"正在生成 {filename}, 共 {num_pages} 页, 起始页码 {start_page}...")

    for page in range(start_page, start_page + num_pages):
        problems = []
        
        # 16题加减法
        for _ in range(16):
            problems.append(get_add_sub_problem())
            
        # 4题乘法
        for _ in range(4):
            problems.append(get_mul_problem())
            
        # 绘制页面标题
        c.setFont("Helvetica-Bold", 12)
        c.drawString(width/2 - 2*cm, height - 1*cm, f"Page {page}")
        c.setFont("Helvetica", 14)
        
        current_y = start_y
        
        # 绘制20道题 (10行 x 2列)
        for row in range(10):
            idx_left = row * 2
            idx_right = row * 2 + 1
            
            # 左列
            if idx_left < len(problems):
                c.drawString(col_1_x - 1*cm, current_y, f"{idx_left + 1}.")
                c.drawString(col_1_x, current_y, problems[idx_left])
            
            # 右列
            if idx_right < len(problems):
                c.drawString(col_2_x - 1*cm, current_y, f"{idx_right + 1}.")
                c.drawString(col_2_x, current_y, problems[idx_right])
                
            current_y -= line_height

        c.showPage()
        
    c.save()
    print("完成！PDF已生成。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成小数四则运算练习题PDF")
    parser.add_argument("-n", "--pages", type=int, default=5, help="总页数 (默认: 5)")
    parser.add_argument("-s", "--start", type=int, default=1, help="起始页码 (默认: 1)")
    parser.add_argument("-o", "--output", type=str, default="math_exercises_v2.pdf", help="输出文件名 (默认: math_exercises_v2.pdf)")
    args = parser.parse_args()

    create_math_pdf(args.output, args.pages, args.start)
