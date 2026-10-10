import React, { useState, useEffect } from 'react';
import { uploadDataset as uploadCsv, getUploads, mapUpload, importUpload, seedDemoMine } from '../services/api';
import { UploadCloud, CheckCircle } from 'lucide-react';

export default function Data({ company, onCompanyChange }) {
  const [invFile, setInvFile] = useState(null);
  const [shipFile, setShipFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [uploads, setUploads] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importSuccess, setImportSuccess] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);

  const handleLoadDemoData = async () => {
    setLoadingDemo(true);
    setError(null);
    try {
      await seedDemoMine();
      setImportSuccess(true);
      // Reload uploads state to clear the demo data prompt if necessary
      const u = await getUploads(company.id);
      setUploads(u);
    } catch (e) {
      let msg = e.message;
      if (e.response?.data?.detail) {
         msg = typeof e.response.data.detail === 'string' ? e.response.data.detail : JSON.stringify(e.response.data.detail);
      }
      setError(msg);
    } finally {
      setLoadingDemo(false);
    }
  };

  useEffect(() => {
    if (company) {
      getUploads(company.id).then(setUploads).catch(console.error);
    }
  }, [company]);

  const handleUpload = (type) => {
    const activeFile = type === 'inventory' ? invFile : shipFile;
    if (!activeFile) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setImportSuccess(false);
    uploadCsv(company.id, type, activeFile)
      .then(r => {
         setResult(r);
         if (r.company_id && r.company_id !== company.id) {
           onCompanyChange(r.company_id);
         }
      })
      .catch(e => {
        let msg = e.message;
        if (e.response?.data?.detail) {
           msg = typeof e.response.data.detail === 'string' ? e.response.data.detail : JSON.stringify(e.response.data.detail);
        }
        setError(msg);
      })
      .finally(() => setLoading(false));
  };

  const handleImport = async () => {
    if (!result) return;
    setImporting(true);
    setError(null);
    try {
      await mapUpload(result.upload_id, result.suggested_mapping);
      await importUpload(company.id, result.upload_id);
      setImportSuccess(true);
      const u = await getUploads(company.id);
      setUploads(u);
    } catch (e) {
      let msg = e.message;
      if (e.response?.data?.detail) {
         msg = typeof e.response.data.detail === 'string' ? e.response.data.detail : JSON.stringify(e.response.data.detail);
      }
      setError(msg);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">DATA INPUT</h1>
        <p className="page-subtitle">Connect the data SupplyIQ needs to understand your supply chain.</p>
      </div>

      {uploads && (
        <div style={{ padding: '16px 24px', background: uploads.length > 0 ? 'var(--status-healthy-bg)' : 'var(--status-watch-bg)', border: `1px solid ${uploads.length > 0 ? 'var(--status-healthy-border)' : 'var(--status-watch-border)'}`, borderRadius: 'var(--r-md)', marginBottom: '32px' }}>
          <strong style={{ color: uploads.length > 0 ? 'var(--status-healthy)' : 'var(--status-watch)' }}>
            {uploads.length > 0 ? 'Company data imported' : 'Demo dataset available'}
          </strong>
          <p style={{ marginTop: '4px', color: 'var(--text-secondary)' }}>
            {uploads.length > 0 
              ? `${uploads.length} dataset(s) imported. Using your uploaded company data.` 
              : 'Preloaded demonstration data is available for exploration.'}
          </p>
          <button 
            className="btn-secondary" 
            style={{ marginTop: '16px', border: '1px solid currentColor', padding: '8px 16px', borderRadius: '4px', background: 'transparent', cursor: 'pointer' }} 
            onClick={handleLoadDemoData} 
            disabled={loadingDemo}
          >
            {loadingDemo ? 'Generating & Loading Large Demo Data...' : 'Load Large Demo Data (Company Specific Training)'}
          </button>
        </div>
      )}

      <div className="grid-2">
        <div className="upload-section">
          <div className="upload-header">
            <div className="upload-icon">📦</div>
            <div>
              <div className="upload-title">INVENTORY & DEMAND</div>
              <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '2px' }}>Products, stock levels, warehouses and historical demand.</div>
            </div>
          </div>
          <div className="upload-desc">
            Supports: inventory, products, sales, demand history, warehouse information, lead-time information.
          </div>
          
          <input type="file" id="inv-upload" style={{ display: 'none' }} onChange={e => setInvFile(e.target.files[0])} />
          <label htmlFor="inv-upload" className="upload-dropzone" style={{ display: 'block' }}>
             <UploadCloud size={32} style={{ color: 'var(--accent-primary)', marginBottom: '16px' }} />
             <div style={{ fontWeight: 500 }}>{invFile ? invFile.name : 'Click to upload CSV or Excel file'}</div>
             <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '8px' }}>XLSX, CSV up to 50MB</div>
          </label>
          {invFile && (
             <button className="btn-primary" style={{ width: '100%', marginTop: '16px' }} onClick={() => handleUpload('inventory')} disabled={loading}>
                {loading ? 'Uploading...' : 'Process Inventory Data'}
             </button>
          )}
        </div>

        <div className="upload-section">
          <div className="upload-header">
            <div className="upload-icon">🚚</div>
            <div>
              <div className="upload-title">SHIPMENTS & LOGISTICS</div>
              <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '2px' }}>Shipment movements, routes, suppliers and transportation.</div>
            </div>
          </div>
          <div className="upload-desc">
            Supports: shipment records, origin/destination, supplier, transport mode, scheduled/actual delivery, route information.
          </div>
          
          <input type="file" id="log-upload" style={{ display: 'none' }} onChange={e => setShipFile(e.target.files[0])} />
          <label htmlFor="log-upload" className="upload-dropzone" style={{ display: 'block' }}>
             <UploadCloud size={32} style={{ color: 'var(--accent-primary)', marginBottom: '16px' }} />
             <div style={{ fontWeight: 500 }}>{shipFile ? shipFile.name : 'Click to upload CSV or Excel file'}</div>
             <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '8px' }}>XLSX, CSV up to 50MB</div>
          </label>
          {shipFile && (
             <button className="btn-primary" style={{ width: '100%', marginTop: '16px' }} onClick={() => handleUpload('shipments')} disabled={loading}>
                {loading ? 'Uploading...' : 'Process Logistics Data'}
             </button>
          )}
        </div>
      </div>

      {error && <div style={{ color: 'var(--status-critical)', padding: '16px', background: 'var(--status-critical-bg)', borderRadius: 'var(--r-md)', marginTop: '24px' }}>{error}</div>}

      {result && (
        <div style={{ marginTop: '24px', padding: '32px', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', background: 'var(--bg-surface-1)' }}>
          <div className="flex-row" style={{ marginBottom: '24px', color: 'var(--status-healthy)' }}>
            <CheckCircle size={24} />
            <h2 style={{ fontSize: '18px', fontWeight: 600 }}>File processed successfully</h2>
          </div>
          
          <div className="grid-3" style={{ marginBottom: '32px' }}>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Rows Processed</div>
              <div style={{ fontSize: '20px', fontWeight: 600 }}>{result.row_count}</div>
            </div>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Columns</div>
              <div style={{ fontSize: '20px', fontWeight: 600 }}>{result.columns?.length || 0}</div>
            </div>
          </div>

          <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '16px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px' }}>Match your columns</h3>
          
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {Object.entries(result.suggested_mapping || {}).map(([raw, standard]) => (
              <div className="mapping-row" key={raw}>
                <div className="mapping-source">{raw}</div>
                <div className="mapping-arrow">→</div>
                <div className="mapping-target matched">
                  <CheckCircle size={14} /> {standard}
                </div>
              </div>
            ))}
          </div>

          {importSuccess ? (
             <div style={{ marginTop: '24px', padding: '16px', background: 'var(--status-healthy-bg)', border: '1px solid var(--status-healthy-border)', borderRadius: 'var(--r-md)', color: 'var(--status-healthy)', fontWeight: 500 }}>
                Data successfully imported and model training triggered!
             </div>
          ) : (
             <button className="btn-primary" style={{ marginTop: '24px', width: '100%' }} onClick={handleImport} disabled={importing}>
                {importing ? 'Importing Data & Training Model...' : 'Confirm Mapping & Import Data'}
             </button>
          )}
        </div>
      )}
    </div>
  );
}
