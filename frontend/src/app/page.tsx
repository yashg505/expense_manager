// Mobile-first: swipe/snap between Budget | Chat | Insights. Desktop: 3 columns.
"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type ChatMsg = { role: "user" | "assistant"; content: string };

type TaxonomyOpt = { id: string; full_path: string | null };

type DraftItem = {
  item_text: string;
  item_type?: string | null;
  quantity: number;
  price: number;
  discount: number;
  predicted_taxonomy_id?: string | null;
  taxonomy_id?: string | null;
  predicted_full_path?: string | null;
};

type ScanResult = {
  file_id: string;
  shop?: string | null;
  date?: string | null;
  time?: string | null;
  items: DraftItem[];
};

async function fireConfetti() {
  const confetti = (await import("canvas-confetti")).default;
  confetti({ particleCount: 120, spread: 70, origin: { y: 0.7 } });
}

export default function Home() {
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

  const [apiOk, setApiOk] = useState<boolean | null>(null);
  const [apiErr, setApiErr] = useState<string | null>(null);

  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: "assistant", content: "Chat is home base. Upload a receipt or ask about your spending." },
  ]);
  const [chatInput, setChatInput] = useState("");

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [scanBusy, setScanBusy] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanErr, setScanErr] = useState<string | null>(null);

  const [taxonomy, setTaxonomy] = useState<TaxonomyOpt[]>([]);
  const [taxErr, setTaxErr] = useState<string | null>(null);

  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmErr, setConfirmErr] = useState<string | null>(null);
  const [confirmOk, setConfirmOk] = useState(false);

  const [budgetPulse, setBudgetPulse] = useState(false);

  const scrollerRef = useRef<HTMLDivElement | null>(null);

  const previewUrl = useMemo(() => {
    if (!selectedFile) return null;
    return URL.createObjectURL(selectedFile);
  }, [selectedFile]);

  useEffect(() => {
    if (!previewUrl) return;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/health`, { cache: "no-store" });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        setApiOk(true);
        setApiErr(null);
      } catch (e: any) {
        setApiOk(false);
        setApiErr(e?.message || "Failed to reach backend");
      }
    })();
  }, [API_BASE]);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_BASE}/taxonomy`, { cache: "no-store" });
        const data = await r.json();
        if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);
        setTaxonomy(Array.isArray(data) ? data : []);
        setTaxErr(null);
      } catch (e: any) {
        setTaxErr(e?.message || "Failed to load taxonomy");
      }
    })();
  }, [API_BASE]);

  function scrollToPane(pane: "budget" | "chat" | "insights", behavior: ScrollBehavior = "smooth") {
    const scroller = scrollerRef.current;
    if (!scroller) return;
    const el = document.getElementById(`pane-${pane}`) as HTMLElement | null;
    if (!el) return;
    scroller.scrollTo({ left: el.offsetLeft, behavior });
  }

  // Mobile default: open the center pane (Chat).
  useEffect(() => {
    const id = window.setTimeout(() => scrollToPane("chat", "auto"), 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sendChat() {
    const text = chatInput.trim();
    if (!text) return;

    setMessages((m) => [...m, { role: "user", content: text }]);
    setChatInput("");

    try {
      const r = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);

      setMessages((m) => [...m, { role: "assistant", content: data?.answer ?? "(no answer)" }]);
    } catch (e: any) {
      setMessages((m) => [...m, { role: "assistant", content: `Backend error: ${e?.message || "unknown error"}` }]);
    }
  }

  async function scanReceipt() {
    if (!selectedFile) return;

    setScanBusy(true);
    setScanErr(null);
    setConfirmErr(null);
    setConfirmOk(false);
    setScanResult(null);

    try {
      const fd = new FormData();
      fd.append("file", selectedFile);

      const r = await fetch(`${API_BASE}/scan-receipt`, { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);

      setScanResult(data);
      scrollToPane("insights");

      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: `Scanned receipt from ${data?.shop || "Unknown"} on ${data?.date || "Unknown date"}. Found ${
            Array.isArray(data?.items) ? data.items.length : 0
          } items. Review on the right and confirm to save.`,
        },
      ]);
    } catch (e: any) {
      setScanErr(e?.message || "Scan failed");
    } finally {
      setScanBusy(false);
    }
  }

  function updateItem(idx: number, patch: Partial<DraftItem>) {
    setScanResult((prev) => {
      if (!prev) return prev;
      const items = [...prev.items];
      items[idx] = { ...items[idx], ...patch };
      return { ...prev, items };
    });
  }

  async function confirmAndSave() {
    if (!scanResult) return;

    setConfirmBusy(true);
    setConfirmErr(null);

    try {
      const r = await fetch(`${API_BASE}/receipts/${scanResult.file_id}/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop: scanResult.shop,
          date: scanResult.date,
          time: scanResult.time,
          items: scanResult.items,
        }),
      });

      const data = await r.json();
      if (!r.ok) throw new Error(data?.detail || `HTTP ${r.status}`);

      setConfirmOk(true);
      setBudgetPulse(true);
      window.setTimeout(() => setBudgetPulse(false), 950);
      await fireConfetti();

      setMessages((m) => [...m, { role: "assistant", content: "Uploaded successfully: saved to DB + Google Sheet." }]);
      scrollToPane("budget");
    } catch (e: any) {
      setConfirmErr(e?.message || "Confirm failed");
      scrollToPane("chat");
    } finally {
      setConfirmBusy(false);
    }
  }

  return (
    <div className="min-vh-100 bg-body-tertiary text-body">
      <nav className="navbar navbar-light bg-white border-bottom sticky-top" style={{ height: 56 }}>
        <div className="container-fluid">
          <span className="navbar-brand mb-0 h1">Expense Manager</span>
          <div className="d-flex align-items-center gap-2">
            <small className="text-muted d-none d-sm-inline">
              API:{" "}
              {apiOk === null ? (
                <span>checking...</span>
              ) : apiOk ? (
                <span className="text-success">connected</span>
              ) : (
                <span className="text-danger">down ({apiErr})</span>
              )}
            </small>
            <button
              className="btn btn-outline-secondary btn-sm"
              type="button"
              data-bs-toggle="offcanvas"
              data-bs-target="#notifTray"
              aria-controls="notifTray"
            >
              Bell
            </button>
          </div>
        </div>
      </nav>

      <div className="offcanvas offcanvas-top" tabIndex={-1} id="notifTray" aria-labelledby="notifTrayLabel">
        <div className="offcanvas-header">
          <h5 className="offcanvas-title" id="notifTrayLabel">
            Notifications
          </h5>
          <button type="button" className="btn-close" data-bs-dismiss="offcanvas" aria-label="Close" />
        </div>
        <div className="offcanvas-body">
          <div className="text-muted small">For exceptions only (spikes, clarifications). We'll wire real alerts later.</div>
          {scanErr ? <div className="alert alert-warning mt-3 mb-0 py-2">Scan error: {scanErr}</div> : null}
          {confirmErr ? <div className="alert alert-danger mt-3 mb-0 py-2">Upload error: {confirmErr}</div> : null}
          {taxErr ? <div className="alert alert-secondary mt-3 mb-0 py-2">Taxonomy: {taxErr}</div> : null}
        </div>
      </div>

      <div ref={scrollerRef} className="pane-snap px-3 py-3">
        <section id="pane-budget" className="pane">
          <div className={`card border-0 shadow-sm ${budgetPulse ? "pulse-glow" : ""}`}>
            <div className="card-body">
              <h5 className="card-title mb-1">Budget</h5>
              <div className="text-muted small mb-3">
                Glance left (limits) {"->"} act (chat) {"->"} verify (results).
              </div>

              <div className="mb-3">
                <div className="d-flex justify-content-between small">
                  <span>Food</span>
                  <span className="text-muted">€230 / €400</span>
                </div>
                <div className="progress" style={{ height: 8 }}>
                  <div className="progress-bar bg-success" style={{ width: "58%" }} />
                </div>
              </div>

              <div className="mb-3">
                <div className="d-flex justify-content-between small">
                  <span>Transport</span>
                  <span className="text-muted">€64 / €120</span>
                </div>
                <div className="progress" style={{ height: 8 }}>
                  <div className="progress-bar bg-info" style={{ width: "53%" }} />
                </div>
              </div>

              <div>
                <div className="d-flex justify-content-between small">
                  <span>Entertainment</span>
                  <span className="text-muted">€90 / €150</span>
                </div>
                <div className="progress" style={{ height: 8 }}>
                  <div className="progress-bar bg-warning" style={{ width: "60%" }} />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="pane-chat" className="pane">
          <div className="card border-0 shadow-sm h-100">
            <div className="card-body d-flex flex-column">
              <div className="d-flex align-items-center justify-content-between mb-2">
                <h5 className="card-title mb-0">Chat</h5>
                <span className="badge text-bg-dark">Home</span>
              </div>

              <div className="border rounded-3 p-2 mb-3 bg-body">
                <div className="d-flex align-items-center gap-2 flex-wrap">
                  <input
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
                    className="form-control form-control-sm"
                  />
                  <button onClick={scanReceipt} disabled={!selectedFile || scanBusy || apiOk !== true} className="btn btn-dark btn-sm">
                    {scanBusy ? "Scanning..." : "Scan"}
                  </button>
                </div>

                {previewUrl ? (
                  <div className="mt-2 rounded-3 overflow-hidden border">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={previewUrl} alt="receipt preview" className="w-100 h-auto" />
                  </div>
                ) : null}

                {scanErr ? <div className="alert alert-danger mt-2 mb-0 py-2 small">Error: {scanErr}</div> : null}
              </div>

              <div className="flex-grow-1 overflow-auto border rounded-3 bg-body-tertiary p-2">
                {messages.map((m, idx) => (
                  <div
                    key={idx}
                    className={`d-flex ${m.role === "user" ? "justify-content-end" : "justify-content-start"} mb-2`}
                  >
                    <div
                      className={`px-3 py-2 rounded-4 small ${m.role === "user" ? "bg-dark text-white" : "bg-white border"}`}
                      style={{ maxWidth: "85%" }}
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-2 d-flex gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") sendChat();
                  }}
                  placeholder="Ask or add expense..."
                  className="form-control"
                />
                <button onClick={sendChat} disabled={apiOk !== true} className="btn btn-dark">
                  Send
                </button>
              </div>
            </div>
          </div>
        </section>

        <section id="pane-insights" className="pane">
          <div className="card border-0 shadow-sm h-100">
            <div className="card-body">
              <div className="d-flex align-items-center justify-content-between mb-2">
                <h5 className="card-title mb-0">Insights</h5>
                {confirmOk ? <span className="badge text-bg-success">Saved</span> : null}
              </div>

              <div className="text-muted small mb-3">Trends (top) + ledger (bottom). Confirming should show up here.</div>

              {confirmOk ? <div className="alert alert-success py-2 small">Uploaded successfully!</div> : null}
              {confirmErr ? <div className="alert alert-danger py-2 small">Upload failed: {confirmErr}</div> : null}

              {!scanResult ? (
                <div className="text-muted small">Scan a receipt in the chat pane to review and confirm.</div>
              ) : (
                <>
                  <div className="mb-2">
                    <input
                      value={scanResult.shop || ""}
                      onChange={(e) => setScanResult((p) => (p ? { ...p, shop: e.target.value } : p))}
                      placeholder="Shop"
                      className="form-control form-control-sm mb-2"
                    />
                    <input
                      value={scanResult.date || ""}
                      onChange={(e) => setScanResult((p) => (p ? { ...p, date: e.target.value } : p))}
                      placeholder="Date (YYYY-MM-DD)"
                      className="form-control form-control-sm mb-2"
                    />
                    <input
                      value={scanResult.time || ""}
                      onChange={(e) => setScanResult((p) => (p ? { ...p, time: e.target.value } : p))}
                      placeholder="Time (HH:MM:SS)"
                      className="form-control form-control-sm"
                    />
                  </div>

                  <div className="vstack gap-2" style={{ maxHeight: "45vh", overflow: "auto" }}>
                    {scanResult.items.map((it, idx) => (
                      <div key={idx} className="border rounded-3 p-2 bg-body">
                        <div className="fw-semibold small">{it.item_text}</div>
                        <div className="text-muted small">{it.item_type || "-"}</div>

                        <div className="row g-2 mt-1">
                          <div className="col-4">
                            <input
                              type="number"
                              value={it.quantity}
                              onChange={(e) => updateItem(idx, { quantity: Number(e.target.value || 0) })}
                              className="form-control form-control-sm"
                              placeholder="Qty"
                            />
                          </div>
                          <div className="col-4">
                            <input
                              type="number"
                              value={it.price}
                              onChange={(e) => updateItem(idx, { price: Number(e.target.value || 0) })}
                              className="form-control form-control-sm"
                              placeholder="Price"
                            />
                          </div>
                          <div className="col-4">
                            <input
                              type="number"
                              value={it.discount}
                              onChange={(e) => updateItem(idx, { discount: Number(e.target.value || 0) })}
                              className="form-control form-control-sm"
                              placeholder="Disc"
                            />
                          </div>
                        </div>

                        <select
                          value={it.taxonomy_id || "UNCATEGORIZED"}
                          onChange={(e) => updateItem(idx, { taxonomy_id: e.target.value })}
                          className="form-select form-select-sm mt-2"
                        >
                          <option value="UNCATEGORIZED">Uncategorized</option>
                          {taxonomy.map((t) => (
                            <option key={t.id} value={t.id}>
                              {t.full_path || t.id}
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>

                  <button onClick={confirmAndSave} disabled={confirmBusy || apiOk !== true} className="btn btn-dark w-100 mt-3">
                    {confirmBusy ? "Saving & exporting..." : "Confirm & Save"}
                  </button>
                </>
              )}
            </div>
          </div>
        </section>
      </div>

      <nav className="navbar navbar-light bg-white border-top fixed-bottom d-lg-none" style={{ height: 64 }}>
        <div className="container-fluid justify-content-around">
          <button className="btn btn-link text-decoration-none" onClick={() => scrollToPane("budget")}>
            Budget
          </button>
          <button className="btn btn-link text-decoration-none fw-semibold" onClick={() => scrollToPane("chat")}>
            Chat
          </button>
          <button className="btn btn-link text-decoration-none" onClick={() => scrollToPane("insights")}>
            Insights
          </button>
        </div>
      </nav>
    </div>
  );
}
