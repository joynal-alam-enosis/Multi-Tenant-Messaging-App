# S3 Integration via MiniStack — Implementation Plan

> **Status**: Draft  
> **Created**: 2026-09-29  
> **References**: `docs/MINISTACK_COGNITO_PLAN.md`, `SYSTEM_DESIGN.md`, MiniStack S3 API docs

---

## 1. Goal

Replace local filesystem storage for conversation exports with **S3-compatible object storage** using **MiniStack** (local) / **AWS S3** (production). Export files are uploaded to S3 instead of written to `backend/exports/`, and downloads are served via presigned URLs or streaming from S3.

---

## 2. Current Export Flow (as-is)

```
User → POST /api/conversations/{id}/export/
     → Celery task `export_conversation`
     → Writes JSON to `backend/exports/export_{task_id}.json`
     → Updates ExportTask.file_path
User → GET /api/exports/{id}/download/
     → Django FileResponse streams local file
```

---

## 3. Target Flow (S3 via MiniStack)

```
User → POST /api/conversations/{id}/export/
     → Celery task `export_conversation`
     → Builds JSON in memory
     → Uploads to S3 (MiniStack): s3://messaging-exports/{user_id}/{task_id}.json
     → Updates ExportTask.s3_key, ExportTask.s3_bucket
User → GET /api/exports/{id}/download/
     → Option A: Generate presigned URL → redirect to S3
     → Option B: Stream from S3 → FileResponse (proxy)
     → Option C: Return presigned URL in JSON (frontend handles download)
```

---

## 4. MiniStack S3 Capabilities

| Feature | MiniStack Support |
|---------|-------------------|
| **S3 API** | Yes — `s3` service on port 4566 |
| **Buckets** | CreateBucket, ListBuckets, HeadBucket |
| **Objects** | PutObject, GetObject, DeleteObject, HeadObject |
| **Presigned URLs** | Yes (via boto3 generate_presigned_url) |
| **Multipart Upload** | Basic support |
| **Lifecycle/Versioning** | Limited |
| **Endpoint** | `http://ministack:4566` (internal), `http://localhost:4566` (host) |
| **Auth** | Dummy keys (`test`/`test`) work locally |

> **Note**: MiniStack S3 is compatible with `boto3` using `endpoint_url=http://ministack:4566`.

---

## 5. Change Scope

### 5.1 In Scope (Must Change)

| Area | Change |
|------|--------|
| **ExportTask model** | Add `s3_bucket`, `s3_key`, `s3_etag`; deprecate `file_path` |
| **Celery task** | Upload JSON to S3 instead of local file |
| **Download view** | Generate presigned URL or stream from S3 |
| **Docker Compose** | Ensure MiniStack S3 port exposed (already on 4566) |
| **Environment** | Add `EXPORT_S3_BUCKET` (default: `messaging-exports`) |
| **Tests** | Mock S3 or use MiniStack in integration tests |

### 5.2 Out of Scope

- Frontend UI changes (download still works via same endpoint)
- Celery worker config (uses same env vars)
- Cognito/auth integration (unchanged)

### 5.3 Deferred / Optional

- Multipart upload for large exports (>100MB)
- Server-side encryption (SSE-S3)
- Cross-region replication
- Export retention policies (lifecycle rules)

---

## 6. Implementation Plan

### Phase 1 — Model & Migration

**Files**: `apps/exports/models.py` (+ migration)

```python
# Add to ExportTask:
s3_bucket = models.CharField(max_length=255, blank=True, default="")
s3_key = models.CharField(max_length=500, blank=True, default="")
s3_etag = models.CharField(max_length=100, blank=True, default="")
# file_path kept for backward compat during transition
```

Run `makemigrations exports` and `migrate`.

---

### Phase 2 — S3 Client Helper

**New file**: `apps/exports/s3.py`

```python
import boto3
from botocore.client import Config
from django.conf import settings

def get_s3_client():
    """Returns boto3 S3 client configured for MiniStack or real AWS."""
    kwargs = {
        "service_name": "s3",
        "region_name": getattr(settings, "AWS_REGION", "us-east-1"),
        "aws_access_key_id": os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        "aws_secret_access_key": os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    }
    endpoint = getattr(settings, "AWS_ENDPOINT_URL", None) or os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
        # MiniStack needs path-style addressing
        kwargs["config"] = Config(s3={"addressing_style": "path"})
    return boto3.client(**kwargs)

def ensure_bucket_exists(bucket_name: str = None):
    """Idempotently create the exports bucket."""
    bucket = bucket_name or getattr(settings, "EXPORT_S3_BUCKET", "messaging-exports")
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
    except client.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            client.create_bucket(Bucket=bucket)
        else:
            raise
    return bucket
```

---

### Phase 3 — Update Celery Task

**File**: `apps/exports/tasks.py`

```python
@shared_task
def export_conversation(export_task_id: str):
    from apps.exports.s3 import get_s3_client, ensure_bucket_exists
    
    try:
        task = ExportTask.objects.select_related('conversation').get(id=export_task_id)
        task.status = ExportTask.Status.PROCESSING
        task.save()

        # ... build JSON data (same as before) ...
        
        # Upload to S3
        bucket = ensure_bucket_exists()
        s3_key = f"exports/{task.user_id}/{task.id}.json"
        
        client = get_s3_client()
        response = client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json.dumps(data, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        
        # Update task with S3 info
        task.status = ExportTask.Status.COMPLETED
        task.s3_bucket = bucket
        task.s3_key = s3_key
        task.s3_etag = response.get("ETag", "").strip('"')
        task.completed_at = timezone.now()
        task.save()
        
    except Exception as e:
        # ... error handling ...
```

