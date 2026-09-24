# Midara Utilities

**Compress DOCX • PDF • PNG • JPEG** and convert images — open-source & self-hosted.

A clean web interface for compressing documents and images.  
All processing happens on **your** server. No external APIs.

---

## Features

| Format       | Action              | Notes                                      |
|--------------|---------------------|--------------------------------------------|
| **DOCX**     | Compress            | Stays as `.docx`. Optimizes images + ZIP   |
| **PDF**      | Compress            | Compresses streams + strips metadata       |
| **PNG/JPEG** | Compress + Convert  | Quality slider, PNG ↔ JPEG                 |

---

## Deploy on Render (Free)

1. Push this repository to GitHub
2. Go to [https://render.com](https://render.com) → sign up with GitHub
3. Click **New → Web Service**
4. Connect this repository
5. Use these settings:

| Setting           | Value                             |
|-------------------|-----------------------------------|
| **Name**          | midara-utilities                  |
| **Runtime**       | Python 3                          |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app`                |
| **Instance Type** | Free                              |

6. Click **Create Web Service**

Your site will be live at something like:  
`https://midara-utilities-xxxx.onrender.com`

> Free tier sleeps after ~15 min of inactivity. First request after sleep takes 30–60 seconds.

---

## Run locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
