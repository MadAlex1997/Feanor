---
title: Traefik routing to FastAPI with JWT validation
phase: 0
status: Completed
---

## Description

Configure Traefik v3 to route external HTTP traffic to the FastAPI `api` service
and validate JWT bearer tokens on every request before forwarding. Traefik should
verify the token signature using Keycloak's JWKS endpoint — no business logic in
the gateway.

## Acceptance criteria

- [ ] All requests to `http://localhost:8000/v1/*` are routed to the `api` container.
- [ ] Traefik fetches Keycloak's JWKS from
      `http://keycloak:8080/realms/feanor/protocol/openid-connect/certs`
      and validates JWT signatures on every request.
- [ ] A request with a valid JWT is forwarded to the API and returns the expected response.
- [ ] A request with no `Authorization` header returns `401` from Traefik (not the API).
- [ ] A request with an expired or invalid JWT returns `401` from Traefik.
- [ ] `GET /health` and `GET /ready` are reachable **without** a JWT (public routes).
- [ ] `GET /docs` and `GET /openapi.json` are reachable without a JWT (dev convenience).
- [ ] Traefik config (static + dynamic) is stored in `traefik/` in the repo and
      mounted into the container — not baked into the image.
- [ ] Rate limiting middleware is defined (even if limits are permissive for MVP):
      e.g., 100 req/s per IP.

## Dependencies

- task-001 (Traefik and Keycloak containers running)
- task-002 (Keycloak `feanor` realm and JWKS endpoint available)
- task-003 (FastAPI `api` service running and added to Docker Compose)

## Notes

- Traefik v3 supports JWT validation via the `plugin` or `forwardAuth` middleware.
  The `forwardAuth` approach (delegating auth to a small sidecar) is simpler to
  maintain than a custom plugin. Evaluate both and document the choice.
- Do not implement claim-level role enforcement in Traefik — that stays in the
  FastAPI route handlers (Phase 1). Traefik only verifies the signature and expiry.
- Public routes (`/health`, `/ready`, `/docs`, `/openapi.json`) should be
  explicitly listed in the Traefik dynamic config, not inferred.
