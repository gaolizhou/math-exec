import io
import json
import math
import os
import random
import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from reportlab.lib import colors
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
SAVED_PRESETS_FILE = BASE_DIR / "saved_presets.json"
MAX_PAGES = 50
MAX_PROBLEMS_PER_OPERATION = 60
MAX_GENERATION_ATTEMPTS = 500
MAX_SAVED_PRESETS = 50
HEADER_OFFSET_PT = 128
FOOTER_SAFE_PT = 52
VALID_REWRITE_MODES = {"any", "with", "without"}

OPERATIONS = {
    "add": {"label": "加法", "symbol": "+", "badge": "+"},
    "sub": {"label": "减法", "symbol": "-", "badge": "−"},
    "mul": {"label": "乘法", "symbol": "×", "badge": "×"},
}

DEFAULT_CONFIG = {
    "worksheet_title": "小学生计算练习单",
    "pages": 5,
    "start_page": 1,
    "filename": "math_exercises.pdf",
    "counts": {
        "add": 8,
        "sub": 8,
        "mul": 4,
    },
    "rules": {
        "integer_digits_min": 1,
        "integer_digits_max": 2,
        "decimal_digits_min": 1,
        "decimal_digits_max": 2,
        "result_min": Decimal("0"),
        "result_max": Decimal("200"),
        "non_negative_subtraction": True,
        "addition_carry_mode": "any",
        "subtraction_borrow_mode": "any",
    },
    "layout": {
        "columns": 2,
        "line_height_mm": 22,
        "font_size": 14,
    },
    "shuffle_problems": True,
}

PRESETS = {
    "default": {
        "label": "默认混合练习",
        "config": {
            "worksheet_title": "小学生计算练习单",
            "pages": 5,
            "start_page": 1,
            "filename": "math_exercises.pdf",
            "counts": {"add": 8, "sub": 8, "mul": 4},
            "rules": {
                "integer_digits_min": 1,
                "integer_digits_max": 2,
                "decimal_digits_min": 1,
                "decimal_digits_max": 2,
                "result_min": "0",
                "result_max": "200",
                "non_negative_subtraction": True,
                "addition_carry_mode": "any",
                "subtraction_borrow_mode": "any",
            },
            "layout": {"columns": 2, "line_height_mm": 22, "font_size": 14},
            "shuffle_problems": True,
        },
    },
    "integer-fast": {
        "label": "整数口算",
        "config": {
            "worksheet_title": "整数口算练习单",
            "pages": 4,
            "start_page": 1,
            "filename": "integer_practice.pdf",
            "counts": {"add": 10, "sub": 10, "mul": 0},
            "rules": {
                "integer_digits_min": 1,
                "integer_digits_max": 2,
                "decimal_digits_min": 0,
                "decimal_digits_max": 0,
                "result_min": "0",
                "result_max": "100",
                "non_negative_subtraction": True,
                "addition_carry_mode": "any",
                "subtraction_borrow_mode": "any",
            },
            "layout": {"columns": 2, "line_height_mm": 18, "font_size": 15},
            "shuffle_problems": True,
        },
    },
    "decimal-focus": {
        "label": "一位/两位小数",
        "config": {
            "worksheet_title": "小数计算专项练习",
            "pages": 5,
            "start_page": 1,
            "filename": "decimal_practice.pdf",
            "counts": {"add": 12, "sub": 8, "mul": 0},
            "rules": {
                "integer_digits_min": 1,
                "integer_digits_max": 1,
                "decimal_digits_min": 1,
                "decimal_digits_max": 2,
                "result_min": "0",
                "result_max": "30",
                "non_negative_subtraction": True,
                "addition_carry_mode": "any",
                "subtraction_borrow_mode": "any",
            },
            "layout": {"columns": 2, "line_height_mm": 22, "font_size": 14},
            "shuffle_problems": True,
        },
    },
    "mixed-challenge": {
        "label": "综合挑战",
        "config": {
            "worksheet_title": "综合挑战练习单",
            "pages": 6,
            "start_page": 1,
            "filename": "mixed_challenge.pdf",
            "counts": {"add": 6, "sub": 6, "mul": 6},
            "rules": {
                "integer_digits_min": 2,
                "integer_digits_max": 3,
                "decimal_digits_min": 1,
                "decimal_digits_max": 2,
                "result_min": "0",
                "result_max": "600",
                "non_negative_subtraction": True,
                "addition_carry_mode": "any",
                "subtraction_borrow_mode": "any",
            },
            "layout": {"columns": 3, "line_height_mm": 18, "font_size": 12},
            "shuffle_problems": True,
        },
    },
}

