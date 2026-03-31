import { useEffect, useMemo, useRef, useState } from "react";

import {
  deletePersona,
  deleteSession,
  health,
  listPersonas,
  listSessions,
  loadSession,
  streamDebate,
  saveSession,
  upsertPersona,
} from "./api/client";

function normalizeError(error) {
  return error instanceof Error ? error.message : String(error);
}

function DebateTranscript({ result, personasByKey }) {
  if (!result || !result.synthesis) {
    return (
      <div className="panel debate-transcript empty">
        <h3>Latest Debate</h3>
        <p>Run a debate to view routing details, round outputs, and synthesis.</p>
      </div>
    );
  }

  const a1Key = result.agent_1;
  const a2Key = result.agent_2;
  const a1 = personasByKey[a1Key]?.data?.display_name || a1Key;
  const a2 = personasByKey[a2Key]?.data?.display_name || a2Key;

  return (
    <div className="panel debate-transcript">
      <div className="transcript-head">
        <h3>Latest Debate</h3>
        <span className="chip">Router</span>
      </div>
      <p className="muted">Agent 1: <strong>{a1}</strong> ({Math.round((result.agent_1_confidence || 0) * 100)}%)</p>
      <p className="muted">Agent 2: <strong>{a2}</strong> ({Math.round((result.agent_2_confidence || 0) * 100)}%)</p>
      <p className="muted">Reason: {result.routing_reason}</p>

      <div className="round-grid">
        <article>
          <h4>{a1} Opening</h4>
          <p>{result.agent_1_opening}</p>
        </article>
        <article>
          <h4>{a2} Opening</h4>
          <p>{result.agent_2_opening}</p>
        </article>
        <article>
          <h4>{a1} Rebuttal</h4>
          <p>{result.agent_1_rebuttal}</p>
        </article>
        <article>
          <h4>{a2} Rebuttal</h4>
          <p>{result.agent_2_rebuttal}</p>
        </article>
        <article>
          <h4>{a1} Closing</h4>
          <p>{result.agent_1_closing}</p>
        </article>
        <article>
          <h4>{a2} Closing</h4>
          <p>{result.agent_2_closing}</p>
        </article>
      </div>

      <div className="synthesis-card">
        <h4>Synthesis</h4>
        <p>{result.synthesis}</p>
      </div>
    </div>
  );
}

