import React, { useState, useEffect, useRef } from 'react';
import { 
  Scale, 
  Send, 
  RefreshCw, 
  FileText, 
  BookOpen, 
  ChevronLeft, 
  ChevronRight,
  Maximize2,
  Minimize2,
  Menu,
  Copy,
  Check,
  Briefcase,
  ShieldCheck,
  FileCheck,
  Sparkles,
  Info
} from 'lucide-react';

interface SourceInfo {
  type: string;
  title: string;
  section?: string;
  snippet: string;
}

interface Message {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
  sources?: SourceInfo[];
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const EXAMPLE_QUESTIONS = [
  "What is the notice period for terminating the agreement?",
  "Does the Integrated Goods and Services Tax Act apply to Jammu and Kashmir?",
  "What is the penalty for GST evasion under Section 122?",
  "Explain the limitation period for cheque bounce cases under NI Act.",
  "What are the key obligations of the service provider in the contract?"
];

const CATEGORIES = [
  {
    icon: <FileCheck className="card-icon" size={20} color="var(--accent-gold)" />,
    title: "Contract Auditing",
    desc: "Scan and check key obligations, clauses, termination rules, and notice periods.",
    query: "What is the notice period for terminating the agreement?"
  },
  {
    icon: <Briefcase className="card-icon" size={20} color="var(--accent-purple)" />,
    title: "GST Regulations",
    desc: "Verify rules regarding tax compliance, evasion penalties, and territorial limits.",
    query: "What is the penalty for GST evasion under Section 122?"
  },
  {
    icon: <Scale className="card-icon" size={20} color="var(--accent-cyan)" />,
    title: "Statutes & Act Codes",
    desc: "Inquire about sections of the Indian Penal Code, Civil Code, Negotiable Instruments, etc.",
    query: "Explain the limitation period for cheque bounce cases under NI Act."
  },
  {
    icon: <ShieldCheck className="card-icon" size={20} color="var(--accent-green)" />,
    title: "Legal Precedents",
    desc: "Retrieve legal rulings, compliance duties, and service provider obligations.",
    query: "What are the key obligations of the service provider in the contract?"
  }
];

function FormattedMessage({ text }: { text: string }) {
  if (!text) return null;

  const parseInline = (lineText: string): React.ReactNode[] => {
    // Regex split for bold **text** and inline `code`
    const parts = lineText.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, idx) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={idx}>{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={idx}>{part.slice(1, -1)}</code>;
      }
      return part;
    });
  };

  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];
  let currentBlock: { type: 'code' | 'list' | 'table'; lines: string[]; lang?: string } | null = null;

  const flushBlock = (key: number) => {
    if (!currentBlock) return;
    if (currentBlock.type === 'code') {
      elements.push(
        <pre key={`code-${key}`}>
          <code>{currentBlock.lines.join('\n')}</code>
        </pre>
      );
    } else if (currentBlock.type === 'list') {
      elements.push(
        <ul key={`list-${key}`}>
          {currentBlock.lines.map((li, i) => (
            <li key={i}>{parseInline(li)}</li>
          ))}
        </ul>
      );
    } else if (currentBlock.type === 'table') {
      const rows = currentBlock.lines.map(line => 
        line.split('|').map(cell => cell.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1)
      );
      if (rows.length > 0) {
        const headers = rows[0];
        const dataRows = rows.slice(2); // Skip separator row
        elements.push(
          <table key={`table-${key}`}>
            <thead>
              <tr>
                {headers.map((h, i) => <th key={i}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {dataRows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => <td key={j}>{parseInline(cell)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        );
      }
    }
    currentBlock = null;
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    if (trimmed.startsWith('```')) {
      if (currentBlock && currentBlock.type === 'code') {
        flushBlock(idx);
      } else {
        flushBlock(idx);
        currentBlock = { type: 'code', lines: [], lang: trimmed.slice(3) };
      }
      return;
    }

    if (currentBlock && currentBlock.type === 'code') {
      currentBlock.lines.push(line);
      return;
    }

    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      if (currentBlock && currentBlock.type === 'table') {
        currentBlock.lines.push(line);
      } else {
        flushBlock(idx);
        currentBlock = { type: 'table', lines: [line] };
      }
      return;
    }

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (currentBlock && currentBlock.type === 'list') {
        currentBlock.lines.push(trimmed.slice(2));
      } else {
        flushBlock(idx);
        currentBlock = { type: 'list', lines: [trimmed.slice(2)] };
      }
      return;
    }

    flushBlock(idx);
    if (trimmed) {
      elements.push(<p key={idx}>{parseInline(line)}</p>);
    }
  });

  flushBlock(lines.length);
  return <>{elements}</>;
}

