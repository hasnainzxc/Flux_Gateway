# Security Model

> Multi-layer tenant isolation, credential management, sandbox boundaries, and API security.

## Threat Model

| Threat | Layer | Mitigation |
|--------|-------|------------|
| Tenant A reads Tenant B's data | DB, ORM, API | Triple-layer tenant_id filter |
| LLM hallucinates and corrupts production DB | Agent | Schema grounding + Reviewer sandbox validation |
| Malicious code in sandbox escapes | Sandbox | No network, tmpfs, CPU/mem limits, ephemeral |
| Connection string leak | Storage | AES-256-GCM encrypted at rest, key in env var |
| API key theft | Auth | Hashed storage, rate limiting, audit logging |
| Webhook spoofing | Events | API key validation + optional HMAC signing |
| SQL injection via LLM output | Agent | Parameterized queries, Reviewer checks, read-only connection for reflection |
| Cross-tenant vector search | RAG | Hardcoded WHERE tenant_id, enforced at ORM level |

## Tenant Isolation — Triple Layer

### Layer 1: Database Row-Level Security

```sql
-- Every tenant-scoped table
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### Layer 2: ORM Event Listener

```python
# Enforced on every query — cannot be bypassed
@event.listens_for(Session, "do_orm_execute")
def inject_tenant_filter(execute_state):
    tenant_id = get_current_tenant()  # From context var
    if tenant_id and execute_state.is_select:
        for table in get_tables(execute_state.statement):
            if hasattr(table, "tenant_id"):
                execute_state.statement = execute_state.statement.where(
                    table.tenant_id == tenant_id
                )
```

### Layer 3: FastAPI Dependency

```python
# Extracted from API key, never from client payload
async def get_current_tenant(
    api_key: str = Header(alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    tenant = await auth_service.validate_api_key(api_key, db)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Set context var for ORM listener
    set_current_tenant(tenant.id)
    return tenant
```

## Credential Storage

```python
from cryptography.fernet import Fernet

class SecretManager:
    """Encrypt/decrypt sensitive values using Fernet (AES-128-CBC, upgraded to AES-256-GCM)."""
    
    def __init__(self):
        self.cipher = Fernet(os.environ["SECRET_ENCRYPTION_KEY"])
    
    def encrypt(self, plaintext: str) -> bytes:
        return self.cipher.encrypt(plaintext.encode())
    
    def decrypt(self, ciphertext: bytes) -> str:
        return self.cipher.decrypt(ciphertext).decode()

# Storage: encrypted value in DB, key in environment variable
# Rotation: versioned keys — store key_version alongside encrypted value
```

Storage schema:
```sql
CREATE TABLE credentials (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    service_type VARCHAR(50) NOT NULL,  -- 'postgresql', 'mysql', 'openai', 'odoo_api'
    encrypted_value BYTEA NOT NULL,
    key_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    CONSTRAINT fk_creds_tenant FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
```

## Sandbox Security

```python
SANDBOX_CONFIG = {
    "network_disabled": True,      # No outbound connections
    "mem_limit": "256m",           # Hard memory cap
    "cpu_quota": 50000,            # 0.5 CPU max
    "tmpfs": {"/tmp": "size=64m"}, # Ephemeral, in-memory only
    "read_only_rootfs": True,      # Cannot modify filesystem
    "security_opt": ["no-new-privileges:true"],
    "cap_drop": ["ALL"],           # Drop all Linux capabilities
    "timeout": 30,                 # Kill after 30 seconds
    "auto_remove": True,           # Destroy on stop
    "labels": {
        "purpose": "code-review",
        "managed_by": "flux-gateway",
    },
}
```

Dangerous SQL operations blocked by Reviewer:
```python
DANGEROUS_PATTERNS = [
    r"\bDROP\b",
    r"\bTRUNCATE\b",
    r"\bALTER\b",
    r"\bCREATE\b",
    r"\bGRANT\b",
    r"\bREVOKE\b",
    r"\bCOPY\b.*FROM",
    r";\s*--",  # SQL injection attempt
]

def check_dangerous_operations(sql: str) -> list[str]:
    warnings = []
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            warnings.append(f"Dangerous operation detected: {pattern}")
    return warnings
```

## API Security

```python
# Rate limiting (Redis token bucket)
class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis
    
    async def check(self, tenant_id: str, limit: int = 100, window: int = 60) -> bool:
        key = f"ratelimit:{tenant_id}:{int(time() / window)}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, window)
        return count <= limit

# FastAPI middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # CORS check
    origin = request.headers.get("origin")
    if origin and origin not in ALLOWED_ORIGINS:
        return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
    
    # Rate limit check (if API key present)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        tenant = await get_tenant_from_key(api_key)
        if not await rate_limiter.check(tenant.id):
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
    
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    
    return response
```

## Audit Logging

```python
# Every security-relevant action logged
async def log_security_event(
    tenant_id: str,
    event_type: str,  # "api_key_created", "connection_added", "query_executed", etc.
    details: dict,
    db: AsyncSession,
):
    event = SecurityAuditLog(
        tenant_id=tenant_id,
        event_type=event_type,
        details=details,
        ip_address=get_client_ip(),
        user_agent=get_user_agent(),
        timestamp=datetime.utcnow(),
    )
    db.add(event)
    await db.commit()
```

## Deployment Security Checklist

- [ ] `SECRET_ENCRYPTION_KEY` in environment, never in code/config
- [ ] Database connection uses TLS
- [ ] pgvector extension installed with RLS enabled
- [ ] Redis password-protected
- [ ] Docker daemon socket restricted
- [ ] API rate limiting active
- [ ] CORS restricted to dashboard domains only
- [ ] Security headers on all responses
- [ ] Audit logging active
- [ ] Regular dependency vulnerability scanning (`pip-audit`, `npm audit`)
