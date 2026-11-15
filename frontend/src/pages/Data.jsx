import React, { useState, useEffect } from 'react';
import { uploadDataset as uploadCsv, getUploads, mapUpload, importUpload, seedDemoMine } from '../services/api';
import { UploadCloud, CheckCircle2, AlertTriangle, Database, Layers, ArrowRight, ShieldCheck, FileSpreadsheet, TrendingUp, Boxes, Warehouse } from 'lucide-react';

export default function Data({ company, onCompanyChange }) {
  const [selectedCategory, setSelectedCategory] = useState('unified');
  const [activeFile, setActiveFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [uploads, setUploads] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importSuccess, setImportSuccess] = useState(null);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [showDemoConfirm, setShowDemoConfirm] = useState(false);

  const fetchUploads = () => {
    if (company?.id) {
      getUploads(company.id).then(setUploads).catch(console.error);
    }
  };

  useEffect(() => {
    fetchUploads();
  }, [company?.id]);

  const handleLoadDemoData = async () => {
    setLoadingDemo(true);
    setError(null);
    try {
      await seedDemoMine();
      setImportSuccess({ imported_row_count: 'All Horizon Demo Records', skipped_row_count: 0 });
      fetchUploads();
      setShowDemoConfirm(false);
    } catch (e) {
      const msg = e.response?.data?.detail || e.message;
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setLoadingDemo(false);
    }
  };

  const handleUpload = () => {
    if (!activeFile) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setImportSuccess(null);
    uploadCsv(company.id, selectedCategory, activeFile)
      .then(r => {
        setResult(r);
        if (r.company_id && r.company_id !== company.id) {
          onCompanyChange(r.company_id);
        }
      })
      .catch(e => {
        const msg = e.response?.data?.detail || e.message;
        setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
      })
      .finally(() => setLoading(false));
  };

  const handleImport = async () => {
    if (!result) return;
    setImporting(true);
    setError(null);
    try {
      await mapUpload(result.upload_id, result.suggested_mapping);
      const importRes = await importUpload(company.id, result.upload_id);
      setImportSuccess(importRes);
      fetchUploads();
    } catch (e) {
      const msg = e.response?.data?.detail || e.message;
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setImporting(false);
    }
  };

  const hasImportedData = uploads && uploads.length > 0;

  return (
    <div className="page animate-fade" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '28px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              DATA & IMPORTS
            </h1>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              Multi-Source Ingestion Pipeline
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
            Ingest company inventory snapshots, transaction sales history, and supplier lead-time parameters.
          </p>
        </div>

        <div>
          <button
            className="btn-secondary"
            onClick={() => setShowDemoConfirm(true)}
            style={{ fontSize: '13px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Database size={14} /> Load Synthetic Demo Dataset
          </button>
        </div>
      </div>

      {/* Demo Seed Confirmation Modal */}
      {showDemoConfirm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', maxWidth: '520px', width: '100%', padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--status-watch)', marginBottom: '16px' }}>
              <AlertTriangle size={20} />
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Confirm Loading Synthetic Demo Data
              </h3>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '20px' }}>
              Loading the demonstration dataset will populate your tenant with the <strong>Horizon Electronics</strong> catalog (15 SKUs, 2 distribution centers, and 3 years of daily demand history). This replaces any current operational records.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button className="btn-secondary" onClick={() => setShowDemoConfirm(false)} disabled={loadingDemo}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleLoadDemoData} disabled={loadingDemo}>
                {loadingDemo ? 'Generating Dataset...' : 'Confirm & Seed Demo Data'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Data Provenance Status Banner */}
      <div style={{ background: hasImportedData ? 'var(--bg-surface-1)' : 'var(--bg-surface-2)', border: `1px solid ${hasImportedData ? 'var(--status-healthy-border)' : 'var(--border-default)'}`, borderRadius: 'var(--r-lg)', padding: '20px 24px', marginBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {hasImportedData ? <CheckCircle2 size={16} color="var(--status-healthy)" /> : <Database size={16} color="var(--accent-primary)" />}
              <span style={{ fontWeight: 700, fontSize: '14px', color: hasImportedData ? 'var(--status-healthy)' : 'var(--text-primary)' }}>
                {hasImportedData ? 'Company Operational Data Active' : 'No Operational Data Ingested Yet'}
              </span>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px', margin: 0 }}>
              {hasImportedData
                ? `${uploads.length} verified file(s) imported. Serving analytics and forecasting exclusively from your tenant records.`
                : 'Upload your company files below or test the analytics engine using pre-configured synthetic demo records.'}
            </p>
          </div>

          {hasImportedData && (
            <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
              <div>Datasets: <strong style={{ color: 'var(--text-primary)' }}>{uploads.length}</strong></div>
              <div>Latest Ingestion: <strong style={{ color: 'var(--text-primary)' }}>{new Date(uploads[0]?.uploaded_at || Date.now()).toLocaleDateString()}</strong></div>
            </div>
          )}
        </div>
      </div>

      {/* Unified Master Ingestion Specification Panel */}
      <div
        style={{
          background: 'var(--bg-surface-1)',
          border: '1px solid var(--border-default)',
          boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
          borderRadius: 'var(--r-lg)',
          padding: '24px 28px',
          marginBottom: '28px',
          position: 'relative',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: 'var(--r-md)', background: 'var(--accent-primary-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-primary)' }}>
              <Layers size={22} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h2 style={{ fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-heading)', color: 'var(--text-primary)', margin: 0 }}>
                  ENTERPRISE MASTER DATASET (UNIFIED INGESTION)
                </h2>
                <span style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.08em', padding: '2px 8px', borderRadius: '3px', background: 'rgba(80, 216, 233, 0.15)', color: 'var(--accent-secondary)', border: '1px solid rgba(80, 216, 233, 0.3)' }}>
                  ALL-IN-ONE PIPELINE
                </span>
              </div>
              <p style={{ fontSize: '12.5px', color: 'var(--text-secondary)', marginTop: '4px', margin: 0 }}>
                Single file ingestion for complete operational synchronization. Ingests sales orders, multi-DC inventory, and supplier lead times simultaneously.
              </p>
            </div>
          </div>
          <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)', padding: '6px 12px', background: 'var(--accent-primary-dim)', borderRadius: 'var(--r-sm)', border: '1px solid rgba(94, 107, 255, 0.3)' }}>
            AUTO-CALIBRATES ML MODELS
          </div>
        </div>

        {/* 3 Core Capability Sub-Modules Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{ background: 'var(--bg-surface-2)', padding: '14px 16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <TrendingUp size={14} color="var(--accent-secondary)" />
              <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>Historical Sales &amp; Demand</strong>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '0 0 6px 0', lineHeight: 1.4 }}>
              3,675+ daily transaction lines across all SKUs. Automatically fits Gradient Boosting and Random Forest forecasters.
            </p>
            <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              date, product_id, quantity, unit_price, promotion, region
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface-2)', padding: '14px 16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <Boxes size={14} color="var(--status-healthy)" />
              <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>Warehouse Inventory Balances</strong>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '0 0 6px 0', lineHeight: 1.4 }}>
              On-hand balances, warehouse assignments, and initial safety buffer thresholds across regional DCs.
            </p>
            <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              warehouse, inventory_level, safety_stock
            </div>
          </div>

          <div style={{ background: 'var(--bg-surface-2)', padding: '14px 16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <Warehouse size={14} color="var(--status-watch)" />
              <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>Supplier Lead Times &amp; Quality</strong>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '0 0 6px 0', lineHeight: 1.4 }}>
              Supplier profiles, contracted lead-time days, reliability ratings, and defect rate parameters for bivariate SS.
            </p>
            <div style={{ fontSize: '10px', color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
              supplier_id, supplier_name, lead_time_days, reliability, defect_rate
            </div>
          </div>
        </div>
      </div>

      {/* File Dropzone & Processing Area */}
      <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '28px', marginBottom: '28px' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '4px' }}>
          Upload File: Enterprise Master Dataset (CSV or XLSX)
        </h3>
        <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '20px' }}>
          Accepts SupplyIQ_Master_Enterprise_Dataset.csv or standard enterprise spreadsheets up to 50MB. Columns will be automatically matched to internal standards.
        </p>

        <input
          type="file"
          id="file-upload"
          accept=".csv,.xlsx,.xls"
          style={{ display: 'none' }}
          onChange={e => { setActiveFile(e.target.files[0]); setResult(null); setImportSuccess(null); }}
        />
        <label
          htmlFor="file-upload"
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            border: '2px dashed var(--border-default)',
            borderRadius: 'var(--r-md)',
            padding: '36px 20px',
            cursor: 'pointer',
            background: 'var(--bg-surface-2)',
            transition: 'border-color 0.2s',
          }}
        >
          <UploadCloud size={36} color="var(--accent-primary)" style={{ marginBottom: '12px' }} />
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
            {activeFile ? activeFile.name : 'Click to select CSV or Excel spreadsheet'}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
            {activeFile ? `${(activeFile.size / 1024).toFixed(1)} KB` : 'Deterministic schema matching with manual override'}
          </div>
        </label>

        {activeFile && !result && (
          <button
            className="btn-primary"
            onClick={handleUpload}
            disabled={loading}
            style={{ width: '100%', marginTop: '16px', padding: '10px' }}
          >
            {loading ? 'Validating File Structure...' : 'Process & Map Enterprise Master Dataset'}
          </button>
        )}
      </div>

      {error && (
        <div style={{ color: 'var(--status-critical)', padding: '16px', background: 'var(--status-critical-bg)', border: '1px solid var(--status-critical-border)', borderRadius: 'var(--r-md)', marginBottom: '24px', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* Mapping & Ingestion Preview Panel */}
      {result && (
        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '28px', marginBottom: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--status-healthy)', marginBottom: '20px' }}>
            <CheckCircle2 size={20} />
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0 }}>File Validated Successfully</h2>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <div style={{ background: 'var(--bg-surface-2)', padding: '12px 16px', borderRadius: 'var(--r-md)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Rows Detected</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>{result.row_count?.toLocaleString()}</div>
            </div>
            <div style={{ background: 'var(--bg-surface-2)', padding: '12px 16px', borderRadius: 'var(--r-md)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Columns</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>{result.columns?.length || 0}</div>
            </div>
            <div style={{ background: 'var(--bg-surface-2)', padding: '12px 16px', borderRadius: 'var(--r-md)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Target Category</div>
              <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>{selectedCategory}</div>
            </div>
          </div>

          <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '12px' }}>
            Column Schema Mapping
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '24px' }}>
            {Object.entries(result.suggested_mapping || {}).map(([raw, standard]) => (
              <div key={raw} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--bg-surface-2)', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-subtle)', fontSize: '12px' }}>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{raw}</span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: standard ? 'var(--status-healthy)' : 'var(--text-tertiary)' }}>
                  <span>→</span>
                  <span style={{ fontWeight: 600 }}>{standard ? `${standard} (Auto-matched)` : 'Ignored'}</span>
                </div>
              </div>
            ))}
          </div>

          {importSuccess ? (
            <div style={{ padding: '16px', background: 'var(--status-healthy-bg)', border: '1px solid var(--status-healthy-border)', borderRadius: 'var(--r-md)', color: 'var(--status-healthy)', fontWeight: 600, fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle2 size={16} />
                <span>Ingestion Complete: {importSuccess.imported_row_count} rows committed to tenant database ({importSuccess.skipped_row_count} skipped/invalid).</span>
              </div>
              {(selectedCategory === 'sales' || selectedCategory === 'unified') && (
                <div style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: 500, paddingLeft: '24px' }}>
                  ✓ Machine learning demand forecasting models & replenishment inventory buffers have been synchronized. Check <a href="/demand" style={{ color: 'var(--accent-primary)', textDecoration: 'underline' }}>Demand Forecasts</a> and <a href="/models" style={{ color: 'var(--accent-primary)', textDecoration: 'underline' }}>Models & Quality</a> to view walk-forward projections!
                </div>
              )}
            </div>
          ) : (
            <button
              className="btn-primary"
              onClick={handleImport}
              disabled={importing}
              style={{ width: '100%', padding: '12px', fontSize: '14px', fontWeight: 600 }}
            >
              {importing ? 'Importing Rows & Recomputing Metrics...' : 'Confirm Mapping & Commit Records'}
            </button>
          )}
        </div>
      )}

      {/* Ingestion History Table */}
      {hasImportedData && (
        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Tenant Ingestion Audit Log
            </h3>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '10px 16px' }}>Filename</th>
                <th style={{ padding: '10px 16px' }}>Category</th>
                <th style={{ padding: '10px 16px' }}>Rows</th>
                <th style={{ padding: '10px 16px' }}>Ingestion Date</th>
                <th style={{ padding: '10px 16px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {uploads.map((u, idx) => (
                <tr key={u.id || u.upload_id || `upload-${idx}`} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <FileSpreadsheet size={14} color="var(--accent-primary)" />
                      {u.original_filename}
                    </div>
                  </td>
                  <td style={{ padding: '10px 16px', textTransform: 'capitalize' }}>{u.dataset_type}</td>
                  <td style={{ padding: '10px 16px' }}>{u.row_count?.toLocaleString() || '—'}</td>
                  <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>
                    {u.uploaded_at ? new Date(u.uploaded_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, background: 'var(--status-healthy-bg)', color: 'var(--status-healthy)' }}>
                      {u.status?.toUpperCase() || 'IMPORTED'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
