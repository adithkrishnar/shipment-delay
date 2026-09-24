import { useEffect, useState } from 'react';
import { uploadDataset, validateUpload, mapUpload, importUpload, getUploads } from '../services/api';
import Panel from '../components/Panel';
import { UploadCloud, CheckCircle, AlertCircle } from 'lucide-react';

/* ── Step flow indicator ─────────────────────────────────────── */
function StepFlow({ currentStep }) {
  // steps: 0=upload, 1=map, 2=validate/import
  const steps = [
    { label: 'Upload', num: 1 },
    { label: 'Map columns', num: 2 },
    { label: 'Validate', num: 3 },
    { label: 'Import', num: 4 },
  ];

  return (
    <div className="step-flow">
      {steps.map((step, idx) => {
        const done = idx < currentStep;
        const active = idx === currentStep;
        return (
          <div key={step.label} style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
            <div className={`step-item${active ? ' active' : done ? ' done' : ''}`}>
              <div className="step-number">{done ? '✓' : step.num}</div>
              <div className="step-label">{step.label}</div>
            </div>
            {idx < steps.length - 1 && (
              <div className="step-connector" />
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ── Quality score display ───────────────────────────────────── */
function QualityScore({ score }) {
  const color = score >= 80 ? 'var(--status-healthy)'
              : score >= 60 ? 'var(--status-watch)'
              : 'var(--status-critical)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ fontSize: 28, fontWeight: 800, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.03em', color }}>
        {score}
        <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-tertiary)' }}>/100</span>
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ height: 6, background: 'var(--bg-surface-3)', borderRadius: 999, overflow: 'hidden' }}>
          <div style={{
            width: `${score}%`,
            height: '100%',
            background: color,
            borderRadius: 999,
            transition: 'width 0.8s var(--ease-out)',
          }} />
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4, fontWeight: 600 }}>Data quality score</div>
      </div>
    </div>
  );
}

