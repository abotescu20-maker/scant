# RAGFlow + Chandra OCR 2 — Integration Plan
## Insurance Broker Agent TPSH

**Date:** 2026-03-30
**Status:** Draft
**Author:** Alex AI / Demo Broker SRL
**Scope:** Document intelligence pipeline for RO + DE insurance workflows

---

## 1. Obiectiv / Goal

Integrate **RAGFlow** (open-source RAG engine) with **Chandra OCR 2** to enable the Insurance Broker Agent to:

1. Ingest, parse, and semantically search insurance documents (policies, offers, claims, compliance reports)
2. Extract structured data from scanned/photographed documents (polițe, certificate RCA, daune, formulare BaFin)
3. Answer broker and client questions grounded in the actual document corpus — not just the SQLite demo data
4. Support document-based compliance verification (ASF / BaFin audit trails)

---

## 2. Stack Overview

```
┌─────────────────────────────────────────────────────────┐
│                  Chainlit UI (app.py)                   │
└────────────────────┬────────────────────────────────────┘
                     │ MCP calls
┌────────────────────▼────────────────────────────────────┐
│           insurance_broker_mcp (MCP Server)             │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ existing     │  │ rag_tools.py │  │ NEW: ocr_tools│ │
│  │ tools (26+)  │  │  (extend)    │  │  .py          │ │
│  └──────────────┘  └──────┬───────┘  └──────┬────────┘ │
└─────────────────────────  │  ────────────────│──────────┘
                            │                  │
               ┌────────────▼──────────────────▼──────────┐
               │           RAGFlow Server                  │
               │  ┌───────────────┐  ┌──────────────────┐ │
               │  │  Knowledge    │  │  Chunking /      │ │
               │  │  Bases        │  │  Embedding       │ │
               │  │  (per topic)  │  │  (Chroma/ES)     │ │
               │  └───────────────┘  └──────────────────┘ │
               │  ┌─────────────────────────────────────┐ │
               │  │        Chandra OCR 2 Pipeline        │ │
               │  │  PDF/image → structured text/JSON    │ │
               │  └─────────────────────────────────────┘ │
               └───────────────────────────────────────────┘
```

---

## 3. RAGFlow — Setup & Configuration

### 3.1 Deployment

```yaml
# docker-compose.ragflow.yml (alongside existing Dockerfile)
services:
  ragflow:
    image: infiniflow/ragflow:latest
    ports:
      - "9380:9380"   # API
      - "9381:9381"   # Web UI
    volumes:
      - ./ragflow-data:/ragflow/data
    environment:
      - RAGFLOW_API_KEY=${RAGFLOW_API_KEY}
      - EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
      # Multilingual: covers RO + DE + EN
```

### 3.2 Knowledge Bases (KB)

| KB Name | Document Types | Language | Chunk Strategy |
|---|---|---|---|
| `kb_rca_casco_ro` | RCA polițe, CASCO condiționate, tarife | RO | 512 tokens, overlap 64 |
| `kb_pad_home_ro` | PAD polițe, notificări PAID Pool | RO | 512 tokens |
| `kb_kfz_de` | KFZ-Haftpflicht, Kaskoversicherung conduits | DE | 512 tokens |
| `kb_claims_ro_de` | Dosare daune, notificări asigurători | RO/DE | 256 tokens (dense) |
| `kb_compliance_asf` | Rapoarte ASF, circulare, legi (132/2017, 260/2008) | RO | 1024 tokens |
| `kb_compliance_bafin` | VVG, PflVG, BaFin Rundschreiben | DE | 1024 tokens |
| `kb_offers` | Oferte generate (PDF/text) | RO/DE/EN | 256 tokens |

### 3.3 Retrieval Configuration

```python
# Per-KB retrieval settings
RETRIEVAL_CONFIG = {
    "kb_compliance_asf": {
        "top_k": 5,
        "similarity_threshold": 0.72,
        "rerank": True,
        "rerank_model": "BAAI/bge-reranker-base"
    },
    "kb_claims_ro_de": {
        "top_k": 3,
        "similarity_threshold": 0.75,
        "rerank": True
    },
    "default": {
        "top_k": 4,
        "similarity_threshold": 0.70,
        "rerank": False
    }
}
```

---

## 4. Chandra OCR 2 — Pipeline

### 4.1 Supported Document Types

| Document | OCR Target Fields | Output Format |
|---|---|---|
| Poliță RCA | Nr. poliță, asigurat, CNP/CUI, vehicul, valabilitate, primă | JSON |
| Certificat RCA | Nr. certificat, perioadă valabilitate, serie/nr. | JSON |
| Poliță CASCO | Nr. poliță, franciză, limite, clauze suplimentare | JSON |
| Certificat PAD | Nr. certificat, adresă, zonă de risc, primă | JSON |
| KFZ-Schein (DE) | Kennzeichen, VIN, Haftpflicht-Nr, Versicherungsbeginn | JSON |
| Dosar daună | Nr. dosar, data eveniment, descriere, valoare estimată | JSON |
| CI / Ausweis | Nume, prenume, CNP/Personalausweis-Nr (masked post-OCR) | JSON (masked) |

