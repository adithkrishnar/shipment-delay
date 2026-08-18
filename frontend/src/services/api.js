import axios from 'axios'
const api=axios.create({baseURL:import.meta.env.VITE_API_URL||'http://127.0.0.1:8000/api',timeout:20000})

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

export const getCompanies=()=>api.get('/companies').then(r=>r.data)
export const seedDemo=()=>api.post('/demo/seed').then(r=>r.data)
export const getDashboard=id=>api.get(`/dashboard/${id}`).then(r=>r.data)
export const getInventory=id=>api.get(`/intelligence/${id}/inventory`).then(r=>r.data)
export const getSuppliers=id=>api.get(`/intelligence/${id}/suppliers`).then(r=>r.data)
export const getAnomalies=id=>api.get(`/intelligence/${id}/anomalies`).then(r=>r.data)
export const getShipments=id=>api.get(`/shipments/${id}?limit=100`).then(r=>r.data)
export const getForecast=(id,horizon=30)=>api.get(`/demand/forecast/${id}?horizon=${horizon}`).then(r=>r.data)
export const getRecommendations=id=>api.get(`/recommendations/${id}`).then(r=>r.data)
export const getModels=id=>api.get(`/models/${id}`).then(r=>r.data)
export const retrain=id=>api.post(`/models/retrain/${id}`).then(r=>r.data)
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
export default api
