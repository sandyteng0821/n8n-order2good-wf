import argparse
import pandas as pd
from fuzzywuzzy import process, fuzz
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
import json
import fitz  # PyMuPDF
import pdfplumber
import os

def extract_text_from_pdf(pdf_path):
    text_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                text_lines.extend(lines)
    return text_lines

def extract_text_from_image(image_path):
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, lang='chi_tra+eng')
    return text.splitlines()

def load_input_lines(input_path):
    if input_path.endswith('.csv'):
        df = pd.read_csv(input_path, header=None)
        return df[0].dropna().tolist()
    elif input_path.endswith('.pdf'):
        return extract_text_from_pdf(input_path)
    elif input_path.endswith(('.jpg', '.jpeg', '.png')):
        return extract_text_from_image(input_path)
    elif input_path.endswith('.txt'):
        with open(input_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines() if line.strip()]
    else:
        raise ValueError("Unsupported file format")

def clean_text(text):
    return re.sub(r'\s+', '', text)

def fuzzy_match_line_tokens(line, product_names, min_score=None):
    # Split line by whitespace or tab and match each token individually
    tokens = re.split(r'[\s\t]+', line)
    best_match = None
    best_score = -1

    for token in tokens:
        match = process.extractOne(token, product_names, scorer=fuzz.token_sort_ratio)
        if match:
            name, score = match
            if score > best_score:
                best_match = (name, score)
                best_score = score

    # Apply minimum score filter if specified
    if min_score is not None and best_score < min_score:
        return None
    return best_match

def fuzzy_match_lines(input_lines, goods_df, min_score=None):
    results = {}
    product_names = goods_df['品名'].tolist()
    for line in input_lines:
        clean_line = clean_text(line)
        if not clean_line:
            continue
        match = fuzzy_match_line_tokens(clean_line, product_names, min_score)
        if match:
            results[line] = [match]
    return results

def extract_metadata_and_item_lines(text_lines):
    order_date = "Unknown"
    customer_name = "Unknown"
    item_lines = []
    item_section = False
    for line in text_lines:
        date_match = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", line)
        if date_match:
            order_date = date_match.group(0).replace("年", "-").replace("月", "-").replace("日", "")

        customer_match = re.search(r"客戶代號:?\s*\S+\s*\(([^)]+)\)", line)
        if customer_match:
            customer_name = customer_match.group(1)

        if "品名" in line and "數量" in line:
            item_section = True
            continue
        if "總金額" in line:
            item_section = False
            continue
        if item_section and line.strip():
            item_lines.append(line.strip())
    return order_date, customer_name, item_lines

def summarize_to_json(text_lines, goods_df, tax=0, status="處理中", input_type="auto", min_score=None):
    if input_type == "auto":
        if all(re.search(r"\s", line) for line in text_lines):
            input_type = "text"
        else:
            input_type = "structured"

    if input_type == "text":
        order_date = "Unknown"
        customer_name = "Unknown"
        item_lines = text_lines
    else:
        order_date, customer_name, item_lines = extract_metadata_and_item_lines(text_lines)

    matches = fuzzy_match_lines(item_lines, goods_df, min_score)
    items = []
    total_amount = 0
    for raw_line, match_list in matches.items():
        if not match_list:
            continue

        matched_name, score = match_list[0]
        product_rows = goods_df[goods_df['品名'] == matched_name]

        if product_rows.empty:
            print(f"[Warning] No match found in goods_df for '{matched_name}'")
            continue

        product_row = product_rows.iloc[0]

        quantity = 1
        unit_price = 0
        match = re.search(r'(\d+)[×xX*](\d+)', raw_line)
        if match:
            quantity = int(match.group(1)) * int(match.group(2))
        else:
            numbers = [int(num) for num in re.findall(r'\d+', raw_line)]
            if len(numbers) == 2:
                quantity, unit_price = numbers
            elif len(numbers) == 1:
                quantity = numbers[0]

        subtotal = quantity * unit_price
        total_amount += subtotal

        item = {
            "product_id": product_row['品號'],
            "matched_name": matched_name,
            "original_input": raw_line,
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
            "match_score": round(score, 2)
        }
        items.append(item)

    result = {
        "customer_name": customer_name,
        "order_date": order_date,
        "items": items,
        "total_amount": total_amount,
        "tax": tax,
        "status": status
    }
    return result

def main():
    parser = argparse.ArgumentParser(description="Invoice agent - match items to product list")
    parser.add_argument("-g", "--goods", required=True, help="Path to goods CSV file")
    parser.add_argument("-i", "--input", required=True, help="Path to input invoice file (pdf/image/csv/txt)")
    parser.add_argument("-o", "--output", default="fuzzy_match_result.json", help="Output JSON file")
    parser.add_argument("--min_score", type=int, default=None, help="Minimum fuzzy match score to accept")
    args = parser.parse_args()

    goods_df = pd.read_csv(args.goods)
    input_lines = load_input_lines(args.input)

    ext = os.path.splitext(args.input)[-1].lower()
    input_type = "text" if ext in [".txt", ".jpg", ".jpeg", ".png"] else "structured"
    json_summary = summarize_to_json(input_lines, goods_df, input_type=input_type, min_score=args.min_score)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(json_summary, f, ensure_ascii=False, indent=2)
    print(f"Done! Results saved to {args.output}")

if __name__ == '__main__':
    main()