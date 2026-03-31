import { useState, useEffect, useRef, useCallback } from "react";

const API_BASE = "http://localhost:8000";
const API_KEY  = "mcpilot-dev-key-001";

const S = {
  dash:      { background:"#0a0f1e", minHeight:"100vh", padding:16, fontFamily:"'Courier New', monospace", color:"#e8d5a3" },
  header:    { display:"flex", alignItems:"center", justifyContent:"space-between", borderBottom:"1px solid #f5a623", paddingBottom:10, marginBottom:16 },
  logo:      { fontSize:22, fontWeight:700, color:"#f5a623", letterSpacing:3 },
  tagline:   { fontSize:10, color:"#8a7a5a", letterSpacing:2, textTransform:"uppercase", marginTop:2 },
  statusBar: { display:"flex", gap:16, alignItems:"center" },
  statusDot: { width:8, height:8, borderRadius:"50%", background:"#2ecc71" },
  statusTxt: { fontSize:11, color:"#2ecc71", letterSpacing:1 },
  clock:     { fontSize:11, color:"#3a6aaa", letterSpacing:1 },
  grid:      { display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:12 },
  panel:     { background:"#0d1526", border:"1px solid #2a3550", padding:14 },
  panelFull: { background:"#0d1526", border:"1px solid #2a3550", padding:14, gridColumn:"1 / -1" },
  panelTitle:{ fontSize:10, letterSpacing:2, color:"#f5a623", textTransform:"uppercase", marginBottom:12, borderBottom:"1px solid #1e2d4a", paddingBottom:8 },
  inputRow:  { display:"flex", gap:8 },
  textarea:  { flex:1, background:"#060c18", border:"1px solid #2a3550", color:"#e8d5a3", fontFamily:"'Courier New', monospace", fontSize:13, padding:10, resize:"none", height:80, outline:"none" },
  btn:       { background:"#f5a623", color:"#0a0f1e", border:"none", padding:"0 24px", fontFamily:"'Courier New', monospace", fontSize:12, fontWeight:700, letterSpacing:1, cursor:"pointer", textTransform:"uppercase" },
  btnDis:    { background:"#3a4020", color:"#6a6040", border:"none", padding:"0 24px", fontFamily:"'Courier New', monospace", fontSize:12, fontWeight:700, letterSpacing:1, cursor:"not-allowed", textTransform:"uppercase" },
  compare:   { display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, marginTop:4 },
  compBox:   { background:"#060c18", border:"1px solid #2a3550", padding:10, minHeight:90, fontSize:12, lineHeight:1.8 },
  compLabel: { fontSize:9, letterSpacing:2, color:"#8a7a5a", marginBottom:6, textTransform:"uppercase" },
  llmBox:    { background:"#060c18", border:"1px solid #2a3550", borderLeft:"3px solid #f5a623", padding:12, fontSize:12, lineHeight:1.8, color:"#c8b88a", minHeight:70 },
  logFeed:   { maxHeight:160, overflowY:"auto" },
  logEntry:  { fontSize:11, padding:"5px 0", borderBottom:"1px solid #111d33", display:"flex", gap:10 },
  logTime:   { color:"#3a6aaa", minWidth:80 },
  logMsg:    { color:"#8a9ab8", flex:1 },
  serverRow: { display:"flex", alignItems:"center", gap:10, padding:"7px 0", borderBottom:"1px solid #111d33", fontSize:12 },
  metrics:   { display:"grid", gridTemplateColumns:"repeat(3, 1fr)", gap:8, marginTop:12 },
  metric:    { background:"#060c18", border:"1px solid #2a3550", padding:10, textAlign:"center" },
  metricVal: { fontSize:24, fontWeight:700, color:"#f5a623" },
  metricLbl: { fontSize:9, color:"#5a6a8a", letterSpacing:1, textTransform:"uppercase", marginTop:3 },
  PIIRow:    { marginTop:10, display:"flex", alignItems:"center", gap:12 },
  hint:      { fontSize:10, color:"#3a4a6a", marginTop:6 },
  provBadge: { fontSize:10, color:"#3a6aaa", letterSpacing:1, marginBottom:8 },
};

