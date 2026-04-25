import { useState, useRef, useCallback, useEffect } from "react"
import Webcam from "react-webcam"
import { analyzeImage, fetchHistory } from "./services/api"
import ResultScreen from "./components/ResultScreen"
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from "recharts"
import "./App.css"

const weekData = [
  { dia: "Seg", saudavel: 4, praga: 0 },
  { dia: "Ter", saudavel: 6, praga: 1 },
  { dia: "Qua", saudavel: 3, praga: 2 },
  { dia: "Qui", saudavel: 7, praga: 0 },
  { dia: "Sex", saudavel: 5, praga: 1 },
  { dia: "Sáb", saudavel: 8, praga: 2 },
  { dia: "Dom", saudavel: 2, praga: 0 },
]

function DonutChart({ value, total, dark }) {
  const pct = Math.round((value / (total || 1)) * 100)
  const data = [{ v: value }, { v: (total - value) || 1 }]
  return (
    <div style={{ position: "relative", width: 72, height: 72 }}>
      <PieChart width={72} height={72}>
        <Pie data={data} cx={31} cy={31} innerRadius={24} outerRadius={34}
          startAngle={90} endAngle={-270} dataKey="v" strokeWidth={0}>
          <Cell fill="#2ecc71" />
          <Cell fill={dark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)"} />
        </Pie>
      </PieChart>
      <div style={{
        position: "absolute", top: "50%", left: "50%",
        transform: "translate(-50%,-50%)",
        fontSize: 13, fontWeight: 700,
        color: dark ? "#e8d88a" : "#1a4d2e",
        fontFamily: "'Cinzel',serif"
      }}>{pct}%</div>
    </div>
  )
}

