"""
RAG (Retrieval-Augmented Generation) tools for Alex Insurance Broker.

Hybrid approach:
  LAYER 1 — ChromaDB (persistent, file-based) for permanent knowledge:
             products, compliance rules, claims guidance, FAQ docs
             Embeddings: all-MiniLM-L6-v2 (local, no API key, ~80MB download once)
  LAYER 2 — Anthropic Claude Vision for ad-hoc document analysis:
             uploaded PDFs/images per conversation (policies, damage photos)
             Uses ANTHROPIC_API_KEY (same key as the main chat)

Exported functions (called directly by app.py TOOL_DISPATCH):
  broker_search_knowledge_fn(query, category, top_k)
  broker_upload_document_fn(file_path, doc_type, description)
  broker_analyze_document_fn(file_path_or_file_id, question, doc_type)
  broker_kb_status_fn()
  broker_kb_reindex_fn()
"""
from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path
from typing import Optional

# ── ChromaDB ──────────────────────────────────────────────────────────────────
try:
    import chromadb
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

# ── Anthropic (Vision + Files API for ad-hoc documents) ──────────────────────
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ── Paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).parent
_MCP_SERVER_DIR = _THIS_DIR.parent.parent          # mcp-server/
_PROJECT_DIR = _MCP_SERVER_DIR.parent              # insurance-broker-agent/
_DB_PATH = _MCP_SERVER_DIR / "insurance_broker.db"
_CHROMA_DIR = _PROJECT_DIR / ".rag_db"             # persistent ChromaDB storage
_DOCS_DIR = _PROJECT_DIR / "docs"

# ── State ─────────────────────────────────────────────────────────────────────
_chroma_client: "chromadb.PersistentClient | None" = None
_collection: "chromadb.Collection | None" = None
_kb_ready = False
_kb_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDING FUNCTION — all-MiniLM-L6-v2 (local, no API key)
# ChromaDB DefaultEmbeddingFunction downloads ~80MB model on first use,
# then caches it in ~/.cache/chroma/. No API key required.
# ─────────────────────────────────────────────────────────────────────────────

def _get_embedding_fn():
    """Return ChromaDB's built-in local embedding function (all-MiniLM-L6-v2)."""
    return DefaultEmbeddingFunction()


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE BASE INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_kb_ready() -> bool:
    """Lazy-init ChromaDB and index all knowledge on first call. Thread-safe."""
    global _chroma_client, _collection, _kb_ready
    if _kb_ready:
        return True
    with _kb_lock:
        if _kb_ready:
            return True
        if not CHROMA_AVAILABLE:
            return False
        # Load .env so GEMINI_API_KEY is available even when called standalone
        try:
            from dotenv import load_dotenv
            _env_file = _PROJECT_DIR / ".env"
            if _env_file.exists():
                load_dotenv(str(_env_file), override=False)
        except ImportError:
            pass
        try:
            _CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
            embed_fn = _get_embedding_fn()
            _collection = _chroma_client.get_or_create_collection(
                name="broker_knowledge",
                embedding_function=embed_fn,
                metadata={"hnsw:space": "cosine"},
            )
            # Only re-index if collection is empty (first run)
            if _collection.count() == 0:
                _index_all()
            _kb_ready = True
            return True
        except Exception as e:
            print(f"[RAG] ChromaDB init failed: {e}")
            return False


def _index_all():
    """Index all knowledge sources into ChromaDB."""
    _index_products()
    _index_claims_guidance()
    _index_compliance_maps()
    _index_docs()
    print(f"[RAG] Knowledge base indexed: {_collection.count()} chunks")


def _add_documents(docs: list[dict]):
    """Add documents to ChromaDB collection. Each doc: {id, text, metadata}."""
    if not docs or _collection is None:
        return
    ids = [d["id"] for d in docs]
    texts = [d["text"] for d in docs]
    metadatas = [d.get("metadata", {}) for d in docs]
    # Upsert to avoid duplicates on re-index
    _collection.upsert(ids=ids, documents=texts, metadatas=metadatas)


