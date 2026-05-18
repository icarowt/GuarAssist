import { useState, useRef, useCallback, useEffect } from "react"
import Webcam from "react-webcam"
import { analyzeImage, fetchHistory } from "./services/api"
import "./App.css"

// ─── Catálogo de pragas (apenas as do banco real) ─────────────────────
const PRAGAS_INFO = {
  antracnose: {
    nome: "Antracnose",
    cientifico: "Colletotrichum guaranicola",
    tratamento: "Realizar poda fitossanitária dos ramos afetados. Aplicar fungicida cúprico (oxicloreto de cobre) nas folhas. Aumentar o espaçamento entre plantas para melhorar ventilação.",
    severidade: "alta"
  },
  cochonilha: {
    nome: "Cochonilha",
    cientifico: "Coccus viridis",
    tratamento: "Aplicar inseticida sistêmico registrado para a cultura. Remover e destruir partes muito infestadas. Monitorar plantas vizinhas.",
    severidade: "media"
  },
  mosca_das_frutas: {
    nome: "Mosca das Frutas",
    cientifico: "Anastrepha sp.",
    tratamento: "Instalar armadilhas com atrativo alimentar. Recolher e destruir frutos caídos. Aplicar inseticida em isca tóxica nas bordas do talhão.",
    severidade: "media"
  },
  superbrotamento: {
    nome: "Superbrotamento",
    cientifico: "Fitoplasma (Mollicutes)",
    tratamento: "Realizar poda dos ramos afetados, cortando 10cm abaixo do ponto afetado. Não há controle químico eficaz. Monitorar a cada 30 dias.",
    severidade: "alta"
  }
}

// ─── Ícones em SVG inline ─────────────────────────────────────────────
const Icon = ({ name, size = 16 }) => {
  const icons = {
    home: <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2h-4v-7H10v7H6a2 2 0 0 1-2-2z" />,
    data: <><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></>,
    bell: <><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></>,
    layers: <><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></>,
    user: <><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></>,
    cog: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></>,
    leaf: <><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10z"/><path d="M2 21c0-3 1.85-5.36 5.08-6"/></>,
    camera: <><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/></>,
    bug: <><rect x="8" y="6" width="8" height="14" rx="4"/><path d="M19 7l-3 2M5 7l3 2M19 13h-3M8 13H5M19 19l-3-2M5 19l3-2M12 2v4"/></>,
    arrowUp: <><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></>,
    arrowRight: <><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><line x1="12" y1="2" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="22"/><line x1="4.93" y1="4.93" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.07" y2="19.07"/><line x1="2" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="22" y2="12"/></>,
    moon: <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>,
    search: <><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></>,
    shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>,
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {icons[name] || null}
    </svg>
  )
}

// ─── Dados mockados (visual) ──────────────────────────────────────────
const LOTES_MOCK = [
  { id: "A", name: "Lote A", area: "1.8 ha", status: "good", label: "PLANTAÇÃO LOTE A\n— vista aérea —", metrics: [{ k: "Plantas", v: "142" }, { k: "Saudáveis", v: "97%" }, { k: "Idade", v: "3 anos" }] },
  { id: "B", name: "Lote B", area: "2.4 ha", status: "warn", label: "PLANTAÇÃO LOTE B\n— vista aérea —", metrics: [{ k: "Plantas", v: "198" }, { k: "Atenção", v: "antracnose" }, { k: "Idade", v: "5 anos" }] },
  { id: "C", name: "Lote C", area: "1.2 ha", status: "good", label: "PLANTAÇÃO LOTE C\n— vista aérea —", metrics: [{ k: "Plantas", v: "96" }, { k: "Saudáveis", v: "92%" }, { k: "Idade", v: "2 anos" }] },
]

