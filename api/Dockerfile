FROM ghcr.io/prefix-dev/pixi:0.67.2 AS build

WORKDIR /app
COPY pixi.toml pixi.lock ./
RUN pixi install --frozen -e api

FROM debian:bookworm-slim AS runtime

WORKDIR /app
COPY --from=build /app/.pixi/envs/api /app/.pixi/envs/api
COPY api/ ./api/

ENV PATH="/app/.pixi/envs/api/bin:$PATH"
ENV PYTHONPATH="/app"

EXPOSE 8080
CMD ["uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
