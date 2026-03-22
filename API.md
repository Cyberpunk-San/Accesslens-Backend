# AccessLens API Technical Reference

AccessLens provides a RESTful API for automated web accessibility auditing. All API endpoints are versioned under `/api/v1/`.

---

## Infrastructure Endpoints

### Root Information
Returns basic API metadata and available endpoint groups.

**Method:** `GET`  
**Path:** `/`

#### Response Sample
```json
{
  "name": "AccessLens API",
  "version": "1.0.0",
  "documentation": "/docs",
  "endpoints": {
    "health": "/health",
    "metrics": "/metrics",
    "api_v1": "/api/v1"
  }
}
```

---

### Health Check
Monitors the operational status of the API and its internal engines.

**Method:** `GET`  
**Path:** `/health`

#### Response Sample
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": 1711094400.0,
  "engines": [
    {
      "name": "wcag_deterministic",
      "version": "1.0.0",
      "capabilities": ["wcag_21", "aria_validation"]
    }
  ]
}
```

---

### Prometheus Metrics
Exposes real-time performance data for monitoring.

**Method:** `GET`  
**Path:** `/metrics`

---

## Core Audit API (`/api/v1`)

### Start Accessibility Audit
Initiates an asynchronous audit of a target URL using specified analysis engines.

**Method:** `POST`  
**Path:** `/api/v1/audit`

#### Request Body (`AuditRequest`)
| Field | Type | Default | Description |
|---|---|---|---|
| `url` | `string` | **Required** | The public URL to audit. Must be reachable by the backend. |
| `engines` | `array[string]` | `["wcag", "structural", "contrast", "heuristic", "navigation", "form"]` | List of engine aliases to execute. |
| `enable_ai` | `boolean` | `false` | Enable the AI contextual analysis layer. |
| `viewport` | `object` | `{"width": 1280, "height": 720}` | Browser viewport dimensions for visual analysis. |

#### Code Snippets

**Python (httpx)**
```python
import httpx

payload = {
    "url": "https://example.com",
    "engines": ["wcag", "contrast", "ai"],
    "enable_ai": True
}

with httpx.Client() as client:
    response = client.post("http://localhost:8000/api/v1/audit", json=payload)
    print(response.json())
```

**cURL**
```bash
curl -X POST http://localhost:8000/api/v1/audit \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://example.com",
       "engines": ["wcag", "structural"],
       "enable_ai": false
     }'
```

---

### Get Audit Results
Retrieves the full `AuditReport` once processing is complete.

**Method:** `GET`  
**Path:** `/api/v1/audit/{audit_id}`

#### Response Sample (`AuditReport`)
```json
{
  "id": "uuid-v4",
  "timestamp": "2024-03-22T10:00:00Z",
  "summary": {
    "total_issues": 12,
    "by_severity": { "critical": 2, "serious": 4, "moderate": 6, "minor": 0 },
    "score": 82.5,
    "confidence_avg": 94.2
  },
  "issues": [
    {
      "id": "issue-uuid",
      "title": "Missing alt attribute",
      "severity": "serious",
      "confidence": "high",
      "engine_name": "wcag_deterministic",
      "location": { "selector": "img.hero-banner" },
      "remediation": { "description": "Add a descriptive alt attribute." }
    }
  ]
}
```

---

### Get Audit Status
Polls the completion status of a specific audit.

**Method:** `GET`  
**Path:** `/api/v1/audit/{audit_id}/status`

---

### List Recent Audits
Returns a paginated list of previously completed audit summaries.

**Method:** `GET`  
**Path:** `/api/v1/audit`

---

### List Available Engines
Returns all registered engines and their capabilities.

**Method:** `GET`  
**Path:** `/api/v1/engines`
