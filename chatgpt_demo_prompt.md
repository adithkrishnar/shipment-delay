# ChatGPT Prompt for Generating SupplyIQ Demo Data

Copy and paste the following prompt into ChatGPT to generate a realistic, unified supply chain dataset that works perfectly with SupplyIQ.

***

**PROMPT:**

You are an expert data engineer. Please generate a realistic, single-table supply chain dataset in CSV format (which I can save as an Excel sheet). I need exactly 100 rows of data representing the last 60 days of operations for a fictional electronics manufacturer called "ElectroTech".

The data MUST be a single unified table containing all of the following columns exactly as named:
- `Order ID` (e.g., ORD-1001)
- `Order Date` (YYYY-MM-DD, spanning the last 60 days)
- `Product Name` (Use 5 specific products: "Quantum Laptop", "Neon Smartphone", "Aero Headphones", "Titan Tablet", "Nova Smartwatch")
- `Category` (e.g., Electronics)
- `Quantity Sold` (integer between 10 and 500)
- `Inventory Level` (integer, representing current stock at the time of the order. Make some low to trigger stockout risks)
- `Supplier Name` (Use 3 specific suppliers: "Alpha Circuits", "Omega Assembly", "Global Tech Parts")
- `Origin` (e.g., "Shenzhen, CN", "Taipei, TW", "Seoul, KR")
- `Destination` (e.g., "Los Angeles, US", "Rotterdam, NL")
- `Planned Delivery Date` (YYYY-MM-DD, typically 10-30 days after Order Date)
- `Actual Delivery Date` (YYYY-MM-DD. Leave about 15 rows BLANK to simulate active shipments. For the others, make about 20% of them later than the Planned Delivery Date to simulate delays)
- `Shipping Mode` (Air, Sea, or Rail)
- `Unit Cost` (integer between 50 and 800 depending on product)
- `Promotion` (0 or 1, simulating whether a discount was active)

**Rules for realism:**
1. **Demand Spikes:** For "Quantum Laptop", make the `Quantity Sold` spike unusually high (e.g., 800) when `Promotion` is 1 to simulate an anomaly.
2. **Supplier Delays:** Make "Omega Assembly" have a higher frequency of late `Actual Delivery Date`s (delayed by 3-8 days).
3. **Stockout Risks:** For rows with late deliveries, make the `Inventory Level` critically low (e.g., 5-20 units) to simulate impending stockouts.

Please output ONLY the raw CSV text so I can easily copy and paste it into a file. Do not include markdown formatting around the CSV if possible.
