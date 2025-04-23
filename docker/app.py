from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
import tempfile
import subprocess
import os
import json

app = FastAPI()

@app.post("/process-invoice")
async def process_invoice(
    invoice_file: UploadFile = File(...),
    goods_file: UploadFile = File(...),
    min_score: int = Form(default=0)
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(invoice_file.filename)[-1]) as invoice_temp:
        invoice_path = invoice_temp.name
        invoice_temp.write(await invoice_file.read())

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as goods_temp:
        goods_path = goods_temp.name
        goods_temp.write(await goods_file.read())

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as output_temp:
        output_path = output_temp.name

    try:
        cmd = [
            "python", "invoice_system.py",
            "-i", invoice_path,
            "-g", goods_path,
            "-o", output_path
        ]
        if min_score is not None:
            cmd.extend(["--min_score", str(min_score)])

        subprocess.run(cmd, check=True)

        with open(output_path, "r", encoding="utf-8") as f:
            result_json = json.load(f)

        return JSONResponse(content=result_json)

    except subprocess.CalledProcessError as e:
        return JSONResponse(content={"error": f"Processing failed: {e}"}, status_code=500)
    finally:
        os.remove(invoice_path)
        os.remove(goods_path)
        os.remove(output_path)