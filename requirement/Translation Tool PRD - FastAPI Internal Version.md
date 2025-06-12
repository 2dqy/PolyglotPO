# Product Requirements Document (PRD)
## Internal PO File Translation Tool - FastAPI Application

### 1. Product Overview

**Product Name:** Internal PO Translation Tool
**Version:** 1.0
**Date:** June 2025
**Target:** Internal company use only

**Purpose:** 
A FastAPI-based web application for internal teams to upload PO (Portable Object) files and translate them to different languages using DeepSeek AI translation service.

**Target Users:**
- Internal development teams
- Localization teams within the organization
- Product managers handling i18n projects
- QA teams testing multilingual features

### 2. Core Features & Requirements

#### 2.1 File Upload & Processing
- **Upload Interface:** HTML form with drag-and-drop support
- **File Validation:** Server-side PO file format validation
- **File Size Limit:** Support files up to 50MB (internal use)
- **Supported Formats:** .po files (GNU gettext format)
- **Temporary Storage:** Files stored temporarily during processing

#### 2.2 Translation Engine Integration
- **AI Provider:** DeepSeek API integration (API Key - sk-a608b107120e4f1491535727fb1a1be7)
- **Batch Processing:** Efficient translation of multiple strings
- **Rate Limiting:** Built-in rate limiting and queue management
- **Context Preservation:** Maintain PO file structure and metadata
- **Error Recovery:** Robust error handling and retry mechanisms

#### 2.3 Internal User Features
- **No Authentication:** Simple internal access (can add basic auth later)
- **Session Management:** Track translation jobs per session
- **Job History:** View recent translation jobs
- **Admin Dashboard:** Monitor system usage and performance

### 3. Technical Architecture

#### 3.1 FastAPI Application Structure
```
translation_tool/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration settings
│   ├── dependencies.py            # Dependency injection
│   │
│   ├── api/                       # API routes
│   │   ├── __init__.py
│   │   ├── upload.py              # File upload endpoints
│   │   ├── translate.py           # Translation endpoints
│   │   ├── download.py            # File download endpoints
│   │   └── admin.py               # Admin/monitoring endpoints
│   │
│   ├── core/                      # Core business logic
│   │   ├── __init__.py
│   │   ├── po_parser.py           # PO file parsing logic
│   │   ├── translation_service.py # Translation orchestration
│   │   ├── deepseek_client.py     # DeepSeek API client
│   │   └── file_manager.py        # File handling utilities
│   │
│   ├── models/                    # Data models
│   │   ├── __init__.py
│   │   ├── po_models.py           # PO file data structures
│   │   ├── translation_models.py  # Translation request/response models
│   │   └── job_models.py          # Translation job models
│   │
│   ├── templates/                 # Jinja2 HTML templates
│   │   ├── base.html              # Base template
│   │   ├── index.html             # Main upload page
│   │   ├── progress.html          # Translation progress page
│   │   ├── results.html           # Results and download page
│   │   ├── history.html           # Job history page
│   │   └── admin.html             # Admin dashboard
│   │
│   ├── static/                    # Static files
│   │   ├── css/
│   │   │   └── styles.css         # Custom styles
│   │   ├── js/
│   │   │   ├── upload.js          # File upload handling
│   │   │   ├── progress.js        # Progress tracking
│   │   │   └── main.js            # General functionality
│   │   └── images/
│   │
│   ├── utils/                     # Utility functions
│   │   ├── __init__.py
│   │   ├── validators.py          # Input validation
│   │   ├── helpers.py             # General helpers
│   │   └── exceptions.py          # Custom exceptions
│   │
│   └── storage/                   # File storage
│       ├── uploads/               # Temporary uploaded files
│       ├── processed/             # Processed files
│       └── downloads/             # Files ready for download
│
├── tests/                         # Test files
├── requirements.txt               # Python dependencies
├── docker-compose.yml             # Docker setup
├── Dockerfile                     # Docker image
└── README.md                      # Documentation
```

#### 3.2 Technology Stack

**Backend Framework:**
- **FastAPI** - Modern, fast web framework
- **Uvicorn** - ASGI server
- **Jinja2** - HTML templating
- **Pydantic** - Data validation
- **aiofiles** - Async file operations

**Core Libraries:**
- **polib** - PO file parsing and manipulation
- **aiohttp** - Async HTTP client for DeepSeek API
- **python-multipart** - File upload handling
- **python-jose** - JWT handling (if auth needed later)

**Development & Deployment:**
- **Docker** - Containerization
- **pytest** - Testing framework
- **black** - Code formatting
- **flake8** - Code linting

### 4. Implementation Details

#### 4.1 Core Models
```python
# models/po_models.py
from pydantic import BaseModel
from typing import List, Optional, Dict

class POEntry(BaseModel):
  msgid: str
  msgstr: str
  msgctxt: Optional[str] = None
  comments: List[str] = []
  references: List[str] = []
  flags: List[str] = []

class POFile(BaseModel):
  headers: Dict[str, str]
  entries: List[POEntry]
  metadata: Dict[str, str]

# models/translation_models.py
class TranslationJob(BaseModel):
  job_id: str
  filename: str
  source_language: str
  target_language: str
  status: str  # pending, processing, completed, failed
  progress: int = 0
  created_at: datetime
  completed_at: Optional[datetime] = None
  error_message: Optional[str] = None
```

