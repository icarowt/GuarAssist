import { useState, useRef, useCallback } from "react"
import Webcam from "react-webcam"
import { analyzeImage } from "./services/api"
import ResultScreen from "./components/ResultScreen"
import HistoryPanel from "./components/HistoryPanel"
import "./App.css"

export default function App() {
  const [page, setPage] = useState("home")
  const [mode, setMode] = useState("upload")
  const [preview, setPreview] = useState(null)
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const webcamRef = useRef(null)

  const handleFileChange = (e) => {
    const selected = e.target.files[0]
    if (!selected) return
    setFile(selected)
    setPreview(URL.createObjectURL(selected))
    setResult(null)
    setError(null)
    setPage("analyze")
  }

  const captureFromCamera = useCallback(() => {
  const imageSrc = webcamRef.current.getScreenshot()
  if (!imageSrc) return

  
  setPreview(imageSrc)
  setMode("upload")
  setLoading(true)
  setResult(null)
  setError(null)

  
  fetch(imageSrc)
    .then(r => r.blob())
    .then(async (blob) => {
      const captured = new File([blob], "captura.jpg", { type: "image/jpeg" })
      setFile(captured)
      
      try {
        
        const data = await analyzeImage(captured)
        setResult(data)
      } catch {
        setError("Erro ao analisar. Verifique se o servidor está rodando.")
      } finally {
        
        setLoading(false)
      }
    })
}, [webcamRef])

  const handleAnalyze = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const data = await analyzeImage(file)
      setResult(data)
    } catch {
      setError("Erro ao analisar. Verifique se o servidor está rodando.")
    } finally {
      setLoading(false)
    }
  }

  const reset = () => {
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
    setMode("upload")
    setPage("home")
  }

  const hora = new Date().getHours()
  const saudacao = hora < 12 ? "BOM DIA" : hora < 18 ? "BOA TARDE" : "BOA NOITE"

  return (
    <div className="app">

      {/* HEADER */}
      <div className="header">
        <div className="logo-group">
          <div className="logo-circle">🌿</div>
          <div>
            <div className="logo-name">GuarAssist</div>
            <div className="logo-sub">Solo &amp; Pragas</div>
          </div>
        </div>
        <div className="notif-btn">🔔</div>
      </div>

      {/* HOME */}
      {page === "home" && (
        <div className="page">
          <div className="hero">
            <div className="greeting">{saudacao}, ICARO</div>
            <h1 className="hero-title">Analisar plantação<br />de guaraná</h1>
          </div>

                <div 
          className="cam-card" 
          onClick={() => {
            setPage("analyze")
            setMode("camera")
          }}
        >
          <div className="cam-icon-wrap">📷</div>
          <p className="cam-label">Usar câmera</p>
          <span className="cam-sub">Aponte para a folha ou fruto</span>
        </div>

          <div className="mini-grid">
            <label className="mini-card">
              <input type="file" accept="image/*" onChange={handleFileChange} hidden />
              <span className="mini-icon">🖼️</span>
              <p>Upload</p>
              <span>Da galeria</span>
            </label>
            <div className="mini-card" onClick={() => setPage("history")}>
              <span className="mini-icon">🕐</span>
              <p>Histórico</p>
              <span>Ver análises</span>
            </div>
          </div>

          <div className="section-label">ANÁLISES RECENTES</div>
          <div className="recent-list">
            {[
              { name: "Foto_folha_01.jpg", date: "hoje, 09:14 — Lote A", ok: true, label: "Saudável" },
              { name: "Foto_fruto_03.jpg", date: "ontem, 14:32 — Lote B", ok: false, label: "Antracnose" },
              { name: "Foto_caule_02.jpg", date: "16/04, 11:00 — Lote A", ok: true, label: "Saudável" },
            ].map((item, i) => (
              <div className="recent-card" key={i}>
                <div className={`recent-dot ${item.ok ? "dot-ok" : "dot-bad"}`} />
                <div className="recent-info">
                  <p>{item.name}</p>
                  <span>{item.date}</span>
                </div>
                <span className={`badge ${item.ok ? "badge-ok" : "badge-bad"}`}>{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ANALYZE */}
      {page === "analyze" && (
        <div className="page">
          <div className="hero">
            <h1 className="hero-title">Diagnóstico</h1>
          </div>

          {mode === "camera" && (
            <div className="webcam-wrap">
              <Webcam ref={webcamRef} screenshotFormat="image/jpeg" className="webcam" />
              <button className="btn-primary" onClick={captureFromCamera}>Capturar</button>
            </div>
          )}

          {mode === "upload" && preview && !result && (
            <div className="preview-wrap">
              <img src={preview} alt="preview" className="preview-img" />
              <div className="preview-actions">
                <button className="btn-secondary" onClick={reset}>Trocar</button>
                <button className="btn-primary" onClick={handleAnalyze} disabled={loading}>
                  {loading ? "Analisando..." : "🔍 Analisar"}
                </button>
              </div>
            </div>
          )}

          {mode === "upload" && !preview && (
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

      {/* HISTORY */}
      {page === "history" && (
        <div className="page">
          <div className="hero">
            <h1 className="hero-title">Histórico</h1>
          </div>
          <HistoryPanel />
        </div>
      )}

      {/* BOTTOM NAV FLUTUANTE */}
      <div className="bottom-nav">
        <div className={`nav-item ${page === "home" ? "nav-active" : ""}`} onClick={() => setPage("home")}>
          <span>🏠</span>
          <span>Início</span>
        </div>
        <div className={`nav-item ${page === "history" ? "nav-active" : ""}`} onClick={() => setPage("history")}>
          <span>📋</span>
          <span>Histórico</span>
        </div>
        <label className="nav-center">
          <input type="file" accept="image/*" capture="environment" onChange={handleFileChange} hidden />
          +
        </label>
        <div className={`nav-item ${page === "analyze" ? "nav-active" : ""}`} onClick={() => setPage("analyze")}>
          <span>🔍</span>
          <span>Análise</span>
        </div>
        <div className="nav-item">
          <span>⚙️</span>
          <span>Config</span>
        </div>
      </div>

    </div>
  )
}
