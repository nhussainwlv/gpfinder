# GPFinder

A professional, domain-specific search engine for finding General Practitioners (GPs) in England. Search by **postcode** or **town name** and get instant, structured results.

**Built by [@Naeem](mailto:n.hussain30@wlv.ac.uk)**

---

## Quick start

```bash
cd /path/to/GPFinder
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000** in your browser.

## Run on another laptop (recommended steps)

1. Install **Python 3.10+** and **Git**.
2. Clone the repository and open it in terminal:
   ```bash
   git clone <your-repo-url>
   cd GPFinder
   ```
3. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Run app without Elasticsearch:
   ```bash
   GPFINDER_ES_ENABLED=false python app.py
   ```
6. Open `http://127.0.0.1:5001` in browser.

### Optional: run with Elasticsearch

If Elasticsearch is running locally on `http://localhost:9200`:

```bash
GPFINDER_ES_ENABLED=true GPFINDER_ES_URL=http://localhost:9200 python app.py
```

---

## Features

- **Search**: Postcode (e.g. `B1 1AA`, `B16`) or town name (e.g. `Birmingham`, `Wolverhampton`)
- **Instant results**: Debounced search as you type; results in card format with name, address, postcode, phone, website, and ratings
- **Search quality controls**: Default GP-practice-only retrieval with optional toggle to include broader primary care services
- **Accessibility**: Voice search with microphone input and text-to-speech reading of search results
- **Richer practice details**: Organisation code, likely service list, and practical patient guidance per result card
- **Care readiness**: Open-now status, next opening window, urgent care alternatives, and appointment/registration guidance
- **Travel options**: Direct links for drive/public transport/walk with quick ETA chips where distance is available
- **Multilingual UI**: English, Hindi, Chinese, Spanish, Arabic, and French options with translated voice prompts
- **Feedback loop**: Per-result “useful” and “details incorrect” feedback captured via API for ongoing quality improvements
- **Backend**: Flask API with input validation, rate limiting (e.g. 30/min per IP), server-side caching (5 min), and Elasticsearch-powered retrieval
- **Security**: Validated input, XSS-safe rendering, optional NHS API key via environment variables
- **Design**: Clean, responsive UI with blues, whites, and grays; smooth animations and clear typography

---

## Documentation

A detailed summary of **how the search engine works** is in:

- **[docs/HOW_GPFINDER_WORKS.md](docs/HOW_GPFINDER_WORKS.md)**  
  Covers user flow, frontend/backend, Elasticsearch indexing + retrieval, data sources, security, and running the app.

---

## Data

- **Included**: UK GP CSV dataset in `data/ukgp.csv`, preprocessed and indexed into Elasticsearch for fast ranked retrieval.
- **Optional**: For live NHS data, configure the Organisation Data Service (ORD) API (see docs and `config.py`). Set `GPFINDER_NHS_ORD_API_KEY` when you have an API key.

---

## Tech stack

- **Frontend**: HTML5, CSS3, JavaScript (vanilla)
- **Backend**: Python 3, Flask, Flask-Caching, Flask-Limiter, Elasticsearch
- **Data**: UK GP CSV file indexed in Elasticsearch + optional NHS ORD API integration