#### 4.2 Main FastAPI Application
```python
# main.py
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
  title="Internal PO Translation Tool",
  description="Translate PO files using DeepSeek AI",
  version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
from app.api import upload, translate, download, admin
app.include_router(upload.router, prefix="/api")
app.include_router(translate.router, prefix="/api")
app.include_router(download.router, prefix="/api")
app.include_router(admin.router, prefix="/admin")

@app.get("/")
async def home(request: Request):
  return templates.TemplateResponse("index.html", {"request": request})
```

#### 4.3 File Upload Handler
```python
# api/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.po_parser import validate_po_file
from app.core.file_manager import save_uploaded_file

router = APIRouter()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
  # Validate file type
  if not file.filename.endswith('.po'):
      raise HTTPException(400, "Only .po files are supported")
  
  # Validate file size (50MB limit)
  if file.size > 50 * 1024 * 1024:
      raise HTTPException(400, "File too large")
  
  # Save and validate PO file
  file_path = await save_uploaded_file(file)
  is_valid, errors = await validate_po_file(file_path)
  
  if not is_valid:
      raise HTTPException(400, f"Invalid PO file: {errors}")
  
  return {"file_id": file_path.stem, "filename": file.filename}
```

#### 4.4 Translation Service
```python
# core/translation_service.py
import asyncio
from typing import List
from app.core.deepseek_client import DeepSeekClient
from app.models.po_models import POFile, POEntry

class TranslationService:
  def __init__(self):
      self.deepseek_client = DeepSeekClient()
      self.max_concurrent = 5  # Limit concurrent API calls
  
  async def translate_po_file(
      self, 
      po_file: POFile, 
      target_language: str,
      progress_callback=None
  ) -> POFile:
      """Translate entire PO file"""
      semaphore = asyncio.Semaphore(self.max_concurrent)
      
      async def translate_entry(entry: POEntry, index: int) -> POEntry:
          async with semaphore:
              if entry.msgid and not entry.msgstr:
                  translated = await self.deepseek_client.translate(
                      text=entry.msgid,
                      target_language=target_language,
                      context=entry.msgctxt
                  )
                  entry.msgstr = translated
              
              if progress_callback:
                  await progress_callback(index + 1, len(po_file.entries))
              
              return entry
      
      # Translate all entries concurrently
      tasks = [
          translate_entry(entry, i) 
          for i, entry in enumerate(po_file.entries)
      ]
      
      translated_entries = await asyncio.gather(*tasks)
      
      # Update PO file with translations
      po_file.entries = translated_entries
      po_file.headers["Language"] = target_language
      
      return po_file
```

#### 4.5 HTML Templates

**Base Template (base.html):**
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}PO Translation Tool{% endblock %}</title>
  <link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet">
  <link rel="stylesheet" href="{{ url_for('static', path='/css/styles.css') }}">
</head>
<body class="bg-gray-100">
  <nav class="bg-blue-600 text-white p-4">
      <div class="container mx-auto">
          <h1 class="text-xl font-bold">Internal PO Translation Tool</h1>
      </div>
  </nav>
  
  <main class="container mx-auto py-8">
      {% block content %}{% endblock %}
  </main>
  
  <script src="{{ url_for('static', path='/js/main.js') }}"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

**Main Upload Page (index.html):**
```html
{% extends "base.html" %}

{% block content %}
<div class="max-w-4xl mx-auto">
  <div class="bg-white rounded-lg shadow-md p-6">
      <h2 class="text-2xl font-bold mb-6">Upload PO File for Translation</h2>
      
      <form id="uploadForm" class="space-y-6">
          <!-- Language Selection -->
          <div class="grid grid-cols-2 gap-4">
              <div>
                  <label class="block text-sm font-medium mb-2">Source Language</label>
                  <select id="sourceLanguage" class="w-full border rounded-md p-2">
                      <option value="auto">Auto-detect</option>
                      <option value="en">English</option>
                      <option value="es">Spanish</option>
                      <!-- More languages -->
                  </select>
              </div>
              <div>
                  <label class="block text-sm font-medium mb-2">Target Language</label>
                  <select id="targetLanguage" class="w-full border rounded-md p-2" required>
                      <option value="">Select target language</option>
                      <option value="es">Spanish</option>
                      <option value="fr">French</option>
                      <option value="de">German</option>
                      <!-- More languages -->
                  </select>
              </div>
          </div>
          
          <!-- File Upload -->
          <div id="dropZone" class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition-colors">
              <div class="space-y-4">
                  <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <div>
                      <p class="text-lg">Drop your PO file here or</p>
                      <button type="button" id="selectFile" class="text-blue-600 hover:text-blue-500">click to select</button>
                      <input type="file" id="fileInput" accept=".po" class="hidden">
                  </div>
                  <p class="text-sm text-gray-500">Maximum file size: 50MB</p>
              </div>
          </div>
          
          <!-- Selected File Display -->
          <div id="selectedFile" class="hidden bg-blue-50 border border-blue-200 rounded-md p-4">
              <div class="flex items-center justify-between">
                  <div>
                      <p class="font-medium" id="fileName"></p>
                      <p class="text-sm text-gray-600" id="fileSize"></p>
                  </div>
                  <button type="button" id="removeFile" class="text-red-600 hover:text-red-500">Remove</button>
              </div>
          </div>
          
          <!-- Submit Button -->
          <button type="submit" id="translateBtn" class="w-full bg-blue-600 text-white py-3 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">
              Start Translation
          </button>
      </form>
  </div>
  
  <!-- Recent Jobs -->
  <div class="mt-8 bg-white rounded-lg shadow-md p-6">
      <h3 class="text-lg font-bold mb-4">Recent Translation Jobs</h3>
      <div id="recentJobs">
          <!-- Jobs will be loaded here -->
      </div>
  </div>
</div>
{% endblock %}

{% block scripts %}
<script src="{{ url_for('static', path='/js/upload.js') }}"></script>
{% endblock %}
```

