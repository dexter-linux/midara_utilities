"""
Midara Utilities - Document & Image Compression / Conversion
Works with flat folder structure (index.html + styles.css in root)
"""

import os
import uuid
import zipfile
import tempfile
from pathlib import Path

from flask import (
    Flask, render_template, request, send_file,
    jsonify, after_this_request, send_from_directory
)
from werkzeug.utils import secure_filename
from PIL import Image
from pypdf import PdfReader, PdfWriter

# ---------------------------------------------------------------------------
# Config – flat structure
# ---------------------------------------------------------------------------
app = Flask(__name__, template_folder='.', static_folder='.')
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

UPLOAD_FOLDER = Path(tempfile.gettempdir()) / "midara_uploads"
OUTPUT_FOLDER = Path(tempfile.gettempdir()) / "midara_outputs"
UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"docx", "pdf", "png", "jpg", "jpeg"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_size(path: Path) -> int:
    return path.stat().st_size


# ---------------------------------------------------------------------------
# DOCX compression
# ---------------------------------------------------------------------------
def compress_docx(input_path: Path, output_path: Path, quality: int = 70) -> dict:
    original_size = get_file_size(input_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(tmp)

        media_dir = tmp / "word" / "media"
        if media_dir.exists():
            for img_path in media_dir.iterdir():
                if img_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}:
                    try:
                        with Image.open(img_path) as img:
                            if img.mode in ("RGBA", "P", "LA"):
                                background = Image.new("RGB", img.size, (255, 255, 255))
                                if img.mode in ("RGBA", "LA"):
                                    background.paste(img, mask=img.split()[-1])
                                else:
                                    background.paste(img)
                                img = background
                            elif img.mode != "RGB":
                                img = img.convert("RGB")

                            save_kwargs = {"optimize": True}
                            if img_path.suffix.lower() in {".jpg", ".jpeg"}:
                                save_kwargs["quality"] = quality
                                save_kwargs["progressive"] = True
                            elif img_path.suffix.lower() == ".png":
                                save_kwargs["compress_level"] = 9

                            img.save(img_path, **save_kwargs)
                    except Exception:
                        continue

        with zipfile.ZipFile(
            output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zf:
            for root, _, files in os.walk(tmp):
                for file in files:
                    abs_path = Path(root) / file
                    arcname = abs_path.relative_to(tmp)
                    zf.write(abs_path, arcname)

    new_size = get_file_size(output_path)
    return {
        "original_size": original_size,
        "compressed_size": new_size,
        "ratio": round((1 - new_size / original_size) * 100, 1) if original_size else 0,
    }


# ---------------------------------------------------------------------------
# PDF compression
# ---------------------------------------------------------------------------
def compress_pdf(input_path: Path, output_path: Path) -> dict:
    original_size = get_file_size(input_path)

    reader = PdfReader(str(input_path))
    writer = PdfWriter()

    for page in reader.pages:
        if hasattr(page, "compress_content_streams"):
            page.compress_content_streams()
        writer.add_page(page)

    writer.add_metadata({})

    with open(output_path, "wb") as f:
        writer.write(f)

    new_size = get_file_size(output_path)
    return {
        "original_size": original_size,
        "compressed_size": new_size,
        "ratio": round((1 - new_size / original_size) * 100, 1) if original_size else 0,
    }


# ---------------------------------------------------------------------------
# Image compression / conversion
# ---------------------------------------------------------------------------
def compress_image(
    input_path: Path,
    output_path: Path,
    quality: int = 75,
    target_format: str | None = None,
) -> dict:
    original_size = get_file_size(input_path)

    with Image.open(input_path) as img:
        fmt = (target_format or img.format or "JPEG").upper()
        if fmt == "JPG":
            fmt = "JPEG"

        if fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        elif img.mode not in ("RGB", "L") and fmt == "JPEG":
            img = img.convert("RGB")

        save_kwargs = {"optimize": True}
        if fmt == "JPEG":
            save_kwargs["quality"] = quality
            save_kwargs["progressive"] = True
        elif fmt == "PNG":
            save_kwargs["compress_level"] = 9

        if fmt == "JPEG" and output_path.suffix.lower() not in {".jpg", ".jpeg"}:
            output_path = output_path.with_suffix(".jpg")
        elif fmt == "PNG" and output_path.suffix.lower() != ".png":
            output_path = output_path.with_suffix(".png")

        img.save(output_path, format=fmt, **save_kwargs)

    new_size = get_file_size(output_path)
    return {
        "original_size": original_size,
        "compressed_size": new_size,
        "ratio": round((1 - new_size / original_size) * 100, 1) if original_size else 0,
        "output_path": str(output_path),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/styles.css")
def styles():
    return send_from_directory(".", "styles.css")


@app.route("/api/process", methods=["POST"])
def process_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not supported. Use DOCX, PDF, PNG or JPEG."}), 400

    quality = int(request.form.get("quality", 75))
    quality = max(10, min(95, quality))
    convert_to = request.form.get("convert_to", "").upper() or None

    original_name = secure_filename(file.filename)
    ext = original_name.rsplit(".", 1)[1].lower()
    unique_id = uuid.uuid4().hex[:10]
    input_path = UPLOAD_FOLDER / f"{unique_id}_{original_name}"
    file.save(input_path)

    try:
        if ext == "docx":
            output_name = f"{Path(original_name).stem}_compressed.docx"
            output_path = OUTPUT_FOLDER / f"{unique_id}_{output_name}"
            stats = compress_docx(input_path, output_path, quality=quality)

        elif ext == "pdf":
            output_name = f"{Path(original_name).stem}_compressed.pdf"
            output_path = OUTPUT_FOLDER / f"{unique_id}_{output_name}"
            stats = compress_pdf(input_path, output_path)

        elif ext in {"png", "jpg", "jpeg"}:
            target_fmt = convert_to if convert_to in {"JPEG", "PNG"} else None
            if target_fmt == "JPEG":
                output_name = f"{Path(original_name).stem}_compressed.jpg"
            elif target_fmt == "PNG":
                output_name = f"{Path(original_name).stem}_compressed.png"
            else:
                output_name = f"{Path(original_name).stem}_compressed.{ext}"
            output_path = OUTPUT_FOLDER / f"{unique_id}_{output_name}"
            stats = compress_image(input_path, output_path, quality=quality, target_format=target_fmt)
            if "output_path" in stats:
                output_path = Path(stats["output_path"])
                output_name = output_path.name

        else:
            return jsonify({"error": "Unsupported type"}), 400

        return jsonify({
            "success": True,
            "original_name": original_name,
            "output_name": output_name,
            "download_id": unique_id,
            "original_size": stats["original_size"],
            "compressed_size": stats["compressed_size"],
            "ratio": stats["ratio"],
            "message": f"Reduced by {stats['ratio']}%",
        })

    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500
    finally:
        if input_path.exists():
            input_path.unlink(missing_ok=True)


@app.route("/api/download/<download_id>")
def download_file(download_id):
    for f in OUTPUT_FOLDER.glob(f"{download_id}_*"):
        @after_this_request
        def cleanup(response):
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass
            return response

        return send_file(
            f,
            as_attachment=True,
            download_name=f.name.split("_", 1)[-1],
        )

    return jsonify({"error": "File not found or already downloaded"}), 404


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Midara Utilities"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
