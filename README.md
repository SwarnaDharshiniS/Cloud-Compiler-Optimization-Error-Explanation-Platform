# ☁️ Cloud Compiler Optimization & Error-Explanation Platform

A fully cloud-native C/C++/Python/Java/Go/Rust compiler platform built on **Microsoft Azure**, featuring LLVM-based optimization, AI-powered error explanation, and a web dashboard — designed to run entirely within the **Azure Students free tier**.

---

## 🏗️ Architecture Overview

```
Browser (Static Web App)
        │
        ▼
Azure Functions (API Layer)
  ├── TriggerCompile  ──► Azure Container Apps (LLVM Docker)
  ├── ExplainError    ──► Azure AI Language Service
  └── GetHistory      ──► Azure Table Storage
        │
        ▼
Azure Blob Storage  +  Azure Table Storage  +  Application Insights
```

---

## 📦 Project Structure

```
├── docker/
│   ├── Dockerfile            # Multi-language compiler container (C, C++, Python, Java, Go, Rust)
│   └── compile_server.py     # Python HTTP server handling /compile requests
├── frontend/
│   └── index.html            # Single-page web dashboard (HTML/CSS/JS)
├── function_app.py           # Azure Functions: TriggerCompile, ExplainError, GetHistory
├── host.json                 # Azure Functions host configuration
├── requirements.txt          # Python dependencies for Azure Functions
├── local.settings.json.sample # Sample config (copy to local.settings.json, fill in your keys)
└── scripts/
    └── setup.sh              # Azure resource provisioning script
```

---

## ☁️ Azure Services Used

| Service | Purpose |
|---|---|
| Azure Container Apps | Runs the LLVM/Clang Docker compiler (scales to 0 when idle) |
| Azure Container Registry | Stores the Docker image |
| Azure Functions (Consumption) | Serverless API layer — TriggerCompile, ExplainError, GetHistory |
| Azure Blob Storage | Stores uploaded source code and compiled output JSON |
| Azure Table Storage | Stores compilation history and error type analytics (bundled in Blob Storage account) |
| Azure AI Language Service (F0) | Extracts key phrases from compiler errors for plain-English explanations |
| Azure Static Web Apps | Hosts the frontend dashboard (free HTTPS) |
| Azure Application Insights | Real-time monitoring of requests, failures, and latency |

---

## 🚀 Getting Started

### Prerequisites

- Ubuntu 20.04+ machine
- Azure Students account ([signup](https://azure.microsoft.com/en-us/free/students/))
- Node.js 20+, Python 3.12+, Docker, Azure CLI, Azure Functions Core Tools v4

### 1. Clone the repo

```bash
git clone https://github.com/SwarnaDharshiniS/Cloud-Compiler-Optimization-Error-Explanation-Platform.git
cd Cloud-Compiler-Optimization-Error-Explanation-Platform
```

### 2. Configure local settings

```bash
cp local.settings.json.sample local.settings.json
# Edit local.settings.json and fill in your Azure keys
```

### 3. Provision Azure resources

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 4. Build & push the Docker image

```bash
cd docker
docker build -t cloud-compiler-llvm:latest .
az acr login --name cloudcompileracr
docker tag cloud-compiler-llvm:latest cloudcompileracr.azurecr.io/cloud-compiler-llvm:latest
docker push cloudcompileracr.azurecr.io/cloud-compiler-llvm:latest
```

### 5. Deploy Azure Functions

```bash
func azure functionapp publish cloud-compiler-func
```

### 6. Deploy the frontend

```bash
cd frontend
swa deploy ./  --deployment-token <YOUR_SWA_TOKEN> --env production
```

---

## 🔌 API Endpoints

Base URL: `https://cloud-compiler-func.azurewebsites.net/api`

### `POST /TriggerCompile`
Compile source code in the cloud.

**Request body:**
```json
{
  "code": "#include<stdio.h>\nint main(){ printf(\"Hello!\"); return 0; }",
  "optimization": "O2",
  "language": "c",
  "userId": "user1"
}
```

**Response:**
```json
{
  "jobId": "uuid-string",
  "results": {
    "O2": { "returncode": 0, "stdout": "", "stderr": "", "success": true }
  }
}
```

**Supported languages:** `c`, `cpp`, `python`, `java`, `go`, `rust`

**Optimization levels:** `O0`, `O1`, `O2`, `O3`, `all`

---

### `POST /ExplainError`
Get an AI-powered explanation of a compiler error.

**Request body:**
```json
{ "error": "error: use of undeclared identifier 'x'" }
```

**Response:**
```json
{
  "errorType": "Undeclared Variable",
  "explanation": "You used a variable that was never declared. Add the type before the variable name.",
  "keyPhrases": ["undeclared identifier", "error"]
}
```

---

### `GET /GetHistory?userId=user1`
Retrieve the last 20 compilation jobs for a user.

**Response:**
```json
[
  {
    "RowKey": "uuid",
    "timestamp": "2024-11-01T10:00:00Z",
    "optimization": "O2",
    "language": "c",
    "success": true,
    "codeLength": 85
  }
]
```

---

## 💰 Cost Summary (Azure Students Free Tier)

| Service | Free Limit | Expected Usage | Cost |
|---|---|---|---|
| Azure Functions | 1M executions/month | ~1000/month | Free |
| Azure Blob Storage | 5 GB LRS | < 100 MB | Free |
| Azure Table Storage | Bundled with Blob Storage | < 10 MB | Free |
| Container Apps | 180K vCPU-s/month | ~10K vCPU-s | Free |
| Static Web Apps | Free (F1) | 1 app | Free |
| AI Language Service | 5000 records/month | ~500/month | Free (F0) |
| Application Insights | 5 GB ingestion | < 100 MB | Free |
| Container Registry | Basic SKU | 1 image | ~$5/month |

> **Note:** Azure Table Storage is bundled inside the Blob Storage account — no separate resource or cost.

---

## 👩‍💻 Author

**Swarna Dharshini S** — Azure Students Account  
19CSE445 Cloud Computing, Amrita School of Computing, Coimbatore
