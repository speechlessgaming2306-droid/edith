import json
import os
import re
import subprocess
import time
import html
import textwrap
import tempfile
from pathlib import Path

from google import genai
from google.genai import types
from env_loader import load_edith_env

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional in cloud/server deployments
    sync_playwright = None

load_edith_env()


class DocumentAgent:
    MODEL = "gemini-2.5-flash"

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def _safe_stem(self, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9 _-]+", "", (value or "").strip()).strip()
        cleaned = cleaned.replace(" ", "_")
        return cleaned[:80] or f"document_{int(time.time())}"

    def _resolve_output_base(self, output_path: str | None) -> Path:
        if output_path:
            expanded = Path(os.path.expanduser(output_path))
            if not expanded.is_absolute():
                expanded = Path.home() / expanded
            if expanded.suffix:
                return expanded.with_suffix("")
            return expanded

        docs_dir = self.workspace_root / "projects" / "temp" / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        return docs_dir / f"document_{int(time.time())}"

    def _resolve_output_folder(self, output_path: str | None) -> Path:
        if output_path:
            expanded = Path(os.path.expanduser(output_path))
            if not expanded.is_absolute():
                expanded = Path.home() / expanded
            return expanded

        docs_dir = self.workspace_root / "projects" / "temp" / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)
        return docs_dir / f"bundle_{int(time.time())}"

    def _extract_json(self, text: str):
        try:
            return json.loads(text)
        except Exception:
            pass
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError("Model did not return valid JSON for the document.")

    def _infer_doc_type(self, prompt: str) -> str:
        lowered = (prompt or "").lower()
        if any(token in lowered for token in ["resume", "cv", "curriculum vitae"]):
            return "resume"
        if any(token in lowered for token in ["email", "mail draft"]):
            return "email"
        if any(token in lowered for token in ["application", "leave letter", "cover letter", "formal letter", "complaint letter", "letter"]):
            return "letter"
        if any(token in lowered for token in ["statement of purpose", "sop", "proposal"]):
            return "proposal"
        return "document"

    def _heuristic_plan(self, prompt: str):
        doc_type = self._infer_doc_type(prompt)
        title = "Generated Document"
        file_stem = self._safe_stem(doc_type)
        blocks = []

        if doc_type == "letter":
            title = "Formal Letter"
            file_stem = self._safe_stem("formal_letter")
            blocks = [
                {"type": "meta_lines", "items": ["Date: ____________", "To,", "The Relevant Authority", "Subject: ____________________"]},
                {"type": "paragraph", "text": "Respected Sir/Madam,"},
                {"type": "paragraph", "text": prompt},
                {"type": "paragraph", "text": "Thank you for your time and consideration."},
                {"type": "signature", "name": "Yours sincerely,", "lines": ["[Your Name]"]},
            ]
        elif doc_type == "resume":
            title = "Resume"
            file_stem = self._safe_stem("resume")
            blocks = [
                {"type": "heading", "text": "Professional Summary"},
                {"type": "paragraph", "text": prompt},
                {"type": "heading", "text": "Experience"},
                {"type": "bullet_list", "items": ["Add experience here.", "Add measurable achievements here."]},
                {"type": "heading", "text": "Education"},
                {"type": "bullet_list", "items": ["Add education here."]},
                {"type": "heading", "text": "Skills"},
                {"type": "bullet_list", "items": ["Add skills here."]},
            ]
        elif doc_type == "email":
            title = "Email Draft"
            file_stem = self._safe_stem("email_draft")
            blocks = [
                {"type": "meta_lines", "items": ["To: ____________", "Subject: ____________________"]},
                {"type": "paragraph", "text": "Dear Sir/Madam,"},
                {"type": "paragraph", "text": prompt},
                {"type": "signature", "name": "Best regards,", "lines": ["[Your Name]"]},
            ]
        elif doc_type == "proposal":
            title = "Proposal"
            file_stem = self._safe_stem("proposal")
            blocks = [
                {"type": "heading", "text": "Overview"},
                {"type": "paragraph", "text": prompt},
                {"type": "heading", "text": "Key Points"},
                {"type": "bullet_list", "items": ["Objective", "Approach", "Expected Outcome"]},
            ]
        else:
            title = "Document"
            file_stem = self._safe_stem("document")
            blocks = [{"type": "paragraph", "text": prompt}]

        return title, file_stem, blocks

    def _render_plan(self, prompt: str):
        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=(
                "You design professional documents. "
                "Return JSON only with keys: title, file_stem, blocks. "
                "blocks must be an array of objects. "
                "Each block must be one of: "
                "{type:'heading', text:'...'}, "
                "{type:'paragraph', text:'...'}, "
                "{type:'bullet_list', items:['...','...']}, "
                "{type:'numbered_list', items:['...','...']}, "
                "{type:'meta_lines', items:['...','...']}, "
                "{type:'signature', name:'...', lines:['...','...']}. "
                "Make the structure appropriate for the user's requested document. "
                "For applications and letters, use proper formal order. "
                "For resumes or statements, use clean sectioning. "
                "For emails, include to/subject line placeholders and a proper closing. "
                "Write polished content, not placeholders, whenever the user gives enough detail. "
                "No markdown. No code fences.\n\n"
                f"User request: {prompt}"
            ),
            config=types.GenerateContentConfig(
                temperature=0.35,
                response_mime_type="application/json",
            ),
        )
        payload = self._extract_json(response.text or "")
        title = payload.get("title") or "Document"
        file_stem = self._safe_stem(payload.get("file_stem") or title)
        blocks = payload.get("blocks") or [{"type": "paragraph", "text": prompt}]
        return title, file_stem, blocks

    def _render_bundle_plan(self, prompt: str):
        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=(
                "You design polished multi-file writing bundles. "
                "Return JSON only with keys: folder_name, overview, files. "
                "files must be an array of objects with keys: filename, title, content. "
                "Each file should be polished, specific, and well-structured in Markdown. "
                "Make the writing feel premium and thoughtfully organized, similar to a strong Claude-style artifact: "
                "clear sections, useful headings, tight prose, concrete takeaways, no filler. "
                "If the user asks for personality traits, split the content into multiple complementary files instead of repeating the same points. "
                "Do not use code fences. Do not return anything except valid JSON.\n\n"
                f"User request: {prompt}"
            ),
            config=types.GenerateContentConfig(
                temperature=0.45,
                response_mime_type="application/json",
            ),
        )
        payload = self._extract_json(response.text or "")
        folder_name = self._safe_stem(payload.get("folder_name") or "bundle")
        overview = payload.get("overview") or ""
        files = payload.get("files") or []
        normalized_files = []
        for i, file in enumerate(files, start=1):
            filename = self._safe_stem(file.get("filename") or file.get("title") or f"file_{i}")
            if not filename.endswith(".md"):
                filename += ".md"
            normalized_files.append({
                "filename": filename,
                "title": file.get("title") or filename.replace("_", " ").replace(".md", "").title(),
                "content": (file.get("content") or "").strip(),
            })
        return folder_name, overview, normalized_files

    def _rtf_escape(self, text: str) -> str:
        text = (text or "").replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
        text = text.replace("\n", "\\line ")
        return text

    def _blocks_to_plain_text(self, title: str, blocks: list[dict]) -> str:
        lines = [title, ""]
        for block in blocks:
            block_type = block.get("type")
            if block_type == "heading":
                lines.extend([block.get("text", ""), ""])
            elif block_type == "paragraph":
                lines.extend([block.get("text", ""), ""])
            elif block_type == "bullet_list":
                for item in block.get("items", []):
                    lines.append(f"- {item}")
                lines.append("")
            elif block_type == "numbered_list":
                for i, item in enumerate(block.get("items", []), start=1):
                    lines.append(f"{i}. {item}")
                lines.append("")
            elif block_type == "meta_lines":
                lines.extend(block.get("items", []))
                lines.append("")
            elif block_type == "signature":
                lines.append(block.get("name", ""))
                lines.extend(block.get("lines", []))
                lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _blocks_to_rtf(self, title: str, blocks: list[dict]) -> str:
        parts = [
            r"{\rtf1\ansi\deff0",
            r"{\fonttbl{\f0 Times New Roman;}{\f1 Helvetica;}}",
            r"\paperw12240\paperh15840\margl1440\margr1440\margt1080\margb1440",
            r"\fs24",
            rf"\qc\b\f1\fs34 {self._rtf_escape(title)}\b0\par\par",
        ]

        for block in blocks:
            block_type = block.get("type")
            if block_type == "heading":
                parts.append(rf"\b\f1\fs26 {self._rtf_escape(block.get('text', ''))}\b0\fs24\par\par")
            elif block_type == "paragraph":
                parts.append(rf"\ql\f0 {self._rtf_escape(block.get('text', ''))}\par\par")
            elif block_type == "bullet_list":
                for item in block.get("items", []):
                    parts.append(rf"\fi-240\li480 \'95\tab {self._rtf_escape(item)}\par")
                parts.append(r"\par")
            elif block_type == "numbered_list":
                for idx, item in enumerate(block.get("items", []), start=1):
                    parts.append(rf"\fi-240\li480 {idx}.\tab {self._rtf_escape(item)}\par")
                parts.append(r"\par")
            elif block_type == "meta_lines":
                for item in block.get("items", []):
                    parts.append(rf"\ql\f0 {self._rtf_escape(item)}\par")
                parts.append(r"\par")
            elif block_type == "signature":
                parts.append(r"\par")
                if block.get("name"):
                    parts.append(rf"\ql\f0 {self._rtf_escape(block.get('name', ''))}\par")
                for line in block.get("lines", []):
                    parts.append(rf"\ql\f0 {self._rtf_escape(line)}\par")
                parts.append(r"\par")

        parts.append("}")
        return "".join(parts)

    def _blocks_to_html(self, title: str, blocks: list[dict]) -> str:
        parts = [
            "<!doctype html><html><head><meta charset='utf-8'>",
            "<meta name='viewport' content='width=device-width, initial-scale=1'>",
            "<style>",
            ":root{--paper:#fffdf8;--ink:#1b1b1b;--muted:#5f5a52;--accent:#20262e;--rule:#d9d2c7;}",
            "*{box-sizing:border-box;}",
            "body{margin:0;background:linear-gradient(180deg,#f3efe8 0%,#ece6dc 100%);color:var(--ink);font-family:Georgia,'Times New Roman',serif;line-height:1.65;padding:32px 16px;}",
            ".page{max-width:8.27in;min-height:11.69in;margin:0 auto;background:var(--paper);padding:0.9in 0.85in;box-shadow:0 18px 50px rgba(33,30,26,.14);border:1px solid rgba(60,52,44,.08);}",
            "h1{font-family:Helvetica,Arial,sans-serif;font-size:24pt;letter-spacing:.02em;line-height:1.15;text-align:center;margin:0 0 10px;color:var(--accent);}",
            ".title-rule{width:92px;height:2px;background:var(--rule);margin:0 auto 24px;border-radius:999px;}",
            "h2{font-family:Helvetica,Arial,sans-serif;font-size:13.5pt;letter-spacing:.03em;text-transform:uppercase;color:var(--accent);margin:24px 0 10px;padding-top:6px;border-top:1px solid var(--rule);}",
            "p{margin:0 0 12px;text-align:justify;}",
            "ul,ol{margin:0 0 16px 22px;padding:0;}",
            "li{margin:0 0 7px;padding-left:4px;}",
            ".meta{margin:0 0 20px;white-space:pre-line;color:var(--muted);font-size:11.4pt;}",
            ".signature{margin-top:26px;padding-top:14px;border-top:1px solid var(--rule);white-space:pre-line;}",
            "@media print{body{background:#fff;padding:0;}.page{box-shadow:none;border:none;min-height:auto;}}",
            "</style></head><body><article class='page'>",
            f"<h1>{html.escape(title)}</h1>",
            "<div class='title-rule'></div>",
        ]

        for block in blocks:
            block_type = block.get("type")
            if block_type == "heading":
                parts.append(f"<h2>{html.escape(block.get('text', ''))}</h2>")
            elif block_type == "paragraph":
                parts.append(f"<p>{html.escape(block.get('text', ''))}</p>")
            elif block_type == "bullet_list":
                items = "".join(f"<li>{html.escape(item)}</li>" for item in block.get("items", []))
                parts.append(f"<ul>{items}</ul>")
            elif block_type == "numbered_list":
                items = "".join(f"<li>{html.escape(item)}</li>" for item in block.get("items", []))
                parts.append(f"<ol>{items}</ol>")
            elif block_type == "meta_lines":
                meta = "<br/>".join(html.escape(item) for item in block.get("items", []))
                parts.append(f"<div class='meta'>{meta}</div>")
            elif block_type == "signature":
                lines = [block.get("name", "")] + list(block.get("lines", []))
                signature = "<br/>".join(html.escape(line) for line in lines if line)
                parts.append(f"<div class='signature'>{signature}</div>")

        parts.append("</article></body></html>")
        return "".join(parts)

    def _build_pdf_with_playwright(self, pdf_path: Path, html_text: str) -> None:
        if sync_playwright is None:
            raise RuntimeError("Playwright is not installed, so PDF generation is unavailable on this deployment.")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page()
                page.set_content(html_text, wait_until="load")
                page.emulate_media(media="print")
                page.pdf(
                    path=str(pdf_path),
                    format="A4",
                    print_background=True,
                    margin={
                        "top": "0.5in",
                        "right": "0.45in",
                        "bottom": "0.55in",
                        "left": "0.45in",
                    },
                )
            finally:
                browser.close()

    def _pdf_escape(self, text: str) -> str:
        return (text or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _wrap_for_pdf(self, text: str, width_chars: int) -> list[str]:
        text = re.sub(r"\s+", " ", (text or "").strip())
        if not text:
            return [""]
        return textwrap.wrap(text, width=max(20, width_chars))

    def _build_pdf(self, pdf_path: Path, title: str, blocks: list[dict]) -> None:
        page_width = 595
        page_height = 842
        margin_x = 54
        top_margin = 68
        bottom_margin = 64
        usable_height = page_height - top_margin - bottom_margin

        lines: list[tuple[str, str, int]] = [("title", title, 18), ("space", "", 10)]

        for block in blocks:
            block_type = block.get("type")
            if block_type == "heading":
                lines.append(("heading", block.get("text", ""), 13))
                lines.append(("space", "", 4))
            elif block_type == "paragraph":
                for line in self._wrap_for_pdf(block.get("text", ""), 92):
                    lines.append(("body", line, 11))
                lines.append(("space", "", 6))
            elif block_type == "meta_lines":
                for item in block.get("items", []):
                    for line in self._wrap_for_pdf(item, 88):
                        lines.append(("meta", line, 11))
                lines.append(("space", "", 8))
            elif block_type == "bullet_list":
                for item in block.get("items", []):
                    wrapped = self._wrap_for_pdf(item, 84)
                    if wrapped:
                        lines.append(("body", f"- {wrapped[0]}", 11))
                        for continuation in wrapped[1:]:
                            lines.append(("body", f"  {continuation}", 11))
                lines.append(("space", "", 8))
            elif block_type == "numbered_list":
                for idx, item in enumerate(block.get("items", []), start=1):
                    wrapped = self._wrap_for_pdf(item, 82)
                    if wrapped:
                        lines.append(("body", f"{idx}. {wrapped[0]}", 11))
                        for continuation in wrapped[1:]:
                            lines.append(("body", f"   {continuation}", 11))
                lines.append(("space", "", 8))
            elif block_type == "signature":
                lines.append(("space", "", 14))
                if block.get("name"):
                    lines.append(("meta", block.get("name", ""), 11))
                for item in block.get("lines", []):
                    lines.append(("meta", item, 11))
                lines.append(("space", "", 6))

        pages: list[list[tuple[str, str, int]]] = []
        current_page: list[tuple[str, str, int]] = []
        current_height = 0

        for kind, text, size in lines:
            line_height = size + 4 if kind != "space" else max(size, 4)
            if current_page and current_height + line_height > usable_height:
                pages.append(current_page)
                current_page = []
                current_height = 0
            current_page.append((kind, text, size))
            current_height += line_height
        if current_page:
            pages.append(current_page)

        objects: list[bytes] = []

        def add_object(content: bytes) -> int:
            objects.append(content)
            return len(objects)

        catalog_id = add_object(b"<< /Type /Catalog /Pages 2 0 R >>")
        pages_id = add_object(b"<< /Type /Pages /Kids [] /Count 0 >>")
        font_regular_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>")
        font_bold_id = add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

        page_ids = []
        for page_lines in pages:
            commands = ["BT"]
            y = page_height - top_margin
            for kind, text, size in page_lines:
                if kind == "space":
                    y -= max(size, 4)
                    continue
                font_ref = "/F2" if kind in {"title", "heading"} else "/F1"
                x = margin_x if kind != "title" else 140
                if kind == "title":
                    text_width_estimate = len(text) * 7
                    x = max(margin_x, (page_width - text_width_estimate) / 2)
                commands.append(f"{font_ref} {size} Tf")
                commands.append(f"1 0 0 1 {x:.2f} {y:.2f} Tm")
                commands.append(f"({self._pdf_escape(text)}) Tj")
                y -= size + 4
            commands.append("ET")
            stream = "\n".join(commands).encode("latin-1", errors="replace")
            content_id = add_object(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
            page_dict = (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            ).encode("latin-1")
            page_ids.append(add_object(page_dict))

        kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
        objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("latin-1")

        pdf = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
        offsets = [0]
        current_offset = len(pdf[0])
        for obj_id, obj in enumerate(objects, start=1):
            entry = f"{obj_id} 0 obj\n".encode("latin-1") + obj + b"\nendobj\n"
            offsets.append(current_offset)
            pdf.append(entry)
            current_offset += len(entry)

        xref_offset = current_offset
        xref = [f"xref\n0 {len(objects) + 1}\n".encode("latin-1"), b"0000000000 65535 f \n"]
        for offset in offsets[1:]:
            xref.append(f"{offset:010d} 00000 n \n".encode("latin-1"))
        trailer = f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("latin-1")
        pdf.extend(xref)
        pdf.append(trailer)
        pdf_path.write_bytes(b"".join(pdf))

    def _build_precision_docx(self, docx_path: Path, title: str, blocks: list[dict]) -> None:
        script_path = Path(__file__).with_name("precision_docx_builder.cjs")
        payload = {"title": title, "blocks": blocks}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            payload_path = Path(handle.name)
        try:
            subprocess.run(
                ["node", str(script_path), str(payload_path), str(docx_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            payload_path.unlink(missing_ok=True)

    def generate(self, prompt: str, output_path: str | None = None, formats: list[str] | None = None, mode: str = "standard"):
        formats = [fmt.lower() for fmt in (formats or ["docx", "pdf"])]
        normalized_mode = (mode or "standard").strip().lower()
        try:
            title, suggested_stem, blocks = self._render_plan(prompt)
        except Exception:
            title, suggested_stem, blocks = self._heuristic_plan(prompt)

        base = self._resolve_output_base(output_path)
        if base.name.startswith("document_") and suggested_stem:
            base = base.with_name(suggested_stem)
        base.parent.mkdir(parents=True, exist_ok=True)

        plain_text = self._blocks_to_plain_text(title, blocks)
        html_text = self._blocks_to_html(title, blocks)
        rtf_text = self._blocks_to_rtf(title, blocks)

        txt_path = base.with_suffix(".txt")
        html_path = base.with_suffix(".html")
        rtf_path = base.with_suffix(".rtf")
        txt_path.write_text(plain_text, encoding="utf-8")
        html_path.write_text(html_text, encoding="utf-8")
        rtf_path.write_text(rtf_text, encoding="utf-8")

        outputs = {"txt": str(txt_path), "html": str(html_path), "rtf": str(rtf_path)}

        if "docx" in formats:
            docx_path = base.with_suffix(".docx")
            if normalized_mode == "precision_docx":
                self._build_precision_docx(docx_path, title, blocks)
            else:
                subprocess.run(
                    ["textutil", "-convert", "docx", str(rtf_path), "-output", str(docx_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            outputs["docx"] = str(docx_path)

        if "pdf" in formats:
            pdf_path = base.with_suffix(".pdf")
            try:
                self._build_pdf_with_playwright(pdf_path, html_text)
            except Exception:
                self._build_pdf(pdf_path, title, blocks)
            outputs["pdf"] = str(pdf_path)

        return {
            "title": title,
            "mode": normalized_mode,
            "outputs": outputs,
        }

    def generate_bundle(self, prompt: str, output_path: str | None = None):
        folder_name, overview, files = self._render_bundle_plan(prompt)
        base_folder = self._resolve_output_folder(output_path)
        if not base_folder.name or base_folder.name == base_folder.anchor:
            base_folder = base_folder / folder_name
        elif output_path is None:
            base_folder = base_folder.with_name(folder_name)

        base_folder.mkdir(parents=True, exist_ok=True)

        written = []
        if overview:
            readme = f"# {folder_name.replace('_', ' ').title()}\n\n{overview.strip()}\n"
            readme_path = base_folder / "README.md"
            readme_path.write_text(readme, encoding="utf-8")
            written.append(str(readme_path))

        for file in files:
            body = file["content"].strip()
            if file.get("title") and not body.startswith("#"):
                body = f"# {file['title']}\n\n{body}"
            file_path = base_folder / file["filename"]
            file_path.write_text(body.rstrip() + "\n", encoding="utf-8")
            written.append(str(file_path))

        return {
            "folder": str(base_folder),
            "files": written,
        }
