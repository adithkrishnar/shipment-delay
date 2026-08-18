import { getDashboard, getForecast, getShipments, getInventory, getSuppliers, getAnomalies, getModels } from './services/api';

async function testAll() {
  const apis = [
    ['dashboard', getDashboard],
    ['forecast', id => getForecast(id, 30)],
    ['shipments', getShipments],
    ['inventory', getInventory],
    ['suppliers', getSuppliers],
    ['anomalies', getAnomalies],
    ['models', getModels]
  ];
  
  for (const [name, fn] of apis) {
    try {
      await fn(1);
      console.log(`${name}: SUCCESS`);
    } catch (e) {
      console.log(`${name}: ERROR - ${e.message} - ${e.response?.data?.detail}`);
    }
  }
}

testAll();
