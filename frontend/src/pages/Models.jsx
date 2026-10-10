import React, { useEffect, useState } from 'react';
import { getModels } from '../services/api';
import Loader from '../components/Loader';

export default function Models({ company }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (company) {
      getModels(company.id).then(setData).catch(e => setError(e.message));
    }
  }, [company]);

  if (error) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load this data.</p>
      <button className="btn-secondary" onClick={() => { setError(null); getModels(company.id).then(setData).catch(e => setError(e.message)); }}>Retry</button>
    </div>
  );
  if (!data) return <Loader />;

  const modelsArray = Array.isArray(data) ? data : (data.models || []);
  const shipmentModel = modelsArray.find(m => m.model_type === 'delay_classifier');

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">ML Models</h1>
        <p className="page-subtitle">Technical configuration and training details.</p>
      </div>

      {shipmentModel ? (
        <div className="panel" style={{ padding: '32px' }}>
           <div className="flex-between" style={{ marginBottom: '24px' }}>
             <h2 style={{ fontSize: '18px', fontWeight: 600 }}>Shipment Delay Classifier</h2>
             <span className="badge badge-info">TRAINED MODEL</span>
           </div>
           
           <div className="grid-2">
               <div>
                 <h3 style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px' }}>Architecture</h3>
                 <div style={{ marginBottom: '16px' }}><strong>Algorithm:</strong> {shipmentModel.metrics?.model_name || 'N/A'}</div>
                 <div style={{ marginBottom: '16px' }}><strong>Model Source:</strong> {shipmentModel.model_source || 'N/A'}</div>
                 <div style={{ marginBottom: '16px' }}><strong>Training Records:</strong> {shipmentModel.dataset_size ? shipmentModel.dataset_size.toLocaleString() : 'N/A'}</div>
                 <div><strong>Features:</strong> {shipmentModel.metrics?.features || 'N/A'}</div>
              </div>
              <div>
                 <h3 style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px' }}>Performance</h3>
                 <div style={{ marginBottom: '16px' }}><strong>Test Accuracy:</strong> {shipmentModel.metrics?.accuracy ? `${(shipmentModel.metrics.accuracy * 100).toFixed(2)}%` : 'N/A'}</div>
                 <div style={{ marginBottom: '16px' }}><strong>Test Precision:</strong> {shipmentModel.metrics?.precision ? `${(shipmentModel.metrics.precision * 100).toFixed(2)}%` : 'N/A'}</div>
                 <div style={{ marginBottom: '16px' }}><strong>Test Recall:</strong> {shipmentModel.metrics?.recall ? `${(shipmentModel.metrics.recall * 100).toFixed(2)}%` : 'N/A'}</div>
                 <div style={{ marginBottom: '16px' }}><strong>Test F1:</strong> {shipmentModel.metrics?.f1 ? `${(shipmentModel.metrics.f1 * 100).toFixed(2)}%` : 'N/A'}</div>
                 <div style={{ marginBottom: '16px' }}><strong>Test ROC-AUC:</strong> {shipmentModel.metrics?.roc_auc ? shipmentModel.metrics.roc_auc.toFixed(4) : 'N/A'}</div>
                 <div style={{ marginBottom: '16px' }}><strong>Test PR-AUC:</strong> {shipmentModel.metrics?.pr_auc ? shipmentModel.metrics.pr_auc.toFixed(4) : 'N/A'}</div>
                 <div><strong>Status:</strong> <span style={{ color: 'var(--status-healthy)', fontWeight: 500 }}>{shipmentModel.status?.toUpperCase() || 'ACTIVE'}</span></div>
              </div>
           </div>
        </div>
      ) : (
        <div className="panel" style={{ textAlign: 'center', padding: '64px 24px', color: 'var(--text-secondary)' }}>
          No company-specific model has been registered.
        </div>
      )}
    </div>
  );
}