# ========================
# PDF 视觉配置
# ========================

PDF_PRIMARY = HexColor("#6366f1")
PDF_PRIMARY_DARK = HexColor("#4f46e5")
PDF_PRIMARY_LIGHT = HexColor("#c7d2fe")
PDF_SUCCESS = HexColor("#10b981")
PDF_WARNING = HexColor("#f59e0b")
PDF_GRAY = HexColor("#64748b")
PDF_GRAY_LIGHT = HexColor("#f1f5f9")
PDF_GRAY_BORDER = HexColor("#e2e8f0")
PDF_TEXT = HexColor("#1e293b")
PDF_FONT = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
PDF_CJK_FONT = "STSong-Light"
PDF_CJK_FONT_EMBEDDED = False


def register_cjk_font():
    global PDF_CJK_FONT, PDF_CJK_FONT_EMBEDDED
    embedded_candidates = [
        ("STHeitiLight", "/System/Library/Fonts/STHeiti Light.ttc", 0),
        ("STHeitiMedium", "/System/Library/Fonts/STHeiti Medium.ttc", 0),
    ]
    for font_name, font_path, subfont_index in embedded_candidates:
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path, subfontIndex=subfont_index))
            PDF_CJK_FONT = font_name
            PDF_CJK_FONT_EMBEDDED = True
            return
        except Exception:
            continue

    pdfmetrics.registerFont(UnicodeCIDFont(PDF_CJK_FONT))
    PDF_CJK_FONT_EMBEDDED = False


register_cjk_font()


class ConfigError(ValueError):
    """配置错误。"""


