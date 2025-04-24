# Invoice Agent System

This script performs intelligent invoice parsing using OCR and fuzzy matching to map free-text or semi-structured invoice items to a known product catalog.

## Core Algorithm Overview

### OCR Handling

- **PDFs**: For structured PDFs, the script uses `pdfplumber` to directly extract readable text, which is more reliable than image-based OCR.
- **Images**: Uses `pytesseract` as a fallback to extract text from image files. However, recognition quality may vary.

#### Recommended Improvements for Image OCR

1. **DeepSeek Prompt (manual intervention)**:
   - Upload the image to DeepSeek with this prompt:

     ```
     Please extract the information (name quantity unit) from the provided image and convert the extracted text to a plain text file (each line contains name quantity unit columns)
     ```

   - Save the resulting text file and input it using `-i` flag.

2. **PaddleOCR (automated & accurate)**:
   - Use PaddleOCR for better Chinese recognition:

     ```bash
     docker pull paddlecloud/paddleocr:2.6-cpu-latest
     docker run --rm -v /mnt/:/mnt/ -it paddlecloud/paddleocr:2.6-cpu-latest /bin/bash
     ```

   - Inside the container:

     ```python
     from paddleocr import PaddleOCR

     ocr = PaddleOCR(
         lang='ch',
         use_gpu=False,
         use_angle_cls=True,
         enable_mkldnn=True
     )
     root_path = "/mnt/RD_Develop/sandyteng/invoice_system/n8n-order2good-wf/testinput/"
     imgs = ["test_image_01.jpeg", "test_image_02.jpg", "test_image_03.jpg"]
     for img in imgs:
         img_path = root_path + img
         result = ocr.ocr(img_path, cls=True)
         for line in result[0]:
             print(line[1][0])
     ```

### Fuzzy Matching Logic

- The script performs fuzzy matching using `fuzzywuzzy.token_sort_ratio` between each token from the input invoice lines and the product names in the catalog.
- If the best score exceeds a configurable threshold (`--min_score`), it's considered a match.

### Metadata Extraction

- For structured PDFs, the script attempts to extract metadata like `order_date`, `customer_name`, and product section lines using regular expressions.
- Products are parsed from "品名" to "總金額" blocks.

### Output

- The final JSON includes:
  - Customer name, order date, matched product IDs, original input line, matched name, quantity, unit price, subtotal, and match confidence score.

## Example Inputs

The following files are located in the `testinput/` directory:

- `customer.goods.csv` (required with `-g`)
- Converted inputs using DeepSeek and PaddleOCR:
  - `deepseek_converted_test_image_01.txt`
  - `deepseek_converted_test_image_02.txt`
  - `deepseek_converted_test_image_03.txt`
- Raw PDF and image examples:
  - `oracle_order_chinese_1.pdf`
  - `sap_order_chinese_4.pdf`
  - `test_image_01.jpeg`
  - `test_image_02.jpg`
  - `test_image_03.jpg`

## Run Example

```bash
python invoice_agent.py -g testinput/customer.goods.csv -i testinput/deepseek_converted_test_image_01.txt -o output.json
```

## Output Format

```json
{
  "customer_name": "Example Corp",
  "order_date": "2024-04-01",
  "items": [
    {
      "product_id": "P12345",
      "matched_name": "高階滑鼠",
      "original_input": "高階滑鼠 2 300",
      "quantity": 2,
      "unit_price": 300,
      "subtotal": 600,
      "match_score": 0.95
    }
  ],
  "total_amount": 600,
  "tax": 0,
  "status": "completed"
}
```
