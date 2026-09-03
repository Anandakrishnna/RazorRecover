import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, 
  TrendingUp, 
  AlertTriangle, 
  RefreshCw, 
  HelpCircle, 
  X, 
  CheckCircle2, 
  Clock, 
  Search, 
  ArrowUpRight, 
  Zap,
  Activity,
  User,
  DollarSign
} from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

export default function App() {
  const [cases, setCases] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filtering state
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  
  // Modal state
  const [selectedCaseId, setSelectedCaseId] = useState(null);
  const [caseDetail, setCaseDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [modalError, setModalError] = useState(null);

  // Fetch initial dashboard data
  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch cases list
      const casesRes = await fetch(`${API_BASE_URL}/cases?limit=100`);
      if (!casesRes.ok) throw new Error(`API error fetching cases: ${casesRes.statusText}`);
      const casesData = await casesRes.json();
      setCases(casesData.cases || []);

      // Fetch metrics evaluation
      const metricsRes = await fetch(`${API_BASE_URL}/metrics/eval`);
      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }
    } catch (err) {
      setError(err.message || 'Failed to connect to RazorRecover API');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  // Open "Why?" Modal & Fetch Case Detail
  const handleOpenModal = async (caseId) => {
    setSelectedCaseId(caseId);
    setCaseDetail(null);
    setLoadingDetail(true);
    setModalError(null);
    
    try {
      const res = await fetch(`${API_BASE_URL}/cases/${caseId}`);
      if (!res.ok) throw new Error(`Failed to load case details for ${caseId}`);
      const data = await res.json();
      setCaseDetail(data);
    } catch (err) {
      setModalError(err.message);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleCloseModal = () => {
    setSelectedCaseId(null);
    setCaseDetail(null);
  };

  // Compute metrics fallback if evaluation API fails
  const totalRevenueAtRisk = metrics ? metrics.revenue_at_risk : cases.reduce((acc, c) => acc + c.revenue_at_risk, 0);
  const totalRecovered = metrics ? metrics.successfully_recovered_revenue : cases.filter(c => c.status === 'RECOVERED').reduce((acc, c) => acc + c.revenue_at_risk, 0);
  const recoveryRate = metrics ? metrics.recovery_rate_pct : (totalRevenueAtRisk > 0 ? (totalRecovered / totalRevenueAtRisk * 100).toFixed(1) : 0);
  const openCasesCount = cases.filter(c => c.status === 'OPEN' || c.status === 'IN_PROGRESS').length;

  // Filter cases
  const filteredCases = cases.filter(c => {
    const matchesStatus = statusFilter === 'ALL' || c.status === statusFilter;
    const matchesSearch = 
      c.transaction_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.customer_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.root_cause.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesStatus && matchesSearch;
  });

  const formatINR = (val) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val || 0);

  const renderStatusBadge = (statusStr) => {
    const st = (statusStr || 'OPEN').toUpperCase();
    switch (st) {
      case 'RECOVERED':
        return <span className="badge badge-recovered"><CheckCircle2 size={12} /> RECOVERED</span>;
      case 'FAILED':
        return <span className="badge badge-failed"><X size={12} /> FAILED</span>;
      case 'ESCALATED':
        return <span className="badge badge-escalated"><AlertTriangle size={12} /> ESCALATED</span>;
      case 'STOPPED':
        return <span className="badge badge-stopped"><Clock size={12} /> STOPPED</span>;
      default:
        return <span className="badge badge-open"><Activity size={12} /> OPEN</span>;
    }
  };

  return (
    <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '32px 24px' }}>
      
      {/* BRANDING & HEADER */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
            <div style={{ background: 'linear-gradient(135deg, #6366f1, #10b981)', padding: '10px', borderRadius: '12px', display: 'flex' }}>
              <ShieldCheck size={28} color="#ffffff" />
            </div>
            <div>
              <h1 style={{ fontSize: '1.75rem', fontWeight: 800, letterSpacing: '-0.025em' }}>RazorRecover</h1>
              <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Autonomous Revenue Recovery & Safety Gated Agent</p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '9999px', fontSize: '0.85rem', color: '#34d399' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#34d399', boxShadow: '0 0 10px #34d399' }}></span>
            API Connected (v1.0.0)
          </div>
          <button 
            onClick={fetchData} 
            disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 18px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: '10px', color: 'var(--text-primary)', cursor: 'pointer', fontWeight: 600, fontSize: '0.875rem', transition: 'all 0.2s' }}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </header>

      {/* ERROR ALERT */}
      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#f87171', padding: '16px', borderRadius: '12px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <AlertTriangle size={20} />
          <div>
            <strong>Backend Connection Issue:</strong> {error}. Ensure FastAPI server is running on <code>http://localhost:8000</code>.
          </div>
        </div>
      )}

      {/* KPI METRIC CARDS HEADER */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px', marginBottom: '36px' }}>
        
        {/* Card 1: Revenue at Risk */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Revenue at Risk</span>
            <div style={{ padding: '8px', background: 'rgba(239, 68, 68, 0.12)', borderRadius: '10px', color: '#f87171' }}>
              <AlertTriangle size={20} />
            </div>
          </div>
          <div style={{ fontSize: '1.875rem', fontWeight: 800, marginBottom: '6px' }}>{formatINR(totalRevenueAtRisk)}</div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Flagged across incoming failure events</p>
        </div>

        {/* Card 2: Recovered Revenue */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Recovered Revenue</span>
            <div style={{ padding: '8px', background: 'rgba(16, 185, 129, 0.12)', borderRadius: '10px', color: '#34d399' }}>
              <TrendingUp size={20} />
            </div>
          </div>
          <div style={{ fontSize: '1.875rem', fontWeight: 800, color: '#34d399', marginBottom: '6px' }}>{formatINR(totalRecovered)}</div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Verified via probabilistic simulations</p>
        </div>

        {/* Card 3: Recovery Rate % */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Recovery Rate</span>
            <div style={{ padding: '8px', background: 'rgba(99, 102, 241, 0.12)', borderRadius: '10px', color: '#818cf8' }}>
              <Zap size={20} />
            </div>
          </div>
          <div style={{ fontSize: '1.875rem', fontWeight: 800, color: '#818cf8', marginBottom: '6px' }}>{recoveryRate}%</div>
          <div style={{ background: 'rgba(255, 255, 255, 0.08)', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
            <div style={{ width: `${Math.min(100, recoveryRate)}%`, background: 'linear-gradient(90deg, #6366f1, #34d399)', height: '100%' }}></div>
          </div>
        </div>

        {/* Card 4: Open Cases */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', fontWeight: 500 }}>Active Cases</span>
            <div style={{ padding: '8px', background: 'rgba(59, 130, 246, 0.12)', borderRadius: '10px', color: '#60a5fa' }}>
              <Activity size={20} />
            </div>
          </div>
          <div style={{ fontSize: '1.875rem', fontWeight: 800, marginBottom: '6px' }}>{openCasesCount} / {cases.length}</div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Currently open in agent pipeline</p>
        </div>

      </section>

      {/* RECOVERY CASE DATA TABLE SECTION */}
      <section className="glass-panel" style={{ padding: '28px' }}>
        
        {/* Table Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Recovery Cases Queue</h2>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Sorted by Expected Recovery Value (₹) DESC</p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            {/* Search Input */}
            <div style={{ position: 'relative' }}>
              <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input 
                type="text" 
                placeholder="Search transaction, customer, cause..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ padding: '10px 16px 10px 38px', background: 'rgba(15, 23, 42, 0.8)', border: '1px solid var(--border-subtle)', borderRadius: '10px', color: 'var(--text-primary)', fontSize: '0.875rem', outline: 'none', width: '280px' }}
              />
            </div>

            {/* Filter Buttons */}
            <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.8)', padding: '4px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              {['ALL', 'RECOVERED', 'ESCALATED', 'STOPPED', 'FAILED', 'OPEN'].map(st => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                    background: statusFilter === st ? 'var(--accent-indigo)' : 'transparent',
                    color: statusFilter === st ? '#ffffff' : 'var(--text-secondary)',
                    transition: 'all 0.15s'
                  }}
                >
                  {st}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Data Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                <th style={{ padding: '14px 16px' }}>Case & Transaction</th>
                <th style={{ padding: '14px 16px' }}>Customer ID</th>
                <th style={{ padding: '14px 16px' }}>Revenue at Risk</th>
                <th style={{ padding: '14px 16px' }}>Root Cause</th>
                <th style={{ padding: '14px 16px' }}>Recovery Prob %</th>
                <th style={{ padding: '14px 16px' }}>Expected Value</th>
                <th style={{ padding: '14px 16px' }}>Status</th>
                <th style={{ padding: '14px 16px', textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                    <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px' }} />
                    Loading recovery cases...
                  </td>
                </tr>
              ) : filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                    No recovery cases matched your filter criteria.
                  </td>
                </tr>
              ) : (
                filteredCases.map(c => (
                  <tr key={c.id} style={{ borderBottom: '1px solid var(--border-subtle)', transition: 'background 0.15s' }}>
                    <td style={{ padding: '16px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{c.id}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{c.transaction_id}</div>
                    </td>
                    <td style={{ padding: '16px', color: 'var(--text-secondary)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <User size={14} color="var(--text-muted)" />
                        {c.customer_id}
                      </div>
                    </td>
                    <td style={{ padding: '16px', fontWeight: 600 }}>
                      {formatINR(c.revenue_at_risk)}
                    </td>
                    <td style={{ padding: '16px' }}>
                      <span style={{ background: 'rgba(255, 255, 255, 0.05)', padding: '4px 8px', borderRadius: '6px', fontSize: '0.75rem', fontFamily: 'var(--font-mono)', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                        {c.root_cause}
                      </span>
                    </td>
                    <td style={{ padding: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 600, color: c.recovery_probability >= 0.7 ? '#34d399' : c.recovery_probability >= 0.4 ? '#fbbf24' : '#f87171' }}>
                          {(c.recovery_probability * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td style={{ padding: '16px', fontWeight: 700, color: 'var(--accent-indigo)' }}>
                      {formatINR(c.expected_recovery_value)}
                    </td>
                    <td style={{ padding: '16px' }}>
                      {renderStatusBadge(c.status)}
                    </td>
                    <td style={{ padding: '16px', textAlign: 'right' }}>
                      <button
                        onClick={() => handleOpenModal(c.id)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '8px 14px',
                          background: 'rgba(99, 102, 241, 0.12)',
                          border: '1px solid rgba(99, 102, 241, 0.3)',
                          borderRadius: '8px',
                          color: '#818cf8',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          cursor: 'pointer',
                          transition: 'all 0.15s'
                        }}
                      >
                        <HelpCircle size={14} />
                        Why?
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* "WHY?" DECISION & AUDIT MODAL */}
      {selectedCaseId && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px', background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)' }}>
          <div className="glass-panel" style={{ width: '100%', maxWidth: '900px', maxHeight: '90vh', overflowY: 'auto', padding: '32px', background: 'var(--bg-modal)', border: '1px solid var(--border-strong)' }}>
            
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
                  <h2 style={{ fontSize: '1.35rem', fontWeight: 800 }}>Decision Rationale & Audit Trail</h2>
                  {caseDetail && renderStatusBadge(caseDetail.case.status)}
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Case ID: <code style={{ fontFamily: 'var(--font-mono)' }}>{selectedCaseId}</code></p>
              </div>

              <button 
                onClick={handleCloseModal}
                style={{ background: 'rgba(255, 255, 255, 0.08)', border: 'none', borderRadius: '8px', padding: '8px', color: 'var(--text-primary)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: '48px', textAlign: 'center', color: 'var(--text-muted)' }}>
                <RefreshCw size={28} className="animate-spin" style={{ margin: '0 auto 16px' }} />
                Fetching case decision records & audit logs from FastAPI...
              </div>
            ) : modalError ? (
              <div style={{ padding: '24px', background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', borderRadius: '10px' }}>
                Error: {modalError}
              </div>
            ) : caseDetail ? (
              <div>
                
                {/* SIDE-BY-SIDE DECISION COMPARISON */}
                <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '16px', color: 'var(--text-secondary)' }}>Agent Decision Comparison</h3>
                
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))', gap: '20px', marginBottom: '32px' }}>
                  
                  {/* Left Box: LLM Recommender */}
                  <div style={{ background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.25)', borderRadius: '12px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#818cf8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>AI Recommender (LLM)</span>
                      <span style={{ fontSize: '0.75rem', background: 'rgba(99, 102, 241, 0.2)', padding: '2px 8px', borderRadius: '4px', color: '#a5b4fc' }}>Proposed</span>
                    </div>
                    <div style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '8px', color: '#f8fafc' }}>
                      Action: <code>{caseDetail.decisions[0]?.recommendation || 'N/A'}</code>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {caseDetail.decisions[0]?.reasoning_text || 'AI proposed action based on event characteristics.'}
                    </p>
                  </div>

                  {/* Right Box: Policy Engine Verdict */}
                  <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: '12px', padding: '20px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                      <span style={{ fontSize: '0.8rem', fontWeight: 700, color: '#34d399', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Deterministic Policy Engine</span>
                      <span className={`badge ${caseDetail.decisions[0]?.policy_check_result === 'APPROVED' ? 'badge-recovered' : 'badge-escalated'}`}>
                        {caseDetail.decisions[0]?.policy_check_result || 'APPROVED'}
                      </span>
                    </div>
                    <div style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '8px', color: '#f8fafc' }}>
                      Allowed Action: <code>{caseDetail.decisions[0]?.action_taken || 'N/A'}</code>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      Gated by Priority Matrix. Ensured zero policy violations and enforced 24h retry / rate limits.
                    </p>
                  </div>

                </div>

                {/* AUDIT LOG TIMELINE */}
                <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '16px', color: 'var(--text-secondary)' }}>Chronological Audit Trail</h3>
                
                <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid var(--border-subtle)', borderRadius: '12px', padding: '20px' }}>
                  {caseDetail.audit_log.map((log, i) => (
                    <div key={log.id} style={{ display: 'flex', gap: '16px', marginBottom: i === caseDetail.audit_log.length - 1 ? 0 : '20px', position: 'relative' }}>
                      
                      {/* Timeline dot & line */}
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--accent-indigo)', border: '2px solid var(--bg-modal)' }}></div>
                        {i < caseDetail.audit_log.length - 1 && (
                          <div style={{ width: '2px', flexGrow: 1, background: 'rgba(255, 255, 255, 0.1)', marginTop: '4px' }}></div>
                        )}
                      </div>

                      {/* Log Details */}
                      <div style={{ flexGrow: 1 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                          <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--accent-indigo)' }}>{log.event_type}</span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                            {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : ''}
                          </span>
                        </div>
                        <pre style={{ background: 'rgba(0, 0, 0, 0.4)', padding: '10px 14px', borderRadius: '8px', fontSize: '0.75rem', color: 'var(--text-secondary)', overflowX: 'auto', fontFamily: 'var(--font-mono)' }}>
                          {typeof log.detail === 'object' ? JSON.stringify(log.detail, null, 2) : log.detail}
                        </pre>
                      </div>

                    </div>
                  ))}
                </div>

              </div>
            ) : null}

          </div>
        </div>
      )}

    </div>
  );
}