### 4.2 OCR Integration Flow

```
Document Upload (PDF / JPG / PNG)
        │
        ▼
  Chandra OCR 2 API
  POST /v2/extract
  {
    "document_type": "rca_policy",
    "language": "ro",           ← auto-detected or explicit
    "output_schema": "structured_json",
    "pii_masking": true         ← GDPR: CNP/CUI masked before storage
  }
        │
        ▼
  Structured JSON response
  {
    "policy_number": "RCA-2026-XXXXXX",
    "insured_name": "...",
    "cnp_masked": "1XXXXXXXX04",  ← only last 2 digits visible
    "vehicle": { "make": "...", "vin": "..." },
    "valid_from": "2026-01-01",
    "valid_to": "2027-01-01",
    "premium_ron": 1250.00
  }
        │
        ▼
  Validate → Upsert to SQLite (insurance_broker.db)
        │
        ▼
  Index full text → RAGFlow KB (kb_rca_casco_ro)
```

### 4.3 Chandra OCR 2 — API Wrapper

File: `mcp-server/insurance_broker_mcp/tools/ocr_tools.py`

```python
import httpx
import os
from typing import Optional

CHANDRA_OCR_BASE_URL = os.getenv("CHANDRA_OCR_URL", "http://localhost:8888")
CHANDRA_OCR_API_KEY  = os.getenv("CHANDRA_OCR_API_KEY", "")

DOCUMENT_SCHEMAS = {
    "rca_policy":    "rca_policy_v2",
    "casco_policy":  "casco_policy_v1",
    "pad_cert":      "pad_certificate_v1",
    "kfz_policy":    "kfz_policy_de_v1",
    "claim_file":    "claim_dossier_v1",
    "identity_doc":  "identity_masked_v1",
}

async def ocr_extract_document(
    file_bytes: bytes,
    filename: str,
    document_type: str,
    language: str = "auto"
) -> dict:
    """
    Send a document to Chandra OCR 2 and return structured JSON.
    PII masking is always enabled (GDPR Art. 5).
    """
    schema = DOCUMENT_SCHEMAS.get(document_type, "generic_v1")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CHANDRA_OCR_BASE_URL}/v2/extract",
            headers={"X-Api-Key": CHANDRA_OCR_API_KEY},
            files={"file": (filename, file_bytes)},
            data={
                "document_type": document_type,
                "output_schema":  schema,
                "language":       language,
                "pii_masking":    "true",
            }
        )
        resp.raise_for_status()
        return resp.json()
```

---

## 5. MCP Tool Extensions

### 5.1 New Tools in `rag_tools.py`

| Tool Name | Description | Input | Output |
|---|---|---|---|
| `broker_rag_search` | Semantic search across KB | query, kb_name, top_k | passages + sources |
| `broker_rag_ingest_document` | Upload + index document | file_bytes, filename, doc_type, client_id | ingestion_id |
| `broker_rag_get_context` | Get RAG context for a client | client_id, topic | relevant passages |
| `broker_ocr_extract` | OCR a document via Chandra OCR 2 | file_bytes, filename, doc_type, lang | structured JSON |
| `broker_ocr_validate_policy` | OCR + auto-validate policy data | file_bytes, policy_type | validation report |

### 5.2 Tool Signatures (MCP)

```python
@mcp.tool()
async def broker_rag_search(
    query: str,
    knowledge_base: str = "kb_rca_casco_ro",
    top_k: int = 4,
    language: str = "auto"
) -> dict:
    """
    Semantic search in RAGFlow knowledge base.
    Returns relevant passages with source document references.
    Use for answering questions about policy conditions, compliance rules,
    claim procedures, or tariff comparisons.
    """

@mcp.tool()
async def broker_ocr_extract(
    file_base64: str,
    filename: str,
    document_type: str,  # rca_policy | casco_policy | pad_cert | kfz_policy | claim_file
    language: str = "auto",
    client_id: Optional[str] = None
) -> dict:
    """
    Extract structured data from a scanned/photographed insurance document.
    PII (CNP, CUI, Personalausweis) is masked per GDPR Art. 5.
    Optionally links extracted data to an existing client profile.
    """

@mcp.tool()
async def broker_ocr_validate_policy(
    file_base64: str,
    filename: str,
    policy_type: str,   # rca | casco | pad | kfz
    expected_client_id: Optional[str] = None
) -> dict:
    """
    OCR a policy document and validate it against the broker database.
    Returns: match_status, discrepancies, validity_period, expiry_alert.
    """
```

---

## 6. GDPR & Compliance Constraints