const WEATHER_MOCK = [
  { d: "Seg", ic: "sun", t: "29°", r: "0 mm", now: false },
  { d: "Ter", ic: "sun", t: "31°", r: "0 mm", now: false },
  { d: "Qua", ic: "cloud", t: "28°", r: "2 mm", now: false },
  { d: "Qui", ic: "rain", t: "26°", r: "12 mm", now: false },
  { d: "Sex", ic: "cloud", t: "27°", r: "3 mm", now: false },
  { d: "Sáb", ic: "sun", t: "30°", r: "0 mm", now: false },
  { d: "Dom", ic: "sun", t: "31°", r: "0 mm", now: true },
]

const ICONS_WEATHER = { sun: "☀️", cloud: "☁️", rain: "🌧️" }

// ─── Componentes ──────────────────────────────────────────────────────
function DotLoader() {
  return (
    <div className="dot-loader">
      {[...Array(8)].map((_, i) => (
        <div key={i} className="dot-loader-dot" style={{ animationDelay: `${i * 0.12}s` }} />
      ))}
    </div>
  )
}

function Ring({ value = 67, size = 132, stroke = 10 }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const off = c - (value / 100) * c
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle className="ring-track" cx={size/2} cy={size/2} r={r} />
        <circle className="ring-prog" cx={size/2} cy={size/2} r={r} strokeDasharray={c} strokeDashoffset={off} />
      </svg>
      <div className="ring-num">{value}%</div>
    </div>
  )
}

function Sidebar({ active, onNavigate, alertsCount, onNewAnalysis }) {
  const items = [
    { id: "home", label: "Início", icon: "home" },
    { id: "data", label: "Dados", icon: "data" },
    { id: "alerts", label: "Alertas", icon: "bell", badge: alertsCount > 0 ? String(alertsCount) : null },
    { id: "lotes", label: "Lotes", icon: "layers" },
    { id: "perfil", label: "Perfil", icon: "user" },
  ]
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <span style={{ color: "var(--leaf)" }}><Icon name="leaf" size={20} /></span>
        </div>
        <div>
          <div className="brand-name">Guarassist</div>
          <div className="brand-tag">Solo & Pragas</div>
        </div>
      </div>

      <div className="nav-section">Geral</div>
      <nav className="nav">
        {items.slice(0, 4).map(it => (
          <button key={it.id}
            className={`nav-item ${active === it.id ? "active" : ""}`}
            onClick={() => onNavigate(it.id)}>
            <span className="nav-icon"><Icon name={it.icon} size={17} /></span>
            <span>{it.label}</span>
            {it.badge && <span className="badge">{it.badge}</span>}
          </button>
        ))}

        <div className="nav-section">Conta</div>
        {items.slice(4).map(it => (
          <button key={it.id}
            className={`nav-item ${active === it.id ? "active" : ""}`}
            onClick={() => onNavigate(it.id)}>
            <span className="nav-icon"><Icon name={it.icon} size={17} /></span>
            <span>{it.label}</span>
          </button>
        ))}

        <div className="sidebar-cta">
          <div className="sidebar-cta-title">Nova análise</div>
          <div className="sidebar-cta-sub">Aponte a câmera para folha ou fruto e identifique pragas em segundos.</div>
          <button className="sidebar-cta-btn" onClick={onNewAnalysis}>
            <Icon name="camera" size={14} />
            Capturar agora
          </button>
        </div>
      </nav>

      <div className="sidebar-foot">
        <div className="avatar">IC</div>
        <div style={{ minWidth: 0 }}>
          <div className="sidebar-foot-name">Icaro Santos</div>
          <div className="sidebar-foot-sub">Sítio Boa Vista, AM</div>
        </div>
      </div>
    </aside>
  )
}

function Topbar({ active, dark, onToggleTheme }) {
  const titles = {
    home: "Visão geral",
    data: "Dados",
    alerts: "Alertas",
    lotes: "Lotes",
    perfil: "Perfil",
    analyze: "Análise"
  }
  return (
    <header className="topbar">
      <div className="topbar-left">
        <div className="crumb">
          Painel <span className="sep">·</span> <b>{titles[active] || "Visão geral"}</b>
        </div>
      </div>
      <div className="topbar-right">
        <div className="topbar-chip">
          <span className="dot"></span>
          Conectado · sincronizado às 09:14
        </div>
        <button className="icon-btn" onClick={onToggleTheme}>
          <Icon name={dark ? "sun" : "moon"} size={16} />
        </button>
        <button className="icon-btn">
          <Icon name="bell" size={16} />
        </button>
      </div>
    </header>
  )
}