export default function App() {
  const [dark, setDark] = useState(true)
  const [page, setPage] = useState("home")
  const [mode, setMode] = useState("upload")
  const [preview, setPreview] = useState(null)
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const webcamRef = useRef(null)

  const now = new Date()
  const dateStr = now.toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "short" })
  const hora = now.getHours()
  const saudacao = hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite"

  useEffect(() => {
    fetchHistory().then(setHistory).catch(() => {})
  }, [])

  const totalAnalises = history.length || 12
  const saudaveis = history.filter(h => h.status === "saudavel").length || 8
  const comPragas = history.filter(h => h.status !== "saudavel").length || 2

  const handleFileChange = (e) => {
    const selected = e.target.files[0]
    if (!selected) return
    setFile(selected)
    setPreview(URL.createObjectURL(selected))
    setResult(null); setError(null)
    setPage("analyze")
  }

  const captureFromCamera = useCallback(() => {
    const imageSrc = webcamRef.current.getScreenshot()
    if (!imageSrc) return
    setPreview(imageSrc); setMode("upload")
    setLoading(true); setResult(null); setError(null)
    fetch(imageSrc).then(r => r.blob()).then(async (blob) => {
      const captured = new File([blob], "captura.jpg", { type: "image/jpeg" })
      setFile(captured)
      try { const data = await analyzeImage(captured); setResult(data) }
      catch { setError("Erro ao analisar. Verifique se o servidor está rodando.") }
      finally { setLoading(false) }
    })
  }, [webcamRef])

  const handleAnalyze = async () => {
    if (!file) return
    setLoading(true); setError(null)
    try { const data = await analyzeImage(file); setResult(data) }
    catch { setError("Erro ao analisar. Verifique se o servidor está rodando.") }
    finally { setLoading(false) }
  }

  const reset = () => {
    setFile(null); setPreview(null); setResult(null)
    setError(null); setMode("upload"); setPage("home")
  }

  const tooltipStyle = {
    background: dark ? "#0f2d1a" : "#fff",
    border: "0.5px solid rgba(46,204,113,0.3)",
    borderRadius: 8, fontSize: 12,
    color: dark ? "#e8d88a" : "#1a4d2e"
  }

  return (
    <div className={`app ${dark ? "dark" : "light"}`}>

      {/* HEADER */}
      <div className="header">
        <div>
          <div className="header-date">{dateStr} — Lote A</div>
          <div className="header-title">{saudacao}, Icaro!</div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button className="theme-toggle" onClick={() => setDark(!dark)}>
            {dark ? "☀️" : "🌙"}
          </button>
          <div className="notif-btn">🔔<span className="notif-dot" /></div>
        </div>
      </div>

      {/* ── HOME ── */}
      {page === "home" && (
        <div className="page">
          <div className="progress-card">
            <div style={{ flex: 1 }}>
              <div className="progress-label">Análises hoje</div>
              <div className="progress-value">
                <span className="progress-highlight">{saudaveis} verificadas</span> de {totalAnalises} plantas
              </div>
              <div className="progress-sub">● {comPragas} aguardando análise</div>
            </div>
            <DonutChart value={saudaveis} total={totalAnalises} dark={dark} />
          </div>

          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-row"><span className="metric-label">Plantas saudáveis</span><span>🌿</span></div>
              <div className="metric-value green">{saudaveis}</div>
              <div className="metric-sub">de {totalAnalises} analisadas</div>
            </div>
            <div className="metric-card">
              <div className="metric-row"><span className="metric-label">Com pragas</span><span>🐛</span></div>
              <div className="metric-value red">{comPragas}</div>
              <div className="metric-sub">antracnose</div>
            </div>
            <div className="metric-card">
              <div className="metric-row"><span className="metric-label">Lotes ativos</span><span>🗺️</span></div>
              <div className="metric-value gold">3</div>
              <div className="metric-sub">A, B e C</div>
            </div>
            <div className="metric-card">
              <div className="metric-row"><span className="metric-label">Últ. análise</span><span>🕐</span></div>
              <div className="metric-value gold" style={{ fontSize: 22 }}>09:14</div>
              <div className="metric-sub">hoje, Lote A</div>
            </div>
          </div>

          <div className="cam-action-btn" onClick={() => { setPage("analyze"); setMode("camera") }}>
            <div className="cam-action-icon">📷</div>
            <div style={{ flex: 1 }}>
              <div className="cam-action-title">Usar câmera</div>
              <div className="cam-action-sub">Aponte para folha ou fruto</div>
            </div>
            <div className="cam-action-arrow">→</div>
          </div>

          <div className="chart-card">
            <div className="chart-title">Ocorrências de Pragas</div>
            <div className="chart-sub">Esta semana: <strong>{comPragas} detecções</strong></div>
            <div className="chart-legend">
              <span><span className="legend-dot green-dot" />Saudável</span>
              <span><span className="legend-dot red-dot" />Praga detectada</span>
            </div>
            <ResponsiveContainer width="100%" height={120}>
              <LineChart data={weekData} margin={{ top: 10, right: 10, left: -30, bottom: 0 }}>
                <XAxis dataKey="dia" tick={{ fontSize: 10, fill: dark ? "rgba(210,181,100,0.5)" : "#888" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: "transparent" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="saudavel" stroke="#2ecc71" strokeWidth={2} dot={{ fill: "#2ecc71", r: 3 }} />
                <Line type="monotone" dataKey="praga" stroke="#e74c3c" strokeWidth={2} dot={{ fill: "#e74c3c", r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* ── DADOS ── */}
      {page === "dados" && (
        <div className="page">
          <div className="hero"><h1 className="hero-title">Dados & Relatórios</h1></div>
          <div className="stats-card">
            <div className="stats-title">Resumo Geral</div>
            <div className="stats-row"><span>Total de análises</span><strong>{totalAnalises}</strong></div>
            <div className="stats-row"><span>Plantas saudáveis</span><strong className="green">{saudaveis}</strong></div>
            <div className="stats-row"><span>Pragas detectadas</span><strong className="red">{comPragas}</strong></div>
            <div className="stats-row"><span>Taxa de saúde</span><strong className="gold">{Math.round((saudaveis / (totalAnalises || 1)) * 100)}%</strong></div>
          </div>
          <div className="chart-card" style={{ marginTop: 14 }}>
            <div className="chart-title">Histórico da semana</div>
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={weekData} margin={{ top: 10, right: 10, left: -30, bottom: 0 }}>
                <XAxis dataKey="dia" tick={{ fontSize: 10, fill: dark ? "rgba(210,181,100,0.5)" : "#888" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="saudavel" stroke="#2ecc71" strokeWidth={2} dot={{ fill: "#2ecc71", r: 3 }} />
                <Line type="monotone" dataKey="praga" stroke="#e74c3c" strokeWidth={2} dot={{ fill: "#e74c3c", r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="chart-card" style={{ marginTop: 14 }}>
            <div className="chart-title">Distribuição</div>
            <div style={{ display: "flex", justifyContent: "center", gap: 32, alignItems: "center", padding: "20px 0" }}>
              <DonutChart value={saudaveis} total={totalAnalises} dark={dark} />
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <span className="legend-dot green-dot" /><span>Saudável — {saudaveis}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <span className="legend-dot red-dot" /><span>Praga — {comPragas}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── ANALYZE ── */}
      {page === "analyze" && (
        <div className="page">
          <div className="hero"><h1 className="hero-title">Diagnóstico</h1></div>
          {mode === "camera" && !loading && !result && (
            <div className="webcam-wrap">
              <Webcam ref={webcamRef} screenshotFormat="image/jpeg" className="webcam" />
              <button className="btn-primary" onClick={captureFromCamera}>📷 Capturar e Analisar</button>
              <button className="btn-secondary" onClick={() => setMode("upload")}>Cancelar</button>
            </div>
          )}
          {mode === "upload" && preview && !result && !loading && (
            <div className="preview-wrap">
              <img src={preview} alt="preview" className="preview-img" />
              <div className="preview-actions">
                <button className="btn-secondary" onClick={reset}>Trocar</button>
                <button className="btn-primary" onClick={handleAnalyze} disabled={loading}>🔍 Analisar</button>
              </div>
            </div>
          )}
          {loading && (
            <div className="analyzing-overlay">
              <div className="spinner-large" />
              <p>Analisando imagem...</p>
              <span>Aguarde um momento</span>
            </div>
          )}
          {mode === "upload" && !preview && !loading && (
            <div className="upload-area">
              <label className="upload-label">
                <input type="file" accept="image/*" onChange={handleFileChange} hidden />
                <span className="upload-icon">🖼️</span>
                <p>Toque para selecionar</p>
                <span>JPG, PNG ou WEBP</span>
              </label>
              <button className="btn-secondary" style={{ marginTop: 16 }} onClick={() => setMode("camera")}>
                📷 Usar câmera
              </button>
            </div>
          )}
          {error && <div className="error-msg">⚠️ {error}</div>}
          {result && <ResultScreen result={result} onNewAnalysis={reset} />}
        </div>
      )}

      {/* ── ALERTAS ── */}
      {page === "alertas" && (
        <div className="page">
          <div className="hero"><h1 className="hero-title">Alertas</h1></div>
          {comPragas > 0 ? (
            <>
              <div className="alert-card urgent">
                <div className="alert-icon">⚠️</div>
                <div className="alert-info">
                  <div className="alert-title">Antracnose detectada</div>
                  <div className="alert-sub">Lote B — Talhão 03 · hoje, 14:32</div>
                  <div className="alert-desc">Aplicar fungicida cúprico nas próximas 48h</div>
                </div>
              </div>
              <div className="alert-card warning">
                <div className="alert-icon">🔍</div>
                <div className="alert-info">
                  <div className="alert-title">Suspeita de cochonilha</div>
                  <div className="alert-sub">Lote C — Talhão 01 · ontem, 09:00</div>
                  <div className="alert-desc">Monitorar nos próximos dias</div>
                </div>
              </div>
            </>
          ) : (
            <div className="history-empty">
              <span>✅</span>
              <p>Nenhum alerta ativo no momento.</p>
            </div>
          )}
        </div>
      )}

      {/* ── PERFIL ── */}
      {page === "perfil" && (
        <div className="page">
          <div className="hero"><h1 className="hero-title">Perfil</h1></div>
          <div className="profile-card">
            <div className="profile-avatar">🧑‍🌾</div>
            <div className="profile-name">Icaro</div>
            <div className="profile-role">Produtor Rural — Manaus, AM</div>
          </div>
          <div className="stats-card" style={{ marginTop: 14 }}>
            <div className="stats-row"><span>Total de análises</span><strong>{totalAnalises}</strong></div>
            <div className="stats-row"><span>Lotes cadastrados</span><strong>3</strong></div>
            <div className="stats-row"><span>Membro desde</span><strong>Abr 2026</strong></div>
          </div>
          <div className="settings-list">
            <div className="settings-item">
              <span>🌙 Modo escuro</span>
              <button className="toggle-btn" onClick={() => setDark(!dark)}>{dark ? "Ligado" : "Desligado"}</button>
            </div>
            <div className="settings-item"><span>🔔 Notificações</span><span className="chevron">›</span></div>
            <div className="settings-item"><span>🗺️ Meus lotes</span><span className="chevron">›</span></div>
            <div className="settings-item"><span>📄 Relatórios</span><span className="chevron">›</span></div>
          </div>
        </div>
      )}

      {/* BOTTOM NAV */}
      <div className="bottom-nav">
        <div className={`nav-item ${page === "home" ? "nav-active" : ""}`} onClick={() => setPage("home")}>
          <span>🏠</span><span>Início</span>
        </div>
        <div className={`nav-item ${page === "dados" ? "nav-active" : ""}`} onClick={() => setPage("dados")}>
          <span>📊</span><span>Dados</span>
        </div>
        <label className="nav-center">
          <input type="file" accept="image/*" capture="environment" onChange={handleFileChange} hidden />+
        </label>
        <div className={`nav-item ${page === "alertas" ? "nav-active" : ""}`} onClick={() => setPage("alertas")}>
          <span>🔔</span><span>Alertas</span>
        </div>
        <div className={`nav-item ${page === "perfil" ? "nav-active" : ""}`} onClick={() => setPage("perfil")}>
          <span>👤</span><span>Perfil</span>
        </div>
      </div>

    </div>
  )
}