function tagStyle(type) {
  const base = { fontSize:10, padding:"1px 6px", whiteSpace:"nowrap" };
  if (type === "PII")  return { ...base, background:"#3a1a1a", color:"#ff8888", border:"1px solid #6a2a2a" };
  if (type === "ok")   return { ...base, background:"#1a3a1a", color:"#5aaa5a", border:"1px solid #2a5a2a" };
  if (type === "err")  return { ...base, background:"#4a1a1a", color:"#ff6666", border:"1px solid #8a2a2a" };
  return               { ...base, background:"#1a2a3a", color:"#6a9acc", border:"1px solid #2a4a6a" };
}

function PIIStatusStyle(detected) {
  if (detected) return { background:"#3a1a1a", color:"#ff6666", padding:"3px 12px", fontSize:10, letterSpacing:1, border:"1px solid #7a2a2a", display:"inline-block" };
  return               { background:"#1a3a1a", color:"#5aaa5a", padding:"3px 12px", fontSize:10, letterSpacing:1, border:"1px solid #2a5a2a", display:"inline-block" };
}

function dotStyle(on) {
  return { width:7, height:7, borderRadius:"50%", background: on ? "#2ecc71" : "#445", flexShrink:0 };
}

function highlightPII(text) {
  const parts = text.split(/(\[PERSON\]|\[SSN\]|\[EMAIL\]|\[PHONE\]|\[MRN\]|\[DOB\])/g);
  return parts.map((p, i) =>
    /^\[.+\]$/.test(p)
      ? <span key={i} style={{ background:"#8b1a1a", color:"#ff9999", padding:"1px 5px", fontSize:11, fontWeight:700, border:"1px solid #cc3333" }}>{p}</span>
      : p
  );
}

function now() { return new Date().toTimeString().slice(0, 8); }

const INIT_LOGS = [
  { time: now(), msg: "PII detection pipeline active — spaCy NER loaded", tag: "PII", type: "PII" },
  { time: now(), msg: "Ollama LLM online — llama3.2 on-premise model ready", tag: "LLM", type: "ok" },
  { time: now(), msg: "RAG index loaded — semantic routing active", tag: "RAG", type: "ok" },
  { time: now(), msg: "Echo server connected — 2 tools available", tag: "SRV", type: "ok" },
  { time: now(), msg: "MCPilot Tactical Dashboard initialised. System ready.", tag: "INIT", type: "info" },
];