function Hero({ name, comPragas, onCameraClick }) {
  const now = new Date()
  const dateStr = now.toLocaleDateString("pt-BR", { weekday: "short", day: "numeric", month: "long" })
  const hora = now.getHours()
  const saudacao = hora < 12 ? "Bom dia" : hora < 18 ? "Boa tarde" : "Boa noite"
  return (
    <section className="hero">
      <div className="greet">
        <div className="greet-decor"></div>
        <div className="greet-eyebrow">
          <span className="pulse"></span>
          {dateStr} · clima ideal para vistoria
        </div>
        <h1 className="greet-title">
          {saudacao}, <em>{name}</em>.
        </h1>
        <p className="greet-sub">
          Sua plantação está com <b style={{ color: "var(--ink)" }}>97% das folhas saudáveis</b>.
          {comPragas > 0 && ` Há ${comPragas} detecções recentes — recomendamos vistoria visual hoje à tarde.`}
        </p>
        <div className="greet-meta">
          <div className="meta-item">
            <div className="lbl">Análises hoje</div>
            <div className="val">08 / 12</div>
          </div>
          <div className="meta-item">
            <div className="lbl">Próx. pulverização</div>
            <div className="val">qui · 20 mai</div>
          </div>
          <div className="meta-item">
            <div className="lbl">Estação</div>
            <div className="val">chuvosa · 78% UR</div>
          </div>
        </div>
      </div>

      <div className="cta-camera" onClick={onCameraClick}>
        <div>
          <div className="cta-camera-eyebrow">— ação rápida —</div>
          <h2 className="cta-camera-title">Analisar<br />uma folha</h2>
          <p className="cta-camera-sub">Aponte a câmera para folha, fruto ou caule. Identifica em segundos.</p>
        </div>
        <div className="cta-camera-tips">
          <span className="tip">📸 luz natural</span>
          <span className="tip">30 cm de distância</span>
        </div>
        <div className="cta-camera-shutter">
          <Icon name="camera" size={20} />
        </div>
      </div>
    </section>
  )
}

function Stats({ saudaveis, total, comPragas }) {
  const pct = Math.round((saudaveis / (total || 1)) * 100)
  return (
    <div className="stats">
      <div className="stat stat-feature">
        <div className="left">
          <div className="stat-lbl">Análises hoje</div>
          <h3><em>{saudaveis} verificadas</em> de {total} plantas</h3>
          <p>Você está dentro da meta diária. Quatro plantas restantes no Lote B aguardam vistoria.</p>
          <div className="progress-row">
            <span className="chip">● {comPragas} aguardando análise</span>
            <span className="chip">↑ +3 vs ontem</span>
          </div>
        </div>
        <Ring value={pct} />
      </div>

      <div className="stat is-good">
        <div className="stat-hd">
          <div className="stat-lbl">Plantas saudáveis</div>
          <span className="stat-icon"><Icon name="leaf" size={18} /></span>
        </div>
        <div>
          <div className="stat-num">{saudaveis * 53}</div>
          <div className="stat-mini-chart" style={{ height: 28 }}>
            {[18, 20, 19, 21, 22, 21, 23].map((v, i) => (
              <i key={i} style={{
                height: `${(v / 23) * 100}%`,
                background: i === 6 ? "var(--leaf)" : "var(--ink-4)",
                opacity: i === 6 ? 1 : 0.4 + (i / 7) * 0.4
              }} />
            ))}
          </div>
        </div>
        <div className="stat-foot">
          <span className="stat-delta up"><Icon name="arrowUp" size={11} /> +2,3%</span>
          <span>vs semana ant.</span>
        </div>
      </div>

      <div className="stat is-alert">
        <div className="stat-hd">
          <div className="stat-lbl">Com pragas</div>
          <span className="stat-icon"><Icon name="bug" size={18} /></span>
        </div>
        <div>
          <div className="stat-num">{comPragas}</div>
          <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 6, fontFamily: "var(--font-mono)" }}>
            {comPragas > 0 ? "antracnose · cochonilha" : "nenhuma praga ativa"}
          </div>
        </div>
        <div className="stat-foot">
          <span className="stat-delta down"><Icon name="arrowUp" size={11} /> +{comPragas}</span>
          <span>desde sex.</span>
        </div>
      </div>
    </div>
  )
}

