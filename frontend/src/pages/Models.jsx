import { useEffect, useState, useRef } from 'react';
import { getModels, retrain, getJob } from '../services/api';
import Panel from '../components/Panel';
import Loader from '../components/Loader';

export default function Models({ company }) {
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState('');
  const [activeJobs, setActiveJobs] = useState([]);
  
  // Ref to keep track of intervals so we can clear them on unmount
  const pollIntervals = useRef({});

  const load = () => {
    if (company) {
      getModels(company.id).then(setD);
    }
  };

  useEffect(() => {
    load();
    return () => {
      // Cleanup any active polling on unmount
      Object.values(pollIntervals.current).forEach(clearInterval);
    };
  }, [company]);

  const handleRetrain = async () => {
    setMsg('Queuing background training jobs...');
    try {
      const response = await retrain(company.id);
      if (response.jobs && response.jobs.length > 0) {
        setMsg('Training started in background.');
        const jobIds = response.jobs.map(j => j.job_id);
        setActiveJobs(prev => [...prev, ...jobIds]);
        
        jobIds.forEach(jobId => {
          pollJob(jobId);
        });
      }
    } catch (e) {
      setMsg(e.response?.data?.detail || e.message);
    }
  };
  
  const pollJob = (jobId) => {
    if (pollIntervals.current[jobId]) return;
    
    pollIntervals.current[jobId] = setInterval(async () => {
      try {
        const jobInfo = await getJob(jobId);
        if (jobInfo.status === 'completed' || jobInfo.status === 'failed') {
          clearInterval(pollIntervals.current[jobId]);
          delete pollIntervals.current[jobId];
          
          setActiveJobs(prev => prev.filter(id => id !== jobId));
          
          if (jobInfo.status === 'completed') {
             setMsg(`Job ${jobId.substring(0,6)} completed! Metrics updated.`);
             load();
          } else {
             setMsg(`Job ${jobId.substring(0,6)} failed: ${jobInfo.error}`);
          }
        } else {
           setMsg(`Job ${jobId.substring(0,6)} is ${jobInfo.status}...`);
        }
      } catch (err) {
        console.error("Polling error", err);
      }
    }, 2500);
  };

  if (!d) return <Loader />;

  return (
    <div className="page">
      <div className="page-title">
        <span className="eyebrow">MODEL CENTER</span>
        <h2>Track training, versions and real test metrics.</h2>
      </div>
      
      <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <button 
           className="primary" 
           onClick={handleRetrain}
           disabled={activeJobs.length > 0}
        >
          {activeJobs.length > 0 ? `Training (${activeJobs.length} active)...` : 'Retrain company models'}
        </button>
      </div>
      
      {msg && <p className="callout">{msg}</p>}
      
      <Panel title="Model registry">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Source</th>
                <th>Version</th>
                <th>Rows</th>
                <th>Metrics</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {d.map(m => (
                <tr key={m.id}>
                  <td>{m.model_type}</td>
                  <td>{m.model_source}</td>
                  <td>{m.version}</td>
                  <td>{m.dataset_size || '—'}</td>
                  <td><small>{JSON.stringify(m.metrics || {}).slice(0, 150)}</small></td>
                  <td>
                     {m.status === 'active' ? (
                        <span style={{ color: 'green', fontWeight: 'bold' }}>{m.status}</span>
                     ) : m.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