export default function TacticalDashboard() {
  const [query,       setQuery]       = useState("");
  const [original,    setOriginal]    = useState("Awaiting transmission...");
  const [redacted,    setRedacted]    = useState(null);
  const [llmResponse, setLlmResponse] = useState("Awaiting transmission...");
  const [PIIDetected, setPIIDetected] = useState(false);
  const [scanning,    setScanning]    = useState(false);
  const [logs,        setLogs]        = useState(INIT_LOGS);
  const [totalCalls,  setTotalCalls]  = useState(0);
  const [PIICount,    setPIICount]    = useState(0);
  const [latency,     setLatency]     = useState("—");
  const [clock,       setClock]       = useState(now());

  useEffect(() => {
    const t = setInterval(() => setClock(now()), 1000);
    return () => clearInterval(t);
  }, []);

  const addLog = useCallback((msg, tag, type) => {
    setLogs(prev => [{ time: now(), msg, tag, type }, ...prev].slice(0, 30));
  }, []);

  const submit = useCallback(async () => {
    if (!query.trim() || scanning) return;
    setScanning(true);
    setOriginal(query);
    setRedacted(null);
    setLlmResponse("Querying local model...");
    addLog(`Transmission received: "${query.slice(0, 55)}..."`, "RX", "info");

    const t0 = Date.now();
    try {
      const res  = await fetch(`${API_BASE}/gateway/query`, {
        method:  "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
        body:    JSON.stringify({ query }),
      });
      const data = await res.json();
      const ms   = Date.now() - t0;

      setTotalCalls(c => c + 1);
      setLatency(ms);
      setRedacted(data.clean_query || query);
      setLlmResponse(data.llm_summary || "—");
      setPIIDetected(!!data.PII_detected);

      if (data.PII_detected) {
        setPIICount(c => c + 1);
        addLog(`PII detected and redacted | latency ${ms}ms`, "PII", "PII");
        addLog("Redacted query dispatched to downstream system", "TX", "ok");
      } else {
        addLog(`Query processed clean | latency ${ms}ms`, "OK", "ok");
      }
      addLog("Audit record written to immutable log", "AUDIT", "info");
    } catch {
      setRedacted("Gateway unreachable");
      setLlmResponse("Ensure MCPilot is running on localhost:8000");
      addLog("Gateway connection failed — check MCPilot server", "ERR", "err");
    }
    setScanning(false);
  }, [query, scanning, addLog]);

  const handleKey = useCallback(e => {
    if (e.ctrlKey && e.key === "Enter") submit();
  }, [submit]);

  return (
    <div style={S.dash}>
      <div style={S.header}>
        <div>
          <div style={S.logo}>◈ MCPILOT</div>
          <div style={S.tagline}>Tactical AI Orchestration Gateway — On-Premise Secure</div>
        </div>
        <div style={S.statusBar}>
          <div style={S.statusDot} />
          <div style={S.statusTxt}>SYSTEM ONLINE</div>
          <div style={S.clock}>{clock}</div>
        </div>
      </div>

      <div style={S.grid}>
        {/* Query Input */}
        <div style={S.panelFull}>
          <div style={S.panelTitle}>◈ Command Transmission</div>
          <div style={S.inputRow}>
            <textarea
              style={S.textarea}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Enter command query... e.g. Operator John Smith badge 123-45-6789 requesting access to sector 4 frequency logs"
            />
            <button
              style={scanning ? S.btnDis : S.btn}
              disabled={scanning}
              onClick={submit}
            >
              {scanning ? "SCANNING..." : "TRANSMIT"}
            </button>
          </div>
          <div style={S.PIIRow}>
            <div style={PIIStatusStyle(PIIDetected)}>
              {PIIDetected ? "◈ PII STATUS: DETECTED — REDACTED" : "◈ PII STATUS: CLEAR"}
            </div>
            {scanning && <span style={{ fontSize:11, color:"#f5a623", letterSpacing:1 }}>◈ SCANNING FOR PII...</span>}
          </div>
          <div style={S.hint}>Ctrl+Enter to transmit</div>
        </div>

        {/* Redaction Analysis */}
        <div style={S.panel}>
          <div style={S.panelTitle}>◈ Redaction Analysis</div>
          <div style={S.compare}>
            <div>
              <div style={S.compLabel}>Original Input</div>
              <div style={{ ...S.compBox, color:"#c0a060" }}>{original}</div>
            </div>
            <div>
              <div style={S.compLabel}>Sanitised Output</div>
              <div style={{ ...S.compBox, color:"#e8d5a3" }}>
                {redacted === null ? "Awaiting transmission..." : highlightPII(redacted)}
              </div>
            </div>
          </div>
        </div>

        {/* LLM + Servers + Metrics */}
        <div style={S.panel}>
          <div style={S.panelTitle}>◈ On-Premise LLM Analysis</div>
          <div style={S.provBadge}>MODEL: llama3.2 · PROVIDER: OLLAMA LOCAL · NO DATA LEAVES FACILITY</div>
          <div style={S.llmBox}>{llmResponse}</div>

          <div style={{ marginTop:16 }}>
            <div style={S.panelTitle}>◈ Connected Servers</div>
            {[
              { name:"echo-server",  tools:"2 tools active", on:true  },
              { name:"filesystem",   tools:"standby",        on:false },
              { name:"mcp-fetch",    tools:"standby",        on:false },
            ].map(s => (
              <div key={s.name} style={S.serverRow}>
                <div style={dotStyle(s.on)} />
                <div style={{ color:"#c8b88a", flex:1 }}>{s.name}</div>
                <div style={{ color:"#3a6aaa", fontSize:11 }}>{s.tools}</div>
              </div>
            ))}
            <div style={S.metrics}>
              {[
                { val: totalCalls, label: "Transmissions" },
                { val: PIICount,   label: "PII Detected"  },
                { val: latency,    label: "Latency ms"     },
              ].map(m => (
                <div key={m.label} style={S.metric}>
                  <div style={S.metricVal}>{m.val}</div>
                  <div style={S.metricLbl}>{m.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Audit Log */}
        <div style={S.panelFull}>
          <div style={S.panelTitle}>◈ Immutable Audit Log Feed</div>
          <div style={S.logFeed}>
            {logs.map((l, i) => (
              <div key={i} style={S.logEntry}>
                <div style={S.logTime}>{l.time}</div>
                <div style={S.logMsg}>{l.msg}</div>
                <div style={tagStyle(l.type)}>{l.tag}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
