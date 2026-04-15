#!/usr/bin/env python3
import io
import shutil
import argparse
import tempfile
import subprocess


from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter, Transformation


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Add a transparent footer image to each page")
    p.add_argument("image", help="PNG/JPEG to insert as footer")
    p.add_argument("pdf", nargs="+", help="One or more PDFs to modify")
    return p.parse_args()


def compress_pdf_inplace(path: str) -> None:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run(
        [
            "gs",
            "-sDEVICE=pdfwrite",
            "-dPDFSETTINGS=/prepress",
            "-dNOPAUSE",
            "-dBATCH",
            "-dQUIET",
            "-dDownsampleColorImages=false",
            "-dDownsampleGrayImages=false",
            "-dDownsampleMonoImages=false",
            f"-sOutputFile={tmp_path}",
            path,
        ],
        check=True,
    )

    shutil.move(tmp_path, path)


def make_image_page(img_path: str, width_pt: float, height_pt: float) -> bytes:
    """
    Create a 1-page PDF sized exactly to (width_pt x height_pt) with only the image drawn.
    The page itself is as small as the image => no page-sized white background when stamping.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width_pt, height_pt))
    c.drawImage(ImageReader(img_path), 0, 0, width=width_pt, height=height_pt, mask="auto")
    c.save()
    return buf.getvalue()


def main():
    args = parse_args()

    with Image.open(args.image) as im:
        img_w_px, img_h_px = im.size
        aspect = img_h_px / img_w_px

    for pdf_path in args.pdf:
        reader = PdfReader(pdf_path)

        first_page = reader.pages[0]
        media_box = first_page.mediabox
        page_width = float(media_box.right) - float(media_box.left)

        footer_w = page_width * 0.12
        footer_h = footer_w * aspect
        x_pos = (page_width - footer_w) / 2.0
        y_pos = 25.0

        overlay_pdf_bytes = make_image_page(args.image, footer_w, footer_h)
        overlay_reader = PdfReader(io.BytesIO(overlay_pdf_bytes))
        overlay_page = overlay_reader.pages[0]

        writer = PdfWriter()

        for page in reader.pages:
            t = Transformation().translate(x_pos, y_pos)
            page.merge_transformed_page(overlay_page, t)
            writer.add_page(page)

        with open(pdf_path, "wb") as f:
            writer.write(f)

        compress_pdf_inplace(pdf_path)


if __name__ == "__main__":
    main()
