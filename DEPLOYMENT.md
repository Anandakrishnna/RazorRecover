# 🚀 RazorRecover Platform Hosting & Deployment Guide

This guide details how to host and deploy the **RazorRecover** Autonomous AI Revenue Recovery platform using containerization or cloud platform providers.

---

## 🏗️ Architecture Summary

RazorRecover is built as a unified single-container platform:
- **Backend API**: Python FastAPI + SQLModel (SQLite/SQLAlchemy) + Google Gemini LLM API integration.
- **Frontend Dashboard**: React + Vite Single Page Application.
- **Unified Container**: In production mode, FastAPI serves both the REST API routes (`/events`, `/cases`, `/metrics`, `/api/health`) and the built React SPA static assets on a single host and port.

---

## 🐋 Option 1: Local or VPS Deployment via Docker / Docker Compose

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker engine installed.

### Using Docker Compose (Recommended)

1. **Set your Gemini API Key (Optional but recommended)**:
   - **Linux / macOS**:
     ```bash
     export GEMINI_API_KEY="AIzaSy..."
     ```
   - **Windows (PowerShell)**:
     ```powershell
     $env:GEMINI_API_KEY="AIzaSy..."
     ```

2. **Launch Container**:
   ```bash
   docker-compose up --build -d
   ```

3. **Access Dashboard & API**:
   - 🌐 **React Single-Page Dashboard**: [http://localhost:8000](http://localhost:8000)
   - ⚡ **API Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)
   - 📖 **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

4. **Stop Container**:
   ```bash
   docker-compose down
   ```

---

### Using Standalone Docker CLI

1. **Build Image**:
   ```bash
   docker build -t razorrecover:latest .
   ```

2. **Run Container**:
   ```bash
   docker run -d \
     -p 8000:8000 \
     -e GEMINI_API_KEY="your-gemini-key-here" \
     --name razorrecover \
     razorrecover:latest
   ```

---

## ☁️ Option 2: Cloud Managed Deployments

### 1. Deploying on Render (Free / Low Cost)
1. Push your repository to GitHub or GitLab.
2. Sign in to [Render Dashboard](https://dashboard.render.com/) and click **New +** -> **Web Service**.
3. Select **Build and deploy from a Git repository**.
4. Choose repository: `RazorRecover`.
5. Configuration:
   - **Runtime**: `Docker`
   - **Region**: Oregon (or nearest)
   - **Instance Type**: Free or Starter
6. Environment Variables:
   - `GEMINI_API_KEY`: *(Your Google Gemini API Key)*
7. Click **Create Web Service**. Render will automatically detect the `Dockerfile`, build the multi-stage image, and expose the live application URL (e.g. `https://razorrecover.onrender.com`).

---

### 2. Deploying on Railway
1. Go to [Railway Dashboard](https://railway.app/) and click **New Project**.
2. Select **Deploy from GitHub repo** -> Select `RazorRecover`.
3. Railway will auto-detect the `Dockerfile`.
4. Go to **Variables** tab and set:
   - `GEMINI_API_KEY`: *(Your Gemini API key)*
5. Click **Generate Domain** under Settings.

---

### 3. Deploying on Google Cloud Run (Serverless Container)
1. Ensure `gcloud` CLI is installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

2. Build & push image to Google Artifact Registry / Container Registry:
   ```bash
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/razorrecover:latest
   ```

3. Deploy to Cloud Run:
   ```bash
   gcloud run deploy razorrecover \
     --image gcr.io/YOUR_PROJECT_ID/razorrecover:latest \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars GEMINI_API_KEY="your-gemini-api-key"
   ```

---

## 🔒 Environment Variables Reference

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `PORT` | Optional | `8000` | Port bound by Uvicorn server (auto-injected by cloud providers). |
| `GEMINI_API_KEY` | Recommended | Empty | Google Gemini API key for live LLM recommendations. Fallback mock engine activates if missing. |
| `VITE_API_BASE_URL` | Optional | `''` (Relative) | Override API host URL for frontend calls if running frontend independently. |

---

## 🧪 Post-Deployment Verification

After deploying, verify the running application:
1. Open `https://<your-app-domain>/api/health` in your browser. Expect: `{"system":"RazorRecover Autonomous Agent API","status":"HEALTHY","version":"1.0.0"}`.
2. Open `https://<your-app-domain>/` to interact with the React Case Queue Dashboard.