### 5. Development Phases

#### Phase 1: Core Infrastructure (Week 1)
- [ ] FastAPI application setup
- [ ] Basic HTML templates and static files
- [ ] File upload functionality
- [ ] PO file parser integration
- [ ] Basic DeepSeek API client

#### Phase 2: Translation Engine (Week 2)
- [ ] Translation service implementation
- [ ] Async job processing
- [ ] Progress tracking system
- [ ] Error handling and recovery
- [ ] File download functionality

#### Phase 3: User Interface (Week 3)
- [ ] Enhanced HTML templates
- [ ] JavaScript for file upload and progress
- [ ] Real-time progress updates
- [ ] Job history and management
- [ ] Admin dashboard

#### Phase 4: Production Ready (Week 4)
- [ ] Docker containerization
- [ ] Configuration management
- [ ] Logging and monitoring
- [ ] Testing suite
- [ ] Documentation

### 6. Configuration & Deployment

#### 6.1 Environment Configuration
```python
# config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
  # DeepSeek API
  deepseek_api_key: str
  deepseek_base_url: str = "https://api.deepseek.com"
  
  # File storage
  upload_dir: str = "app/storage/uploads"
  processed_dir: str = "app/storage/processed"
  download_dir: str = "app/storage/downloads"
  max_file_size: int = 50 * 1024 * 1024  # 50MB
  
  # Translation settings
  max_concurrent_translations: int = 5
  translation_timeout: int = 300  # 5 minutes
  
  # Application
  debug: bool = False
  host: str = "0.0.0.0"
  port: int = 8000
  
  class Config:
      env_file = ".env"

settings = Settings()
```

#### 6.2 Docker Setup
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
translation-tool:
  build: .
  ports:
    - "8000:8000"
  environment:
    - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
  volumes:
    - ./app/storage:/app/app/storage
  restart: unless-stopped
```

### 7. Security & Internal Use

#### 7.1 Internal Security Measures
- **Network Access:** Deploy on internal network only
- **File Validation:** Strict PO file validation
- **Input Sanitization:** Sanitize all user inputs
- **Rate Limiting:** Prevent API abuse
- **File Cleanup:** Automatic cleanup of temporary files

#### 7.2 Optional Authentication (Future)
```python
# For future implementation if needed
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
  # Simple basic auth for internal use
  if credentials.username != "internal" or credentials.password != "password":
      raise HTTPException(
          status_code=status.HTTP_401_UNAUTHORIZED,
          detail="Invalid credentials"
      )
  return credentials.username
```

### 8. Monitoring & Maintenance

#### 8.1 Logging Strategy
```python
import logging
from app.config import settings

logging.basicConfig(
  level=logging.INFO if not settings.debug else logging.DEBUG,
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)
```

#### 8.2 Health Checks
```python
@app.get("/health")
async def health_check():
  return {
      "status": "healthy",
      "timestamp": datetime.utcnow(),
      "version": "1.0.0"
  }
```

### 9. Testing Strategy

```python
# tests/test_translation.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_upload_valid_po_file():
  with open("tests/sample.po", "rb") as f:
      response = client.post(
          "/api/upload",
          files={"file": ("sample.po", f, "application/octet-stream")}
      )
  assert response.status_code == 200

def test_translate_po_file():
  # Test translation functionality
  pass
```

### 10. Success Metrics for Internal Tool

- **Adoption Rate:** 80% of localization team using within 1 month
- **Processing Speed:** <2 minutes for typical PO files
- **Reliability:** 99% uptime during business hours
- **User Satisfaction:** Positive feedback from internal teams
- **Error Rate:** <1% translation job failures

---

**Development Notes:**
- Start with MVP focusing on core upload/translate/download workflow
- Use simple HTML/CSS/JS for UI (no complex frontend framework needed)
- Implement proper async handling for file processing
- Add comprehensive logging for debugging internal issues
- Design for easy deployment on internal infrastructure