export default function Data({ company, onCompanyChange }) {
  const [type, setType] = useState('sales');
  const [file, setFile] = useState(null);
  const [u, setU] = useState(null);
  const [mapping, setMapping] = useState({});
  const [validation, setValidation] = useState(null);
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);

  const refresh = () => getUploads(company.id).then(setHistory).catch(() => {});

  useEffect(() => { refresh(); }, [company]);

  const upload = () => {
    setBusy(true);
    uploadDataset(company.id, type, file)
      .then(x => {
        setU(x);
        setMapping(x.suggested_mapping || {});
        setValidation(null);
        setResult(null);
        refresh();
      })
      .finally(() => setBusy(false));
  };

  const validate = () => {
    setBusy(true);
    validateUpload(u.upload_id, mapping).then(setValidation).finally(() => setBusy(false));
  };

  const saveMap = () => {
    setBusy(true);
    mapUpload(u.upload_id, mapping).then(() => validate()).finally(() => setBusy(false));
  };

  const imp = () => {
    setBusy(true);
    importUpload(u.company_id || company.id, u.upload_id)
      .then(x => { 
        setResult(x); 
        if (onCompanyChange && x.company_id !== company.id) {
          onCompanyChange(x.company_id);
          // also refresh uploads for the new company
          getUploads(x.company_id).then(setHistory).catch(() => {});
        } else {
          refresh();
        }
      })
      .finally(() => setBusy(false));
  };

  // Determine current step
  const currentStep = result ? 4 : validation ? 3 : u ? 1 : 0;

  // All available target fields
  const allTargetFields = u
    ? [...new Set([
        ...Object.values(u.suggested_mapping || {}).filter(Boolean),
        'date','product_id','quantity','demand','inventory_level','warehouse',
        'safety_stock','shipment_id','origin','destination','carrier',
        'planned_delivery','actual_delivery','distance','weight','transport_mode',
        'supplier_id','supplier_name','lead_time','reliability','cost','defect_rate',
      ])]
    : [];

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">Data Management</div>
        <h1 className="page-title">Bring your company's data into the intelligence layer.</h1>
        <p className="page-subtitle">Upload → map → validate → import. Works with different company column names.</p>
      </div>

      {/* Step flow */}
      <StepFlow currentStep={currentStep} />

      {/* ── Step 1: Upload ─────────────────────────────────────── */}
      <Panel title="1 — Upload dataset">
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
          <div>
            <div className="field-label">Dataset type</div>
            <select value={type} onChange={e => setType(e.target.value)} aria-label="Dataset type">
              <option>sales</option>
              <option>inventory</option>
              <option>shipments</option>
              <option>suppliers</option>
            </select>
          </div>

          <div>
            <div className="field-label">CSV or Excel file</div>
            <label className="drop" style={{ padding: '16px', textAlign: 'center', cursor: 'pointer', display: 'block' }}>
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={e => setFile(e.target.files?.[0])}
                style={{ display: 'none' }}
                aria-label="Select file"
              />
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                <UploadCloud size={24} style={{ color: 'var(--text-tertiary)' }} aria-hidden="true" />
                {file ? (
                  <div className="drop-filename">
                    <CheckCircle size={12} aria-hidden="true" />
                    {file.name}
                  </div>
                ) : (
                  <>
                    <div className="drop-text">Drop file or click to browse</div>
                    <div className="drop-subtext">.csv, .xlsx, .xls</div>
                  </>
                )}
              </div>
            </label>
          </div>
        </div>

        <button
          className="primary"
          onClick={upload}
          disabled={!file || busy}
          style={{ display: 'flex', alignItems: 'center', gap: 8 }}
        >
          {busy ? (
            <><div className="spinner" style={{ width: 13, height: 13, borderWidth: 2 }} aria-hidden="true" />Working…</>
          ) : (
            <><UploadCloud size={13} aria-hidden="true" />Upload &amp; inspect</>
          )}
        </button>
      </Panel>

      {/* ── Step 2: Column mapping ─────────────────────────────── */}
      {u && (
        <Panel title={`2 — Column mapping · ${u.row_count} rows detected`}>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source column</th>
                  <th>Map to field</th>
                </tr>
              </thead>
              <tbody>
                {u.columns.map(c => (
                  <tr key={c}>
                    <td>
                      <strong>{c}</strong>
                    </td>
                    <td>
                      <select
                        value={mapping[c] || ''}
                        onChange={e => setMapping({ ...mapping, [c]: e.target.value || null })}
                        style={{ width: 'auto', minWidth: 200 }}
                        aria-label={`Map column ${c}`}
                      >
                        <option value="">— ignore —</option>
                        {allTargetFields.map(x => (
                          <option key={x} value={x}>{x}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center' }}>
            <button
              className="primary"
              onClick={saveMap}
              disabled={busy}
              style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            >
              {busy ? (
                <><div className="spinner" style={{ width: 13, height: 13, borderWidth: 2 }} aria-hidden="true" />Validating…</>
              ) : 'Save mapping & validate'}
            </button>
          </div>

          {/* Validation summary */}
          {validation && (
            <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
              <QualityScore score={validation.data_quality_score} />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', padding: '12px 14px', textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--status-healthy)', fontVariantNumeric: 'tabular-nums' }}>{validation.valid_row_count}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 4 }}>Valid rows</div>
                </div>
                <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', padding: '12px 14px', textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: validation.errors?.length > 0 ? 'var(--status-critical)' : 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                    {validation.errors?.length || 0}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 4 }}>Errors</div>
                </div>
                <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', padding: '12px 14px', textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 800, color: validation.warnings?.length > 0 ? 'var(--status-watch)' : 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                    {validation.warnings?.length || 0}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: 4 }}>Warnings</div>
                </div>
              </div>
            </div>
          )}
        </Panel>
      )}

      {/* ── Step 3: Import ─────────────────────────────────────── */}
      {validation && (
        <Panel title="3 — Import to database">
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.6 }}>
            Review the validation report. If there are no blocking required-field errors, import into the company's database.
          </p>

          {validation.missing_required_fields?.length > 0 && (
            <div style={{
              padding: '12px 14px',
              background: 'var(--status-critical-bg)',
              border: '1px solid var(--status-critical-border)',
              borderRadius: 'var(--r-lg)',
              marginBottom: 16,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
            }}>
              <AlertCircle size={14} style={{ color: 'var(--status-critical)', marginTop: 1, flexShrink: 0 }} aria-hidden="true" />
              <div style={{ fontSize: 12, color: 'var(--status-critical)', fontWeight: 500 }}>
                Missing required fields: {validation.missing_required_fields.join(', ')}
              </div>
            </div>
          )}

          <button
            className="primary"
            onClick={imp}
            disabled={validation.missing_required_fields?.length > 0 || busy}
            style={{ display: 'flex', alignItems: 'center', gap: 8 }}
          >
            {busy ? (
              <><div className="spinner" style={{ width: 13, height: 13, borderWidth: 2 }} aria-hidden="true" />Importing…</>
            ) : (
              <><CheckCircle size={13} aria-hidden="true" />Import into database</>
            )}
          </button>

          {result && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
                Import result
              </div>
              <pre className="json">{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </Panel>
      )}

      {/* ── Import history ─────────────────────────────────────── */}
      <Panel title="Import history">
        {history.length === 0 ? (
          <div className="empty">No imports yet for this company.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Rows</th>
                  <th>Quality score</th>
                </tr>
              </thead>
              <tbody>
                {history.map(x => (
                  <tr key={x.upload_id}>
                    <td>
                      <strong>{x.original_filename}</strong>
                    </td>
                    <td>
                      <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: 'var(--accent-primary)', background: 'var(--accent-primary-dim)', border: '1px solid rgba(34,211,238,0.2)', borderRadius: 'var(--r-sm)', padding: '2px 7px' }}>
                        {x.dataset_type}
                      </span>
                    </td>
                    <td>
                      <span style={{
                        fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase',
                        color: x.status === 'imported' ? 'var(--status-healthy)' : x.status === 'failed' ? 'var(--status-critical)' : 'var(--status-watch)',
                        background: x.status === 'imported' ? 'var(--status-healthy-bg)' : x.status === 'failed' ? 'var(--status-critical-bg)' : 'var(--status-watch-bg)',
                        border: `1px solid ${x.status === 'imported' ? 'var(--status-healthy-border)' : x.status === 'failed' ? 'var(--status-critical-border)' : 'var(--status-watch-border)'}`,
                        borderRadius: 'var(--r-sm)', padding: '2px 7px',
                      }}>
                        {x.status}
                      </span>
                    </td>
                    <td style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)', fontWeight: 600 }}>
                      {x.row_count ?? <span style={{ color: 'var(--text-muted)' }}>—</span>}
                    </td>
                    <td>
                      {x.data_quality_score != null ? (
                        <span style={{
                          fontVariantNumeric: 'tabular-nums',
                          fontWeight: 700,
                          color: x.data_quality_score >= 80 ? 'var(--status-healthy)'
                               : x.data_quality_score >= 60 ? 'var(--status-watch)'
                               : 'var(--status-critical)',
                        }}>
                          {x.data_quality_score}/100
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}