| Constraint | Implementation |
|---|---|
| Art. 5 — Data minimisation | CNP/CUI/Steuernummer masked post-OCR before indexing |
| Art. 17 — Right to erasure | RAGFlow delete-document API + SQLite CASCADE delete |
| Art. 25 — Privacy by design | PII masking in Chandra OCR 2 is non-optional |
| Art. 32 — Security | All KB access authenticated (RAGFLOW_API_KEY env var) |
| ASF Norma 20/2023 | Audit log of every document ingested (client_id, timestamp, doc_type) |
| BaFin MaGo | Document retention index (7 years for DE policies) |

```python
# Audit log entry on every ingestion
async def _log_document_ingestion(client_id, doc_type, ragflow_doc_id, filename):
    await db.execute("""
        INSERT INTO document_audit_log
        (client_id, document_type, ragflow_doc_id, filename, ingested_at, ingested_by)
        VALUES (?, ?, ?, ?, datetime('now'), 'mcp_server')
    """, (client_id, doc_type, ragflow_doc_id, filename))
```

---

## 7. Implementation Phases

### Phase 1 — Foundation (Sprint 1, ~1 week)

- [ ] Add `docker-compose.ragflow.yml` with RAGFlow + Elasticsearch
- [ ] Configure 7 Knowledge Bases (empty) via RAGFlow API
- [ ] Implement `ocr_tools.py` with Chandra OCR 2 wrapper
- [ ] Add `document_audit_log` table to SQLite schema
- [ ] Unit tests: OCR mock → structured JSON → validation

### Phase 2 — RAG Integration (Sprint 2, ~1 week)

- [ ] Extend `rag_tools.py`: `broker_rag_search`, `broker_rag_ingest_document`
- [ ] Register new MCP tools in `server.py`
- [ ] Seed KB with sample documents (laws, standard policy conditions)
- [ ] Integration test: Alex answers "Ce acoperă polița CASCO pentru furt?" using RAG context

### Phase 3 — OCR Workflows (Sprint 3, ~1 week)

- [ ] Implement `broker_ocr_validate_policy` with discrepancy detection
- [ ] Add document upload endpoint to Chainlit UI (`app.py`)
- [ ] Auto-trigger `broker_check_rca_validity` on OCR of RCA certificate
- [ ] Cross-validate OCR output vs. SQLite client data

### Phase 4 — Production Hardening (Sprint 4, ~1 week)

- [ ] PII masking verification tests (CNP never in plaintext in RAGFlow index)
- [ ] RAGFlow backup to GCS bucket (align with existing GCS setup)
- [ ] Multilingual embedding benchmark (RO/DE/EN recall@5)
- [ ] Broker UI: document history per client with RAGFlow source links
- [ ] Load test: 50 concurrent OCR requests

---

## 8. Environment Variables

```bash
# .env additions
RAGFLOW_API_KEY=rf_...
RAGFLOW_BASE_URL=http://localhost:9380
RAGFLOW_DEFAULT_KB=kb_rca_casco_ro

CHANDRA_OCR_URL=http://localhost:8888
CHANDRA_OCR_API_KEY=ch_...

# Embedding model (multilingual for RO+DE)
RAGFLOW_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

## 9. Testing Strategy

```
tests/
  test_ocr_tools.py        # unit: Chandra OCR 2 mock responses per doc type
  test_rag_search.py       # unit: RAGFlow search mock + retrieval quality
  test_ocr_validate.py     # integration: OCR → validate → DB match
  test_pii_masking.py      # security: CNP/CUI never exposed in any output
  test_multilingual.py     # e2e: RO query → RO KB, DE query → DE KB
```

### Acceptance Criteria

| Test | Pass Condition |
|---|---|
| RCA OCR accuracy | >95% field extraction on test set of 20 scanned polițe |
| RAG recall@5 | >80% — correct passage in top 5 results for 30 compliance questions |
| PII masking | 0 CNP/CUI/Steuernummer in plaintext in RAGFlow index |
| Latency | OCR < 8s/doc, RAG search < 1.5s |
| Multilingual | RO queries hit RO KBs, DE queries hit DE KBs (language routing) |

---

## 10. Open Questions / Decisions Needed

1. **Chandra OCR 2 — self-hosted vs. cloud API?** (impacts latency and data residency for GDPR)
2. **RAGFlow embedding model** — multilingual MiniLM vs. dedicated RO/DE models?
3. **Chunking strategy for polițe** — header/section-aware chunking vs. fixed tokens?
4. **RAGFlow version** — v0.14+ required for multi-KB routing support
5. **GCS bucket structure** — separate bucket for OCR source docs vs. sharing with existing offer uploads?

---

## 11. References

- RAGFlow API docs: `http://localhost:9381` (local UI) / GitHub: infiniflow/ragflow
- Chandra OCR 2 API: `/v2/docs` (internal deployment)
- Existing RAG scaffold: `mcp-server/insurance_broker_mcp/tools/rag_tools.py`
- Existing GCS upload: `mcp-server/insurance_broker_mcp/tools/drive_tools.py`
- ASF Norma 20/2023 — cerințe privind arhivarea documentelor de asigurare
- BaFin MaGo 2022 — IT-Mindestvorgaben Versicherungsunternehmen