def decimal_to_plain_str(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def parse_int(value, default, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def parse_decimal_value(value, default):
    if value in (None, ""):
        value = default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ConfigError("结果范围必须是合法数字。") from exc


def parse_rewrite_mode(value, default="any"):
    candidate = str(value or default).strip().lower()
    return candidate if candidate in VALID_REWRITE_MODES else default


def sanitize_filename(raw_name):
    candidate = str(raw_name or DEFAULT_CONFIG["filename"]).strip()
    candidate = re.sub(r'[\\/:*?"<>|]+', "_", candidate)
    candidate = candidate or DEFAULT_CONFIG["filename"]
    if not candidate.lower().endswith(".pdf"):
        candidate = f"{candidate}.pdf"
    return candidate[:120]


def sanitize_title(raw_title):
    title = str(raw_title or DEFAULT_CONFIG["worksheet_title"]).strip()
    return title[:36] or DEFAULT_CONFIG["worksheet_title"]


def sanitize_preset_label(raw_label):
    label = re.sub(r"\s+", " ", str(raw_label or "").strip())
    return label[:30]


def slugify_preset_name(raw_label):
    label = sanitize_preset_label(raw_label).lower()
    label = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", label)
    label = re.sub(r"-{2,}", "-", label).strip("-")
    if label:
        return label
    return f"preset-{int(datetime.now(timezone.utc).timestamp())}"


def build_layout_metrics(layout):
    line_height_pt = layout["line_height_mm"] * mm
    usable_height = A4[1] - HEADER_OFFSET_PT - FOOTER_SAFE_PT
    rows_per_page = max(1, int(usable_height // line_height_pt))
    capacity_per_page = rows_per_page * layout["columns"]
    return {
        "line_height_pt": line_height_pt,
        "rows_per_page": rows_per_page,
        "capacity_per_page": capacity_per_page,
    }


def read_saved_preset_store():
    if not SAVED_PRESETS_FILE.exists():
        return {}
    try:
        data = json.loads(SAVED_PRESETS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def write_saved_preset_store(store):
    SAVED_PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = SAVED_PRESETS_FILE.with_suffix(".tmp")
    tmp_file.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_file.replace(SAVED_PRESETS_FILE)


def normalize_preset_record(preset_key, record, source):
    config, metrics = normalize_config(record.get("config") or {})
    return {
        "preset_key": preset_key,
        "label": sanitize_preset_label(record.get("label") or preset_key),
        "config": serialize_config(config, metrics),
        "source": source,
        "updated_at": record.get("updated_at"),
    }


def get_builtin_presets():
    presets = {}
    for preset_key, record in PRESETS.items():
        presets[preset_key] = normalize_preset_record(preset_key, record, "built_in")
    return presets


def get_saved_presets():
    normalized = {}
    for preset_key, record in read_saved_preset_store().items():
        try:
            normalized[preset_key] = normalize_preset_record(preset_key, record, "saved")
        except ConfigError:
            continue
    return dict(
        sorted(
            normalized.items(),
            key=lambda item: item[1].get("updated_at") or "",
            reverse=True,
        )
    )


def mode_text(mode, noun):
    if mode == "with":
        return f"必须有{noun}"
    if mode == "without":
        return f"不允许{noun}"
    return "不限"


def normalize_config(payload):
    data = payload or {}
    config = deepcopy(DEFAULT_CONFIG)

    config["worksheet_title"] = sanitize_title(data.get("worksheet_title"))
    config["pages"] = parse_int(data.get("pages"), config["pages"], 1, MAX_PAGES)
    config["start_page"] = parse_int(data.get("start_page"), config["start_page"], 1, 9999)
    config["filename"] = sanitize_filename(data.get("filename"))
    config["shuffle_problems"] = parse_bool(data.get("shuffle_problems"), True)

    counts = config["counts"]
    counts["add"] = parse_int(data.get("add_count"), counts["add"], 0, MAX_PROBLEMS_PER_OPERATION)
    counts["sub"] = parse_int(data.get("sub_count"), counts["sub"], 0, MAX_PROBLEMS_PER_OPERATION)
    counts["mul"] = parse_int(data.get("mul_count"), counts["mul"], 0, MAX_PROBLEMS_PER_OPERATION)

    if sum(counts.values()) <= 0:
        raise ConfigError("至少需要生成 1 道题。")

    rules = config["rules"]
    rules["integer_digits_min"] = parse_int(data.get("integer_digits_min"), rules["integer_digits_min"], 0, 4)
    rules["integer_digits_max"] = parse_int(data.get("integer_digits_max"), rules["integer_digits_max"], 0, 4)
    rules["decimal_digits_min"] = parse_int(data.get("decimal_digits_min"), rules["decimal_digits_min"], 0, 3)
    rules["decimal_digits_max"] = parse_int(data.get("decimal_digits_max"), rules["decimal_digits_max"], 0, 3)

    if rules["integer_digits_min"] > rules["integer_digits_max"]:
        rules["integer_digits_min"], rules["integer_digits_max"] = (
            rules["integer_digits_max"],
            rules["integer_digits_min"],
        )
    if rules["decimal_digits_min"] > rules["decimal_digits_max"]:
        rules["decimal_digits_min"], rules["decimal_digits_max"] = (
            rules["decimal_digits_max"],
            rules["decimal_digits_min"],
        )

    if rules["integer_digits_max"] == 0 and rules["decimal_digits_max"] == 0:
        raise ConfigError("整数位数和小数位数不能同时为 0。")

    rules["result_min"] = parse_decimal_value(data.get("result_min"), DEFAULT_CONFIG["rules"]["result_min"])
    rules["result_max"] = parse_decimal_value(data.get("result_max"), DEFAULT_CONFIG["rules"]["result_max"])
    if rules["result_min"] > rules["result_max"]:
        rules["result_min"], rules["result_max"] = rules["result_max"], rules["result_min"]

    rules["non_negative_subtraction"] = parse_bool(data.get("non_negative_subtraction"), True)
    rules["addition_carry_mode"] = parse_rewrite_mode(
        data.get("addition_carry_mode"),
        rules["addition_carry_mode"],
    )
    rules["subtraction_borrow_mode"] = parse_rewrite_mode(
        data.get("subtraction_borrow_mode"),
        rules["subtraction_borrow_mode"],
    )

    layout = config["layout"]
    layout["columns"] = parse_int(data.get("columns"), layout["columns"], 1, 3)
    layout["line_height_mm"] = parse_int(data.get("line_height_mm"), layout["line_height_mm"], 12, 36)
    layout["font_size"] = parse_int(data.get("font_size"), layout["font_size"], 11, 20)

    metrics = build_layout_metrics(layout)
    total_per_page = sum(counts.values())
    if total_per_page > metrics["capacity_per_page"]:
        raise ConfigError(
            f"当前版式每页最多容纳 {metrics['capacity_per_page']} 题，请减少题量或调小行距。"
        )

    return config, metrics


def quantizer(decimal_digits):
    return Decimal("1") if decimal_digits == 0 else Decimal("1").scaleb(-decimal_digits)


def format_decimal(value: Decimal, decimal_digits: int) -> str:
    normalized = value.quantize(quantizer(decimal_digits))
    if decimal_digits == 0:
        return str(int(normalized))
    return f"{normalized:.{decimal_digits}f}"


def build_number(rules):
    integer_digits = random.randint(rules["integer_digits_min"], rules["integer_digits_max"])
    decimal_digits = random.randint(rules["decimal_digits_min"], rules["decimal_digits_max"])

    if integer_digits == 0 and decimal_digits == 0:
        decimal_digits = 1

    if integer_digits > 0:
        integer_part = random.randint(10 ** (integer_digits - 1), 10 ** integer_digits - 1)
    else:
        integer_part = 0

    if decimal_digits > 0:
        lower_bound = 1 if integer_digits == 0 else 0
        fractional_part = random.randint(lower_bound, 10 ** decimal_digits - 1)
    else:
        fractional_part = 0

    value = Decimal(integer_part)
    if decimal_digits > 0:
        value += Decimal(fractional_part) * quantizer(decimal_digits)

    return {
        "value": value,
        "text": format_decimal(value, decimal_digits),
        "integer_digits": integer_digits,
        "decimal_digits": decimal_digits,
    }


def scaled_integer(number_meta, scale):
    factor = Decimal(10) ** scale
    return int((number_meta["value"] * factor).to_integral_value())


def has_addition_carry(left_meta, right_meta):
    scale = max(left_meta["decimal_digits"], right_meta["decimal_digits"])
    left_int = scaled_integer(left_meta, scale)
    right_int = scaled_integer(right_meta, scale)
    carry = 0

    while left_int > 0 or right_int > 0 or carry > 0:
        left_digit = left_int % 10
        right_digit = right_int % 10
        if left_digit + right_digit + carry >= 10:
            return True
        carry = 0
        left_int //= 10
        right_int //= 10
    return False


def has_subtraction_borrow(left_meta, right_meta):
    scale = max(left_meta["decimal_digits"], right_meta["decimal_digits"])
    left_int = scaled_integer(left_meta, scale)
    right_int = scaled_integer(right_meta, scale)
    borrow = 0

    while left_int > 0 or right_int > 0:
        left_digit = left_int % 10
        right_digit = right_int % 10
        if left_digit - borrow < right_digit:
            return True
        borrow = 0
        left_int //= 10
        right_int //= 10
    return False


def match_rewrite_rule(operation, rules, left_meta, right_meta):
    if operation == "add":
        mode = rules["addition_carry_mode"]
        if mode == "any":
            return True
        has_rewrite = has_addition_carry(left_meta, right_meta)
        return has_rewrite if mode == "with" else not has_rewrite

    if operation == "sub":
        mode = rules["subtraction_borrow_mode"]
        if mode == "any":
            return True
        has_rewrite = has_subtraction_borrow(left_meta, right_meta)
        return has_rewrite if mode == "with" else not has_rewrite

    return True


def calculate_result(operation, left_value: Decimal, right_value: Decimal) -> Decimal:
    if operation == "add":
        return left_value + right_value
    if operation == "sub":
        return left_value - right_value
    if operation == "mul":
        return left_value * right_value
    raise ConfigError(f"不支持的题型：{operation}")


def answer_scale(operation, left_meta, right_meta):
    if operation in {"add", "sub"}:
        return max(left_meta["decimal_digits"], right_meta["decimal_digits"])
    if operation == "mul":
        return left_meta["decimal_digits"] + right_meta["decimal_digits"]
    return 0


def build_problem(operation, rules):
    metadata = OPERATIONS[operation]

    for _ in range(MAX_GENERATION_ATTEMPTS):
        left = build_number(rules)
        right = build_number(rules)

        if operation == "sub" and rules["non_negative_subtraction"] and left["value"] < right["value"]:
            left, right = right, left

        if not match_rewrite_rule(operation, rules, left, right):
            continue

        result = calculate_result(operation, left["value"], right["value"])
        if result < rules["result_min"] or result > rules["result_max"]:
            continue

        scale = answer_scale(operation, left, right)
        return {
            "text": f"{left['text']} {metadata['symbol']} {right['text']} =",
            "type": operation,
            "answer": format_decimal(result, scale),
            "symbol": metadata["symbol"],
            "operation_label": metadata["label"],
        }

    range_text = f"{decimal_to_plain_str(rules['result_min'])} ~ {decimal_to_plain_str(rules['result_max'])}"
    raise ConfigError(
        f"当前条件太严格，无法稳定生成“{metadata['label']}”题目。请放宽位数范围、结果范围，或调整进位 / 退位规则（当前结果范围：{range_text}）。"
    )


def generate_problems(config):
    problems = []
    for operation_key in ("add", "sub", "mul"):
        for _ in range(config["counts"][operation_key]):
            problems.append(build_problem(operation_key, config["rules"]))
    if config["shuffle_problems"]:
        random.shuffle(problems)
    return problems


def generate_page_data(config):
    pages = []
    for idx in range(config["pages"]):
        pages.append(
            {
                "page_num": idx + 1,
                "display_page_num": config["start_page"] + idx,
                "problems": generate_problems(config),
            }
        )
    return pages


def serialize_config(config, metrics=None):
    serialized = {
        "worksheet_title": config["worksheet_title"],
        "pages": config["pages"],
        "start_page": config["start_page"],
        "filename": config["filename"],
        "counts": dict(config["counts"]),
        "rules": {
            "integer_digits_min": config["rules"]["integer_digits_min"],
            "integer_digits_max": config["rules"]["integer_digits_max"],
            "decimal_digits_min": config["rules"]["decimal_digits_min"],
            "decimal_digits_max": config["rules"]["decimal_digits_max"],
            "result_min": decimal_to_plain_str(config["rules"]["result_min"]),
            "result_max": decimal_to_plain_str(config["rules"]["result_max"]),
            "non_negative_subtraction": config["rules"]["non_negative_subtraction"],
            "addition_carry_mode": config["rules"]["addition_carry_mode"],
            "subtraction_borrow_mode": config["rules"]["subtraction_borrow_mode"],
        },
        "layout": dict(config["layout"]),
        "shuffle_problems": config["shuffle_problems"],
    }
    if metrics:
        serialized["layout_metrics"] = metrics
    return serialized


def build_summary(config, metrics):
    total_per_page = sum(config["counts"].values())
    operation_summary = []
    for key in ("add", "sub", "mul"):
        count = config["counts"][key]
        if count > 0:
            operation_summary.append(
                {
                    "key": key,
                    "label": OPERATIONS[key]["label"],
                    "count": count,
                    "symbol": OPERATIONS[key]["symbol"],
                }
            )

    integer_min = config["rules"]["integer_digits_min"]
    integer_max = config["rules"]["integer_digits_max"]
    decimal_min = config["rules"]["decimal_digits_min"]
    decimal_max = config["rules"]["decimal_digits_max"]

    add_count = config["counts"]["add"]
    sub_count = config["counts"]["sub"]

    return {
        "total_pages": config["pages"],
        "total_problems": config["pages"] * total_per_page,
        "problems_per_page": total_per_page,
        "capacity_per_page": metrics["capacity_per_page"],
        "rows_per_page": metrics["rows_per_page"],
        "columns": config["layout"]["columns"],
        "line_height_mm": config["layout"]["line_height_mm"],
        "font_size": config["layout"]["font_size"],
        "operation_summary": operation_summary,
        "integer_digits_text": f"{integer_min} ~ {integer_max} 位",
        "decimal_digits_text": f"{decimal_min} ~ {decimal_max} 位",
        "result_range_text": (
            f"{decimal_to_plain_str(config['rules']['result_min'])} ~ "
            f"{decimal_to_plain_str(config['rules']['result_max'])}"
        ),
        "shuffle_problems": config["shuffle_problems"],
        "non_negative_subtraction": config["rules"]["non_negative_subtraction"],
        "addition_carry_text": mode_text(config["rules"]["addition_carry_mode"], "进位") if add_count else "未启用",
        "subtraction_borrow_text": mode_text(config["rules"]["subtraction_borrow_mode"], "退位") if sub_count else "未启用",
    }


# ========================
# PDF 绘制
# ========================


def draw_rounded_rect(c, x, y, w, h, radius, fill_color=None, stroke_color=None, stroke_width=0.5):
    path = c.beginPath()
    path.moveTo(x + radius, y)
    path.lineTo(x + w - radius, y)
    path.arcTo(x + w - radius, y, x + w, y + radius, radius)
    path.lineTo(x + w, y + h - radius)
    path.arcTo(x + w, y + h - radius, x + w - radius, y + h, radius)
    path.lineTo(x + radius, y + h)
    path.arcTo(x + radius, y + h, x, y + h - radius, radius)
    path.lineTo(x, y + radius)
    path.arcTo(x, y + radius, x + radius, y, radius)
    path.close()

    if fill_color:
        c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(stroke_width)

    c.drawPath(path, fill=1 if fill_color else 0, stroke=1 if stroke_color else 0)


def draw_circle(c, center_x, center_y, radius, fill_color):
    c.setFillColor(fill_color)
    c.circle(center_x, center_y, radius, fill=1, stroke=0)


def contains_cjk(text):
    return any("\u4e00" <= char <= "\u9fff" for char in str(text))


def pick_font(text, bold=False):
    if contains_cjk(text):
        return PDF_CJK_FONT
    return PDF_FONT_BOLD if bold else PDF_FONT


def set_text_font(c, text, size, bold=False):
    font_name = pick_font(text, bold=bold)
    c.setFont(font_name, size)
    return font_name


def draw_header_bar(c, width, height, page_num, title):
    bar_height = 42
    bar_y = height - bar_height - 12
    draw_rounded_rect(c, 20, bar_y, width - 40, bar_height, 8, fill_color=PDF_PRIMARY)

    for idx, alpha in enumerate([0.3, 0.2, 0.15]):
        c.setFillColor(Color(1, 1, 1, alpha))
        c.circle(45 + idx * 18, bar_y + bar_height / 2, 4, fill=1, stroke=0)

    c.setFillColor(white)
    set_text_font(c, title, 15, bold=True)
    c.drawString(100, bar_y + 14, title)

    subtitle = "Configurable Arithmetic Worksheet"
    set_text_font(c, subtitle, 8.5)
    c.setFillColor(Color(1, 1, 1, 0.8))
    c.drawString(100, bar_y + 3, subtitle)

    page_label = f"Page {page_num}"
    label_width = 74
    label_x = width - 20 - label_width - 10
    label_y = bar_y + (bar_height - 22) / 2
    draw_rounded_rect(c, label_x, label_y, label_width, 22, 11, fill_color=Color(1, 1, 1, 0.2))
    c.setFillColor(white)
    page_label_font = set_text_font(c, page_label, 10, bold=True)
    text_width = c.stringWidth(page_label, page_label_font, 10)
    c.drawString(label_x + (label_width - text_width) / 2, label_y + 6.5, page_label)


def draw_info_bar(c, width, height, summary):
    info_y = height - 72
    draw_rounded_rect(c, 25, info_y, width - 50, 28, 5, fill_color=PDF_GRAY_LIGHT)

    c.setFillColor(PDF_GRAY)
    operation_text = "  |  ".join(
        f"{item['label']} {item['count']}题" for item in summary["operation_summary"]
    ) or "暂无题目"
    line_one = f"每页 {summary['problems_per_page']} 题  |  {operation_text}"
    line_two = (
        f"整数位 {summary['integer_digits_text']}  |  小数位 {summary['decimal_digits_text']}"
        f"  |  结果范围 {summary['result_range_text']}"
    )
    set_text_font(c, line_one, 7.2)
    c.drawString(35, info_y + 15, line_one)
    set_text_font(c, line_two, 7.2)
    c.drawString(35, info_y + 6, line_two)


def draw_problem_item(c, x, y, idx, problem, font_size):
    circle_radius = 9
    circle_color = PDF_PRIMARY
    if problem["type"] == "mul":
        circle_color = PDF_WARNING
    elif problem["type"] == "sub":
        circle_color = PDF_SUCCESS

    draw_circle(c, x, y, circle_radius, circle_color)

    c.setFillColor(white)
    c.setFont(PDF_FONT_BOLD, 8.2)
    num_text = str(idx)
    num_width = c.stringWidth(num_text, PDF_FONT_BOLD, 8.2)
    c.drawString(x - num_width / 2, y - 3, num_text)

    c.setFillColor(PDF_TEXT)
    c.setFont(PDF_FONT, font_size)
    c.drawString(x + 18, y - (font_size * 0.28), problem["text"])


def draw_footer(c, width, page_num, total_pages):
    footer_y = 18
    c.setStrokeColor(PDF_GRAY_BORDER)
    c.setLineWidth(0.5)
    c.line(25, footer_y + 16, width - 25, footer_y + 16)

    c.setFont(PDF_FONT, 7)
    c.setFillColor(PDF_GRAY)
    c.drawString(25, footer_y + 3, "Generated by Math Practice Web App")

    c.setFillColor(PDF_PRIMARY)
    mid_x = width / 2
    for delta in (-8, 0, 8):
        c.circle(mid_x + delta, footer_y + 8, 1.5, fill=1, stroke=0)

    page_info = f"{page_num} / {total_pages}"
    page_width = c.stringWidth(page_info, PDF_FONT, 7)
    c.setFillColor(PDF_GRAY)
    c.drawString(width - 25 - page_width, footer_y + 3, page_info)


def create_math_pdf_bytes(pages_data, config, summary):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    layout = config["layout"]
    metrics = build_layout_metrics(layout)
    columns = layout["columns"]
    line_height = metrics["line_height_pt"]
    font_size = layout["font_size"]

    left_margin = 26
    right_margin = 26
    column_gap = 18
    column_width = (width - left_margin - right_margin - column_gap * (columns - 1)) / columns
    column_positions = [
        left_margin + col_idx * (column_width + column_gap) + 10 for col_idx in range(columns)
    ]
    start_y = height - HEADER_OFFSET_PT
    total_page_label = pages_data[-1]["display_page_num"] if pages_data else config["start_page"]

    for page_data in pages_data:
        c.setFillColor(white)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        draw_rounded_rect(c, 14, 10, width - 28, height - 20, 10, stroke_color=PDF_GRAY_BORDER, stroke_width=0.3)

        draw_header_bar(c, width, height, page_data["display_page_num"], config["worksheet_title"])
        draw_info_bar(c, width, height, summary)

        problem_count = len(page_data["problems"])
        row_count = math.ceil(problem_count / columns)

        for row_idx in range(row_count):
            row_y = start_y - row_idx * line_height
            if row_idx > 0:
                separator_y = row_y + line_height * 0.52
                c.setStrokeColor(colors.HexColor("#eff1f5"))
                c.setLineWidth(0.3)
                c.setDash(2, 4)
                c.line(left_margin - 2, separator_y, width - right_margin + 2, separator_y)
                c.setDash()

            for col_idx in range(columns):
                problem_idx = row_idx * columns + col_idx
                if problem_idx >= problem_count:
                    continue
                draw_problem_item(
                    c,
                    column_positions[col_idx],
                    row_y,
                    problem_idx + 1,
                    page_data["problems"][problem_idx],
                    font_size,
                )

        draw_footer(c, width, page_data["display_page_num"], total_page_label)
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer


# ========================
# Web 路由
# ========================


@app.route("/")
def index():
    defaults = serialize_config(DEFAULT_CONFIG, build_layout_metrics(DEFAULT_CONFIG["layout"]))
    return render_template(
        "index.html",
        defaults=defaults,
        built_in_presets=get_builtin_presets(),
        saved_presets=get_saved_presets(),
    )


@app.route("/api/presets", methods=["GET"])
def preset_list():
    return jsonify({
        "built_in": get_builtin_presets(),
        "saved": get_saved_presets(),
    })


@app.route("/api/presets/save", methods=["POST"])
def preset_save():
    payload = request.get_json(silent=True) or {}
    preset_label = sanitize_preset_label(payload.get("preset_name"))
    if not preset_label:
        return jsonify({"error": "请先填写模板名称。"}), 400

    try:
        config, metrics = normalize_config(payload)
    except ConfigError as exc:
        return jsonify({"error": str(exc)}), 400

    store = read_saved_preset_store()
    preset_key = slugify_preset_name(preset_label)
    if preset_key not in store and len(store) >= MAX_SAVED_PRESETS:
        return jsonify({"error": f"最多只能保存 {MAX_SAVED_PRESETS} 个模板。"}), 400

    store[preset_key] = {
        "label": preset_label,
        "config": serialize_config(config, metrics),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_saved_preset_store(store)

    return jsonify({
        "message": f"已保存模板：{preset_label}",
        "saved_key": preset_key,
        "saved": get_saved_presets(),
    })


@app.route("/api/presets/delete", methods=["POST"])
def preset_delete():
    payload = request.get_json(silent=True) or {}
    preset_key = str(payload.get("preset_key") or "").strip()
    if not preset_key:
        return jsonify({"error": "没有指定要删除的模板。"}), 400

    store = read_saved_preset_store()
    if preset_key not in store:
        return jsonify({"error": "模板不存在，可能已经被删除。"}), 404

    deleted_label = store[preset_key].get("label") or preset_key
    del store[preset_key]
    write_saved_preset_store(store)

    return jsonify({
        "message": f"已删除模板：{deleted_label}",
        "saved": get_saved_presets(),
    })


@app.route("/api/preview", methods=["POST"])
def preview():
    try:
        config, metrics = normalize_config(request.get_json(silent=True) or {})
        pages = generate_page_data(config)
        return jsonify(
            {
                "pages": pages,
                "config": serialize_config(config, metrics),
                "summary": build_summary(config, metrics),
            }
        )
    except ConfigError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/download", methods=["POST"])
def download():
    try:
        config, metrics = normalize_config(request.get_json(silent=True) or {})
        pages = generate_page_data(config)
        summary = build_summary(config, metrics)
        pdf_buffer = create_math_pdf_bytes(pages, config, summary)
        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=config["filename"],
        )
    except ConfigError as exc:
        return jsonify({"error": str(exc)}), 400


@app.route("/api/regenerate", methods=["POST"])
def regenerate_single():
    try:
        config, metrics = normalize_config(request.get_json(silent=True) or {})
        problems = generate_problems(config)
        return jsonify(
            {
                "problems": problems,
                "config": serialize_config(config, metrics),
                "summary": build_summary(config, metrics),
            }
        )
    except ConfigError as exc:
        return jsonify({"error": str(exc)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000, debug=True)
