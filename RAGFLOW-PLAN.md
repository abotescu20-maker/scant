# RAGFlow + Chandra OCR 2 — Integration Plan
## Claims AI TPSH · Insurance Broker Agent · Demo Broker SRL

**Version:** 2.0
**Date:** 2026-03-31
**Status:** Approved for Implementation
**Author:** Alex AI / Demo Broker SRL
**Scope:** Document intelligence pipeline — RO + DE insurance workflows
**Infrastructure:** Hetzner Cloud (self-hosted) + Docker Compose

---

## Cuprins / Table of Contents

1. [Obiectiv / Goal](#1-obiectiv--goal)
2. [Stack Overview](#2-stack-overview)
3. [Roluri și Permisiuni / Roles & Permissions](#3-roluri-și-permisiuni--roles--permissions)
4. [Arhitectura Hetzner + Docker Compose](#4-arhitectura-hetzner--docker-compose)
5. [RAGFlow — Knowledge Bases](#5-ragflow--knowledge-bases)
6. [Chandra OCR 2 — Pipeline](#6-chandra-ocr-2--pipeline)
7. [Admin PDF-to-Web](#7-admin-pdf-to-web)
8. [Document Validation Pipeline](#8-document-validation-pipeline)
9. [Grounded Citations](#9-grounded-citations)
10. [MCP Tool Extensions](#10-mcp-tool-extensions)
11. [GDPR & Compliance](#11-gdpr--compliance)
12. [Plan 5 Faze · 12 Săptămâni](#12-plan-5-faze--12-săptămâni)
13. [Costuri / Cost Model](#13-costuri--cost-model)
14. [Environment Variables](#14-environment-variables)
15. [Testing Strategy](#15-testing-strategy)
16. [References](#16-references)

---

## 1. Obiectiv / Goal

Integrate **RAGFlow** (open-source RAG engine, infiniflow) with **Chandra OCR 2** to power a **Claims AI TPSH** (Third Party Stakeholder Hub) for Demo Broker SRL, enabling:

1. **OCR ingestion** — Scan and parse scanned/photographed insurance documents: polițe RCA/CASCO/PAD, KFZ-Schein, dosare daune, formulare BaFin, constatări amiabile
2. **Semantic search** — Answer broker and client questions grounded in the actual document corpus, not just the SQLite demo data
3. **Document validation** — Cross-validate OCR output against the SQLite + Firestore client database; flag discrepancies automatically
4. **Admin PDF-to-Web** — Convert ingested PDFs into structured, searchable web views inside the Admin panel for broker review
5. **Grounded citations** — Every AI answer includes source document references (chunk ID, page, filename) for audit trails
6. **Multi-role access** — Brokers, Claims Adjusters, Admins, and Compliance Officers each see only what they're authorized to see
7. **ASF / BaFin compliance** — Full document audit trail, PII masking, 7-year retention index for DE, ASF Norma 20/2023 archiving for RO

---

## 2. Stack Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Hetzner Cloud (CPX51)                            │
│                                                                         │
│  ┌──────────────────┐    ┌────────────────────────────────────────────┐ │
│  │  Chainlit UI     │    │          Admin Panel (FastAPI)             │ │
│  │  app.py          │    │  /admin/documents  /admin/claims           │ │
│  │  :8000           │    │  PDF-to-Web viewer  Validation dashboard   │ │
│  └────────┬─────────┘    └───────────────────┬────────────────────────┘ │
│           │ MCP calls                        │ REST                     │
│  ┌────────▼──────────────────────────────────▼────────────────────────┐ │
│  │              insurance_broker_mcp  (MCP Server :9000)              │ │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐ │ │
│  │  │ existing tools │  │ rag_tools.py   │  │ ocr_tools.py (NEW)   │ │ │
│  │  │ (26+ tools)    │  │ (extended)     │  │ Chandra OCR 2 client │ │ │
│  │  └────────────────┘  └───────┬────────┘  └──────────┬───────────┘ │ │
│  └─────────────────────────────│──────────────────────│──────────────┘ │
│                                │                      │                 │
│  ┌─────────────────────────────▼──────────────────────▼──────────────┐ │
│  │                      RAGFlow  :9380 (API) / :9381 (UI)            │ │
│  │  ┌─────────────────┐  ┌────────────────────┐  ┌────────────────┐ │ │
│  │  │  Knowledge Bases│  │  Elasticsearch     │  │  MinIO (S3)    │ │ │
│  │  │  7 KBs          │  │  :9200 (vectors)   │  │  :9000 (docs)  │ │ │
│  │  └─────────────────┘  └────────────────────┘  └────────────────┘ │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │             Chandra OCR 2  :8888                                 │   │
│  │  PDF/JPG/PNG  →  structured JSON  (PII masked)                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐   │
│  │  SQLite (local)  │   │  Firestore (GCP) │   │  GCS Bucket      │   │
│  │  insurance_      │   │  persistent state│   │  (doc originals) │   │
│  │  broker.db       │   │                  │   │                  │   │
│  └──────────────────┘   └──────────────────┘   └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Roluri și Permisiuni / Roles & Permissions

### 3.1 Role Matrix

| Rol | Claims AI | RAG Search | OCR Upload | Admin PDF-to-Web | Validation | Delete/Erase |
|-----|-----------|------------|------------|------------------|------------|--------------|
| **Broker** | ✅ citire + creare | ✅ toate KB | ✅ documente proprii | ❌ | ✅ read-only | ❌ |
| **Senior Broker** | ✅ citire + creare + aprobare | ✅ toate KB | ✅ orice document | ✅ read-only | ✅ full | ❌ |
| **Claims Adjuster** | ✅ full (dosare daune) | ✅ kb_claims_ro_de | ✅ constatări, facturi | ✅ read-only (daune) | ✅ full | ❌ |
| **Compliance Officer** | ✅ read-only | ✅ toate KB | ❌ | ✅ full | ✅ full | ❌ |
| **Admin** | ✅ full | ✅ toate KB + admin | ✅ orice document | ✅ full | ✅ full | ✅ cu confirmare |
| **Client (readonly)** | ✅ dosarele proprii | ✅ kb_offers (proprii) | ❌ | ❌ | ❌ | ❌ |

### 3.2 RBAC Implementation

```python
# shared/auth.py — Role-Based Access Control
ROLE_PERMISSIONS = {
    "broker": {
        "rag_search": ["kb_rca_casco_ro", "kb_pad_home_ro", "kb_kfz_de",
                       "kb_claims_ro_de", "kb_compliance_asf", "kb_compliance_bafin", "kb_offers"],
        "ocr_upload": ["own_clients"],
        "admin_pdf_view": False,
        "delete_documents": False,
    },
    "claims_adjuster": {
        "rag_search": ["kb_claims_ro_de", "kb_rca_casco_ro"],
        "ocr_upload": ["claim_file", "constatare", "invoice"],
        "admin_pdf_view": ["claims_only"],
        "delete_documents": False,
    },
    "compliance_officer": {
        "rag_search": ["all"],
        "ocr_upload": [],
        "admin_pdf_view": ["all_readonly"],
        "delete_documents": False,
    },
    "admin": {
        "rag_search": ["all"],
        "ocr_upload": ["all"],
        "admin_pdf_view": ["full"],
        "delete_documents": True,   # requires 2-step confirmation
    },
    "client_readonly": {
        "rag_search": ["kb_offers"],    # filtered to own client_id
        "ocr_upload": [],
        "admin_pdf_view": False,
        "delete_documents": False,
    },
}
```

---

## 4. Arhitectura Hetzner + Docker Compose

### 4.1 Server Specification (Hetzner)

| Parametru | Valoare |
|-----------|---------|
| Server tip | CPX51 (AMD, 16 vCPU, 32 GB RAM, 360 GB NVMe) |
| OS | Ubuntu 24.04 LTS |
| Rețea | Hetzner private network + Floating IP |
| Backup | Hetzner Snapshot (zilnic) + GCS bucket sync |
| Locație | Nuremberg, DE (data residency EU — GDPR compliant) |

### 4.2 Docker Compose — Servicii Complete

```yaml
# docker-compose.yml (Hetzner deployment)
version: "3.9"

networks:
  broker-net:
    driver: bridge

volumes:
  ragflow-data:
  minio-data:
  es-data:
  chandra-data:
  chroma-data:
  sqlite-data:
  redis-data:

services:

  # ─── Main App (Chainlit UI + MCP Server) ──────────────────────────────────
  broker-app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"   # Chainlit UI
      - "9000:9000"   # MCP Server (internal)
    environment:
      - RAGFLOW_BASE_URL=http://ragflow:9380
      - RAGFLOW_API_KEY=${RAGFLOW_API_KEY}
      - CHANDRA_OCR_URL=http://chandra-ocr:8888
      - CHANDRA_OCR_API_KEY=${CHANDRA_OCR_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - GCS_BUCKET_NAME=${GCS_BUCKET_NAME}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/gcs-key.json
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - sqlite-data:/app/mcp-server/data
      - chroma-data:/app/.rag_db
      - ./gcs-key.json:/app/gcs-key.json:ro
    depends_on:
      ragflow:
        condition: service_healthy
      chandra-ocr:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - broker-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ─── RAGFlow ──────────────────────────────────────────────────────────────
  ragflow:
    image: infiniflow/ragflow:v0.17.2
    ports:
      - "9380:9380"   # RAGFlow REST API
      - "9381:9381"   # RAGFlow Web UI (Admin only)
    environment:
      - RAGFLOW_API_KEY=${RAGFLOW_API_KEY}
      - EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
      - ES_HOST=http://elasticsearch:9200
      - MINIO_HOST=minio:9000
      - MINIO_USER=${MINIO_USER}
      - MINIO_PASSWORD=${MINIO_PASSWORD}
      - REDIS_HOST=redis
      - MYSQL_HOST=ragflow-mysql
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
    volumes:
      - ragflow-data:/ragflow/data
    depends_on:
      - elasticsearch
      - minio
      - redis
      - ragflow-mysql
    networks:
      - broker-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9380/v1/system/version"]
      interval: 60s
      timeout: 15s
      retries: 5

  # ─── Elasticsearch (RAGFlow vector + text index) ──────────────────────────
  elasticsearch:
    image: elasticsearch:8.11.3
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - ES_JAVA_OPTS=-Xms2g -Xmx4g
      - bootstrap.memory_lock=true
    volumes:
      - es-data:/usr/share/elasticsearch/data
    ulimits:
      memlock:
        soft: -1
        hard: -1
    networks:
      - broker-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9200/_cluster/health"]
      interval: 30s
      timeout: 10s
      retries: 5

  # ─── MinIO (Object storage for RAGFlow documents) ─────────────────────────
  minio:
    image: minio/minio:RELEASE.2024-01-31T20-20-33Z
    command: server /data --console-address ":9001"
    ports:
      - "127.0.0.1:9001:9001"   # MinIO console — localhost only
    environment:
      - MINIO_ROOT_USER=${MINIO_USER}
      - MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
    volumes:
      - minio-data:/data
    networks:
      - broker-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ─── MySQL (RAGFlow metadata) ──────────────────────────────────────────────
  ragflow-mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_PASSWORD}
      - MYSQL_DATABASE=ragflow
      - MYSQL_USER=ragflow
      - MYSQL_PASSWORD=${MYSQL_PASSWORD}
    volumes:
      - ./ragflow-mysql-data:/var/lib/mysql
    networks:
      - broker-net
    restart: unless-stopped

  # ─── Chandra OCR 2 ────────────────────────────────────────────────────────
  chandra-ocr:
    image: chandraocr/chandra-ocr-2:latest
    # Alternative: build from internal registry if self-hosted
    # image: registry.demobrokersrl.ro/chandra-ocr-2:2.x
    ports:
      - "127.0.0.1:8888:8888"   # OCR API — localhost only, not exposed externally
    environment:
      - CHANDRA_API_KEY=${CHANDRA_OCR_API_KEY}
      - PII_MASKING_DEFAULT=true
      - SUPPORTED_LANGUAGES=ro,de,en
      - GPU_ENABLED=false   # Set true if Hetzner GPU server used
    volumes:
      - chandra-data:/chandra/data
    networks:
      - broker-net
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ─── Redis (queues, caching, session) ─────────────────────────────────────
  redis:
    image: redis:7.2-alpine
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    networks:
      - broker-net
    restart: unless-stopped

  # ─── Nginx (reverse proxy + TLS termination) ──────────────────────────────
  nginx:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro   # Certbot / Let's Encrypt certs
    depends_on:
      - broker-app
    networks:
      - broker-net
    restart: unless-stopped
```

### 4.3 Nginx Configuration (TLS + Role Routing)

```nginx
# nginx/nginx.conf
server {
    listen 443 ssl http2;
    server_name broker.demobrokersrl.ro;

    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    # Chainlit UI — all authenticated users
    location / {
        proxy_pass http://broker-app:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Admin panel — restricted by IP + role header
    location /admin {
        allow 10.0.0.0/8;   # Hetzner private network only
        deny all;
        proxy_pass http://broker-app:8000;
    }

    # RAGFlow UI — admin only via Nginx basic auth
    location /ragflow-ui/ {
        allow 10.0.0.0/8;
        deny all;
        proxy_pass http://ragflow:9381/;
        auth_basic "RAGFlow Admin";
        auth_basic_user_file /etc/nginx/htpasswd;
    }
}
```

---

## 5. RAGFlow — Knowledge Bases

### 5.1 Knowledge Base Inventory

| KB Name | Document Types | Limba | Chunk Strategy | Reranker |
|---------|---------------|-------|----------------|----------|
| `kb_rca_casco_ro` | Polițe RCA, CASCO, tarife, ghiduri | RO | 512 tok, overlap 64 | BGE-reranker-base |
| `kb_pad_home_ro` | Polițe PAD, notificări PAID Pool, Legea 260/2008 | RO | 512 tok | ❌ |
| `kb_kfz_de` | KFZ-Haftpflicht, Kaskoversicherung, VVG extras | DE | 512 tok | BGE-reranker-base |
| `kb_claims_ro_de` | Dosare daune, constatări, ghiduri asigurători | RO/DE | 256 tok (dense) | BGE-reranker-base |
| `kb_compliance_asf` | Rapoarte ASF, circulare, Legea 132/2017, 260/2008, Norma 20/2023 | RO | 1024 tok | BGE-reranker-base |
| `kb_compliance_bafin` | VVG, PflVG, BaFin Rundschreiben, MaGo 2022 | DE | 1024 tok | BGE-reranker-base |
| `kb_offers` | Oferte generate, prezentări produse, FAQ | RO/DE/EN | 256 tok | ❌ |

### 5.2 Retrieval Configuration

```python
# mcp-server/insurance_broker_mcp/tools/rag_tools.py
RETRIEVAL_CONFIG = {
    "kb_compliance_asf": {
        "top_k": 5,
        "similarity_threshold": 0.72,
        "rerank": True,
        "rerank_model": "BAAI/bge-reranker-base",
        "citation_format": "ASF [{source_doc}, Art. {article}]",
    },
    "kb_compliance_bafin": {
        "top_k": 5,
        "similarity_threshold": 0.72,
        "rerank": True,
        "rerank_model": "BAAI/bge-reranker-base",
        "citation_format": "BaFin [{source_doc}, § {section}]",
    },
    "kb_claims_ro_de": {
        "top_k": 3,
        "similarity_threshold": 0.75,
        "rerank": True,
        "rerank_model": "BAAI/bge-reranker-base",
        "citation_format": "Dosar [{doc_id}, p. {page}]",
    },
    "kb_rca_casco_ro": {
        "top_k": 4,
        "similarity_threshold": 0.70,
        "rerank": True,
        "citation_format": "Poliță [{policy_number}, Cl. {clause}]",
    },
    "default": {
        "top_k": 4,
        "similarity_threshold": 0.68,
        "rerank": False,
        "citation_format": "[{source_doc}, p. {page}]",
    },
}
```

### 5.3 Embedding Model

```
Model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- Multilingual: acoperire RO + DE + EN din cutie
- Dimensiune: 384 dims — rapid, eficient pe CPU
- Alternativă premium: intfloat/multilingual-e5-large (768 dims, mai bun la DE tehnic)
- Self-hosted în RAGFlow — fără apeluri externe
```

---

## 6. Chandra OCR 2 — Pipeline

### 6.1 Documente Suportate

| Document | Câmpuri extrase | Format ieșire | Mascare PII |
|----------|----------------|---------------|-------------|
| Poliță RCA | Nr. poliță, asigurat, vehicul (marca/VIN), valabilitate, primă RON/EUR | JSON | CNP → `1XXXXXXXX04` |
| Certificat RCA | Nr. certificat, perioadă, serie/nr., asigurător | JSON | ❌ |
| Poliță CASCO | Nr. poliță, franciză %, limite, clauze, excluderi | JSON | CNP/CUI masked |
| Certificat PAD | Nr. cert, adresă, zonă risc (A/B), primă | JSON | Adresă parțial |
| KFZ-Schein (DE) | Kennzeichen, VIN, Haftpflicht-Nr, Versicherungsbeginn | JSON | Personalausweis masked |
| Dosar daună | Nr. dosar, data eveniment, descriere, valoare estimată | JSON | ❌ |
| Constatare amiabilă | Ambii șoferi, daune, semnături, schiță | JSON | CNP → masked |
| CI / Ausweis | Nume, prenume, CNP/Personalausweis-Nr | JSON (masked) | CNP complet masked |
| Factură reparație | Emitent, CUI, total RON/EUR, TVA, piese | JSON | ❌ |

### 6.2 OCR Flow

```
Document Upload (PDF / JPG / PNG / TIFF)
        │
        ▼
  Pre-processing (Chandra OCR 2)
  - Deskew + denoise
  - Auto-rotate
  - Language detection (ro/de/en)
        │
        ▼
  POST /v2/extract
  {
    "document_type": "rca_policy",
    "language": "auto",
    "output_schema": "rca_policy_v2",
    "pii_masking": true,           ← GDPR Art. 5 — OBLIGATORIU
    "confidence_threshold": 0.85
  }
        │
        ▼
  Structured JSON response
  {
    "policy_number": "RCA-2026-XXXXXX",
    "insured_name": "Ion Popescu",
    "cnp_masked": "1XXXXXXXX04",
    "vehicle": {
      "make": "Dacia",
      "model": "Logan",
      "vin": "UU1R...",
      "registration": "B-123-ABC"
    },
    "valid_from": "2026-01-01",
    "valid_to": "2027-01-01",
    "premium_ron": 1250.00,
    "insurer": "Allianz-Tiriac",
    "confidence": 0.94,
    "ocr_warnings": []
  }
        │
        ├── confidence < 0.85 → Flag for manual review
        │
        ▼
  Validate against SQLite (broker_ocr_validate_policy)
        │
        ▼
  Index full text → RAGFlow KB (kb_rca_casco_ro)
        │
        ▼
  Upload original → GCS Bucket (originals/rca/{client_id}/{filename})
        │
        ▼
  Audit log entry → document_audit_log table
```

### 6.3 OCR API Wrapper

File: `mcp-server/insurance_broker_mcp/tools/ocr_tools.py`

```python
import httpx, os, base64
from typing import Optional

CHANDRA_OCR_BASE_URL = os.getenv("CHANDRA_OCR_URL", "http://localhost:8888")
CHANDRA_OCR_API_KEY  = os.getenv("CHANDRA_OCR_API_KEY", "")

DOCUMENT_SCHEMAS = {
    "rca_policy":       "rca_policy_v2",
    "casco_policy":     "casco_policy_v1",
    "pad_cert":         "pad_certificate_v1",
    "kfz_policy":       "kfz_policy_de_v1",
    "claim_file":       "claim_dossier_v1",
    "constatare":       "constatare_amiabila_v1",
    "invoice_repair":   "invoice_repair_v1",
    "identity_doc":     "identity_masked_v1",
}

async def ocr_extract_document(
    file_bytes: bytes,
    filename: str,
    document_type: str,
    language: str = "auto",
    confidence_threshold: float = 0.85,
) -> dict:
    """
    Send document to Chandra OCR 2. PII masking always enabled (GDPR Art. 5).
    Returns structured JSON + confidence scores + warnings.
    """
    schema = DOCUMENT_SCHEMAS.get(document_type, "generic_v1")
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            f"{CHANDRA_OCR_BASE_URL}/v2/extract",
            headers={"X-Api-Key": CHANDRA_OCR_API_KEY},
            files={"file": (filename, file_bytes)},
            data={
                "document_type":        document_type,
                "output_schema":        schema,
                "language":             language,
                "pii_masking":          "true",
                "confidence_threshold": str(confidence_threshold),
            }
        )
        resp.raise_for_status()
        result = resp.json()
        # Flag low-confidence results for manual review
        if result.get("confidence", 1.0) < confidence_threshold:
            result["requires_manual_review"] = True
            result["review_reason"] = f"Confidence {result['confidence']:.0%} < threshold {confidence_threshold:.0%}"
        return result
```

---

## 7. Admin PDF-to-Web

### 7.1 Funcționalitate

Fiecare PDF ingerat prin Chandra OCR 2 sau upload manual este convertit automat într-o **vizualizare web structurată** în panoul Admin, fără a expune fișierul brut.

**Caracteristici Admin PDF-to-Web:**
- Randare HTML din JSON structurat (nu embed PDF) → performanță + securitate
- Câmpuri evidențiate cu cod culoare: ✅ valid, ⚠️ discrepanță, ❌ lipsă
- Buton **"Aprobare"** (Senior Broker / Admin) cu semnătură digitală timestamp
- Buton **"Respingere + Notă"** → alertă automată în Claims queue
- Download PDF original (cu watermark "VERIFICAT" după aprobare)
- Audit trail vizibil: cine a aprobat, când, ce acțiuni s-au efectuat

### 7.2 Admin Router

File: `admin/router.py` — extensii noi:

```python
# admin/router.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from shared.auth import require_role

router = APIRouter(prefix="/admin")

@router.get("/documents", response_class=HTMLResponse)
async def list_documents(user=Depends(require_role(["admin", "compliance_officer", "senior_broker"]))):
    """Document management dashboard — all ingested documents with status."""
    ...

@router.get("/documents/{doc_id}/view", response_class=HTMLResponse)
async def view_document_web(
    doc_id: str,
    user=Depends(require_role(["admin", "compliance_officer", "senior_broker", "claims_adjuster"]))
):
    """
    PDF-to-Web viewer: renders structured JSON fields as HTML.
    No raw PDF served — only structured data with PII masking applied.
    """
    ...

@router.post("/documents/{doc_id}/approve")
async def approve_document(
    doc_id: str,
    user=Depends(require_role(["admin", "senior_broker"]))
):
    """Approve an OCR-extracted document. Records approver + timestamp."""
    ...

@router.post("/documents/{doc_id}/reject")
async def reject_document(
    doc_id: str,
    reason: str,
    user=Depends(require_role(["admin", "senior_broker", "claims_adjuster"]))
):
    """Reject a document with a note — triggers Claims queue alert."""
    ...

@router.get("/claims", response_class=HTMLResponse)
async def claims_dashboard(user=Depends(require_role(["admin", "claims_adjuster", "senior_broker"]))):
    """Claims AI TPSH dashboard — validation status, pending reviews."""
    ...
```

### 7.3 Admin Templates

File: `admin/templates/document_view.html`

```html
<!-- Structured web view — NO raw PDF embed -->
<div class="document-card" data-doc-id="{{ doc.id }}" data-status="{{ doc.status }}">
  <div class="doc-header">
    <span class="badge badge-{{ doc.status }}">{{ doc.status | upper }}</span>
    <span class="doc-type">{{ doc.document_type }}</span>
    <span class="confidence">OCR Confidence: {{ doc.confidence | round(1) }}%</span>
  </div>

  <div class="fields-grid">
    {% for field, value in doc.fields.items() %}
    <div class="field {% if field in doc.discrepancies %}field-error{% elif value %}field-ok{% else %}field-missing{% endif %}">
      <label>{{ field | replace('_', ' ') | title }}</label>
      <span class="value">{{ value or '— lipsă —' }}</span>
      {% if field in doc.discrepancies %}
      <span class="discrepancy-note">⚠️ {{ doc.discrepancies[field] }}</span>
      {% endif %}
    </div>
    {% endfor %}
  </div>

  {% if doc.requires_manual_review %}
  <div class="review-banner">
    ⚠️ Verificare manuală necesară — confidence sub prag
  </div>
  {% endif %}

  <div class="action-bar" {% if not user.can_approve %}style="display:none"{% endif %}>
    <button class="btn-approve" onclick="approveDoc('{{ doc.id }}')">✅ Aprobare</button>
    <button class="btn-reject" onclick="rejectDoc('{{ doc.id }}')">❌ Respingere</button>
    <a class="btn-download" href="/admin/documents/{{ doc.id }}/original">⬇️ Original PDF</a>
  </div>

  <div class="audit-trail">
    <h4>Audit Trail</h4>
    {% for entry in doc.audit_log %}
    <div class="audit-entry">
      {{ entry.timestamp }} — {{ entry.user }} — {{ entry.action }}
    </div>
    {% endfor %}
  </div>
</div>
```

---

## 8. Document Validation Pipeline

### 8.1 Flux Validare Automată

```
OCR JSON Result
      │
      ▼
 Step 1: Schema Validation
 - Câmpuri obligatorii prezente?
 - Formate corecte (date ISO, sume numerice)?
 - CNP valid (algoritm checksum)?
      │
      ├── FAIL → status: "schema_error" → manual review queue
      │
      ▼
 Step 2: DB Cross-validation (SQLite)
 - client_id match pe baza numelui + vehiculului?
 - Poliță nr. deja în DB? (update vs. create)
 - Perioadă valabilitate în conflict cu altă poliță activă?
      │
      ├── MISMATCH → status: "discrepancy" → flag fields
      │
      ▼
 Step 3: Business Rules
 - RCA: Perioadă max 12 luni? Suma min 1.22M EUR?
 - PAD: Zonă risc A sau B corectă?
 - KFZ: Kennzeichen format valid (DE)?
 - CASCO: Franciză % în interval acceptat (0-20%)?
      │
      ├── VIOLATION → status: "compliance_warning" → alert broker
      │
      ▼
 Step 4: Expiry Alerts
 - Scadență < 45 zile (RCA) → renewal alert
 - Scadență < 30 zile (PAD, CASCO, KFZ) → renewal alert
      │
      ▼
 Step 5: RAGFlow Index
 - Ingest text + metadata → KB corespunzătoare
 - Stocare original → GCS bucket
 - Audit log entry
      │
      ▼
 status: "validated" | "pending_review" | "approved"
```

### 8.2 Validation Rules Engine

```python
# mcp-server/insurance_broker_mcp/tools/ocr_tools.py

VALIDATION_RULES = {
    "rca_policy": {
        "required_fields": ["policy_number", "insured_name", "vehicle", "valid_from",
                            "valid_to", "premium_ron", "insurer"],
        "business_rules": [
            {
                "rule": "max_duration_days",
                "check": lambda d: (d["valid_to"] - d["valid_from"]).days <= 366,
                "message": "RCA: Perioadă > 12 luni — verificare necesară",
            },
            {
                "rule": "min_liability_eur",
                "check": lambda d: d.get("liability_limit_eur", 0) >= 1_220_000,
                "message": "RCA: Limită răspundere sub minimul legal (1.22M EUR)",
                "severity": "compliance_warning",
            },
        ],
    },
    "pad_cert": {
        "required_fields": ["cert_number", "address", "risk_zone", "premium"],
        "business_rules": [
            {
                "rule": "valid_risk_zone",
                "check": lambda d: d.get("risk_zone") in ["A", "B"],
                "message": "PAD: Zonă risc invalidă — trebuie A sau B",
                "severity": "schema_error",
            },
        ],
    },
    "kfz_policy": {
        "required_fields": ["kennzeichen", "vin", "policy_number", "valid_from"],
        "business_rules": [
            {
                "rule": "kennzeichen_format",
                "check": lambda d: bool(re.match(r"^[A-ZÄÖÜ]{1,3}-[A-Z]{1,2}\s?\d{1,4}[EH]?$",
                                                  d.get("kennzeichen", ""))),
                "message": "KFZ: Format Kennzeichen invalid",
            },
        ],
    },
}
```

---

## 9. Grounded Citations

### 9.1 Principiu

Fiecare răspuns generat de Alex folosind RAG **trebuie să includă citări precise** la sursele din knowledge base. Citările sunt atașate automat la output-ul tool-ului `broker_rag_search`.

### 9.2 Format Citări

```
Exemplu output broker:

> Conform condițiilor generale CASCO, clauza de furt acoperă sustragerea
> totală a vehiculului, cu franciză standard 10% din valoarea de piață.
> *(Sursă: kb_rca_casco_ro · CASCO-Generali-2025.pdf, p. 4, Cl. 3.2.1 · Relevanță: 91%)*

> Nach den allgemeinen Versicherungsbedingungen der Kaskoversicherung gilt
> der Diebstahlschutz ab vollständiger Entwendung des Fahrzeugs.
> *(Quelle: kb_kfz_de · AXA-Vollkasko-AVB-2024.pdf, S. 7, § 4.1 · Relevanz: 88%)*
```

### 9.3 Citation Engine

```python
# mcp-server/insurance_broker_mcp/tools/rag_tools.py

def _format_citation(chunk: dict, kb_name: str) -> str:
    """Build a grounded citation string from a RAGFlow chunk."""
    meta = chunk.get("metadata", {})
    doc_name = meta.get("source_document", "document necunoscut")
    page = meta.get("page_number")
    clause = meta.get("clause") or meta.get("section") or meta.get("article")
    score_pct = round(chunk.get("similarity", 0) * 100, 0)

    parts = [f"**{kb_name}** · {doc_name}"]
    if page:
        parts.append(f"p. {page}")
    if clause:
        parts.append(f"Cl. {clause}")
    parts.append(f"Relevanță: {score_pct:.0f}%")

    return "*(Sursă: " + " · ".join(parts) + ")*"


async def broker_rag_search_fn(
    query: str,
    knowledge_base: str = "kb_rca_casco_ro",
    top_k: int = 4,
    include_citations: bool = True,
) -> str:
    """
    Semantic search în RAGFlow. Returnează pasaje relevante + citări grounded.
    Citările includ: KB name, filename, pagina, clauza, scorul de relevanță.
    """
    config = RETRIEVAL_CONFIG.get(knowledge_base, RETRIEVAL_CONFIG["default"])
    # ... RAGFlow API call ...
    results = []
    for chunk in ragflow_response["chunks"]:
        passage = chunk["content"]
        citation = _format_citation(chunk, knowledge_base) if include_citations else ""
        results.append(f"{passage}\n{citation}")
    return "\n\n---\n\n".join(results)
```

### 9.4 Anti-Hallucination Guard

```python
# Dacă RAGFlow returnează 0 rezultate sau similarity < threshold:
if not chunks or max(c["similarity"] for c in chunks) < config["similarity_threshold"]:
    return (
        "⚠️ Nu am găsit informații verificate în knowledge base pentru această întrebare.\n"
        "Vă rog consultați direct documentele originale sau contactați asigurătorul.\n"
        "Nu pot genera un răspuns fără sursă documentată pentru întrebări de conformitate."
    )
```

---

## 10. MCP Tool Extensions

### 10.1 Noi tool-uri MCP

| Tool | Descriere | Input | Output |
|------|-----------|-------|--------|
| `broker_rag_search` | Căutare semantică în KB (cu citări) | query, kb_name, top_k | pasaje + citări grounded |
| `broker_rag_ingest_document` | Upload + indexare document | file_bytes, filename, doc_type, client_id | ingestion_id + audit entry |
| `broker_rag_get_context` | Context RAG pentru un client | client_id, topic | pasaje relevante filtr. pe client |
| `broker_rag_delete_document` | Șterge document (GDPR Art. 17) | ragflow_doc_id, client_id, reason | confirmare + audit |
| `broker_ocr_extract` | OCR document via Chandra OCR 2 | file_base64, filename, doc_type, lang | JSON structurat + confidence |
| `broker_ocr_validate_policy` | OCR + validare automată vs. DB | file_base64, policy_type, client_id | raport validare + discrepanțe |
| `broker_admin_document_status` | Status document în Admin queue | doc_id | status, reviewer, aprobare |

### 10.2 Tool Signatures (MCP)

```python
@mcp.tool()
async def broker_rag_search(
    query: str,
    knowledge_base: str = "kb_rca_casco_ro",
    top_k: int = 4,
    language: str = "auto",
    include_citations: bool = True,
) -> str:
    """
    Căutare semantică în RAGFlow knowledge base.
    Returnează pasaje relevante cu citări grounded (filename, pagina, clauza, relevanță %).
    Folosește pentru răspunsuri despre: condiții polițe, reguli conformitate ASF/BaFin,
    proceduri daune, comparații tarife. NU generează răspunsuri fără sursă documentată.
    """

@mcp.tool()
async def broker_ocr_extract(
    file_base64: str,
    filename: str,
    document_type: str,
    language: str = "auto",
    client_id: Optional[str] = None,
) -> dict:
    """
    Extrage date structurate dintr-un document scanat/fotografiat.
    PII (CNP, CUI, Personalausweis) mascat conform GDPR Art. 5.
    document_type: rca_policy | casco_policy | pad_cert | kfz_policy |
                   claim_file | constatare | invoice_repair | identity_doc
    Linkează opțional datele extrase la profilul clientului existent.
    """

@mcp.tool()
async def broker_ocr_validate_policy(
    file_base64: str,
    filename: str,
    policy_type: str,
    expected_client_id: Optional[str] = None,
) -> dict:
    """
    OCR document poliță + validare automată vs. baza de date broker.
    Returnează: match_status, discrepancies{}, validity_period, expiry_alert,
    compliance_warnings[], requires_manual_review.
    policy_type: rca | casco | pad | kfz
    """

@mcp.tool()
async def broker_rag_delete_document(
    ragflow_doc_id: str,
    client_id: str,
    reason: str,
) -> str:
    """
    Șterge un document din RAGFlow + SQLite audit log (GDPR Art. 17 — dreptul la ștergere).
    Necesită client_id valid și motiv documentat.
    Înregistrează: doc_id, client_id, user, timestamp, reason în ștergere_audit_log.
    """
```

---

## 11. GDPR & Compliance

### 11.1 Constrângeri Implementate

| Articol GDPR | Implementare | Tool/Modul |
|-------------|-------------|------------|
| Art. 5 — Minimizare date | CNP/CUI/Steuernummer mascat post-OCR înainte de indexare | `ocr_tools.py` — `pii_masking: true` (non-optional) |
| Art. 17 — Drept la ștergere | RAGFlow delete-document API + SQLite CASCADE + GCS delete | `broker_rag_delete_document` |
| Art. 25 — Privacy by design | Mascare PII în Chandra OCR 2 obligatorie; nu se stochează text brut cu CNP | `ocr_tools.py` |
| Art. 32 — Securitate | Acces KB autentificat (RAGFLOW_API_KEY); TLS Nginx; private network | Docker Compose + Nginx |
| Art. 13/14 — Transparență | Citările grounded arată sursa exactă — clientul știe de unde vine info | `broker_rag_search` citations |
| ASF Norma 20/2023 | Audit log complet la fiecare ingestion (client_id, timestamp, doc_type, user) | `document_audit_log` table |
| BaFin MaGo 2022 | Retention index 7 ani pentru polițe DE — GCS lifecycle policy | GCS bucket config |

### 11.2 Audit Log Schema

```sql
-- SQLite: mcp-server/insurance_broker.db
CREATE TABLE document_audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id       TEXT NOT NULL,
    document_type   TEXT NOT NULL,
    ragflow_doc_id  TEXT,
    gcs_path        TEXT,
    filename        TEXT NOT NULL,
    action          TEXT NOT NULL,  -- 'ingested' | 'validated' | 'approved' | 'rejected' | 'deleted'
    performed_by    TEXT NOT NULL,  -- username sau 'mcp_server'
    performed_at    TEXT NOT NULL DEFAULT (datetime('now')),
    discrepancies   TEXT,           -- JSON string
    notes           TEXT,
    ip_address      TEXT
);

CREATE TABLE stergere_audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ragflow_doc_id  TEXT NOT NULL,
    client_id       TEXT NOT NULL,
    requested_by    TEXT NOT NULL,
    requested_at    TEXT NOT NULL DEFAULT (datetime('now')),
    reason          TEXT NOT NULL,
    confirmed_by    TEXT,           -- Admin who confirmed deletion
    confirmed_at    TEXT,
    gdpr_article    TEXT DEFAULT 'Art. 17'
);
```

---

## 12. Plan 5 Faze · 12 Săptămâni

### Faza 1 — Foundation & Infrastructure (Săptămânile 1–2)

**Obiectiv:** Hetzner live cu Docker Compose complet; RAGFlow + Chandra OCR 2 pornite; KB-uri create (goale).

**Responsabil:** DevOps / Backend Lead
**Deliverables:**

- [ ] Provisionare server Hetzner CPX51 (Ubuntu 24.04)
- [ ] `docker-compose.yml` complet cu toate 8 servicii (broker-app, ragflow, elasticsearch, minio, mysql, chandra-ocr, redis, nginx)
- [ ] Certbot / Let's Encrypt TLS pentru `broker.demobrokersrl.ro`
- [ ] Creare 7 Knowledge Bases în RAGFlow via API (goale)
- [ ] Adăugare tabel `document_audit_log` și `stergere_audit_log` în schema SQLite
- [ ] Variables `.env.production` complete (RAGFLOW_API_KEY, CHANDRA_OCR_API_KEY, MINIO_*, MYSQL_*)
- [ ] Smoke test: RAGFlow health check ✅, Chandra OCR health check ✅
- [ ] Deploy `broker-app` pe Hetzner (migrare de pe Cloud Run sau coexistență)

**Acceptance criteria:**
- `docker-compose up -d` → toate serviciile `healthy`
- RAGFlow UI accesibil pe `https://broker.demobrokersrl.ro/ragflow-ui/`
- Chandra OCR `/health` returnează `200 OK`

---

### Faza 2 — RAGFlow Integration & KB Seeding (Săptămânile 3–5)

**Obiectiv:** RAG search funcțional cu citări; KB-uri populate cu documente seed.

**Responsabil:** Backend / ML Engineer
**Deliverables:**

- [ ] Extindere `rag_tools.py`: `broker_rag_search_fn` cu citări grounded
- [ ] Implementare `broker_rag_ingest_document` (upload fișier → RAGFlow API → index)
- [ ] Implementare `broker_rag_get_context` (filtrare per client_id)
- [ ] Implementare `broker_rag_delete_document` (GDPR Art. 17)
- [ ] Înregistrare 4 noi tool-uri MCP în `server.py`
- [ ] **KB Seeding:**
  - `kb_compliance_asf`: Legea 132/2017, Legea 260/2008, ASF Norma 20/2023 (PDF-uri publice)
  - `kb_compliance_bafin`: VVG extras, PflVG, BaFin Rundschreiben 10/2017
  - `kb_rca_casco_ro`: Condiții generale sample Allianz-Tiriac RCA + CASCO
  - `kb_claims_ro_de`: Ghid daune complet per asigurător (din `claims_tools.py`)
- [ ] Test e2e: Alex răspunde la "Ce acoperă CASCO pentru furt total?" cu citare din KB

**Acceptance criteria:**
- RAG recall@5 > 80% pe un set de 30 întrebări de conformitate
- Fiecare răspuns RAG include cel puțin o citare `*(Sursă: ...)*`
- Anti-hallucination guard funcționează: 0 răspunsuri fără sursă pentru întrebări de compliance

---

### Faza 3 — Chandra OCR 2 + Claims Pipeline (Săptămânile 6–8)

**Obiectiv:** OCR funcțional pentru toate tipurile de documente; validare automată vs. DB.

**Responsabil:** Backend Engineer + Claims Adjuster (UAT)
**Deliverables:**

- [ ] Creare `ocr_tools.py` complet cu toate 8 tipuri de documente
- [ ] Implementare `broker_ocr_extract` MCP tool
- [ ] Implementare `broker_ocr_validate_policy` cu `VALIDATION_RULES` engine
- [ ] Auto-trigger `broker_check_rca_validity` la OCR certificat RCA
- [ ] Upload document → GCS bucket (`originals/{doc_type}/{client_id}/{filename}`)
- [ ] Audit log entry la fiecare OCR (din `document_audit_log`)
- [ ] Test PII masking: CNP niciodată în plaintext în RAGFlow index
- [ ] Ingestare text OCR rezultat → KB corespunzătoare (automatizat)
- [ ] Endpoint upload document în Chainlit UI (`app.py`) — drag & drop PDF/JPG

**Acceptance criteria:**
- RCA OCR accuracy > 95% field extraction pe 20 polițe scanate test
- Validare detectează discrepanțe (CNP mismatch, dată expirare greșită) corect
- 0 CNP/CUI/Steuernummer în plaintext în nicio tabelă sau index RAGFlow
- Latență OCR < 8s/document

---

### Faza 4 — Admin PDF-to-Web + Validation Dashboard (Săptămânile 9–10)

**Obiectiv:** Admin panel complet cu vizualizare web, aprobare/respingere, claims dashboard.

**Responsabil:** Frontend / Full-Stack Engineer
**Deliverables:**

- [ ] Extindere `admin/router.py`: `/documents`, `/documents/{id}/view`, `/approve`, `/reject`, `/claims`
- [ ] Template `admin/templates/document_view.html` — web view structurat (fără PDF embed brut)
- [ ] Template `admin/templates/claims_dashboard.html` — Claims AI TPSH queue
- [ ] Implementare RBAC complet (`shared/auth.py`) — 6 roluri conform matricei §3.1
- [ ] Notificări email la: document respins, discrepanță detectată, scadență < 45 zile RCA
- [ ] Watermark "VERIFICAT" pe PDF original după aprobare (weasyprint)
- [ ] `broker_admin_document_status` MCP tool
- [ ] Pagina de istoric documente per client (cu link RAGFlow source)

**Acceptance criteria:**
- Broker (rol) NU poate accesa `/admin/documents` — 403
- Admin poate aproba/respinge document cu audit trail complet
- PDF-to-Web renderează toate câmpurile cu cod culoare corect (verde/galben/roșu)
- Email notificare trimisă în < 2 minute de la eveniment

---

### Faza 5 — Production Hardening, Load Testing & GDPR Audit (Săptămânile 11–12)

**Obiectiv:** Sistem production-ready, auditat GDPR, documentat, live pe Hetzner.

**Responsabil:** Senior Engineer + Compliance Officer
**Deliverables:**

- [ ] **Load test:** 50 request-uri OCR concurente → latență < 10s, 0 erori 5xx
- [ ] **Load test:** 200 request-uri RAG search concurente → latență < 2s
- [ ] **PII audit:** Scanare completă RAGFlow index pentru CNP/CUI pattern — 0 leaks
- [ ] **Backup:**
  - RAGFlow data → GCS bucket sync (zilnic, retenție 30 zile)
  - SQLite → GCS snapshot (zilnic)
  - Elasticsearch → GCS snapshot API
- [ ] **Multilingual benchmark:** RO queries → RO KBs, DE queries → DE KBs (language routing 100%)
- [ ] **Monitoring:** Uptime check (UptimeRobot sau Hetzner monitoring) + alertă email la downtime
- [ ] **GDPR Art. 17 test:** Cerere ștergere completă per client → documente șterse din RAGFlow + GCS + SQLite
- [ ] **Documentație:** README actualizat, runbook Hetzner, onboarding admin guide
- [ ] **Go-live checklist:** TLS valid, toate porturile interne private, RAGFlow UI fără acces public

**Acceptance criteria:**
- Toate testele de load trec fără degradare
- 0 CNP/CUI în plaintext confirmat de PII audit
- GDPR erasure completă în < 5 minute de la cerere
- Uptime > 99.5% pe primele 7 zile post-launch

---

## 13. Costuri / Cost Model

### 13.1 Infrastructure (Hetzner)

| Resursă | Tip | Cost lunar (EUR) | Note |
|---------|-----|-----------------|------|
| Server principal | CPX51 (16 vCPU, 32GB RAM, 360GB NVMe) | ~75 EUR/lună | RAGFlow + ES + App |
| Floating IP | IPv4 static | ~3 EUR/lună | DNS stabil |
| Backup server | Hetzner Snapshots (zilnic) | ~15 EUR/lună | 20% din server cost |
| Volume suplimentar | 500GB (documente OCR originals) | ~25 EUR/lună | dacă NVMe insuficient |
| **Total Hetzner** | | **~118 EUR/lună** | |

### 13.2 External Services

| Serviciu | Plan | Cost lunar (EUR) | Note |
|---------|------|-----------------|------|
| Chandra OCR 2 | Self-hosted (inclus în Hetzner) | 0 EUR | Docker image |
| Chandra OCR 2 (cloud) | Alternativă: 1000 doc/zi | ~200 EUR/lună | Dacă nu self-hosted |
| GCS Bucket | Standard storage 100GB + ops | ~3 EUR/lună | Documente originale |
| Google Firestore | Free tier (1GB, 50K ops/zi) | 0 EUR | Demo scale |
| Let's Encrypt TLS | Gratuit | 0 EUR | Auto-reînnoire Certbot |
| Anthropic API | claude-sonnet-4-6 (RAG answers) | ~50–150 EUR/lună | Estimat 100K tokens/zi |
| **Total servicii externe** | | **~53–353 EUR/lună** | depinde de OCR mode |

### 13.3 Cost Total Estimat

| Scenariul | Cost lunar | Note |
|-----------|-----------|------|
| **Minim** (OCR self-hosted, volume mic) | **~170 EUR/lună** | Hetzner + GCS + Claude API |
| **Standard** (OCR self-hosted, volum mediu) | **~220 EUR/lună** | + monitoring tools |
| **Cloud OCR** (Chandra cloud API) | **~370 EUR/lună** | Dacă self-hosted indisponibil |

### 13.4 Cost per Document Procesat

```
OCR (self-hosted): ~0 EUR/doc (cost inclus în server)
RAG indexare:      ~0 EUR/doc (Elasticsearch self-hosted)
RAG search:        ~0.001 EUR/query (Claude API pentru answer generation)
GCS storage:       ~0.02 EUR/GB/lună (documente originale)

Estimat 500 doc/lună → cost marginal: ~0.5 EUR/lună extra GCS
```

---

## 14. Environment Variables

```bash
# .env.production — Hetzner deployment

# ─── RAGFlow ──────────────────────────────────────────────────────────────
RAGFLOW_API_KEY=rf_live_xxxxxxxxxxxx
RAGFLOW_BASE_URL=http://ragflow:9380
RAGFLOW_DEFAULT_KB=kb_rca_casco_ro
RAGFLOW_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

# ─── Chandra OCR 2 ────────────────────────────────────────────────────────
CHANDRA_OCR_URL=http://chandra-ocr:8888
CHANDRA_OCR_API_KEY=ch_live_xxxxxxxxxxxx

# ─── MinIO (RAGFlow object storage) ───────────────────────────────────────
MINIO_USER=ragflow_admin
MINIO_PASSWORD=<strong_password_here>

# ─── MySQL (RAGFlow metadata) ─────────────────────────────────────────────
MYSQL_PASSWORD=<strong_password_here>

# ─── Existing (unchanged) ─────────────────────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
GCS_BUCKET_NAME=demo-broker-srl-docs
GOOGLE_APPLICATION_CREDENTIALS=/app/gcs-key.json
REDIS_URL=redis://redis:6379/0

# ─── Admin RBAC ───────────────────────────────────────────────────────────
ADMIN_JWT_SECRET=<strong_secret_here>
ADMIN_SESSION_TIMEOUT_MINUTES=60
```

---

## 15. Testing Strategy

### 15.1 Structura Teste

```
tests/
├── unit/
│   ├── test_ocr_tools.py          # Mock Chandra OCR 2 → JSON response per doc_type
│   ├── test_rag_search.py         # Mock RAGFlow search + citation generation
│   ├── test_validation_rules.py   # Business rules engine per doc_type
│   └── test_pii_masking.py        # CNP/CUI/Steuernummer niciodată în plaintext
├── integration/
│   ├── test_ocr_validate.py       # OCR → validate → DB cross-check (live)
│   ├── test_rag_ingest.py         # Upload doc → RAGFlow index → search retrieval
│   └── test_admin_workflow.py     # Upload → OCR → validate → Admin approve → audit
├── e2e/
│   ├── test_claims_pipeline.py    # End-to-end claim: upload constatare → dosar daună creat
│   ├── test_multilingual.py       # RO query → RO KB, DE query → DE KB
│   └── test_gdpr_erasure.py       # Art. 17: delete request → 0 traces remaining
└── load/
    ├── locustfile.py              # 50 concurrent OCR + 200 concurrent RAG search
    └── k6_rag_bench.js            # k6 load test pentru RAG search latency
```

### 15.2 Criterii de Acceptare Finale

| Test | Condiție de trecere |
|------|-------------------|
| RCA OCR accuracy | > 95% extracție câmpuri pe set de 20 polițe scanate |
| CASCO/PAD/KFZ OCR accuracy | > 90% extracție câmpuri pe set de 10 doc/tip |
| RAG recall@5 | > 80% — pasaj corect în top 5 pentru 30 întrebări de conformitate |
| Citation coverage | 100% răspunsuri RAG compliance includ citare grounded |
| PII masking | 0 CNP/CUI/Steuernummer plaintext în nicio tabelă sau index |
| Latență OCR | < 8s/document (single, fără concurență) |
| Latență RAG search | < 1.5s/query (fără reranking) |
| Latență RAG + rerank | < 3s/query |
| GDPR erasure | 0 urme document după ștergere completă (RAGFlow + GCS + SQLite) |
| Load test OCR | 50 req. concurente → latență < 10s, 0 erori 5xx |
| Load test RAG | 200 req. concurente → latență < 2s, 0 erori 5xx |
| Uptime | > 99.5% primele 7 zile post-launch |
| RBAC | Broker → 403 pe /admin; Client → acces limitat la propriile dosare |

---

## 16. References

### Intern
- `mcp-server/insurance_broker_mcp/tools/rag_tools.py` — RAG scaffold existent (ChromaDB Layer 1)
- `mcp-server/insurance_broker_mcp/tools/claims_tools.py` — Claims guidance + insurer data
- `mcp-server/insurance_broker_mcp/tools/drive_tools.py` — GCS upload existent
- `admin/router.py` — Admin panel (extensibil)
- `shared/auth.py` — Autentificare (extensibil cu RBAC)
- `Dockerfile` — Build existent (baza pentru docker-compose)

### RAGFlow
- GitHub: `infiniflow/ragflow` (v0.17+)
- RAGFlow REST API: `http://ragflow:9380/v1/`
- RAGFlow Web UI: `http://ragflow:9381`

### Chandra OCR 2
- API Docs: `/v2/docs` (deployment intern)
- Endpoint extracție: `POST /v2/extract`
- Health check: `GET /health`

### Regulatoriu
- ASF Norma 20/2023 — Cerințe arhivare documente asigurare (RO)
- BaFin MaGo 2022 — IT-Mindestvorgaben Versicherungsunternehmen (DE)
- Legea 132/2017 — Asigurarea obligatorie RCA (RO)
- Legea 260/2008 — Asigurarea obligatorie a locuințelor PAD (RO)
- VVG (Versicherungsvertragsgesetz) — Contract asigurare DE
- PflVG (Pflichtversicherungsgesetz) — Asigurare obligatorie auto DE
- GDPR Regulamentul (UE) 2016/679

---

*MCP Server: insurance_broker_mcp | Infrastructure: Hetzner CPX51 + Docker Compose*
*RAGFlow: infiniflow/ragflow:v0.17+ | OCR: Chandra OCR 2 | DB: SQLite + Firestore + GCS*
*Versiune plan: 2.0 | Data: 2026-03-31 | Status: Approved*