def _index_products():
    """Index insurance products from SQLite."""
    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, product_type, insurer_id, insurer_name, currency, "
            "annual_premium, insured_sum, coverage_summary, exclusions FROM products"
        ).fetchall()
        conn.close()
        docs = []
        for r in rows:
            text = (
                f"Produs: {r['product_type']} — {r['insurer_name']}\n"
                f"Tip: {r['product_type']}\n"
                f"Asigurător: {r['insurer_name']} ({r['insurer_id']})\n"
                f"Primă anuală: {r['annual_premium']} {r['currency']}\n"
                f"Sumă asigurată: {r['insured_sum'] or 'N/A'}\n"
                f"Acoperire: {r['coverage_summary'] or 'N/A'}\n"
                f"Excluderi: {r['exclusions'] or 'N/A'}"
            )
            docs.append({
                "id": f"product:{r['id']}",
                "text": text,
                "metadata": {
                    "category": "product",
                    "product_id": r["id"],
                    "product_type": r["product_type"] or "",
                    "name": f"{r['product_type']} {r['insurer_name']}",
                },
            })
        _add_documents(docs)
    except Exception as e:
        print(f"[RAG] Product indexing failed: {e}")


def _index_claims_guidance():
    """Index claims guidance data (insurer hotlines, procedures)."""
    # Import the dict directly from claims_tools
    try:
        from insurance_broker_mcp.tools.claims_tools import CLAIMS_GUIDANCE
    except ImportError:
        # Fallback inline data
        CLAIMS_GUIDANCE = {}

    docs = []
    for insurer, info in CLAIMS_GUIDANCE.items():
        text = (
            f"Ghid daune: {insurer}\n"
            f"Telefon daune: {info.get('daune_phone', 'N/A')}\n"
            f"Email daune: {info.get('daune_email', 'N/A')}\n"
            f"Portal online: {info.get('portal', 'N/A')}\n"
            f"Timp mediu procesare: {info.get('avg_processing_days', 'N/A')} zile\n"
            f"Documente necesare: {', '.join(info.get('required_docs', []))}\n"
            f"Note: {info.get('notes', '')}"
        )
        docs.append({
            "id": f"claims_guidance:{insurer.lower().replace(' ', '_')}",
            "text": text,
            "metadata": {"category": "claims_guidance", "insurer": insurer},
        })
    _add_documents(docs)


def _index_compliance_maps():
    """Index ASF and BaFin compliance classification maps."""
    try:
        from insurance_broker_mcp.tools.compliance_tools import ASF_CLASS_MAP, BAFIN_CLASS_MAP
    except ImportError:
        ASF_CLASS_MAP, BAFIN_CLASS_MAP = {}, {}

    docs = []
    for code, desc in ASF_CLASS_MAP.items():
        docs.append({
            "id": f"asf_class:{code}",
            "text": f"Clasă ASF (România): {code} — {desc}",
            "metadata": {"category": "compliance", "regulator": "ASF", "code": code},
        })
    for code, desc in BAFIN_CLASS_MAP.items():
        docs.append({
            "id": f"bafin_class:{code}",
            "text": f"Klasse BaFin (Deutschland): {code} — {desc}",
            "metadata": {"category": "compliance", "regulator": "BaFin", "code": code},
        })
    _add_documents(docs)


def _index_docs():
    """Index markdown documents from docs/ folder."""
    if not _DOCS_DIR.exists():
        return
    docs = []
    for md_file in _DOCS_DIR.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            # Chunk by heading (split on ## or ###)
            chunks = _chunk_markdown(content, source=md_file.name)
            docs.extend(chunks)
        except Exception:
            pass
    _add_documents(docs)