function ChatHistory({ chatHistory }) {
  return (
    <div className="panel history-panel">
      <h3>Session History</h3>
      {chatHistory.length === 0 ? (
        <p className="muted">No messages yet.</p>
      ) : (
        <div className="history-list">
          {chatHistory.map((item, index) => (
            <div key={`${index}-${item.role}`} className={`history-item ${item.role}`}>
              <span className="history-role">{item.role}</span>
              <p>{item.content}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [apiStatus, setApiStatus] = useState("checking");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [streamProgress, setStreamProgress] = useState(null); // null={idle}, {currentNode, allNodes: []}
  const unsubscribeRef = useRef(null);

  const [question, setQuestion] = useState("");
  const [selectionMode, setSelectionMode] = useState("auto");
  const [selectedAgent1, setSelectedAgent1] = useState("");
  const [selectedAgent2, setSelectedAgent2] = useState("");

  const [sessionName, setSessionName] = useState("");
  const [chatHistory, setChatHistory] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [lastResult, setLastResult] = useState(null);

  const [personas, setPersonas] = useState([]);
  const [personaKey, setPersonaKey] = useState("");
  const [personaName, setPersonaName] = useState("");
  const [personaColor, setPersonaColor] = useState("bold white");
  const [personaTags, setPersonaTags] = useState("");
  const [personaPrompt, setPersonaPrompt] = useState("");

  const personasByKey = useMemo(
    () => Object.fromEntries(personas.map((item) => [item.key, item])),
    [personas]
  );

  const personaKeys = useMemo(() => personas.map((item) => item.key), [personas]);

  async function refreshCoreData() {
    const [personaRows, sessionRows] = await Promise.all([listPersonas(), listSessions()]);
    setPersonas(personaRows);
    setSessions(sessionRows);
  }

  async function bootstrap() {
    try {
      await health();
      setApiStatus("online");
      await refreshCoreData();
    } catch (err) {
      setApiStatus("offline");
      setError(normalizeError(err));
    }
  }

  useEffect(() => {
    bootstrap();
  }, []);

  async function handleRunDebate(event) {
    event.preventDefault();
    setError("");

    if (!question.trim()) {
      setError("Question is required.");
      return;
    }

    const selectedAgents = [selectedAgent1, selectedAgent2].filter(Boolean);
    if (selectionMode === "manual") {
      if (selectedAgents.length !== 2) {
        setError("Manual mode requires exactly two selected personas.");
        return;
      }
      if (selectedAgent1 === selectedAgent2) {
        setError("Manual mode requires two different personas.");
        return;
      }
    }

    try {
      setBusy(true);
      setStreamProgress({ currentNode: "Initializing...", allNodes: [] });

      // Cleanup any previous subscription
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }

      const debatePayload = {
        user_input: question.trim(),
        chat_history: chatHistory,
        selection_mode: selectionMode,
        selected_agents: selectionMode === "manual" ? selectedAgents : [],
        session_name: sessionName.trim() || null,
      };

      let finalResult = null;

      const unsubscribe = await streamDebate(
        debatePayload,
        (event) => {
          if (event.node === "error") {
            setError(event.error || "Streaming error occurred");
            setBusy(false);
            setStreamProgress(null);
          } else if (event.node === "session_save_error") {
            setError(event.error || "Session save failed");
            setBusy(false);
            setStreamProgress(null);
          } else if (event.node === "completion") {
            // Save session name if returned, and update chat history
            if (event.saved_session_name) {
              setSessionName(event.saved_session_name);
            }
            if (event.chat_history) {
              setChatHistory(event.chat_history);
            }
            // Display completion message
            setStreamProgress((prev) => ({
              ...prev,
              currentNode: "Debate Complete ✓",
            }));
            setBusy(false);
            setTimeout(() => {
              setStreamProgress(null);
              setQuestion("");
              refreshCoreData();
            }, 500);
          } else if (event.node === "stream_complete") {
            // Stream ended, waiting for final processing
            setStreamProgress((prev) => ({
              ...prev,
              currentNode: "Finalizing...",
            }));
          } else if (event.result) {
            // Regular debate event
            finalResult = event.result;
            setLastResult(event.result);
            setStreamProgress((prev) => ({
              currentNode: event.node,
              allNodes: Array.from(
                new Set([...(prev?.allNodes || []), event.node])
              ),
            }));
          }
        },
        (error) => {
          setError(normalizeError(error));
          setBusy(false);
          setStreamProgress(null);
        }
      );

      unsubscribeRef.current = unsubscribe;
    } catch (err) {
      setError(normalizeError(err));
      setBusy(false);
      setStreamProgress(null);
    }
  }

  async function handleSaveSession() {
    setError("");
    const normalized = sessionName.trim();
    if (!normalized) {
      setError("Set a session name before saving.");
      return;
    }
    try {
      setBusy(true);
      await saveSession({
        name: normalized,
        chat_history: chatHistory,
        selection_mode: selectionMode,
      });
      await refreshCoreData();
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleLoadSession(name) {
    setError("");
    try {
      setBusy(true);
      const loaded = await loadSession(name);
      setSessionName(loaded.name);
      setSelectionMode(loaded.selection_mode);
      setChatHistory(loaded.chat_history || []);
      setLastResult(null);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteSession(name) {
    setError("");
    try {
      setBusy(true);
      await deleteSession(name);
      if (sessionName === name) {
        setSessionName("");
      }
      await refreshCoreData();
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleSavePersona(event) {
    event.preventDefault();
    setError("");

    const key = personaKey.trim().toLowerCase();
    if (!key) {
      setError("Persona key is required.");
      return;
    }

    const tags = personaTags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);

    if (!personaName.trim() || !personaPrompt.trim() || tags.length === 0) {
      setError("Persona requires display name, tags, and system prompt.");
      return;
    }

    try {
      setBusy(true);
      await upsertPersona(key, {
        display_name: personaName.trim(),
        color: personaColor.trim() || "bold white",
        tags,
        system_prompt: personaPrompt.trim(),
      });
      setPersonaKey("");
      setPersonaName("");
      setPersonaColor("bold white");
      setPersonaTags("");
      setPersonaPrompt("");
      await refreshCoreData();
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeletePersona(key) {
    setError("");
    try {
      setBusy(true);
      await deletePersona(key);
      await refreshCoreData();
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setBusy(false);
    }
  }

  function handleEditPersona(persona) {
    setPersonaKey(persona.key);
    setPersonaName(persona.data.display_name);
    setPersonaColor(persona.data.color || "bold white");
    setPersonaTags(persona.data.tags.join(", "));
    setPersonaPrompt(persona.data.system_prompt);
    setError("");
  }

  function handleClearPersonaForm() {
    setPersonaKey("");
    setPersonaName("");
    setPersonaColor("bold white");
    setPersonaTags("");
    setPersonaPrompt("");
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <p className="eyebrow">AI Persona Debate Arena</p>
        <h1>Web Control Room</h1>
        <p className="tagline">Run the same debate engine from the browser while keeping the CLI workflow intact.</p>
        <div className="status-row">
          <span className={`status ${apiStatus}`}>API: {apiStatus}</span>
          <span className="status">Mode: {selectionMode}</span>
          <span className="status">Session: {sessionName || "none"}</span>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <main className="layout-grid">
        <section className="panel debate-control">
          <div className="panel-head">
            <h2>Debate</h2>
            <span className="chip">Streaming enabled</span>
          </div>

          <form onSubmit={handleRunDebate}>
            <label>
              Session name
              <input
                value={sessionName}
                onChange={(event) => setSessionName(event.target.value)}
                placeholder="session_20260331"
                disabled={busy}
              />
            </label>

            <label>
              Selection mode
              <select value={selectionMode} onChange={(event) => setSelectionMode(event.target.value)} disabled={busy}>
                <option value="auto">auto</option>
                <option value="manual">manual</option>
              </select>
            </label>

            {selectionMode === "manual" ? (
              <div className="manual-grid">
                <label>
                  Persona 1
                  <select value={selectedAgent1} onChange={(event) => setSelectedAgent1(event.target.value)} disabled={busy}>
                    <option value="">Select persona</option>
                    {personaKeys.map((key) => (
                      <option key={key} value={key}>{key}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Persona 2
                  <select value={selectedAgent2} onChange={(event) => setSelectedAgent2(event.target.value)} disabled={busy}>
                    <option value="">Select persona</option>
                    {personaKeys.map((key) => (
                      <option key={key} value={key}>{key}</option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}

            <label>
              Debate question
              <textarea
                rows={4}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Should we prioritize Mars colonization over Earth climate resilience?"
                disabled={busy}
              />
            </label>

            {streamProgress ? (
              <div className="stream-progress">
                <div className="progress-bar-container">
                  <div className="progress-bar-fill"></div>
                </div>
                <p className="progress-text">
                  {streamProgress.currentNode}
                </p>
                {streamProgress.allNodes.length > 0 && (
                  <div className="progress-nodes">
                    {streamProgress.allNodes.map((node) => (
                      <span key={node} className="node-badge">
                        {node.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ) : null}

            <div className="button-row">
              <button type="submit" disabled={busy}>{busy ? "Running..." : "Run Debate"}</button>
              <button type="button" className="ghost" disabled={busy} onClick={handleSaveSession}>Save Session</button>
            </div>
          </form>
        </section>

        <DebateTranscript result={lastResult} personasByKey={personasByKey} />

        <ChatHistory chatHistory={chatHistory} />

        <section className="panel sessions-panel">
          <h2>Sessions</h2>
          {sessions.length === 0 ? (
            <p className="muted">No saved sessions.</p>
          ) : (
            <ul className="list-table">
              {sessions.map((session) => (
                <li key={session.name}>
                  <div>
                    <strong>{session.name}</strong>
                    <p>{session.selection_mode} · {session.messages} messages</p>
                  </div>
                  <div className="row-actions">
                    <button type="button" className="ghost" disabled={busy} onClick={() => handleLoadSession(session.name)}>Load</button>
                    <button type="button" className="danger" disabled={busy} onClick={() => handleDeleteSession(session.name)}>Delete</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel personas-panel">
          <h2>Personas</h2>
          <ul className="list-table">
            {personas.map((persona) => (
              <li key={persona.key}>
                <div>
                  <strong>{persona.key}</strong>
                  <p>{persona.data.display_name} · <span className="origin-badge">{persona.origin}</span></p>
                </div>
                <div className="row-actions">
                  {persona.origin === "custom" && (
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy}
                      onClick={() => handleEditPersona(persona)}
                    >
                      Edit
                    </button>
                  )}
                  {persona.origin === "custom" ? (
                    <button
                      type="button"
                      className="danger"
                      disabled={busy}
                      onClick={() => handleDeletePersona(persona.key)}
                    >
                      Delete
                    </button>
                  ) : (
                    <span className="chip">built-in</span>
                  )}
                </div>
              </li>
            ))}
          </ul>

          <form className="persona-form" onSubmit={handleSavePersona}>
            <h3>{personaKey ? "Update Custom Persona" : "Create New Persona"}</h3>
            <p className="form-hint">
              {personaKey 
                ? `Editing "${personaKey}" — modify fields and click Save to update.`
                : "Enter a unique key (snake_case) and fill in all fields to create a new persona."}
            </p>
            <label>
              Key (snake_case)
              <input 
                value={personaKey} 
                onChange={(event) => setPersonaKey(event.target.value)} 
                placeholder="my_philosopher"
                disabled={personaKey && personas.some(p => p.key === personaKey && p.origin === "custom") ? false : false}
              />
            </label>
            <label>
              Display name
              <input value={personaName} onChange={(event) => setPersonaName(event.target.value)} />
            </label>
            <label>
              Color
              <input value={personaColor} onChange={(event) => setPersonaColor(event.target.value)} placeholder="bold white" />
            </label>
            <label>
              Tags (comma separated)
              <input value={personaTags} onChange={(event) => setPersonaTags(event.target.value)} placeholder="startup, product, strategy" />
            </label>
            <label>
              System prompt
              <textarea rows={4} value={personaPrompt} onChange={(event) => setPersonaPrompt(event.target.value)} />
            </label>
            <div className="button-row">
              <button type="submit" disabled={busy}>{personaKey ? "Update Persona" : "Create Persona"}</button>
              {personaKey && (
                <button 
                  type="button" 
                  className="ghost" 
                  disabled={busy}
                  onClick={handleClearPersonaForm}
                >
                  Clear Form
                </button>
              )}
            </div>
          </form>
        </section>
      </main>
    </div>
  );
}