function App() {
  const [status, setStatus] = useState<{
    llm_loaded: boolean;
    databases_loaded: boolean;
    device: string;
    status: string;
  } | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [selectedSource, setSelectedSource] = useState<number | null>(null);
  const [showSourcesPanel, setShowSourcesPanel] = useState(true);
  
  // Responsive sidebar drawer states
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: string } | null>(null);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  // Check backend status
  const checkStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      } else {
        setStatus(prev => prev ? { ...prev, status: 'error' } : { llm_loaded: false, databases_loaded: false, device: 'unknown', status: 'error' });
      }
    } catch (err) {
      console.error("Failed to fetch status:", err);
      setStatus({
        llm_loaded: false,
        databases_loaded: false,
        device: 'offline',
        status: 'error'
      });
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Adjust textarea height dynamically
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [inputText]);

  const handleSendMessage = async (textToSend: string) => {
    if (!textToSend.trim() || loading) return;

    const userMsgId = Date.now().toString();
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    const userMessage: Message = {
      id: userMsgId,
      sender: 'user',
      text: textToSend,
      timestamp
    };

    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setLoading(true);

    try {
      const historyPayload: [string, string][] = [];
      for (let i = 0; i < messages.length; i += 2) {
        if (messages[i] && messages[i + 1]) {
          historyPayload.push([messages[i].text, messages[i + 1].text]);
        }
      }

      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          query: textToSend,
          history: historyPayload
        })
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Inference failed");
      }

      const data = await res.json();
      
      const botMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'bot',
        text: data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: data.sources
      };

      setMessages(prev => [...prev, botMessage]);
      if (data.sources && data.sources.length > 0) {
        setSources(data.sources);
        setSelectedSource(0);
      }
    } catch (error: any) {
      console.error(error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'bot',
        text: `⚠️ Error: ${error.message || "Failed to communicate with local model server. Make sure backend.py is running."}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(inputText);
    }
  };

  const handleCopyText = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
      .then(() => {
        setCopiedMessageId(id);
        setToast({ message: "Text copied to clipboard", type: "success" });
        setTimeout(() => setCopiedMessageId(null), 2000);
      })
      .catch(err => {
        console.error("Copy failed", err);
      });
  };

  const isServerReady = status?.llm_loaded && status?.databases_loaded;

  return (
    <div className="app-container">
      {/* Background orbs */}
      <div className="glow-orb orb-cyan"></div>
      <div className="glow-orb orb-gold"></div>

      {/* 1. Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="brand">
            <Scale className="brand-icon" size={28} />
            <div>
              <h1>LegalSahyak</h1>
              <div className="brand-subtitle">AI Indian Legal System</div>
            </div>
          </div>
        </div>

        {/* Status indicator */}
        <div className="status-card">
          <div className="status-row">
            <span className="status-label">RAG Engine:</span>
            <span className="status-value">
              <span className={`status-dot ${status?.databases_loaded ? 'active' : 'pending'}`}></span>
              {status?.databases_loaded ? 'Active Sync' : 'Connecting...'}
            </span>
          </div>
          <div className="status-row">
            <span className="status-label">LLM Weights:</span>
            <span className="status-value">
              <span className={`status-dot ${status?.llm_loaded ? 'active' : 'pending'}`}></span>
              {status?.llm_loaded ? 'Loaded' : 'Idle'}
            </span>
          </div>
          <div className="status-row">
            <span className="status-label">Device Type:</span>
            <span className="status-value" style={{ textTransform: 'uppercase', fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
              {status?.device || 'CPU / RAG'}
            </span>
          </div>
        </div>

        {/* Examples */}
        <div className="examples-section">
          <h3 className="examples-title">
            <Sparkles size={12} color="var(--accent-gold)" /> Quick Suggestions
          </h3>
          {EXAMPLE_QUESTIONS.map((q, idx) => (
            <button
              key={idx}
              className="example-btn"
              disabled={!isServerReady}
              onClick={() => {
                setInputText(q);
                setSidebarOpen(false);
                textareaRef.current?.focus();
              }}
            >
              {q}
            </button>
          ))}
        </div>

        <div className="sidebar-footer">
          <p>© 2026 LegalSahyak AI</p>
          <p style={{ marginTop: '4px', fontSize: '0.65rem', color: 'var(--text-muted)' }}>
            Grounded in Indian statutory laws, regulations & service agreements.
          </p>
        </div>
      </aside>

      {/* 2. Main Chat Workspace */}
      <main className="main-chat">
        <header className="chat-header">
          <div className="chat-header-title">
            <button className="mobile-menu-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
              <Menu size={20} />
            </button>
            <span>⚖️ Workspace Console</span>
          </div>
          <div className="chat-header-actions">
            <button 
              className="header-btn" 
              onClick={() => {
                setMessages([]);
                setSources([]);
                setSelectedSource(null);
                setToast({ message: "Console cleared successfully", type: "info" });
              }}
            >
              <RefreshCw size={13} />
              Reset Console
            </button>
            <button 
              className="header-btn" 
              onClick={() => setShowSourcesPanel(!showSourcesPanel)}
            >
              {showSourcesPanel ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
              {showSourcesPanel ? 'Hide Sources' : 'Show Sources'}
            </button>
          </div>
        </header>

        {/* Messages */}
        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="empty-chat">
              <div className="empty-icon-wrapper">
                <Scale size={32} />
              </div>
              <h2>LegalSahyak Grounded Agent</h2>
              <p>
                RAG search grounded in Indian Statutes, Acts, and Contract agreements. Ask custom clauses or select a domain below to begin:
              </p>
              
              <div className="category-grid">
                {CATEGORIES.map((cat, idx) => (
                  <div 
                    key={idx} 
                    className="category-card" 
                    onClick={() => {
                      if (isServerReady) {
                        setInputText(cat.query);
                        textareaRef.current?.focus();
                      } else {
                        setToast({ message: "System is initializing. Please wait...", type: "warning" });
                      }
                    }}
                  >
                    <div className="card-header-row">
                      {cat.icon}
                      <span>{cat.title}</span>
                    </div>
                    <div className="card-desc">{cat.desc}</div>
                  </div>
                ))}
              </div>

              {!isServerReady && (
                <div style={{
                  background: 'var(--accent-gold-dim)',
                  border: '1px solid rgba(226, 179, 60, 0.2)',
                  borderRadius: '12px',
                  padding: '0.85rem 1.25rem',
                  fontSize: '0.8rem',
                  color: 'var(--accent-gold)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.65rem',
                  marginTop: '1.5rem',
                  width: '100%',
                  justifyContent: 'center'
                }}>
                  <RefreshCw size={14} className="animate-spin" style={{ animation: 'spin 2s linear infinite' }} />
                  <span>Loading local weights & FAISS databases. This may take a moment...</span>
                </div>
              )}
            </div>
          ) : (
            messages.map((m) => (
              <div key={m.id} className={`message-bubble ${m.sender}`}>
                <div className="message-avatar">
                  {m.sender === 'user' ? 'U' : '⚖️'}
                </div>
                <div className="message-content-wrapper">
                  <button 
                    className={`copy-btn ${copiedMessageId === m.id ? 'copied' : ''}`}
                    onClick={() => handleCopyText(m.text, m.id)}
                    title="Copy message"
                  >
                    {copiedMessageId === m.id ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                  <div className="message-content">
                    <FormattedMessage text={m.text} />
                  </div>
                  <div className="message-time">
                    {m.timestamp}
                  </div>
                </div>
              </div>
            ))
          )}

          {loading && (
            <div className="message-bubble bot">
              <div className="message-avatar">⚖️</div>
              <div className="message-content-wrapper">
                <div className="message-content" style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}>
                  <div className="skeleton-container">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                      <Sparkles size={12} color="var(--accent-cyan)" />
                      <span style={{ fontSize: '0.78rem', color: 'var(--accent-cyan)', fontWeight: 'bold' }}>Retrieving & Synthesizing response...</span>
                    </div>
                    <div className="skeleton-line w-90"></div>
                    <div className="skeleton-line w-80"></div>
                    <div className="skeleton-line w-60"></div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="input-area-container">
          <div className="input-box">
            <textarea
              ref={textareaRef}
              className="input-textarea"
              placeholder={isServerReady ? "Enter legal or compliance inquiry..." : "Connecting to LegalSahyak agent..."}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={!isServerReady || loading}
              rows={1}
            />
            <button
              className="send-btn"
              onClick={() => handleSendMessage(inputText)}
              disabled={!isServerReady || !inputText.trim() || loading}
            >
              <Send size={18} />
            </button>
          </div>
          <div style={{ textAlign: 'center', marginTop: '0.75rem', fontSize: '0.7rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }}>
            <Info size={11} /> Grounded results are generated only from retrieved document clauses.
          </div>
        </div>
      </main>

      {/* 3. Sources sidebar */}
      <aside className={`sources-panel ${showSourcesPanel ? 'open' : 'collapsed'}`}>
        <div className="sources-header">
          <BookOpen className="sources-header-icon" size={20} />
          <h2>Grounded Clauses</h2>
        </div>

        <div className="sources-content">
          {sources.length === 0 ? (
            <div className="no-sources-state">
              <FileText className="no-sources-icon" size={40} />
              <p style={{ fontSize: '0.82rem' }}>
                Sources will appear here once retrieved by the RAG model.
              </p>
            </div>
          ) : (
            sources.map((s, idx) => (
              <div
                key={idx}
                className={`source-card ${s.type} ${selectedSource === idx ? 'selected' : ''}`}
                onClick={() => setSelectedSource(idx)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="source-tag">{s.type}</span>
                  {selectedSource === idx ? <Minimize2 size={12} color="var(--text-muted)" /> : <Maximize2 size={12} color="var(--text-muted)" />}
                </div>
                <div className="source-title">{s.title}</div>
                {s.section && <div className="source-section">{s.section}</div>}
                <div className={`source-snippet ${selectedSource === idx ? 'expanded' : ''}`}>
                  {s.snippet}
                </div>
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Toast Notification */}
      {toast && (
        <div className="toast-container">
          <div className="toast">
            <Sparkles size={14} color="var(--accent-cyan)" />
            <span>{toast.message}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