def _chunk_markdown(content: str, source: str, max_chars: int = 800) -> list[dict]:
    """Split markdown into chunks by heading. Max ~800 chars per chunk."""
    import re
    # Split on ## or ### headings
    parts = re.split(r"\n(?=#{1,3} )", content)
    chunks = []
    for i, part in enumerate(parts):
        part = part.strip()
        if not part or len(part) < 30:
            continue
        # Further split long parts by paragraph
        if len(part) > max_chars:
            paragraphs = part.split("\n\n")
            buffer = ""
            sub_idx = 0
            for para in paragraphs:
                if len(buffer) + len(para) < max_chars:
                    buffer += ("\n\n" if buffer else "") + para
                else:
                    if buffer:
                        chunks.append({
                            "id": f"doc:{source}:{i}:{sub_idx}",
                            "text": buffer,
                            "metadata": {"category": "faq_doc", "source": source},
                        })
                        sub_idx += 1
                    buffer = para
            if buffer:
                chunks.append({
                    "id": f"doc:{source}:{i}:{sub_idx}",
                    "text": buffer,
                    "metadata": {"category": "faq_doc", "source": source},
                })
        else:
            chunks.append({
                "id": f"doc:{source}:{i}",
                "text": part,
                "metadata": {"category": "faq_doc", "source": source},
            })
    return chunks


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC TOOL FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def broker_search_knowledge_fn(
    query: str,
    category: Optional[str] = None,
    top_k: int = 5,
) -> str:
    """
    Semantic search in the broker knowledge base (RAG Layer 1).

    Searches across:
    - Insurance products (coverage details, exclusions, target segments)
    - Claims guidance (insurer hotlines, required docs, processing times)
    - Compliance maps (ASF/BaFin class codes)
    - FAQ and project documentation

    Args:
        query:    Natural language question or keyword
        category: Optional filter — 'product', 'claims_guidance', 'compliance', 'faq_doc'
        top_k:    Number of results (default 5, max 10)

    Returns markdown with top matches and relevance scores.
    """
    if not _ensure_kb_ready():
        return "⚠️ Knowledge base unavailable (ChromaDB not initialized). Use broker_search_products for products."

    try:
        top_k = min(int(top_k), 10)
        where = {"category": {"$eq": category}} if category else None
        results = _collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        if not documents:
            return f"Nu am găsit informații relevante pentru: **{query}**\n\nÎncearcă `broker_search_products` pentru produse specifice."

        lines = [f"## Rezultate cunoștințe pentru: *{query}*\n"]
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
            score = round((1 - dist) * 100, 1)  # cosine distance → similarity %
            cat_label = {
                "product": "📦 Produs",
                "claims_guidance": "🏥 Ghid daune",
                "compliance": "⚖️ Conformitate",
                "faq_doc": "📄 Documentație",
            }.get(meta.get("category", ""), "📋 Info")

            lines.append(f"### {i}. {cat_label} — {score}% relevanță")
            # Show first 400 chars of the chunk
            preview = doc[:400].replace("\n", "\n> ")
            lines.append(f"> {preview}")
            if len(doc) > 400:
                lines.append("> *(continuare disponibilă)*")
            # Add structured metadata hints
            if meta.get("product_id"):
                lines.append(f"\n🔗 ID Produs: `{meta['product_id']}` — folosește `broker_search_products` pentru detalii complete")
            if meta.get("insurer"):
                lines.append(f"\n🏢 Asigurător: {meta['insurer']}")
            if meta.get("source"):
                lines.append(f"\n📁 Sursă: {meta['source']}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"❌ Eroare knowledge base: {e}"


def broker_upload_document_fn(
    file_path: str,
    doc_type: str = "policy",
    description: str = "",
) -> str:
    """
    Upload a document to Anthropic Files API for persistent analysis (RAG Layer 2).

    Use for: scanned policies, damage photos, invoices, handwritten forms.
    The returned file_id can be reused in broker_analyze_document without re-uploading.

    Args:
        file_path:   Absolute path to PDF or image file
        doc_type:    'policy', 'claim_photo', 'invoice', 'constatare', 'id_card', 'other'
        description: Short description for audit (e.g. "Polița RCA Allianz CLI001")

    Returns file_id and confirmation.
    """
    if not ANTHROPIC_AVAILABLE:
        return "❌ Anthropic SDK not available."

    path = Path(file_path)
    if not path.exists():
        return f"❌ Fișierul nu există: `{file_path}`"

    ALLOWED_MIME = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime = ALLOWED_MIME.get(path.suffix.lower())
    if not mime:
        return f"❌ Format nesuportat: `{path.suffix}`. Suportate: PDF, PNG, JPG, WEBP, GIF"

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "❌ ANTHROPIC_API_KEY lipsă din .env"

    try:
        client = anthropic.Anthropic(api_key=api_key)
        with open(file_path, "rb") as f:
            response = client.beta.files.upload(
                file=(path.name, f, mime),
            )
        file_id = response.id
        size_kb = path.stat().st_size // 1024

        return (
            f"✅ **Document încărcat cu succes**\n\n"
            f"- **Fișier:** {path.name}\n"
            f"- **Tip:** {doc_type}\n"
            f"- **Dimensiune:** {size_kb} KB\n"
            f"- **File ID:** `{file_id}`\n"
            f"- **Descriere:** {description or 'N/A'}\n\n"
            f"Folosește `broker_analyze_document` cu `file_id={file_id}` pentru a extrage date."
        )
    except Exception as e:
        return f"❌ Upload eșuat: {e}"


def broker_analyze_document_fn(
    file_path_or_file_id: str,
    question: str = "",
    doc_type: str = "policy",
) -> str:
    """
    Analyze a document using Claude Vision (RAG Layer 2 — Anthropic Files API).

    Works with:
    - file_id (from broker_upload_document) — no re-upload needed
    - local file path (PDF/image) — sends inline

    Automatic extraction by doc_type:
    - 'policy':      policy number, insurer, dates, premium, coverage clauses, exclusions
    - 'claim_photo': damage description, severity, affected parts, repair estimate
    - 'invoice':     vendor, items, amounts, total, tax
    - 'constatare':  both drivers, witnesses, damage, signatures (handwriting support)
    - 'id_card':     name, address, CNP/ID number (for client creation)
    - 'other':       general extraction based on question

    Args:
        file_path_or_file_id: Local path OR Anthropic file_id (starts with 'file_')
        question:  Specific question about the document (optional — auto-prompt used if empty)
        doc_type:  Document type for optimal extraction prompt

    Returns structured extraction in markdown.
    """
    if not ANTHROPIC_AVAILABLE:
        return "❌ Anthropic SDK not available."

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "❌ ANTHROPIC_API_KEY lipsă din .env"

    # Auto-prompts by document type
    AUTO_PROMPTS = {
        "policy": (
            "Extrage din această poliță de asigurare:\n"
            "1. Numărul poliței\n2. Asigurătorul\n3. Asiguratul (nume, CNP/cod fiscal)\n"
            "4. Data începere și data expirare\n5. Prima de asigurare (sumă + monedă)\n"
            "6. Suma asigurată\n7. Tipul de acoperire (RCA/CASCO/PAD etc.)\n"
            "8. Principalele clauze de acoperire\n9. Principalele excluderi\n"
            "Returnează ca JSON structurat."
        ),
        "claim_photo": (
            "Analizează această fotografie de daună auto:\n"
            "1. Zona/zonele afectate (față, spate, stânga, dreapta, etc.)\n"
            "2. Tipul daunei (zgârietură, impact, deformare, spargere)\n"
            "3. Severitate estimată: ușoară / medie / gravă\n"
            "4. Piese probabil afectate\n5. Estimare cost reparație (EUR/RON)\n"
            "6. Este vehiculul condus? (daună totală sau parțială?)\n"
            "Returnează ca raport structurat."
        ),
        "invoice": (
            "Extrage din această factură:\n"
            "1. Emitent (firmă, CUI, adresă)\n2. Destinatar\n"
            "3. Numărul și data facturii\n4. Lista poziții (denumire, cantitate, preț unitar)\n"
            "5. Total fără TVA\n6. TVA\n7. Total cu TVA\n8. Moneda\n"
            "Returnează ca JSON structurat."
        ),
        "constatare": (
            "Extrage din această constatare amiabilă de accident:\n"
            "1. Data și locul accidentului\n"
            "2. Șofer 1: nume, permis, vehicul, asigurător, poliță RCA\n"
            "3. Șofer 2: nume, permis, vehicul, asigurător, poliță RCA\n"
            "4. Martori (dacă există)\n5. Descrierea accidentului\n"
            "6. Schița (dacă e lizibilă)\n7. Semnăturile ambilor șoferi (da/nu)\n"
            "Returnează ca raport structurat. Gestionează text scris de mână în română."
        ),
        "id_card": (
            "Extrage din acest buletin/carte de identitate:\n"
            "1. Numele complet\n2. CNP\n3. Data nașterii\n4. Adresa\n"
            "5. Seria și numărul CI\n6. Data expirare CI\n"
            "Returnează ca JSON. IMPORTANT: tratează datele ca date personale sensibile."
        ),
        "other": "",
    }

    prompt = question or AUTO_PROMPTS.get(doc_type, AUTO_PROMPTS["other"])
    if not prompt:
        prompt = "Descrie conținutul acestui document și extrage informațiile relevante pentru un broker de asigurări."

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # Determine source: file_id or local path
        if file_path_or_file_id.startswith("file_"):
            # Use Anthropic Files API — no re-upload
            content = [
                {
                    "type": "text",
                    "text": prompt,
                },
                {
                    "type": "document",
                    "source": {
                        "type": "file",
                        "file_id": file_path_or_file_id,
                    },
                },
            ]
        else:
            # Local file — send inline
            path = Path(file_path_or_file_id)
            if not path.exists():
                return f"❌ Fișierul nu există: `{file_path_or_file_id}`"

            import base64
            with open(path, "rb") as f:
                data = base64.standard_b64encode(f.read()).decode("utf-8")

            suffix = path.suffix.lower()
            if suffix == ".pdf":
                content = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "document",
                        "source": {"type": "base64", "media_type": "application/pdf", "data": data},
                    },
                ]
            else:
                mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                            ".webp": "image/webp", ".gif": "image/gif"}
                media_type = mime_map.get(suffix, "image/jpeg")
                content = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": data},
                    },
                ]

        response = client.beta.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": content}],
            betas=["files-api-2025-04-14"],
        )

        result_text = response.content[0].text

        doc_name = (
            file_path_or_file_id if file_path_or_file_id.startswith("file_")
            else Path(file_path_or_file_id).name
        )
        return (
            f"## Analiză document: `{doc_name}`\n"
            f"**Tip:** {doc_type}\n\n"
            f"{result_text}"
        )

    except Exception as e:
        return f"❌ Analiză eșuată: {e}"


