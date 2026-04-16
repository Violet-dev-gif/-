from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.database import Base, engine
from app.schemas import HealthResponse, ModelInfoResponse, SolveRequest, SolveResponse
from app.services.agents import AgentOrchestrator
from app.services.cache_service import CacheService
from app.services.fusion import VoteFusion
from app.services.persistence import PersistenceService
from app.services.retrieval import RetrievalService
from app.services.scheduler import ModelScheduler
from app.services.solve_pipeline import SolvePipeline
from app.services.validator import AnswerValidator

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.app_debug)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cache_service = CacheService(settings=settings)
scheduler = ModelScheduler(settings=settings)
retrieval_service = RetrievalService()
orchestrator = AgentOrchestrator(scheduler=scheduler, retrieval_service=retrieval_service)
fusion = VoteFusion()
validator = AnswerValidator()
persistence = PersistenceService()
solve_pipeline = SolvePipeline(
    cache_service=cache_service,
    orchestrator=orchestrator,
    fusion=fusion,
    validator=validator,
    persistence=persistence,
)


@app.on_event("startup")
async def startup_event() -> None:
    # 临时关闭数据库初始化，避免本地无可用数据库时阻塞服务启动
    # 后续如需启用数据库，可恢复下方 create_all 调用
    # Base.metadata.create_all(bind=engine)
    try:
        await cache_service.connect()
    except Exception:
        # Redis 不可用时自动回退为内存缓存
        pass


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        app=settings.app_name,
        env=settings.app_env,
        status="ok",
        redis_connected=cache_service.is_connected,
        db_ready=True,
    )


@app.get("/models", response_model=list[ModelInfoResponse])
async def models() -> list[ModelInfoResponse]:
    return [ModelInfoResponse(**item) for item in scheduler.list_models()]


@app.post("/solve", response_model=SolveResponse)
async def solve(request: SolveRequest) -> SolveResponse:
    try:
        return await solve_pipeline.solve(request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"solve failed: {exc}") from exc
