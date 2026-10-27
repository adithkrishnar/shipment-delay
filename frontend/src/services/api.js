import axios from 'axios'
const api=axios.create({baseURL:import.meta.env.VITE_API_URL||'http://127.0.0.1:8000/api',timeout:120000})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const login = (username, password) => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  return api.post('/v1/auth/login', formData).then(r => r.data);
};

export const getMe = () => api.get('/v1/auth/me').then(r => r.data);
export const register = (email, password, company_name) => api.post('/v1/auth/register', { email, password, company_name }).then(r => r.data);
export const getCompanies=()=>api.get('/companies').then(r=>r.data)
export const seedDemo=()=>api.post('/demo/seed').then(r=>r.data)
export const seedDemoMine=()=>api.post('/demo/seed_mine').then(r=>r.data)
export const getDashboard=id=>api.get(`/dashboard/${id}`).then(r=>r.data)
export const explainDashboard=id=>api.get(`/dashboard/${id}/explain`).then(r=>r.data)
export const getInventory=id=>api.get(`/intelligence/${id}/inventory`).then(r=>r.data)
export const getSuppliers=id=>api.get(`/intelligence/${id}/suppliers`).then(r=>r.data)
export const getAnomalies=id=>api.get(`/intelligence/${id}/anomalies`).then(r=>r.data)
export const getShipments=id=>api.get(`/shipments/${id}?limit=100`).then(r=>r.data)
export const getShipmentImpact=(companyId, shipmentId)=>api.get(`/intelligence/${companyId}/shipments/${shipmentId}/impact`).then(r=>r.data)
export const getForecast=(id,horizon=30,productId=null)=>api.get(`/demand/forecast/${id}`,{params:{horizon,...(productId?{product_id:productId}:{})}}).then(r=>r.data)
export const getRecommendations=id=>api.get(`/recommendations/${id}`).then(r=>r.data)
export const getModels=id=>api.get(`/models/${id}`).then(r=>r.data)
export const retrain=id=>api.post(`/models/retrain/${id}`).then(r=>r.data)
export const retrainModel=id=>api.post(`/models/retrain/${id}`).then(r=>r.data)
export const trainBaseModels=()=>api.post('/models/train/base').then(r=>r.data)
export const getJob=jobId=>api.get(`/models/jobs/${jobId}`).then(r=>r.data)
export const getCompanyJobs=id=>api.get(`/models/${id}/jobs`).then(r=>r.data)
export const simulate=payload=>api.post('/simulator',payload).then(r=>r.data)
export const getWeather=port=>api.get(`/live/weather?port=${encodeURIComponent(port)}`).then(r=>r.data)
export const getNews=q=>api.get(`/live/news?query=${encodeURIComponent(q)}`).then(r=>r.data)
export const uploadDataset=(companyId,datasetType,file)=>{const f=new FormData();f.append('company_id',companyId);f.append('dataset_type',datasetType);f.append('file',file);return api.post('/upload',f).then(r=>r.data)}
export const validateUpload=(uploadId,mapping)=>api.post('/data/validate',{upload_id:uploadId,column_mapping:mapping}).then(r=>r.data)
export const mapUpload=(uploadId,mapping)=>api.post('/data/map',{upload_id:uploadId,column_mapping:mapping}).then(r=>r.data)
export const importUpload=(companyId,uploadId)=>api.post(`/data/import?company_id=${companyId}&upload_id=${uploadId}`).then(r=>r.data)
export const getUploads=id=>api.get(`/data/uploads/${id}`).then(r=>r.data)
export const getCapabilities=id=>api.get(`/data/uploads/${id}/capabilities`).then(r=>r.data)
export default api

export const getMultiLegShipment = (companyId, shipmentId, scenario) => api.get(`/shipments/${companyId}/multi-leg/${shipmentId}?scenario=${scenario}`).then(r => r.data);

// ── Inventory Intelligence & Optimization API Endpoints ──────────
export const getInventoryOverview = (companyId) => api.get(`/inventory/overview/${companyId}`).then(r => r.data);
export const getInventoryExplorer = (companyId, params = {}) => api.get(`/inventory/explorer/${companyId}`, { params }).then(r => r.data);
export const getProductInventoryDetail = (companyId, productId) => api.get(`/inventory/product/${companyId}/${productId}`).then(r => r.data);
export const getAbcXyzInsights = (companyId) => api.get(`/inventory/insights/abc-xyz/${companyId}`).then(r => r.data);
export const getAgingInsights = (companyId) => api.get(`/inventory/insights/aging/${companyId}`).then(r => r.data);
export const getWarehousesAnalytics = (companyId) => api.get(`/inventory/warehouses/${companyId}`).then(r => r.data);
export const getReplenishmentPlan = (companyId, serviceLevel = 0.95, horizonDays = 30) => api.get(`/inventory/replenishment/${companyId}`, { params: { service_level: serviceLevel, horizon_days: horizonDays } }).then(r => r.data);
export const getWarehouseTransfers = (companyId) => api.get(`/inventory/transfers/${companyId}`).then(r => r.data);
export const simulateDelay = (payload) => api.post('/inventory/simulate/delay', payload).then(r => r.data);
export const simulateWhatIf = (payload) => api.post('/inventory/simulate/what-if', payload).then(r => r.data);

// ── Action Center Approvals & Real Warehouse Transfers ────────────
export const approveAction = (companyId, payload) =>
  api.post(`/recommendations/${companyId}/approve`, payload).then(r => r.data);
export const getActionApprovals = (companyId) =>
  api.get(`/recommendations/${companyId}/approvals`).then(r => r.data);

export const executeWarehouseTransfer = (payload) =>
  api.post('/inventory/transfers/execute', payload).then(r => r.data);
export const getWarehouseTransferHistory = (companyId) =>
  api.get(`/inventory/transfers/history/${companyId}`).then(r => r.data);

// ── Persistent What-If Scenarios ──────────────────────────────────
export const saveScenario = (payload) =>
  api.post('/inventory/scenarios', payload).then(r => r.data);
export const getSavedScenarios = (companyId) =>
  api.get(`/inventory/scenarios/${companyId}`).then(r => r.data);
export const deleteSavedScenario = (companyId, scenarioId) =>
  api.delete(`/inventory/scenarios/${companyId}/${scenarioId}`).then(r => r.data);

