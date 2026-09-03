import React, { useState, useEffect } from 'react';
import { 
  RefreshCw, 
  X, 
  Search, 
  HelpCircle,
  AlertCircle
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
      const casesRes = await fetch(`${API_BASE_URL}/cases?limit=100`);
      if (!casesRes.ok) throw new Error(`API error fetching cases: ${casesRes.statusText}`);
      const casesData = await casesRes.json();
      setCases(casesData.cases || []);

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
  const activeCasesCount = cases.filter(c => c.status === 'OPEN' || c.status === 'IN_PROGRESS').length;

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

  const renderStatusTag = (statusStr) => {
    const st = (statusStr || 'OPEN').toUpperCase();
    switch (st) {
      case 'RECOVERED':
        return <span className="tag-badge tag-recovered">RECOVERED</span>;
      case 'FAILED':
        return <span className="tag-badge tag-failed">FAILED</span>;
      case 'ESCALATED':
        return <span className="tag-badge tag-escalated">ESCALATED</span>;
      case 'STOPPED':
        return <span className="tag-badge tag-stopped">STOPPED</span>;
      default:
        return <span className="tag-badge tag-open">OPEN</span>;
    }
  };

  return (
    <div style={{ maxWidth: '1360px', margin: '0 auto', padding: '24px 32px' }}>
      
      {/* PAGE HEADER */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', paddingBottom: '16px', borderBottom: '1px solid var(--border-color)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '2px' }}>
            <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em' }}>RazorRecover Ops Console</h1>
            <span style={{ fontSize: '11px', fontWeight: 600, background: '#f0fdf4', color: '#0f766e', border: '1px solid #ccfbf1', padding: '2px 8px', borderRadius: '4px' }}>
              v1.0.0 Live API
            </span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Autonomous Revenue Recovery Operations & Safety Audit Monitor</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button 
            onClick={fetchData} 
            disabled={loading}
            className="ops-btn-outline"
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Sync Data
          </button>
        </div>
      </header>

      {/* ERROR ALERT */}
      {error && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', color: '#991b1b', padding: '12px 16px', borderRadius: '6px', marginBottom: '24px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <AlertCircle size={16} />
          <div>
            <strong>API Connection Error:</strong> {error}. Verify FastAPI server is running on <code>http://localhost:8000</code>.
          </div>
        </div>
      )}

      {/* KPI HEADER CARDS (4 IN A ROW) */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '24px' }}>
        
        {/* Card 1: Revenue at Risk */}
        <div className="ops-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '8px' }}>REVENUE AT RISK</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em', marginBottom: '4px' }}>{formatINR(totalRevenueAtRisk)}</div>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>Total flagged across failure events</div>
        </div>

        {/* Card 2: Recovered Revenue */}
        <div className="ops-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '8px' }}>RECOVERED REVENUE</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--accent)', letterSpacing: '-0.02em', marginBottom: '4px' }}>{formatINR(totalRecovered)}</div>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>Verified outcome simulations</div>
        </div>

        {/* Card 3: Recovery Rate % */}
        <div className="ops-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '8px' }}>RECOVERY RATE</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--accent)', letterSpacing: '-0.02em', marginBottom: '4px' }}>{recoveryRate}%</div>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>Target benchmark: &gt; 35.0%</div>
        </div>

        {/* Card 4: Active Cases */}
        <div className="ops-card" style={{ padding: '20px' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '8px' }}>ACTIVE CASES</div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em', marginBottom: '4px' }}>{activeCasesCount} <span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--text-muted)' }}>/ {cases.length}</span></div>
          <div style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>Pending intervention or resolution</div>
        </div>

      </section>

      {/* RECOVERY CASE DATA TABLE SECTION */}
      <section className="ops-card" style={{ padding: '20px' }}>
        
        {/* Table Controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', gap: '16px' }}>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-main)' }}>Recovery Case Queue</h2>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Ranked by Expected Recovery Value (ERV = Amount × P[Recovery])</div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Search Input */}
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-subtle)' }} />
              <input 
                type="text" 
                placeholder="Filter ID, customer, cause..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="ops-input"
                style={{ paddingLeft: '30px', width: '240px' }}
              />
            </div>

            {/* Filter Buttons */}
            <div style={{ display: 'flex', gap: '2px', background: 'var(--bg-subtle)', padding: '2px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              {['ALL', 'RECOVERED', 'ESCALATED', 'STOPPED', 'FAILED', 'OPEN'].map(st => (
                <button
                  key={st}
                  onClick={() => setStatusFilter(st)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '3px',
                    fontSize: '11px',
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                    background: statusFilter === st ? 'var(--bg-surface)' : 'transparent',
                    color: statusFilter === st ? 'var(--text-main)' : 'var(--text-muted)',
                    boxShadow: statusFilter === st ? '0 1px 2px rgba(0,0,0,0.05)' : 'none',
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
          <table className="ops-table">
            <thead>
              <tr>
                <th>Case ID</th>
                <th>Txn ID</th>
                <th>Customer ID</th>
                <th>Revenue at Risk</th>
                <th>Root Cause</th>
                <th>Recovery Prob</th>
                <th>Expected Value</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Audit</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    Loading recovery cases...
                  </td>
                </tr>
              ) : filteredCases.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                    No recovery cases found matching filter criteria.
                  </td>
                </tr>
              ) : (
                filteredCases.map(c => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>{c.id}</td>
                    <td className="mono-text" style={{ color: 'var(--text-muted)' }}>{c.transaction_id}</td>
                    <td style={{ color: 'var(--text-body)' }}>{c.customer_id}</td>
                    <td style={{ fontWeight: 600, color: 'var(--text-main)' }}>
                      {formatINR(c.revenue_at_risk)}
                    </td>
                    <td>
                      <span className="mono-text" style={{ background: 'var(--bg-subtle)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                        {c.root_cause}
                      </span>
                    </td>
                    <td style={{ fontWeight: 600, color: c.recovery_probability >= 0.7 ? '#065f46' : c.recovery_probability >= 0.4 ? '#92400e' : '#991b1b' }}>
                      {(c.recovery_probability * 100).toFixed(0)}%
                    </td>
                    <td style={{ fontWeight: 700, color: 'var(--accent)' }}>
                      {formatINR(c.expected_recovery_value)}
                    </td>
                    <td>
                      {renderStatusTag(c.status)}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => handleOpenModal(c.id)}
                        className="ops-btn-outline"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 8px' }}
                      >
                        <HelpCircle size={12} />
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

      {/* "WHY?" DECISION RATIONALE & AUDIT MODAL */}
      {selectedCaseId && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px', background: 'rgba(15, 23, 42, 0.4)', backdropFilter: 'blur(4px)' }}>
          <div className="ops-card" style={{ width: '100%', maxWidth: '880px', maxHeight: '88vh', overflowY: 'auto', padding: '24px', background: 'var(--bg-surface)' }}>
            
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px', paddingBottom: '12px', borderBottom: '1px solid var(--border-color)' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '2px' }}>
                  <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-main)' }}>Decision Rationale & Audit Trail</h2>
                  {caseDetail && renderStatusTag(caseDetail.case.status)}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Case ID: <span className="mono-text" style={{ color: 'var(--text-main)' }}>{selectedCaseId}</span></div>
              </div>

              <button 
                onClick={handleCloseModal}
                style={{ background: 'transparent', border: 'none', borderRadius: '4px', padding: '4px', color: 'var(--text-muted)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                Loading decision records...
              </div>
            ) : modalError ? (
              <div style={{ padding: '16px', background: '#fee2e2', color: '#991b1b', borderRadius: '4px', fontSize: '13px' }}>
                Error: {modalError}
              </div>
            ) : caseDetail ? (
              <div>
                
                {/* SIDE-BY-SIDE DECISION COMPARISON */}
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
                  Agent Decision Comparison
                </div>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '24px' }}>
                  
                  {/* Left Box: LLM Recommender */}
                  <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>AI Recommender (LLM)</span>
                      <span className="mono-text" style={{ fontSize: '11px', background: '#e0f2fe', color: '#0369a1', padding: '1px 6px', borderRadius: '3px' }}>Proposed</span>
                    </div>
                    <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-main)' }}>
                      Proposed: <span className="mono-text">{caseDetail.decisions[0]?.recommendation || 'N/A'}</span>
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--text-body)', lineHeight: 1.5 }}>
                      {caseDetail.decisions[0]?.reasoning_text || 'AI proposed action based on event parameters.'}
                    </p>
                  </div>

                  {/* Right Box: Policy Engine Verdict */}
                  <div style={{ background: 'var(--accent-light)', border: '1px solid #bbf7d0', borderRadius: '6px', padding: '16px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Deterministic Policy Engine</span>
                      <span className="tag-badge tag-recovered">
                        {caseDetail.decisions[0]?.policy_check_result || 'APPROVED'}
                      </span>
                    </div>
                    <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-main)' }}>
                      Allowed Action: <span className="mono-text">{caseDetail.decisions[0]?.action_taken || 'N/A'}</span>
                    </div>
                    <p style={{ fontSize: '12px', color: 'var(--text-body)', lineHeight: 1.5 }}>
                      Gated by Priority Matrix. Verified zero policy violations and enforced rate limits.
                    </p>
                  </div>

                </div>

                {/* AUDIT LOG TIMELINE */}
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '12px' }}>
                  Chronological Audit Trail
                </div>
                
                <div style={{ border: '1px solid var(--border-color)', borderRadius: '6px', overflow: 'hidden' }}>
                  {caseDetail.audit_log.map((log, i) => (
                    <div key={log.id} style={{ padding: '12px 16px', borderBottom: i === caseDetail.audit_log.length - 1 ? 'none' : '1px solid var(--border-color)', background: i % 2 === 0 ? 'var(--bg-surface)' : 'var(--bg-subtle)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent)' }}>{log.event_type}</span>
                        <span className="mono-text" style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                          {log.id} | {log.timestamp ? new Date(log.timestamp).toISOString() : ''}
                        </span>
                      </div>
                      <pre className="mono-text" style={{ background: 'var(--bg-page)', border: '1px solid var(--border-color)', padding: '8px 12px', borderRadius: '4px', fontSize: '11px', color: 'var(--text-body)', overflowX: 'auto' }}>
                        {typeof log.detail === 'object' ? JSON.stringify(log.detail, null, 2) : log.detail}
                      </pre>
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
