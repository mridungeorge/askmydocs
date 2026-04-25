"""
Multi-modal RAG — handling images, tables, and charts in PDFs.

Why this matters:
Most real business documents (product catalogues, reports,
research papers) contain charts and tables.
Text-only RAG extracts zero information from them.

What we do:
1. Extract images from PDF pages using PyMuPDF (fitz)
2. Send each image to NVIDIA's vision LLM
3. Get a text description of the image
4. Store that description as a chunk with source_type="image"
5. At retrieval time, image descriptions compete with text chunks

The user never knows the difference — they just get better answers.

Why this approach over dedicated vision embeddings:
- Simpler to implement
- Works with your existing text embedding pipeline
- NVIDIA's vision model is excellent at describing charts/tables
- No separate vector space to manage

Limitation: Very image-heavy PDFs (scanned docs) are slow.
For production HSW use case (product catalogues), this is fine
because product catalogues have mostly text with some product images.
"""

import fitz  # PyMuPDF
import base64
import io
from openai import OpenAI
from backend.config import NVIDIA_API_KEY, NVIDIA_BASE_URL, VISION_MODEL

nvidia = OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_API_KEY)


def extract_images_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Extract all images from a PDF.

    Returns list of:
    {
        "page": int,
        "image_index": int,
        "image_b64": str,  # base64 encoded image
        "width": int,
        "height": int,
    }

    Filters out tiny images (icons, decorative elements)
    that wouldn't contain meaningful content.
    """
    doc    = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []

    for page_num in range(len(doc)):
        page      = doc[page_num]
        img_list  = page.get_images(full=True)

        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            try:
                base_image  = doc.extract_image(xref)
                image_bytes = base_image["image"]
                width       = base_image.get("width", 0)
                height      = base_image.get("height", 0)

                # Skip tiny images — likely icons or decorative
                # Minimum 100x100 pixels to be meaningful
                if width < 100 or height < 100:
                    continue

                # Skip images that are mostly white (blank areas)
                # by checking file size — blank images are tiny
                if len(image_bytes) < 5000:
                    continue

                image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
                images.append({
                    "page":        page_num + 1,
                    "image_index": img_idx,
                    "image_b64":   image_b64,
                    "width":       width,
                    "height":      height,
                    "ext":         base_image.get("ext", "png"),
                })

            except Exception:
                continue

    doc.close()
    return images


def extract_tables_from_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Extract tables from PDF using PyMuPDF's table detection.

    Returns list of:
    {
        "page": int,
        "table_index": int,
        "text": str,  # table content as formatted text
    }
    """
    doc    = fitz.open(stream=pdf_bytes, filetype="pdf")
    tables = []

    for page_num in range(len(doc)):
        page = doc[page_num]

        try:
            # PyMuPDF table detection
            page_tables = page.find_tables()

            for t_idx, table in enumerate(page_tables.tables):
                # Convert table to text representation
                rows     = table.extract()
                if not rows:
                    continue

                # Format as markdown table for better LLM understanding
                lines = []
                for i, row in enumerate(rows):
                    cells = [str(c or "").strip() for c in row]
                    lines.append("| " + " | ".join(cells) + " |")
                    if i == 0:
                        lines.append("|" + "|".join(["---"] * len(cells)) + "|")

                table_text = "\n".join(lines)

                if len(table_text) > 50:  # skip empty tables
                    tables.append({
                        "page":        page_num + 1,
                        "table_index": t_idx,
                        "text":        table_text,
                    })

        except Exception:
            continue

    doc.close()
    return tables


def describe_image(image_b64: str, page_num: int, context: str = "") -> str:
    """
    Use NVIDIA's vision model to describe an image.

    Why we send page context:
    Telling the model "this is from page 3 of a technical paper"
    helps it give more relevant descriptions than treating
    the image in isolation.

    Returns a text description of the image content.
    """
    context_note = f"This image is from page {page_num} of a document."
    if context:
        context_note += f" Document context: {context[:100]}"

    prompt = f"""{context_note}

Describe this image in detail for use in a document search system.
Focus on:
- Type of content (chart, graph, diagram, table, photo, illustration)
- Key data points, trends, or values shown
- Labels, titles, axis labels if present
- Main conclusion or insight the image conveys

Be specific and factual. Your description will be used to answer questions about this document."""

    try:
        response = nvidia.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            max_tokens=300,
            temperature=0.1,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"[Image on page {page_num} — description unavailable: {str(e)[:50]}]"


def process_pdf_multimodal(
    pdf_bytes: bytes,
    doc_title: str,
    max_images: int = 20,
) -> list[dict]:
    """
    Full multi-modal processing pipeline for a PDF.

    Returns list of extra chunks (images + tables) to add to Qdrant
    alongside the text chunks from normal ingest.

    Each returned dict has:
    {
        "text":        str,  # description or table content
        "source_type": str,  # "image" or "table"
        "page":        int,
        "source_name": str,
    }

    max_images: cap to prevent very slow processing on image-heavy PDFs
    """
    extra_chunks = []

    # Process images
    images = extract_images_from_pdf(pdf_bytes)

    # Cap to max_images
    if len(images) > max_images:
        images = images[:max_images]

    for img in images:
        description = describe_image(
            img["image_b64"],
            img["page"],
            context=doc_title,
        )
        extra_chunks.append({
            "text":        f"[Image on page {img['page']}]: {description}",
            "source_type": "image",
            "page":        img["page"],
            "source_name": doc_title,
        })

    # Process tables
    tables = extract_tables_from_pdf(pdf_bytes)
    for table in tables:
        extra_chunks.append({
            "text":        f"[Table on page {table['page']}]:\n{table['text']}",
            "source_type": "table",
            "page":        table["page"],
            "source_name": doc_title,
        })

    return extra_chunks