function Lotes() {
  return (
    <div className="lotes">
      {LOTES_MOCK.map(l => (
        <div className="lote" key={l.id}>
          <div className="lote-img">
            <div className={`placeholder-img ${l.status}`}>
              <div className="ph-label">{l.label}</div>
            </div>
            <div className={`lote-status ${l.status}`}>
              <span className="dot"></span>
              {l.status === "good" ? "Saudável" : l.status === "warn" ? "Atenção" : "Crítico"}
            </div>
            <div className="lote-area">{l.area}</div>
          </div>
          <div className="lote-body">
            <div className="lote-name">
              <h3>{l.name}</h3>
              <div className="arrow"><Icon name="arrowRight" size={12} /></div>
            </div>
            <div className="lote-metrics">
              {l.metrics.map((m, i) => (
                <div key={i}>
                  <div className="m">{m.k}</div>
                  <div className="v">{m.v}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

function Detections({ history }) {
  const items = history.length > 0 ? history.slice(0, 6).map((h, i) => ({
    t: new Date(h.timestamp * 1000).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
    lote: `Lote ${["A", "B", "C"][i % 3]} — fileira ${String(i + 1).padStart(2, "0")}`,
    res: h.status === "saudavel" ? "Folha saudável" : (PRAGAS_INFO[h.disease?.toLowerCase()]?.nome || h.disease || "Praga detectada"),
    status: h.status === "saudavel" ? "good" : "alert",
    conf: Math.round((h.confidence || 0.9) * 100)
  })) : [
    { t: "09:14", lote: "Lote A — fileira 04", res: "Folha saudável", status: "good", conf: 96 },
    { t: "09:02", lote: "Lote C — fileira 11", res: "Cochonilha", status: "alert", conf: 92 },
    { t: "08:47", lote: "Lote B — fileira 07", res: "Antracnose", status: "warn", conf: 81 },
    { t: "08:31", lote: "Lote A — fileira 02", res: "Folha saudável", status: "good", conf: 98 },
    { t: "08:12", lote: "Lote B — fileira 09", res: "Antracnose", status: "warn", conf: 76 },
    { t: "07:58", lote: "Lote A — fileira 01", res: "Folha saudável", status: "good", conf: 94 },
  ]

  // Conta pragas reais detectadas
  const pragasCount = {}
  items.forEach(d => {
    if (d.status !== "good") {
      pragasCount[d.res] = (pragasCount[d.res] || 0) + 1
    }
  })

  const pragas = Object.entries(pragasCount).map(([nome, count]) => {
    const key = Object.keys(PRAGAS_INFO).find(k => PRAGAS_INFO[k].nome === nome)
    const info = key ? PRAGAS_INFO[key] : null
    return {
      name: nome,
      sci: info?.cientifico || "—",
      count,
      pct: Math.min(count * 25, 100)
    }
  }).sort((a, b) => b.count - a.count)

  if (pragas.length === 0) {
    pragas.push(
      { name: "Antracnose", sci: "Colletotrichum guaranicola", count: 0, pct: 0 },
      { name: "Cochonilha", sci: "Coccus viridis", count: 0, pct: 0 }
    )
  }

  return (
    <div className="detection-grid">
      <div className="feed">
        <div className="feed-hd">
          <div>
            <h3>Detecções recentes</h3>
            <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 2 }}>{items.length} análises recentes</div>
          </div>
        </div>
        <div className="feed-list">
          {items.map((d, i) => (
            <div key={i} className="feed-item">
              <div className="feed-thumb">
                <div className={`placeholder-img ${d.status}`}>
                  <div className="ph-label" style={{ fontSize: 8 }}>{i + 1}</div>
                </div>
              </div>
              <div>
                <div className="feed-title">{d.res}</div>
                <div className="feed-meta">{d.t} · {d.lote} · {d.conf}% confiança</div>
              </div>
              <span className={`feed-tag ${d.status}`}>
                {d.status === "good" ? "Saudável" : d.status === "warn" ? "Atenção" : "Crítico"}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="pest-card">
        <h3>Pragas detectadas</h3>
        <div className="sub">Distribuição nos últimos 7 dias</div>
        <div className="pest-list">
          {pragas.map((p, i) => (
            <div className="pest-row" key={i}>
              <div className="pest-thumb">
                <div className="placeholder-img alert"></div>
              </div>
              <div>
                <div className="pest-name">{p.name}</div>
                <div className="pest-sci">{p.sci}</div>
              </div>
              <div className="pest-count">{String(p.count).padStart(2, "0")}</div>
              <div className="bar-wrap">
                <div className="bar" style={{ width: `${p.pct}%` }}></div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ marginTop: "auto", paddingTop: 18, borderTop: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 10, fontSize: 12, color: "var(--ink-3)" }}>
          <span style={{ color: "var(--leaf)" }}><Icon name="shield" size={14} /></span>
          <span>Banco com <b style={{ color: "var(--ink)" }}>4 espécies</b> de pragas do guaranazeiro.</span>
        </div>
      </div>
    </div>
  )
}

function Weather() {
  return (
    <div className="weather-card">
      <div className="weather-hd">
        <div>
          <h3>Janela de pulverização</h3>
          <p className="sub">Previsão de 7 dias · estação chuvosa</p>
        </div>
      </div>
      <div className="weather-row">
        {WEATHER_MOCK.map((w, i) => (
          <div key={i} className={`weather-day ${w.now ? "now" : ""}`}>
            <div className="d">{w.d}</div>
            <div className="ic">{ICONS_WEATHER[w.ic]}</div>
            <div className="t">{w.t}</div>
            <div className="r">{w.r}</div>
          </div>
        ))}
      </div>
      <div className="spray-advice">
        <span>☀️</span>
        <span>Sábado tem <b>melhor janela</b> para pulverizar — sem chuva nas 48h seguintes.</span>
      </div>
    </div>
  )
}

// ─── App ──────────────────────────────────────────────────────────────
export default function App() {
  const [dark, setDark] = useState(true)
  const [active, setActive] = useState("home")
  const [mode, setMode] = useState("upload")
  const [preview, setPreview] = useState(null)
  const [file, setFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [history, setHistory] = useState([])
  const webcamRef = useRef(null)

  useEffect(() => {
    document.body.classList.toggle("theme-light", !dark)
  }, [dark])

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
    setActive("analyze")
  }

  const captureFromCamera = useCallback(() => {
    const imageSrc = webcamRef.current?.getScreenshot()
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
    try {
      const data = await analyzeImage(file)
      setResult(data)
      // Atualiza histórico
      fetchHistory().then(setHistory).catch(() => {})
    }
    catch { setError("Erro ao analisar. Verifique se o servidor está rodando.") }
    finally { setLoading(false) }
  }

  const reset = () => {
    setFile(null); setPreview(null); setResult(null)
    setError(null); setMode("upload")
  }

  const startNewAnalysis = () => {
    reset(); setActive("analyze"); setMode("camera")
  }

  const renderContent = () => {
    if (active === "home") {
      return (
        <div className="animate-up">
          <Hero name="Icaro" comPragas={comPragas} onCameraClick={startNewAnalysis} />
          <div className="section-h">
            <div>
              <h2>Hoje, em números</h2>
              <div className="sub">Resumo das análises e estado da plantação</div>
            </div>
          </div>
          <Stats saudaveis={saudaveis} total={totalAnalises} comPragas={comPragas} />
          <Lotes />
          <div className="section-h">
            <div>
              <h2>Atividade & pragas</h2>
              <div className="sub">Histórico de análises e espécies identificadas</div>
            </div>
          </div>
          <Detections history={history} />
          <div style={{ marginTop: 22 }}>
            <Weather />
          </div>
          <footer className="foot-sig">
            <div>Guarassist · IA agronômica para guaranazeiros</div>
            <div className="right">
              <span>v0.4.2</span>
              <span>· última sincronização: agora</span>
              <span>· Sítio Boa Vista</span>
            </div>
          </footer>
        </div>
      )
    }

    if (active === "analyze") {
      return (
        <div className="analysis-container animate-up">
          <h1 className="analysis-title">Análise de planta</h1>
          <p className="analysis-sub">Envie uma foto ou use a câmera para identificar pragas em segundos.</p>

          {mode === "camera" && !loading && !result && (
            <div className="webcam-container">
              <Webcam ref={webcamRef} screenshotFormat="image/jpeg" className="webcam" videoConstraints={{ facingMode: "environment" }} />
              <div className="cam-actions">
                <button className="btn-secondary" onClick={() => setMode("upload")}>Cancelar</button>
                <button className="btn-primary" onClick={captureFromCamera}>📷 Capturar e analisar</button>
              </div>
            </div>
          )}

          {mode === "upload" && preview && !loading && !result && (
            <div className="preview-container">
              <img src={preview} alt="preview" className="preview-img" />
              <div className="cam-actions" style={{ marginTop: 16 }}>
                <button className="btn-secondary" onClick={reset}>Trocar imagem</button>
                <button className="btn-primary" onClick={handleAnalyze}>🔍 Analisar</button>
              </div>
            </div>
          )}

          {mode === "upload" && !preview && !loading && !result && (
            <div style={{ width: "100%" }}>
              <label className="upload-zone">
                <input type="file" accept="image/*" onChange={handleFileChange} hidden />
                <div className="upload-icon">🖼️</div>
                <h3>Selecione uma imagem</h3>
                <p>JPG, PNG ou WEBP · até 10MB</p>
              </label>
              <div style={{ marginTop: 16 }}>
                <button className="btn-secondary" onClick={() => setMode("camera")}>📷 Usar câmera</button>
              </div>
            </div>
          )}

          {loading && (
            <div className="analyzing-overlay">
              <DotLoader />
              <p>Analisando imagem</p>
              <span>Aguarde alguns segundos</span>
            </div>
          )}

          {error && <div className="error-msg">⚠️ {error}</div>}

          {result && <ResultCard result={result} onReset={reset} />}
        </div>
      )
    }

    if (active === "data") {
      return (
        <div className="animate-up">
          <div className="section-h">
            <div>
              <h2>Dados & relatórios</h2>
              <div className="sub">Análise estatística da plantação</div>
            </div>
          </div>
          <Stats saudaveis={saudaveis} total={totalAnalises} comPragas={comPragas} />
          <div style={{ marginTop: 28 }}>
            <Detections history={history} />
          </div>
          <div style={{ marginTop: 22 }}>
            <Weather />
          </div>
        </div>
      )
    }

    if (active === "alerts") {
      return (
        <div className="animate-up">
          <div className="section-h">
            <div>
              <h2>Alertas ativos</h2>
              <div className="sub">Pragas detectadas que exigem atenção</div>
            </div>
          </div>
          {comPragas > 0 ? (
            <>
              <div className="alert-item urgent">
                <div className="alert-item-icon">⚠️</div>
                <div style={{ flex: 1 }}>
                  <div className="alert-item-title">Antracnose detectada</div>
                  <div className="alert-item-sub">Lote B · hoje, 14:32</div>
                  <div className="alert-item-desc">Aplicar fungicida cúprico nas próximas 48h. Realizar poda fitossanitária.</div>
                </div>
              </div>
              <div className="alert-item">
                <div className="alert-item-icon">🔍</div>
                <div style={{ flex: 1 }}>
                  <div className="alert-item-title">Suspeita de cochonilha</div>
                  <div className="alert-item-sub">Lote C · ontem, 09:00</div>
                  <div className="alert-item-desc">Monitorar nos próximos dias antes de aplicar tratamento.</div>
                </div>
              </div>
            </>
          ) : (
            <div className="empty-state">
              <div className="ic">✅</div>
              <p>Nenhum alerta ativo no momento.</p>
            </div>
          )}
        </div>
      )
    }

    if (active === "lotes") {
      return (
        <div className="animate-up">
          <div className="section-h">
            <div>
              <h2>Meus lotes</h2>
              <div className="sub">Áreas cadastradas e monitoradas</div>
            </div>
          </div>
          <Lotes />
        </div>
      )
    }

    if (active === "perfil") {
      return (
        <div className="animate-up" style={{ maxWidth: 600, margin: "0 auto" }}>
          <div className="profile-block">
            <div className="profile-avatar-big">IC</div>
            <div className="profile-name-big">Icaro Santos</div>
            <div className="profile-role-big">Produtor Rural · Sítio Boa Vista, Manaus AM</div>
          </div>
          <div className="settings-list-edit">
            <div className="setting-row">
              <span>Total de análises</span>
              <strong style={{ fontFamily: "var(--font-mono)" }}>{totalAnalises}</strong>
            </div>
            <div className="setting-row">
              <span>Lotes cadastrados</span>
              <strong style={{ fontFamily: "var(--font-mono)" }}>3</strong>
            </div>
            <div className="setting-row">
              <span>Membro desde</span>
              <strong style={{ fontFamily: "var(--font-mono)" }}>Abr 2026</strong>
            </div>
            <div className="setting-row">
              <span>Modo escuro</span>
              <button className="btn-secondary" style={{ width: "auto", padding: "6px 14px" }} onClick={() => setDark(!dark)}>
                {dark ? "Ligado" : "Desligado"}
              </button>
            </div>
          </div>
        </div>
      )
    }

    return null
  }

  return (
    <div className="app">
      <Sidebar
        active={active}
        onNavigate={setActive}
        alertsCount={comPragas}
        onNewAnalysis={startNewAnalysis}
      />
      <div className="main">
        <Topbar active={active} dark={dark} onToggleTheme={() => setDark(!dark)} />
        <main className="canvas">
          {renderContent()}
        </main>
      </div>
    </div>
  )
}

// ─── Result Card ──────────────────────────────────────────────────────
function ResultCard({ result, onReset }) {
  const isHealthy = result.status === "saudavel"
  const confidence = Math.round((result.confidence || 0) * 100)
  const diseaseKey = result.disease?.toLowerCase().replace(/\s/g, "_").replace(/[^a-z_]/g, "")
  const info = isHealthy ? null : (PRAGAS_INFO[diseaseKey] || {
    nome: result.disease,
    cientifico: "—",
    tratamento: "Consulte um técnico agrícola para orientação específica."
  })

  return (
    <div className="result-card animate-up">
      <div className="result-hd">
        <div className={`result-status ${isHealthy ? "good" : "bad"}`}>
          {isHealthy ? "● Diagnóstico concluído" : "● Praga detectada"}
        </div>
        <h2 className={`result-title ${isHealthy ? "good" : "bad"}`}>
          {isHealthy ? <>Planta <em>saudável</em>.</> : <><em>{info.nome}</em></>}
        </h2>
        {!isHealthy && <div className="result-sub">{info.cientifico}</div>}
      </div>
      <div className="result-body">
        <div className="result-metrics">
          <div className="result-metric">
            <div className="lbl">Confiança</div>
            <div className="val">{confidence}%</div>
          </div>
          <div className="result-metric">
            <div className="lbl">Status</div>
            <div className="val">{isHealthy ? "Saudável" : "Atenção"}</div>
          </div>
        </div>

        {!isHealthy && info.tratamento && (
          <div className="tratamento-section">
            <h4>Tratamento recomendado</h4>
            <p>{info.tratamento}</p>
          </div>
        )}

        <div className="result-actions">
          <button className="btn-secondary" onClick={onReset}>Nova análise</button>
          <button className="btn-primary">Gerar relatório</button>
        </div>
      </div>
    </div>
  )
}
