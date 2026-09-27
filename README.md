# 🇮🇳 IP-SAKTI Sahayak

### Multilingual, Source-Cited AI Assistant for Intellectual Property & Regulatory Guidance in Ayurveda

[![Smart India Hackathon](https://img.shields.io/badge/Smart%20India%20Hackathon-2026-orange)]()
[![Problem Statement](https://img.shields.io/badge/SIH-SIH26045-blue)]()
[![Domain](https://img.shields.io/badge/Domain-AI%20%7C%20RAG%20%7C%20IP%20%7C%20AYUSH-green)]()
[![Architecture](https://img.shields.io/badge/Architecture-Hybrid%20RAG-purple)]()
[![Authentication](https://img.shields.io/badge/Auth-Supabase-green)]()

> **IP-SAKTI Sahayak** is a multilingual, source-cited AI research assistant designed to provide grounded guidance on Intellectual Property, Ayurveda, Traditional Knowledge, Access & Benefit Sharing (ABS), and regulatory frameworks across Indian and international regimes.

---

## 🏆 Smart India Hackathon 2026

| Field | Details |
|---|---|
| **SIH Code** | `SIH26045` |
| **Problem Statement** | **IP-SAKTI Sahayak** |
| **Category** | Software |
| **Domain** | AI / RAG / Intellectual Property / AYUSH |
| **Core Technology** | Hybrid Retrieval-Augmented Generation |
| **Primary Objective** | Source-grounded IP and regulatory research |

### Problem Statement

> **IP-SAKTI Sahayak — a multilingual, RAG-based (source-cited) AI assistant for Intellectual Property and regulatory guidance in Ayurveda, across national and international regimes.**

---

# 📌 Table of Contents

- [The Problem](#-the-problem)
- [Our Solution](#-our-solution)
- [Why IP-SAKTI Sahayak Is Different](#-why-ip-sakti-sahayak-is-different)
- [Key Features](#-key-features)
- [How the System Works](#-how-the-system-works)
- [System Architecture](#-system-architecture)
- [RAG Pipeline](#-rag-pipeline)
- [Confidence Score](#-confidence-score)
- [Multilingual & Voice Architecture](#-multilingual--voice-architecture)
- [Authentication & Security](#-authentication--security)
- [Research History](#-research-history)
- [Source & Citation System](#-source--citation-system)
- [Project Statistics](#-project-statistics)
- [Technology Stack](#-technology-stack)
- [Repository Structure](#-repository-structure)
- [Deployment Architecture](#-deployment-architecture)
- [Budget & Cost Strategy](#-budget--cost-strategy)
- [Future Upgrades](#-future-upgrades)
- [Limitations](#-limitations)
- [Getting Started](#-getting-started)
- [Team](#-team)
- [License](#-license)

---

# 🔎 The Problem

Researching Intellectual Property and regulatory requirements in Ayurveda is difficult because relevant information is distributed across multiple domains:

- Intellectual Property regulations
- Patents and trademarks
- AYUSH regulations
- Traditional Knowledge
- Access & Benefit Sharing
- Biological resources
- National regulatory frameworks
- International IP frameworks
- Government notifications and official sources

A conventional chatbot can generate a fluent answer, but fluency does not guarantee that the answer is:

- grounded in authoritative sources,
- jurisdiction-aware,
- traceable,
- reproducible,
- or safe when evidence is insufficient.

### The core problem

**Users need research assistance, not just generated text.**

IP-SAKTI Sahayak therefore treats every research query as a retrieval, reasoning, evidence and verification problem.

---

# 💡 Our Solution

## IP-SAKTI Sahayak

IP-SAKTI Sahayak combines:

**Hybrid Retrieval + Multi-Agent Reasoning + Live Research + Citation Validation + Confidence Assessment + Abstention**

into one research workflow.

```text
User Question
      │
      ▼
Language Detection
      │
      ▼
Query Processing
      │
      ▼
┌─────────────────────────────┐
│      HYBRID RETRIEVAL       │
│                             │
│  FAISS      BM25      WEB   │
│    │          │        │    │
└────┼──────────┼────────┼────┘
     │          │        │
     └──────────┼────────┘
                ▼
        RRF Fusion
                │
                ▼
        Cross-Encoder
         Re-ranking
                │
                ▼
       Multi-Agent Layer
    ┌───────────┼───────────┐
    ▼           ▼           ▼
 IP Agent   AYUSH Agent   TK/ABS Agent
    │           │           │
    └───────────┼───────────┘
                ▼
             Gemini
                │
                ▼
       Citation Validation
                │
                ▼
        Confidence Engine
                │
        ┌───────┴────────┐
        ▼                ▼
      ANSWER           ABSTAIN
        │
        ▼
  Cited Research Response
