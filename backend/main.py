from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.analyze import router as analyze_router
from routes.history import router as history_router
from routes.stats import router as stats_router
from database.database import init_db
from contextlib import asynccontextmanager

app = FastAPI(
    title="GuarAssist API",
    description="Detecção de pragas em plantações de guaraná via IA",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # URL do React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Servidor rodando... ")
    init_db()
    yield
    print("Encerrando servidor...")

# escrevas essas rotas da seguinte forma>
# /api/analyze (Exemplo prático)
# É necessário fazer o teste dessa rota pela documentação, segue a rota
# /docs 
app.include_router(analyze_router, prefix="/api")
# Essa rota retorna todo o histórico de analises.
app.include_router(history_router, prefix="/api")
# essa rota retorna um resumo de analises e pragas encontradas.
app.include_router(stats_router, prefix="/api")

@app.get("/")
def root():
    return {"status": "GuarAssist API rodando ✅"}
 
