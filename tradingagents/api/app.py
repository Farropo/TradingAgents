"""Local FastAPI app for TradingAgents."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tradingagents.api.routers import analysis, codex, config, dashboard, fiscal, ledger, markets, reports
from tradingagents.api.schemas import HealthResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title="TradingAgents Local API",
        version="0.1.0",
        description="Local-only API for analysis, Codex-assisted workflows, ledger, and PT fiscal dossier.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    def health():
        return HealthResponse()

    app.include_router(config.router)
    app.include_router(dashboard.router)
    app.include_router(codex.router)
    app.include_router(ledger.router)
    app.include_router(fiscal.router)
    app.include_router(analysis.router)
    app.include_router(markets.router)
    app.include_router(reports.router)
    return app


app = create_app()
