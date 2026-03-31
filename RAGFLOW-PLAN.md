# RAGFlow + Chandra OCR 2 — Plan Complet Integrare
## Insurance Broker Agent · Claims AI TPSH · Demo Broker SRL

**Data:** 2026-03-31
**Status:** Specification Completă
**Autor:** Alex AI / Demo Broker SRL
**Scope:** Pipeline complet document intelligence RO + DE — OCR, RAG, validare, UI admin, roluri, costuri

---

## Cuprins

1. [Obiectiv & Viziune](#1-obiectiv--viziune)
2. [Workflow Admin PDF-to-Web](#2-workflow-admin-pdf-to-web)
3. [Validare Documente Client](#3-validare-documente-client)
4. [Arhitectura Docker Compose (Hetzner Germania)](#4-arhitectura-docker-compose-hetzner-germania)
5. [Grounded Citations — Pagină, Bounding Box, Confidence](#5-grounded-citations--pagini-bounding-box-confidence)
6. [Roluri & Permisiuni](#6-roluri--permisiuni)
7. [Costuri Estimative](#7-costuri-estimative)
8. [Plan Implementare — 5 Faze, 12 Săptămâni](#8-plan-implementare--5-faze-12-sptmni)
9. [Stack Tehnic Detaliat](#9-stack-tehnic-detaliat)
10. [Knowledge Bases RAGFlow](#10-knowledge-bases-ragflow)
11. [GDPR & Conformitate](#11-gdpr--conformitate)
12. [Testing & Acceptance Criteria](#12-testing--acceptance-criteria)
13. [Environment Variables](#13-environment-variables)
14. [Referințe](#14-referine)

---

## 1. Obiectiv & Viziune

### 1.1 Problema

Brokerul de asigurări procesează zilnic zeci de documente PDF scanate, formulare completate de mână și acte de identitate. Fluxul curent este manual:

- **Operatorul** primește PDF prin email → deschide → citește → introduce manual în sistem
- **Validarea** documentelor client (CI, contracte, polițe) se face vizual, subiectiv
- **Răspunsurile** agentului Alex se bazează doar pe datele demo din SQLite, nu pe documentele reale

### 1.2 Soluția

Integrarea **RAGFlow** (orchestrator RAG open-source) + **Chandra OCR 2** (motor OCR specializat în documente financiare/asigurări) pentru a crea un pipeline complet:

```
PDF scanat / Fotografie document
          │
          ▼
  [Chandra OCR 2] ──► Tabele, checkbox-uri, text scris de mână
          │
          ▼
  [RAGFlow] ──────────► Orchestrare, chunking, indexare
          │
          ▼
  [FastAPI + Next.js] ► Formular web pre-completat → Admin editează
          │
          ▼
  [PostgreSQL + MinIO] ► Stocare structurată + documente originale
          │
          ▼
  [Alex (Chainlit)] ──► Răspunsuri grounded cu citări din documente
```

### 1.3 Cazuri de Utilizare Principale

| Caz | Actor | Beneficiu |
|---|---|---|
| Upload poliță RCA scanată | Operator Editare | 90% câmpuri completate automat în 8s |
| Validare dosar daună | Operator Validare | Inconsistențe detectate automat, JSON Oracle |
| Răspuns la întrebare despre condiții poliță | Broker/Client | Răspuns citat cu pagina exactă din poliță |
| Audit conformitate ASF | Master Admin | Raport automat cu surse verificabile |

---

## 2. Workflow Admin PDF-to-Web

### 2.1 Flux Detaliat

```
┌─────────────────────────────────────────────────────────────────┐
│  ETAPA 1: UPLOAD                                                 │
│  Admin/Operator → Drag & Drop PDF în Next.js UI                 │
│  → MinIO pre-signed URL → fișier stocat în bucket               │
│  → Job ID returnat → status polling prin WebSocket              │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  ETAPA 2: OCR — Chandra OCR 2                                    │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │ Layout      │  │ Table        │  │ Handwriting             │ │
│  │ Detection   │  │ Extraction   │  │ Recognition             │ │
│  │ (bounding   │  │ (celule,     │  │ (semnături,             │ │
│  │  boxes)     │  │ anteturi)    │  │ valori completate       │ │
│  └─────────────┘  └──────────────┘  │ manual)                 │ │
│  ┌─────────────┐  ┌──────────────┐  └─────────────────────────┘ │
│  │ Checkbox    │  │ Stamp/Seal   │                               │
│  │ Detection   │  │ Detection    │                               │
│  │ (bifat/     │  │ (ștampilă    │                               │
│  │  nebifat)   │  │  validă)     │                               │
│  └─────────────┘  └──────────────┘                               │
│                                                                  │
│  Output: JSON cu coordonate (page, x1,y1,x2,y2) + confidence   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  ETAPA 3: RAGFlow ORCHESTRARE                                    │
│                                                                  │
│  • Mapping câmpuri OCR → schema document (tip poliță/dosar)     │
│  • Cross-reference cu KB (validare valori, coduri, sume)        │
│  • Completare câmpuri lipsă din context RAG                     │
│  • Generare "formular propus" cu nivel de încredere per câmp    │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  ETAPA 4: FORMULAR WEB — Next.js UI                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ [PDF Viewer]          │  [Formular Editabil]             │   │
│  │                       │                                  │   │
│  │  PDF original cu      │  Nr. Poliță: [RCA-2026-XXXX] ✓ │   │
│  │  highlight pe         │  Asigurat:  [Ion Popescu    ] ✓ │   │
│  │  câmpurile extrase    │  Valabil:   [01.01.2026     ] ⚠ │   │
│  │                       │  Primă RON: [1.250,00       ] ✓ │   │
│  │  🟢 = confidence>90%  │  VIN:       [WBA...         ] ✗ │   │
│  │  🟡 = 70-90%          │  CNP:       [MASCAT         ] 🔒│   │
│  │  🔴 = <70%            │                                  │   │
│  │                       │  [Salvează] [Respinge] [Aprobare]│   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  ETAPA 5: EDITARE & APROBARE                                     │
│                                                                  │
│  Operator Editare: modifică câmpuri cu ✗ sau ⚠                  │
│  → Câmpul editat se marchează "manual_override=true"            │
│  → Audit trail: valoarea OCR vs. valoarea editată               │
│  → Submit → Status: "pending_validation"                        │
│                                                                  │
│  Operator Validare: review independent                           │
│  → Aprobă / Respinge / Solicită completări                      │
│  → Dacă aprobat: upsert PostgreSQL + indexare RAGFlow           │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Schema JSON Formular Propus

```json
{
  "job_id": "job_abc123",
  "document_type": "rca_policy",
  "processing_time_ms": 7340,
  "proposed_form": {
    "policy_number": {
      "value": "RCA-2026-123456",
      "confidence": 0.97,
      "page": 1,
      "bbox": [120, 45, 380, 68],
      "source": "ocr_primary",
      "manual_override": false
    },
    "insured_name": {
      "value": "Ion Popescu",
      "confidence": 0.94,
      "page": 1,
      "bbox": [120, 90, 420, 112],
      "source": "ocr_primary",
      "manual_override": false
    },
    "cnp": {
      "value": "MASCAT_GDPR",
      "confidence": 0.99,
      "page": 1,
      "bbox": [120, 130, 300, 150],
      "source": "ocr_primary",
      "pii_masked": true,
      "manual_override": false
    },
    "valid_from": {
      "value": "2026-01-01",
      "confidence": 0.82,
      "page": 1,
      "bbox": [200, 180, 320, 198],
      "source": "ocr_primary",
      "warning": "Date format ambiguous — verify manually",
      "manual_override": false
    },
    "vin": {
      "value": "",
      "confidence": 0.0,
      "page": 2,
      "bbox": null,
      "source": "not_found",
      "requires_manual_entry": true,
      "manual_override": false
    }
  },
  "validation_flags": [
    {"field": "valid_from", "severity": "warning", "message": "Format dată ambiguu"},
    {"field": "vin", "severity": "error", "message": "VIN neextras — câmp obligatoriu"}
  ],
  "rag_cross_checks": [
    {
      "check": "premium_range_validation",
      "result": "pass",
      "detail": "Prima RON 1250 se încadrează în intervalul tipic RCA pentru vehicul de 1.6L"
    }
  ]
}
```

### 2.3 Tipuri de Documente Suportate

| Document | Câmpuri Cheie | Tabele | Checkboxuri | Manuscris |
|---|---|---|---|---|
| Poliță RCA | Nr., asigurat, vehicul, valabilitate, primă | ✗ | ✗ | ✗ |
| Poliță CASCO | Nr., franciză, clauze, limite | ✓ (clauze) | ✓ (clauze opționale) | ✗ |
| Certificat PAD | Nr., adresă, zonă risc, primă | ✗ | ✗ | ✗ |
| Dosar daună | Nr. dosar, data, descriere, estimat | ✓ (articole daune) | ✓ (tipuri daune) | ✓ (declarații) |
| CI / Buletin | Nume, CNP (mascat), adresă | ✗ | ✗ | ✓ (semnătură) |
| KFZ-Schein (DE) | Kennzeichen, VIN, dată înmatriculare | ✗ | ✗ | ✗ |
| Formular BaFin | Toate câmpurile | ✓ | ✓ | ✓ |

---

## 3. Validare Documente Client

### 3.1 Pipeline Validare

```
Document scanat (CI, contract, poliță)
          │
          ├─► OCR Chandra OCR 2 → JSON brut
          │
          ▼
  [Modul Validare Consistență]
          │
          ├─► Verificare 1: Consistență internă document
          │   • Suma primei = primă de bază + taxe (matematică)
          │   • Data expirare > data emitere
          │   • VIN format valid (17 caractere alfanumerice, fără I/O/Q)
          │   • CNP checksum valid (algoritm ASF)
          │
          ├─► Verificare 2: Cross-document consistency
          │   • Numele din CI = Numele din poliță
          │   • Adresa din CI = Adresa din contract
          │   • Nr. înmatriculare din certificat = Nr. din poliță
          │
          ├─► Verificare 3: Cross-DB validation
          │   • Nr. poliță există în SQLite/PostgreSQL?
          │   • Asigurătorul este pe lista autorizată ASF/BaFin?
          │   • Valabilitatea nu este expirată față de astăzi?
          │
          ├─► Verificare 4: RAG semantic validation
          │   • Clauze din poliță vs. condiții standard din KB
          │   • Detectare clauze nestandard sau modificate manual
          │   • Flags: "Clauza X diferă de modelul standard cu 15%"
          │
          └─► Output: JSON Oracle
```

### 3.2 JSON Oracle — Schema

```json
{
  "validation_id": "val_2026_003112",
  "timestamp": "2026-03-31T10:30:00Z",
  "document_type": "rca_policy",
  "client_id": "CLI001",
  "overall_status": "WARNING",
  "score": 78,
  "checks": {
    "internal_consistency": {
      "status": "PASS",
      "checks_run": 6,
      "checks_passed": 6,
      "details": []
    },
    "cross_document": {
      "status": "WARNING",
      "checks_run": 4,
      "checks_passed": 3,
      "details": [
        {
          "check": "name_match_ci_vs_policy",
          "status": "WARNING",
          "message": "CI: 'Ion-Vasile Popescu' vs Poliță: 'Ion Popescu' — diferență minoră în prenume compus",
          "severity": "low",
          "action_required": "Confirmați cu clientul dacă este același titular"
        }
      ]
    },
    "database_validation": {
      "status": "PASS",
      "checks_run": 3,
      "checks_passed": 3,
      "details": []
    },
    "rag_semantic_validation": {
      "status": "WARNING",
      "checks_run": 2,
      "checks_passed": 1,
      "details": [
        {
          "check": "clause_standard_comparison",
          "status": "FLAG",
          "message": "Clauza 4.3 (excluderi CASCO) diferă cu 23% față de modelul standard Allianz 2026",
          "severity": "medium",
          "source_kb": "kb_rca_casco_ro",
          "source_page": 12,
          "action_required": "Verificați cu emitentul dacă este versiunea corectă a condițiilor"
        }
      ]
    }
  },
  "pii_handling": {
    "cnp_detected": true,
    "cnp_masked": true,
    "cnp_stored": false,
    "gdpr_compliant": true
  },
  "recommended_action": "MANUAL_REVIEW",
  "processing_time_ms": 4230
}
```

### 3.3 Niveluri de Severitate & Acțiuni

| Status | Scor | Acțiune Recomandată | Poate fi aprobat de |
|---|---|---|---|
| `PASS` | 90-100 | Aprobare automată posibilă | Operator Validare |
| `WARNING` | 70-89 | Review manual recomandat | Operator Validare |
| `FLAG` | 50-69 | Review obligatoriu + confirmare client | Operator Validare + Master Admin |
| `FAIL` | 0-49 | Respingere document + solicitare reemitere | Master Admin |

---

## 4. Arhitectura Docker Compose (Hetzner Germania)

### 4.1 Specificații Server Hetzner

| Tip | Server | vCPU | RAM | SSD | Preț/lună |
|---|---|---|---|---|---|
| **Minimum viable** | CPX31 | 4 | 8 GB | 160 GB | ~18€ |
| **Recomandat** | CPX41 | 8 | 16 GB | 240 GB | ~28€ |
| **Producție** | CPX51 | 16 | 32 GB | 360 GB | ~68€ |

**Locație:** `nbg1` (Nürnberg) sau `fsn1` (Falkenstein) — Germania, conform GDPR Art. 44-49.

### 4.2 Docker Compose Complet

```yaml
# docker-compose.tpsh.yml
# RAGFlow + Chandra OCR 2 + Full Stack — TPSH Claims AI
# Hetzner CPX41 — 8 vCPU, 16 GB RAM, Germania

version: "3.9"

volumes:
  postgres_data:
  redis_data:
  minio_data:
  ragflow_data:
  chandra_ocr_models:
  nginx_certs:

networks:
  tpsh_internal:
    driver: bridge
  tpsh_external:
    driver: bridge

services:

  # ─────────────────────────────────────────────
  # REVERSE PROXY & SSL
  # ─────────────────────────────────────────────
  nginx:
    image: nginx:1.25-alpine
    container_name: tpsh_nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
      - nginx_certs:/etc/letsencrypt
    networks:
      - tpsh_external
      - tpsh_internal
    depends_on:
      - nextjs
      - fastapi
      - chainlit
      - ragflow
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s

  # ─────────────────────────────────────────────
  # DATABASE — PostgreSQL
  # (Înlocuiește SQLite pentru producție)
  # ─────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: tpsh_postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-tpsh_broker}
      POSTGRES_USER: ${POSTGRES_USER:-broker_admin}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d:ro
    networks:
      - tpsh_internal
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-broker_admin}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─────────────────────────────────────────────
  # CACHE & QUEUE — Redis
  # ─────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: tpsh_redis
    command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks:
      - tpsh_internal
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s

  # ─────────────────────────────────────────────
  # OBJECT STORAGE — MinIO
  # (Documente PDF originale + modele OCR)
  # ─────────────────────────────────────────────
  minio:
    image: minio/minio:latest
    container_name: tpsh_minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minio_admin}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
      MINIO_SITE_REGION: eu-central-1
    volumes:
      - minio_data:/data
    ports:
      - "127.0.0.1:9000:9000"   # API (intern)
      - "127.0.0.1:9001:9001"   # Console (intern)
    networks:
      - tpsh_internal
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s

  # MinIO bucket setup (runs once)
  minio_init:
    image: minio/mc:latest
    container_name: tpsh_minio_init
    depends_on:
      minio:
        condition: service_healthy
    entrypoint: >
      /bin/sh -c "
        mc alias set minio http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD};
        mc mb --ignore-existing minio/tpsh-documents;
        mc mb --ignore-existing minio/tpsh-ocr-results;
        mc mb --ignore-existing minio/tpsh-ragflow-backup;
        mc policy set private minio/tpsh-documents;
        echo 'MinIO buckets initialized';
      "
    networks:
      - tpsh_internal
    restart: on-failure

  # ─────────────────────────────────────────────
  # RAGFlow — Orchestrator RAG
  # ─────────────────────────────────────────────
  ragflow:
    image: infiniflow/ragflow:v0.15.1
    container_name: tpsh_ragflow
    environment:
      RAGFLOW_API_KEY: ${RAGFLOW_API_KEY}
      EMBEDDING_MODEL: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
      RERANKER_MODEL: BAAI/bge-reranker-base
      ES_HOST: ragflow_elasticsearch
      REDIS_HOST: redis
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
    volumes:
      - ragflow_data:/ragflow/data
      - ./ragflow/config:/ragflow/conf:ro
    ports:
      - "127.0.0.1:9380:9380"   # API (intern)
      - "127.0.0.1:9381:9381"   # Web UI (intern, acces via Nginx)
    networks:
      - tpsh_internal
    depends_on:
      - ragflow_elasticsearch
      - redis
      - minio
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G

  # RAGFlow depinde de Elasticsearch pentru vector search
  ragflow_elasticsearch:
    image: elasticsearch:8.13.0
    container_name: tpsh_elasticsearch
    environment:
      - discovery.type=single-node
      - ES_JAVA_OPTS=-Xms1g -Xmx2g
      - xpack.security.enabled=false
      - xpack.ml.enabled=false
    volumes:
      - ./ragflow-es-data:/usr/share/elasticsearch/data
    networks:
      - tpsh_internal
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -q '\"status\":\"green\"\\|\"status\":\"yellow\"'"]
      interval: 30s
      timeout: 10s
      retries: 5
    deploy:
      resources:
        limits:
          memory: 3G

  # ─────────────────────────────────────────────
  # Chandra OCR 2 — Motor OCR
  # ─────────────────────────────────────────────
  chandra_ocr:
    image: chandraai/chandra-ocr:2.0-gpu-optional
    container_name: tpsh_chandra_ocr
    environment:
      CHANDRA_API_KEY: ${CHANDRA_OCR_API_KEY}
      CHANDRA_MODEL_PATH: /models
      CHANDRA_SUPPORTED_LANGS: ro,de,en
      CHANDRA_PII_MASKING: "true"
      CHANDRA_TABLE_DETECTION: "true"
      CHANDRA_HANDWRITING: "true"
      CHANDRA_CHECKBOX_DETECTION: "true"
      CHANDRA_MAX_FILE_SIZE_MB: "50"
      CHANDRA_WORKERS: "4"
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
    volumes:
      - chandra_ocr_models:/models
    ports:
      - "127.0.0.1:8888:8888"   # API (intern)
    networks:
      - tpsh_internal
    depends_on:
      - minio
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 3G
        reservations:
          memory: 2G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8888/health"]
      interval: 30s

  # ─────────────────────────────────────────────
  # FastAPI — Backend API
  # ─────────────────────────────────────────────
  fastapi:
    build:
      context: ./backend
      dockerfile: Dockerfile.fastapi
    container_name: tpsh_fastapi
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      RAGFLOW_API_KEY: ${RAGFLOW_API_KEY}
      RAGFLOW_BASE_URL: http://ragflow:9380
      CHANDRA_OCR_URL: http://chandra_ocr:8888
      CHANDRA_OCR_API_KEY: ${CHANDRA_OCR_API_KEY}
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      ENVIRONMENT: production
    networks:
      - tpsh_internal
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      chandra_ocr:
        condition: service_healthy
      ragflow:
        condition: service_started
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G

  # ─────────────────────────────────────────────
  # Next.js — Admin UI
  # ─────────────────────────────────────────────
  nextjs:
    build:
      context: ./frontend
      dockerfile: Dockerfile.nextjs
    container_name: tpsh_nextjs
    environment:
      NEXT_PUBLIC_API_URL: https://${DOMAIN}/api
      NEXT_PUBLIC_MINIO_PUBLIC_URL: https://${DOMAIN}/files
      NODE_ENV: production
    networks:
      - tpsh_internal
    depends_on:
      - fastapi
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M

  # ─────────────────────────────────────────────
  # Chainlit — Chat UI (Alex AI Broker)
  # ─────────────────────────────────────────────
  chainlit:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: tpsh_chainlit
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      RAGFLOW_API_KEY: ${RAGFLOW_API_KEY}
      RAGFLOW_BASE_URL: http://ragflow:9380
      CHANDRA_OCR_URL: http://chandra_ocr:8888
      CHANDRA_OCR_API_KEY: ${CHANDRA_OCR_API_KEY}
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
    networks:
      - tpsh_internal
    depends_on:
      - fastapi
      - ragflow
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G

  # ─────────────────────────────────────────────
  # Celery Worker — Procesare asincronă OCR/RAG
  # ─────────────────────────────────────────────
  celery_worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.fastapi
    container_name: tpsh_celery_worker
    command: celery -A app.worker worker --loglevel=info --concurrency=4 -Q ocr,rag,validation
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      RAGFLOW_API_KEY: ${RAGFLOW_API_KEY}
      RAGFLOW_BASE_URL: http://ragflow:9380
      CHANDRA_OCR_URL: http://chandra_ocr:8888
      CHANDRA_OCR_API_KEY: ${CHANDRA_OCR_API_KEY}
      MINIO_ENDPOINT: minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
    networks:
      - tpsh_internal
    depends_on:
      - redis
      - postgres
      - chandra_ocr
      - ragflow
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 1G

  # ─────────────────────────────────────────────
  # Celery Beat — Scheduler (renewals, backup)
  # ─────────────────────────────────────────────
  celery_beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.fastapi
    container_name: tpsh_celery_beat
    command: celery -A app.worker beat --loglevel=info --scheduler redis_celery_beat.schedulers:RedisScheduler
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
    networks:
      - tpsh_internal
    depends_on:
      - redis
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
```

### 4.3 Configurare Nginx

```nginx
# nginx/conf.d/tpsh.conf

# Admin UI (Next.js)
server {
    listen 443 ssl http2;
    server_name admin.broker.example.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    location / {
        proxy_pass http://nextjs:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/ {
        proxy_pass http://fastapi:8000/;
        proxy_set_header Host $host;
        client_max_body_size 50M;  # PDF upload
    }
}

# Chat UI (Chainlit / Alex)
server {
    listen 443 ssl http2;
    server_name broker.example.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    location / {
        proxy_pass http://chainlit:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";  # WebSocket
        proxy_set_header Host $host;
    }
}

# RAGFlow UI (acces restricționat la Master Admin)
server {
    listen 443 ssl http2;
    server_name ragflow.broker.example.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # Restricție IP — doar rețea internă broker
    allow 10.0.0.0/8;
    deny all;

    location / {
        proxy_pass http://ragflow:9381;
        proxy_set_header Host $host;
    }
}
```

### 4.4 Diagrama Rețea

```
Internet
    │
    ▼
[Hetzner Firewall]
    │  (:443 only)
    ▼
[Nginx] ─────────────────────────────────────────────
    │                        │                    │
    ▼                        ▼                    ▼
[Next.js :3000]      [Chainlit :8000]     [FastAPI :8000]
    │                        │                    │
    └────────────────────────┴──────────┬─────────┘
                                        │ tpsh_internal network
              ┌─────────────────────────┼───────────────────────┐
              │                         │                       │
              ▼                         ▼                       ▼
     [RAGFlow :9380]          [Chandra OCR :8888]     [PostgreSQL :5432]
              │                         │                       │
              ▼                         │               [Redis :6379]
     [Elasticsearch]                   │                       │
              │                [MinIO :9000]          [Celery Workers]
              └─────────────────────────┘
```

---

## 5. Grounded Citations — Pagini, Bounding Box, Confidence

### 5.1 Schema Citare

Fiecare răspuns al lui Alex generat din RAGFlow include citări verificabile:

```json
{
  "answer": "Conform polițiței CASCO nr. RCA-2026-123456, franciza aplicabilă este de 5% din valoarea daunei, minim 300 EUR.",
  "citations": [
    {
      "citation_id": "c001",
      "text": "Franciza: 5% din valoarea daunei, minim 300 EUR",
      "document": {
        "id": "doc_abc123",
        "filename": "polita_casco_ion_popescu_2026.pdf",
        "upload_date": "2026-03-15",
        "client_id": "CLI001"
      },
      "location": {
        "page": 3,
        "bbox": {
          "x1": 120,
          "y1": 245,
          "x2": 480,
          "y2": 268,
          "unit": "points"
        }
      },
      "confidence": 0.94,
      "confidence_level": "high",
      "ocr_engine": "chandra_ocr_2",
      "rag_similarity": 0.87
    }
  ],
  "grounding_summary": {
    "total_citations": 1,
    "avg_confidence": 0.94,
    "sources_used": ["kb_rca_casco_ro"],
    "answer_grounded": true
  }
}
```

### 5.2 UI Highlighting în Next.js

```typescript
// components/PDFViewerWithHighlights.tsx

interface Citation {
  citation_id: string;
  text: string;
  location: {
    page: number;
    bbox: { x1: number; y1: number; x2: number; y2: number; unit: string };
  };
  confidence: number;
  confidence_level: "high" | "medium" | "low";
}

// Culori per nivel de confidence
const CONFIDENCE_COLORS = {
  high:   { bg: "rgba(34, 197, 94, 0.3)",  border: "#16a34a" },  // verde
  medium: { bg: "rgba(234, 179,  8, 0.3)", border: "#ca8a04" },  // galben
  low:    { bg: "rgba(239,  68, 68, 0.3)", border: "#dc2626" },  // roșu
};

// Highlight-urile sunt redate direct pe canvas-ul PDF (pdf.js)
// Click pe highlight → tooltip cu textul extras + confidence score
// Hover pe citare în chat → scroll automat la pagina corespunzătoare
```

### 5.3 Afișare în Chainlit (Alex Chat)

```python
# În răspunsul lui Alex, citările apar ca footnote-uri clicabile:

response_with_citations = """
Conform condițiilor polițiței dumneavoastră CASCO^[1], franciza este de **5% din valoarea daunei, minim 300 EUR**.

Pentru daune sub valoarea franciței, asigurătorul nu acoperă costurile^[2].

---
**Surse:**
[1] Poliță CASCO Ion Popescu, p. 3 · Confidence: 94% · [📄 Vezi document](...)
[2] Condiții generale CASCO Allianz 2026, p. 8 · Confidence: 89% · [📄 Vezi document](...)
"""
```

### 5.4 Confidence Score — Interpretare

| Interval | Label | Culoare UI | Acțiune |
|---|---|---|---|
| 0.90 – 1.00 | `high` | 🟢 Verde | Afișat direct |
| 0.70 – 0.89 | `medium` | 🟡 Galben | Afișat cu avertisment |
| 0.50 – 0.69 | `low` | 🔴 Roșu | Afișat cu "verificați manual" |
| < 0.50 | `very_low` | ⛔ Gri | Nu se include în răspuns |

---

## 6. Roluri & Permisiuni

### 6.1 Matricea Rolurilor

| Permisiune | Master Admin | Operator Validare | Operator Editare | Client |
|---|:---:|:---:|:---:|:---:|
| **Upload documente** | ✅ | ✅ | ✅ | ✅ (ale sale) |
| **Vizualizare formular OCR propus** | ✅ | ✅ | ✅ | ❌ |
| **Editare câmpuri formular** | ✅ | ✅ | ✅ | ❌ |
| **Aprobare document** | ✅ | ✅ | ❌ | ❌ |
| **Respingere document** | ✅ | ✅ | ❌ | ❌ |
| **Vizualizare JSON Oracle validare** | ✅ | ✅ | ✅ (read-only) | ❌ |
| **Acces RAGFlow UI** | ✅ | ❌ | ❌ | ❌ |
| **Gestionare Knowledge Bases** | ✅ | ❌ | ❌ | ❌ |
| **Vizualizare documente ALL clienți** | ✅ | ✅ | ❌ | ❌ |
| **Vizualizare documente propriile** | ✅ | ✅ | ✅ | ✅ |
| **Rapoarte ASF/BaFin** | ✅ | ✅ | ❌ | ❌ |
| **Gestionare utilizatori** | ✅ | ❌ | ❌ | ❌ |
| **Audit log complet** | ✅ | ❌ | ❌ | ❌ |
| **Chat Alex (Chainlit)** | ✅ | ✅ | ✅ | ✅ |
| **Citări grounded în chat** | ✅ | ✅ | ✅ | ⚠ (fără PII) |
| **Export PDF/XLSX** | ✅ | ✅ | ❌ | ✅ (ale sale) |
| **Ștergere documente (GDPR Art. 17)** | ✅ | ❌ | ❌ | ✅ (ale sale) |
| **Setări sistem** | ✅ | ❌ | ❌ | ❌ |

### 6.2 Schema JWT

```json
{
  "sub": "user_id_uuid",
  "email": "operator@broker.ro",
  "role": "OPERATOR_VALIDARE",
  "permissions": [
    "documents:read:all",
    "documents:write:own",
    "validation:approve",
    "validation:reject",
    "reports:read"
  ],
  "client_id": null,
  "iat": 1743415200,
  "exp": 1743501600
}
```

### 6.3 Fluxul de Aprobare

```
Upload Document
      │
      ▼
[PENDING_OCR] ──► Chandra OCR 2 procesează
      │
      ▼
[PENDING_EDIT] ──► Operator Editare verifică/completează
      │
      ▼
[PENDING_VALIDATION] ──► Operator Validare aprobă/respinge
      │               └──► Dacă scor < 70: → [PENDING_MASTER_REVIEW]
      ▼
[APPROVED] ──► Indexare RAGFlow + upsert PostgreSQL
      │
      ▼  (sau)
[REJECTED] ──► Notificare client + motiv
```

---

## 7. Costuri Estimative

### 7.1 Infrastructură Hetzner

| Componentă | Specificații | Preț/lună |
|---|---|---|
| Server CPX41 | 8 vCPU, 16 GB RAM, 240 GB SSD | ~28€ |
| Server CPX31 (minimum) | 4 vCPU, 8 GB RAM, 160 GB SSD | ~18€ |
| Floating IP | IPv4 static | ~4€ |
| Backup automat (20%) | Snapshot zilnic | ~5-13€ |
| Traffic | 20 TB inclus | 0€ |
| **Total infrastructură** | CPX41 + IP + backup | **~37-45€/lună** |

### 7.2 Servicii Externe

| Serviciu | Utilizare estimată | Preț/lună |
|---|---|---|
| Anthropic Claude Sonnet | ~500K tokens/lună (chat broker) | ~3-8€ |
| Chandra OCR 2 (cloud tier) | ~500 documente/lună | ~5-15€ |
| Domeniu + SSL (Let's Encrypt) | 1 domeniu | ~1-2€/an |
| **Total servicii** | | **~8-25€/lună** |

### 7.3 Total Lunar Estimat

| Scenariu | Server | Servicii | **Total** |
|---|---|---|---|
| **Minimum viable** (CPX31, 200 doc/lună) | ~27€ | ~8€ | **~35-40€/lună** |
| **Standard** (CPX41, 500 doc/lună) | ~37€ | ~15€ | **~46-55€/lună** |
| **Scalat** (CPX41, 2000 doc/lună) | ~45€ | ~35€ | **~70-81€/lună** |

### 7.4 Cost per Dosar

Estimare pentru **500 dosare/lună** (standard):

| Cost | Calcul | Valoare |
|---|---|---|
| Server alocat | 37€ ÷ 500 | ~0.074€/dosar |
| OCR (Chandra) | 15€ ÷ 500 | ~0.030€/dosar |
| Claude API | 8€ ÷ 500 | ~0.016€/dosar |
| **Total per dosar** | | **~0.12€/dosar** |

**Interval estimat: 0.07€ – 0.20€/dosar** (depinde de complexitate document și număr de pagini).

### 7.5 Optimizări Cost

- **Embedding-uri locale**: `paraphrase-multilingual-MiniLM-L12-v2` rulat pe server — elimină cost API embedding (~2€/lună economie)
- **OCR batch**: procesarea nocturnă a documentelor non-urgente reduce costul Chandra cu ~30%
- **Cache RAGFlow**: întrebările frecvente se servesc din Redis, fără re-embedding
- **Chandra OCR 2 self-hosted**: pe CPX51 (32GB RAM), costul OCR devine 0€, +40€/lună server

---

## 8. Plan Implementare — 5 Faze, 12 Săptămâni

### Faza 1 — Fundație & Infrastructură (Săptămânile 1-2)

**Obiectiv:** Server Hetzner funcțional cu toate serviciile pornite.

```
Săptămâna 1:
  [ ] Provisionare server Hetzner CPX41 (nbg1, Germania)
  [ ] Configurare UFW firewall: 22, 80, 443 only
  [ ] Instalare Docker + Docker Compose v2.24+
  [ ] Deploy docker-compose.tpsh.yml — verificare healthcheck-uri
  [ ] Configurare SSL (Let's Encrypt via Certbot sau acme.sh)
  [ ] Configurare Nginx reverse proxy (3 subdomain-uri)
  [ ] Init MinIO buckets: tpsh-documents, tpsh-ocr-results, tpsh-ragflow-backup
  [ ] Init PostgreSQL schema (migrare din SQLite + tabele noi)

Săptămâna 2:
  [ ] Configurare RAGFlow — creare 7 Knowledge Bases (goale)
  [ ] Seed KB cu documente legislative (Legea 132/2017, VVG, PAD norme)
  [ ] Verificare Chandra OCR 2: test pe 5 documente sample
  [ ] Configurare Redis Sentinel (HA opțional)
  [ ] Backup automat Hetzner + testare restore
  [ ] Monitoring: Uptime Robot sau Grafana/Prometheus (opțional)
```

**Deliverables:**
- Server live cu toate containerele healthy
- RAGFlow UI accesibil pe ragflow.broker.example.com
- 7 KB create, 3 KB seeded cu documente legislative
- Test OCR: RCA, CASCO, PAD sample → JSON valid

---

### Faza 2 — OCR Pipeline (Săptămânile 3-5)

**Obiectiv:** Pipeline complet PDF → OCR → JSON → formular web.

```
Săptămâna 3:
  [ ] Implementare ocr_tools.py — wrapper Chandra OCR 2
      • ocr_extract_document(file_bytes, doc_type, lang)
      • ocr_extract_with_citations(file_bytes) → bounding boxes
      • ocr_detect_document_type(file_bytes) → auto-detection
  [ ] Schema-uri JSON per tip document (7 tipuri)
  [ ] PII masking obligatoriu: CNP, Steuernummer, Personalausweis
  [ ] Audit log tabel: document_ocr_log în PostgreSQL
  [ ] Unit tests: mock Chandra → validare JSON output

Săptămâna 4:
  [ ] FastAPI endpoints:
      POST /api/v1/documents/upload (pre-signed MinIO URL)
      POST /api/v1/documents/{id}/process (trigger OCR async)
      GET  /api/v1/documents/{id}/status (polling)
      GET  /api/v1/documents/{id}/form   (formular propus)
      PUT  /api/v1/documents/{id}/form   (editare operator)
  [ ] Celery task: process_document_ocr (queue: ocr)
  [ ] WebSocket endpoint pentru status real-time
  [ ] Error handling: timeout OCR (>60s), fallback manual

Săptămâna 5:
  [ ] Next.js — pagina Upload Document
      • Drag & drop PDF (max 50MB)
      • Progress bar cu etape: Upload → OCR → Review
      • WebSocket status updates
  [ ] Next.js — pagina Formular Review
      • Split view: PDF Viewer (left) + Formular (right)
      • Highlight bounding boxes per câmp (pdf.js)
      • Color coding: verde/galben/roșu per confidence
      • Butoane: Salvează / Respinge / Trimite la Validare
  [ ] Integrare completă: Upload → OCR → Review funcțional end-to-end
```

**Deliverables:**
- Upload PDF → JSON extras în <10s pentru documente simple
- Formular web cu highlight bounding boxes funcțional
- 5 tipuri de documente procesate corect în teste

---

### Faza 3 — RAGFlow & Validare (Săptămânile 6-8)

**Obiectiv:** Indexare documente aprobate + validare semantică + răspunsuri grounded.

```
Săptămâna 6:
  [ ] Extindere rag_tools.py pentru RAGFlow:
      • broker_rag_search(query, kb, top_k) → passages + citations
      • broker_rag_ingest_document(file_bytes, metadata) → doc_id
      • broker_rag_delete_document(doc_id) → GDPR Art. 17
      • broker_rag_get_context(client_id, topic) → relevant passages
  [ ] Celery task: index_approved_document (queue: rag)
  [ ] Trigger automat: aprobare document → indexare RAGFlow
  [ ] Multi-KB routing: RO query → kb_ro*, DE query → kb_de*

Săptămâna 7:
  [ ] Modul validare consistență:
      • validate_internal_consistency(json_form) → checks
      • validate_cross_document(doc_a, doc_b) → discrepancies
      • validate_against_db(json_form, client_id) → match_report
      • validate_semantic_rag(json_form, kb) → clause_flags
  [ ] JSON Oracle schema completă
  [ ] FastAPI endpoint: POST /api/v1/documents/{id}/validate
  [ ] Celery task: validate_document (queue: validation)
  [ ] Flow aprobare: PENDING_EDIT → PENDING_VALIDATION → APPROVED

Săptămâna 8:
  [ ] Integrare Alex (Chainlit) cu RAGFlow grounded:
      • broker_rag_search în CLAUDE.md tool list
      • Răspunsuri cu citări: pagina, confidence, link document
      • Format footnote [1], [2] în mesaje
  [ ] Next.js — pagina Validare:
      • JSON Oracle vizualizat (checks tree)
      • Aprobare/Respingere cu comentariu obligatoriu
      • Notificare automată operator/client la status change
  [ ] Integrare completă: doc aprobat → indexat → Alex răspunde din el
```

**Deliverables:**
- Document aprobat → indexat în RAGFlow în <30s
- Alex citează din documente reale ale clientului
- JSON Oracle generat pentru orice document validat

---

### Faza 4 — Roluri, Securitate & GDPR (Săptămânile 9-10)

**Obiectiv:** RBAC complet, audit trail, conformitate GDPR/ASF/BaFin.

```
Săptămâna 9:
  [ ] Implementare RBAC complet (4 roluri)
  [ ] JWT cu permissions granulare (matricea din §6)
  [ ] Middleware FastAPI: permisiune check per endpoint
  [ ] Next.js: componente condiționale per rol
  [ ] Pagina admin: gestiune utilizatori (Master Admin only)
  [ ] Rate limiting: 10 upload/minut per utilizator
  [ ] CORS configurat strict (domenii whitelisted)

Săptămâna 10:
  [ ] PII masking verificare completă:
      [ ] CNP/CUI niciodată în plaintext în RAGFlow index
      [ ] Steuernummer/Personalausweis mascat
      [ ] Test automat: scan index ES pentru PII regex
  [ ] Audit log complet:
      [ ] document_ocr_log (fiecare OCR)
      [ ] document_approval_log (fiecare aprobare/respingere)
      [ ] rag_query_log (fiecare interogare RAGFlow)
      [ ] user_action_log (fiecare acțiune utilizator)
  [ ] GDPR Art. 17 — delete workflow:
      [ ] Ștergere document: MinIO + RAGFlow + PostgreSQL (CASCADE)
      [ ] Confirmare triplă: operator + master admin + timestamp
  [ ] Retenție documente:
      [ ] DE policies: 7 ani (BaFin MaGo 2022)
      [ ] RO policies: 5 ani (ASF Norma 20/2023)
      [ ] Auto-arhivare (nu ștergere) după perioadă
```

**Deliverables:**
- RBAC funcțional: fiecare rol vede/poate exact ce trebuie
- 0 PII în plaintext în index (test automat trece)
- Delete workflow GDPR Art. 17 funcțional

---

### Faza 5 — Optimizare, Load Test & Go-Live (Săptămânile 11-12)

**Obiectiv:** Performanță, monitorizare, documentație, lansare producție.

```
Săptămâna 11:
  [ ] Load testing (Locust sau k6):
      [ ] 50 upload simultane → procesare OK
      [ ] 100 RAG queries/minut → latență <1.5s
      [ ] 20 OCR simultane → fără timeout
  [ ] Multilingual benchmark:
      [ ] 30 întrebări RO → RAG recall@5 >80%
      [ ] 30 întrebări DE → RAG recall@5 >80%
      [ ] Routing corect: RO → kb_ro*, DE → kb_de*
  [ ] OCR accuracy test:
      [ ] 20 polițe RCA scanate → >95% câmpuri corecte
      [ ] 10 formulare daune → >90% câmpuri corecte
  [ ] Optimizare Redis cache pentru RAG (TTL 1h pentru queries frecvente)
  [ ] Optimizare Elasticsearch indices (shards, replici)

Săptămâna 12:
  [ ] Documentație operațională:
      [ ] Runbook: restart servicii, rollback, backup/restore
      [ ] Ghid utilizator per rol (PDF, RO+DE+EN)
      [ ] API docs (FastAPI auto-generated /docs)
  [ ] Monitoring dashboard (Uptime Robot / Grafana):
      [ ] Alertă: serviciu down → Slack/email
      [ ] Alertă: disk >80% → Slack
      [ ] Alertă: OCR error rate >10% → Slack
  [ ] Seed KB cu documente reale (condițiile asigurătorilor principali):
      [ ] Allianz, Generali, Omniasig, PAID Pool (RO)
      [ ] Allianz DE, AXA DE, Signal Iduna (DE)
  [ ] Final smoke test end-to-end (toate cele 4 roluri)
  [ ] Go-Live ✅
```

**Deliverables:**
- Toate testele de acceptance treac (§12)
- Documentație completă pentru operatori
- KB seeded cu documente reale ale asigurătorilor
- Sistem live, monitorizat, documentat

---

## 9. Stack Tehnic Detaliat

### 9.1 Backend FastAPI

```
backend/
  app/
    main.py              # FastAPI app factory
    config.py            # Settings (pydantic-settings)
    auth/
      jwt_handler.py     # JWT encode/decode
      rbac.py            # Role-based access control middleware
      dependencies.py    # FastAPI dependencies (get_current_user)
    api/v1/
      documents.py       # Upload, status, form CRUD
      validation.py      # JSON Oracle endpoints
      users.py           # User management (Master Admin)
      reports.py         # ASF/BaFin reports
    services/
      ocr_service.py     # Chandra OCR 2 integration
      rag_service.py     # RAGFlow integration
      validation_service.py  # Consistency checks
      minio_service.py   # Object storage operations
    worker/
      tasks.py           # Celery tasks (OCR, RAG, validation)
      scheduler.py       # Celery beat scheduled tasks
    models/
      document.py        # SQLAlchemy models
      user.py
      audit.py
    schemas/
      document.py        # Pydantic schemas (request/response)
      validation.py      # JSON Oracle schema
```

### 9.2 Frontend Next.js

```
frontend/
  app/
    (auth)/
      login/page.tsx
    (dashboard)/
      layout.tsx           # Sidebar cu navigare per rol
      page.tsx             # Dashboard overview
      documents/
        upload/page.tsx    # Upload + drag & drop
        [id]/review/page.tsx    # Formular OCR review
        [id]/validation/page.tsx # JSON Oracle
      clients/
        page.tsx
        [id]/page.tsx
      reports/page.tsx
  components/
    pdf-viewer/
      PDFViewer.tsx        # pdf.js wrapper
      BoundingBoxOverlay.tsx  # Highlight boxes pe PDF
      CitationTooltip.tsx  # Tooltip cu confidence
    forms/
      DocumentForm.tsx     # Formular editabil post-OCR
      FieldStatus.tsx      # Verde/galben/roșu per câmp
    validation/
      OracleReport.tsx     # JSON Oracle vizualizat
      CheckTree.tsx        # Arbore de verificări
  lib/
    api.ts                 # API client (fetch wrapper)
    websocket.ts           # WebSocket pentru status
    auth.ts                # NextAuth.js sau custom JWT
```

### 9.3 MCP Tools Noi (insurance_broker_mcp)

```
mcp-server/insurance_broker_mcp/tools/
  ocr_tools.py       # NOU: Chandra OCR 2 wrapper (5 tools)
  rag_tools.py       # EXTINS: RAGFlow integration (4 tools noi)
  validation_tools.py  # NOU: JSON Oracle, consistency checks (3 tools)
```

| Tool | Descriere |
|---|---|
| `broker_ocr_extract` | OCR document → JSON structurat cu coordonate |
| `broker_ocr_validate_policy` | OCR + validare vs. DB |
| `broker_ocr_detect_type` | Auto-detecție tip document |
| `broker_ocr_batch_process` | Procesare asincronă mai multor documente |
| `broker_ocr_get_status` | Status job OCR |
| `broker_rag_search` | Căutare semantică în KB (cu citări grounded) |
| `broker_rag_ingest` | Indexare document aprobat în KB |
| `broker_rag_delete` | Ștergere document din KB (GDPR) |
| `broker_rag_get_context` | Context RAG pentru un client + topic |
| `broker_validate_document` | Validare completă → JSON Oracle |
| `broker_validate_consistency` | Cross-document consistency check |
| `broker_get_validation_report` | Raport validare existent |

---

## 10. Knowledge Bases RAGFlow

### 10.1 Configurare KB

| KB Name | Tip Documente | Limbă | Chunk (tokens) | Overlap | Top-K | Threshold |
|---|---|---|---|---|---|---|
| `kb_rca_casco_ro` | Polițe RCA/CASCO, tarife, condiții | RO | 512 | 64 | 4 | 0.70 |
| `kb_pad_home_ro` | PAD, home, notificări PAID Pool | RO | 512 | 64 | 4 | 0.70 |
| `kb_kfz_de` | KFZ-Haftpflicht, Kasko, Gebäude | DE | 512 | 64 | 4 | 0.72 |
| `kb_claims_ro_de` | Dosare daune, corespondență asigurători | RO/DE | 256 | 32 | 3 | 0.75 |
| `kb_compliance_asf` | Legi (132/2017, 260/2008), circulare ASF | RO | 1024 | 128 | 5 | 0.72 |
| `kb_compliance_bafin` | VVG, PflVG, BaFin Rundschreiben | DE | 1024 | 128 | 5 | 0.72 |
| `kb_offers` | Oferte generate, comparații, template-uri | RO/DE/EN | 256 | 32 | 3 | 0.68 |
| `kb_client_docs` | Documente aprobate ale clienților | RO/DE | 512 | 64 | 5 | 0.75 |

### 10.2 Documente Seed (Lansare)

```
kb_compliance_asf/
  Legea_132_2017_RCA_Romania.pdf
  Legea_260_2008_PAD_Romania.pdf
  Norma_ASF_20_2023_arhivare.pdf
  Norma_ASF_20_2020_informatii_clienti.pdf

kb_compliance_bafin/
  VVG_2008_Versicherungsvertragsgesetz.pdf
  PflVG_2007_Pflichtversicherungsgesetz.pdf
  BaFin_MaGo_2022_IT_Mindestvorgaben.pdf
  GDV_Musterbedingungen_KFZ_2023.pdf

kb_rca_casco_ro/
  Conditii_generale_CASCO_Allianz_2026.pdf
  Conditii_generale_CASCO_Generali_2026.pdf
  Conditii_generale_RCA_Omniasig_2026.pdf
  Tarifar_orientativ_RCA_2026.pdf

kb_kfz_de/
  Allianz_KFZ_Versicherungsbedingungen_2026.pdf
  AXA_Kasko_AVB_2026.pdf
  Signal_Iduna_KFZ_2026.pdf
```

---

## 11. GDPR & Conformitate

### 11.1 Măsuri Tehnice

| Cerință GDPR | Implementare |
|---|---|
| Art. 5 — Minimizare date | CNP/CUI/Steuernummer mascat imediat post-OCR, înainte de stocare |
| Art. 17 — Dreptul la ștergere | Delete workflow: MinIO → RAGFlow → PostgreSQL CASCADE; confirmare dublă |
| Art. 25 — Privacy by design | PII masking activat by default în Chandra OCR 2, nu opțional |
| Art. 32 — Securitate | TLS 1.3, JWT signed, PostgreSQL encrypted at rest, MinIO server-side encryption |
| Art. 30 — Registrul activităților | Audit log complet în PostgreSQL (user, acțiune, document, timestamp, IP) |
| Art. 44-49 — Transfer internațional | Date rămân pe Hetzner Germania (EU) — nu se transferă în afara UE |
| ASF Norma 20/2023 | Log ingestion document (client_id, doc_type, data) + retenție 5 ani |
| BaFin MaGo 2022 | Retenție polițe DE: 7 ani; audit trail IT; acces restricționat |

### 11.2 Mascarea PII

```python
# PII masking — reguli standard
PII_MASKING_RULES = {
    "cnp_ro": {
        "pattern": r"\b\d{13}\b",
        "mask": lambda m: m.group(0)[:1] + "X" * 9 + m.group(0)[-3:],
        "description": "CNP român — păstrează prima și ultimele 3 cifre"
    },
    "cui_ro": {
        "pattern": r"\bRO\d{6,10}\b",
        "mask": lambda m: "RO" + "X" * (len(m.group(0)) - 5) + m.group(0)[-3:],
        "description": "CUI român"
    },
    "steuernummer_de": {
        "pattern": r"\b\d{2,3}/\d{3}/\d{5}\b",
        "mask": lambda m: "XX/XXX/XXXXX",
        "description": "Steuernummer Germania"
    },
    "personalausweis_de": {
        "pattern": r"\b[A-Z]{1,2}\d{7}\b",
        "mask": lambda m: m.group(0)[:2] + "XXXXX" + m.group(0)[-2:],
        "description": "Personalausweis — păstrează prefix și sufix"
    }
}
```

---

## 12. Testing & Acceptance Criteria

### 12.1 Suite de Teste

```
tests/
  unit/
    test_ocr_tools.py          # Mock Chandra → JSON valid per tip document
    test_rag_tools.py          # Mock RAGFlow → passages cu citări
    test_validation_service.py # Consistency checks (internal, cross-doc, DB)
    test_pii_masking.py        # CNP/CUI/Steuernummer niciodată în plaintext
    test_jwt_rbac.py           # Fiecare rol: acces corect/blocat
  integration/
    test_ocr_pipeline.py       # Upload → OCR → formular propus (end-to-end)
    test_rag_ingest_search.py  # Ingest document → search → găsit
    test_approval_flow.py      # PENDING_OCR → APPROVED complet
    test_gdpr_delete.py        # Delete → MinIO + RAGFlow + PG toate șterse
  e2e/
    test_multilingual.py       # RO query → KB ro, DE query → KB de
    test_grounded_citations.py # Alex răspunde cu citări valide
    test_full_workflow.py      # Upload → OCR → Edit → Validate → Alex answer
  security/
    test_pii_index_scan.py     # Scan ES index pentru PII regex (trebuie 0 matches)
    test_rbac_bypass.py        # Tentative de bypass permisiuni → toate blocate
```

### 12.2 Criterii de Acceptare

| Test | Condiție de Trecere |
|---|---|
| OCR accuracy RCA | >95% câmpuri corecte pe set de 20 polițe scanate |
| OCR accuracy dosare daune | >90% câmpuri corecte (include câmpuri scrise de mână) |
| OCR latență | <8s per document simplu (1-2 pagini) |
| RAG recall@5 RO | >80% — răspuns corect în top 5 pentru 30 întrebări compliance |
| RAG recall@5 DE | >80% — idem pentru 30 întrebări în germană |
| RAG latență | <1.5s per query semantic |
| PII masking | 0 CNP/CUI/Steuernummer în plaintext în ES index |
| RBAC | 0 endpoint-uri accesibile fără permisiunile corecte |
| Delete GDPR | Document șters → absent din MinIO + RAGFlow + PostgreSQL |
| Uptime | >99.5% monthly (Hetzner SLA + configurare Nginx) |
| Load OCR | 50 upload simultane → <30s procesare (fără erori) |
| Load RAG | 100 queries/minut → latență <2s (percentila 95) |

---

## 13. Environment Variables

```bash
# .env.tpsh — variabile complete

# ─── PostgreSQL ───────────────────────────────
POSTGRES_DB=tpsh_broker
POSTGRES_USER=broker_admin
POSTGRES_PASSWORD=<generate-strong-password>
DATABASE_URL=postgresql+asyncpg://broker_admin:<password>@postgres/tpsh_broker

# ─── Redis ────────────────────────────────────
REDIS_PASSWORD=<generate-strong-password>
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# ─── MinIO ────────────────────────────────────
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=<generate-strong-password>
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET_DOCUMENTS=tpsh-documents
MINIO_BUCKET_OCR=tpsh-ocr-results
MINIO_BUCKET_BACKUP=tpsh-ragflow-backup

# ─── RAGFlow ──────────────────────────────────
RAGFLOW_API_KEY=rf_<generate>
RAGFLOW_BASE_URL=http://ragflow:9380
RAGFLOW_DEFAULT_KB=kb_rca_casco_ro
RAGFLOW_EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
RAGFLOW_RERANKER_MODEL=BAAI/bge-reranker-base

# ─── Chandra OCR 2 ────────────────────────────
CHANDRA_OCR_URL=http://chandra_ocr:8888
CHANDRA_OCR_API_KEY=ch_<generate>
CHANDRA_OCR_TIMEOUT_S=60
CHANDRA_OCR_MAX_FILE_MB=50

# ─── Anthropic ────────────────────────────────
ANTHROPIC_API_KEY=sk-ant-<your-key>
ANTHROPIC_MODEL=claude-sonnet-4-6

# ─── Autentificare ────────────────────────────
JWT_SECRET_KEY=<generate-256bit-key>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# ─── Aplicație ────────────────────────────────
DOMAIN=broker.example.com
ENVIRONMENT=production
LOG_LEVEL=INFO
CORS_ORIGINS=https://broker.example.com,https://admin.broker.example.com
```

---

## 14. Referințe

### Proiect Existent
- Scaffold RAG curent: `mcp-server/insurance_broker_mcp/tools/rag_tools.py`
- Claims tools: `mcp-server/insurance_broker_mcp/tools/claims_tools.py`
- Upload GCS: `mcp-server/insurance_broker_mcp/tools/drive_tools.py`
- Agent SDK: `agent-sdk/orchestrator.py`
- Chat UI: `app.py` (Chainlit)

### RAGFlow
- GitHub: https://github.com/infiniflow/ragflow
- Docs: RAGFlow v0.15+ required pentru multi-KB routing
- API: `GET/POST /api/v1/kb`, `/api/v1/retrieval`, `/api/v1/document`

### Chandra OCR 2
- Endpoint principal: `POST /v2/extract`
- Docs: `/v2/docs` (deployment intern)
- Suportă: PDF, JPEG, PNG, TIFF — max 50MB, max 100 pagini

### Legislație & Conformitate
- ASF Legea 132/2017 — Asigurarea obligatorie RCA
- ASF Legea 260/2008 — Asigurarea obligatorie PAD
- ASF Norma 20/2023 — Cerințe arhivare documente
- BaFin VVG (2008) — Versicherungsvertragsgesetz
- BaFin PflVG (2007) — Pflichtversicherungsgesetz
- BaFin MaGo 2022 — IT-Mindestvorgaben Versicherungsunternehmen
- GDPR (EU) 2016/679 — Regulamentul general privind protecția datelor

### Tools & Libraries
- `infiniflow/ragflow:v0.15.1` — RAGFlow Docker image
- `elasticsearch:8.13.0` — Vector search pentru RAGFlow
- `minio/minio:latest` — Object storage (compatibil S3)
- `postgres:16-alpine` — DB producție
- `redis:7-alpine` — Cache + queue
- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` — Embedding model RO+DE+EN
- `BAAI/bge-reranker-base` — Reranker pentru recall îmbunătățit
- `pdf.js` (Mozilla) — PDF rendering în browser cu bounding box overlay
- `FastAPI 0.111+` — Backend API async
- `Next.js 14+` — Admin UI (App Router)
- `Celery 5+` + `Redis` — Task queue asincron

---

*Demo Broker SRL · ASF License RBK-DEMO-001 · BaFin Registration*
*Plan generat: 2026-03-31 · Versiune: 2.0 Completă*