def broker_kb_status_fn() -> str:
    """
    Returns knowledge base status: number of indexed chunks, categories, last update.
    Useful for admin/debugging.
    """
    if not CHROMA_AVAILABLE:
        return "❌ ChromaDB nu este instalat."

    ready = _ensure_kb_ready()
    if not ready or _collection is None:
        return "❌ Knowledge base nu a putut fi inițializat."

    try:
        total = _collection.count()
        # Get category breakdown
        all_meta = _collection.get(include=["metadatas"])["metadatas"]
        categories: dict[str, int] = {}
        for m in all_meta:
            cat = m.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        lines = ["## 📚 Knowledge Base Status\n", f"**Total chunks indexate:** {total}\n"]
        lines.append("**Categorii:**")
        cat_labels = {
            "product": "📦 Produse",
            "claims_guidance": "🏥 Ghid daune",
            "compliance": "⚖️ Conformitate",
            "faq_doc": "📄 Documentație",
        }
        for cat, count in sorted(categories.items()):
            label = cat_labels.get(cat, cat)
            lines.append(f"- {label}: {count} chunks")

        lines.append(f"\n**Storage:** `{_CHROMA_DIR}`")
        lines.append("**Stare:** ✅ Operațional")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Eroare status: {e}"


def broker_kb_reindex_fn() -> str:
    """
    Force re-index all knowledge sources (products, compliance, docs).
    Use after adding new products to the database or updating docs/ files.
    """
    global _kb_ready
    if not CHROMA_AVAILABLE:
        return "❌ ChromaDB nu este instalat."

    with _kb_lock:
        _kb_ready = False

    ready = _ensure_kb_ready()
    if not ready:
        return "❌ Re-indexare eșuată."

    # Delete and re-create collection
    try:
        _chroma_client.delete_collection("broker_knowledge")
    except Exception:
        pass

    global _collection
    embed_fn = _get_embedding_fn()
    _collection = _chroma_client.get_or_create_collection(
        name="broker_knowledge",
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )
    _index_all()

    count = _collection.count()
    return f"✅ **Re-indexare completă** — {count} chunks indexate în knowledge base."