---

### Phase 4 — Update Download View

**File**: `apps/exports/views.py`

**Option A: Presigned URL redirect (recommended for large files)**
```python
class DownloadExportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        task = get_object_or_404(ExportTask, pk=pk, user=request.user)
        
        if task.status != ExportTask.Status.COMPLETED:
            return Response({"error": "Export is not ready yet."}, status=400)
        
        if not task.s3_key:
            return Response({"error": "Export file not found (no S3 key)."}, status=404)
        
        client = get_s3_client()
        presigned_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": task.s3_bucket, "Key": task.s3_key},
            ExpiresIn=3600,  # 1 hour
        )
        
        return HttpResponseRedirect(presigned_url)
```

**Option B: Return presigned URL as JSON (frontend handles download)**
```python
        return Response({
            "download_url": presigned_url,
            "filename": f"conversation_export_{task.id}.json",
            "expires_in": 3600,
        })
```

**Option C: Stream from S3 (proxy, no redirect)**
```python
        obj = client.get_object(Bucket=task.s3_bucket, Key=task.s3_key)
        return FileResponse(
            obj["Body"],
            as_attachment=True,
            filename=f"conversation_export_{task.id}.json",
            content_type="application/json",
        )
```

> **Recommendation**: Option A for simplicity; Option B if frontend needs to show progress.

---

### Phase 5 — Configuration

**Add to `config/settings.py`**:
```python
EXPORT_S3_BUCKET = os.environ.get("EXPORT_S3_BUCKET", "messaging-exports")
```

**Add to `docker-compose.yml` (backend & celery_worker)**:
```yaml
environment:
  - EXPORT_S3_BUCKET=messaging-exports
  - AWS_ENDPOINT_URL=http://ministack:4566
  - AWS_REGION=us-east-1
  - AWS_ACCESS_KEY_ID=test
  - AWS_SECRET_ACCESS_KEY=test
```

---

### Phase 6 — Bucket Bootstrap

**New management command**: `apps/exports/management/commands/bootstrap_exports_bucket.py`

```python
from django.core.management.base import BaseCommand
from apps.exports.s3 import ensure_bucket_exists

class Command(BaseCommand):
    help = "Ensure S3 exports bucket exists (idempotent)"

    def handle(self, *args, **options):
        bucket = ensure_bucket_exists()
        self.stdout.write(self.style.SUCCESS(f"Export bucket ready: {bucket}"))
```

**Update backend startup command in `docker-compose.yml`**:
```yaml
command: >
  sh -c "python manage.py bootstrap_cognito &&
         python manage.py bootstrap_exports_bucket &&
         python manage.py migrate &&
         python manage.py seed || true &&
         daphne -b 0.0.0.0 -p 8000 config.asgi:application"
```

---

### Phase 7 — Tests

| Test | Approach |
|------|----------|
| Unit: task uploads to S3 | Mock `boto3.client` |
| Integration: full flow with MiniStack | Use MiniStack S3 in test container |
| Download view returns presigned URL | Verify URL format + expiry |
| Bucket bootstrap idempotent | Run twice, verify no error |

**New test file**: `backend/tests/test_exports_s3.py`

---

## 7. File Summary

| File | Action |
|------|--------|
| `apps/exports/models.py` | Add S3 fields + migration |
| `apps/exports/s3.py` | **NEW** - S3 client + bucket helper |
| `apps/exports/tasks.py` | Upload to S3 instead of local file |
| `apps/exports/views.py` | Generate presigned URL for download |
| `apps/exports/management/commands/bootstrap_exports_bucket.py` | **NEW** - bucket creation |
| `config/settings.py` | Add `EXPORT_S3_BUCKET` setting |
| `docker-compose.yml` | Add `EXPORT_S3_BUCKET` env var |
| `backend/tests/test_exports_s3.py` | **NEW** - S3 export tests |

---

## 8. Migration Strategy

1. **Deploy model changes** (add S3 fields, keep `file_path`)
2. **Deploy S3 upload logic** (writes to both S3 and local for transition)
3. **Switch download to S3** (presigned URL)
4. **Remove local file write** after verification
5. **Optional**: Migrate existing exports to S3 (one-off script)

---

## 9. Effort Estimate

| Phase | Effort |
|-------|--------|
| Phase 1: Model & Migration | S |
| Phase 2: S3 Client Helper | S |
| Phase 3: Celery Task Update | M |
| Phase 4: Download View | S |
| Phase 5: Configuration | S |
| Phase 6: Bucket Bootstrap | S |
| Phase 7: Tests | M |
| **Total** | **~2-3 days** |

---

## 10. Open Questions

1. **Presigned URL vs Streaming**: Which download approach? (A/B/C above)
2. **Bucket naming**: Per-environment buckets (`messaging-exports-dev`, `messaging-exports-prod`) or single with prefixes?
3. **Retention**: Auto-delete exports after N days via S3 lifecycle?
4. **Frontend**: Handle redirect (Option A) or fetch blob (Option B)?
5. **Large exports**: Need multipart upload for conversations with >50k messages?