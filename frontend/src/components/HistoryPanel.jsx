// src/components/HistoryPanel.jsx
import { useEffect, useState } from "react"
import { fetchHistory } from "../services/api"

export default function HistoryPanel() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchHistory()
      .then(setHistory)
      .catch(() => setError("Erro ao carregar histórico. Verifique se o servidor está rodando."))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="history-loading">
      <div className="spinner" />
      <p>Carregando histórico...</p>
    </div>
  )

  if (error) return (
    <div className="error-msg">⚠️ {error}</div>
  )

  if (history.length === 0) return (
    <div className="history-empty">
      <span>🌿</span>
      <p>Nenhuma análise realizada ainda.</p>
    </div>
  )

  return (
    <div className="history-list">
      {history.map((item) => (
        <div className="recent-card" key={item.id}>
          <div className={`recent-dot ${item.status === "saudavel" ? "dot-ok" : "dot-bad"}`} />
          <div className="recent-info">
            <p>{item.filename || "Imagem analisada"}</p>
            <span>{new Date(item.timestamp * 1000).toLocaleString("pt-BR")}</span>
          </div>
          <div style={{ textAlign: "right" }}>
            <span className={`badge ${item.status === "saudavel" ? "badge-ok" : "badge-bad"}`}>
              {item.status === "saudavel" ? "Saudável" : item.disease || "Praga"}
            </span>
            <div style={{ fontSize: 11, color: "rgba(210,181,100,0.4)", marginTop: 3 }}>
              {Math.round((item.confidence || 0) * 100)}% confiança
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
