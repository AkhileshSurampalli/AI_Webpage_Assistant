# AI Page Assistant — Chrome Extension + FastAPI Backend

A Chrome extension that uses RAG (Retrieval-Augmented Generation) to summarise
any webpage and answer questions about its content — powered by LangChain, FAISS,
the OpenAI API, and a FastAPI backend.

---

## Architecture

```
┌─────────────────────────────────────────┐
│         Chrome Extension                 │
│  ┌─────────────┐   ┌─────────────────┐  │
│  │  popup.html  │   │   popup.js      │  │
│  │  (UI layer)  │◄──│  (logic layer)  │  │
│  └─────────────┘   └────────┬────────┘  │
│                              │           │
│  ┌──────────────────────┐    │           │
│  │   content.js         │    │           │
│  │   (page HTML access) │    │           │
│  └──────────────────────┘    │           │
└─────────────────────────────────────────┘
                               │
                    POST /summarize
                    POST /ask
                               │
                               ▼
┌─────────────────────────────────────────┐
│         FastAPI Backend (main.py)        │
│                                         │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │  HTML Parser  │  │  Text Chunker   │  │
│  │ (BeautifulSoup│  │ (LangChain      │  │
│  │  noise removal│  │  RecursiveText  │  │
│  └──────┬───────┘  └────────┬────────┘  │
│         └────────┬──────────┘           │
│                  ▼                       │
│  ┌──────────────────────────────────┐   │
│  │   FAISS Vector Store             │   │
│  │   (per-page RAG index, cached    │   │
│  │    in memory by content hash)    │   │
│  └──────────────────────────────────┘   │
│                  │                       │
│                  ▼                       │
│  ┌──────────────────────────────────┐   │
│  │   OpenAI API (GPT-4o-mini)       │   │
│  │   · /summarize → direct prompt   │   │
│  │   · /ask       → RetrievalQA     │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

---

## Features

- **Auto-summary on open** — as soon as you click the extension icon,
  the current page is summarised in 3-4 sentences
- **Q&A with RAG** — ask any question; the backend chunks the page,
  builds a FAISS index, retrieves relevant passages, and generates a grounded answer
- **Page caching** — FAISS index is cached per unique page (by content hash),
  so repeated questions on the same page are faster and cheaper
- **Clean UI** — dark-mode popup with chat history and source chunk count
- **Noise removal** — scripts, nav, footer, and ads stripped before processing

---

## Setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt

# Set your OpenAI API key
set OPENAI_API_KEY=your_key_here   # Windows
export OPENAI_API_KEY=your_key_here  # Mac/Linux

# Start the server
uvicorn main:app --reload --port 8000
```

### 2. Chrome Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder from this project
5. The AI Page Assistant icon will appear in your toolbar

> **Note:** The backend must be running on `localhost:8000` for the extension to work.

---

## Usage

1. Navigate to any webpage
2. Click the AI Page Assistant icon
3. The page summary loads automatically
4. Type a question in the input box and press Enter or click ➤
5. The agent retrieves relevant sections of the page and answers your question

---

## Example

On a research paper page:
```
Summary: This paper introduces a novel transformer architecture for
time-series anomaly detection in industrial IoT systems, achieving
state-of-the-art results on three benchmark datasets...

You: What datasets were used for evaluation?
Agent [RAG · 3 chunks]: The paper evaluated the model on three
benchmark datasets: SMD (Server Machine Dataset), MSL (Mars Science
Laboratory), and SMAP (Soil Moisture Active Passive)...
```

---

## Tech Stack

**Extension:** HTML · CSS · JavaScript (Manifest V3)
**Backend:** FastAPI · LangChain · FAISS · OpenAI API · BeautifulSoup4 · Python

---

## Project Structure

```
chrome_agent/
├── backend/
│   ├── main.py           # FastAPI server — /summarize and /ask endpoints
│   └── requirements.txt
└── extension/
    ├── manifest.json     # Chrome extension config (Manifest V3)
    ├── popup.html        # Extension popup UI
    ├── popup.js          # UI logic + API calls
    ├── content.js        # Content script (page access)
    ├── background.js     # Service worker
    └── icons/            # Extension icons (add 16x16, 48x48, 128x128 PNGs)
```
