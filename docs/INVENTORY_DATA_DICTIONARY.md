# SupplyIQ Inventory Intelligence — Data Dictionary

## 1. Domain Entities & Database Schema

### 1.1 Products (`products`)
Stores the canonical catalog of items managed across company distribution nodes.
- `id` (INTEGER, Primary Key): Internal unique surrogate key.
- `company_id` (INTEGER, Foreign Key -> `companies.id`, Indexed): Multi-tenant ownership identifier.
- `external_product_id` (VARCHAR(120), Indexed): SKU or identifier from company ERP/WMS.
- `name` (VARCHAR(255)): Human-readable product name.
- `category` (VARCHAR(120), Nullable): Product segment or taxonomy (e.g. "Semiconductors", "Brakes").
- `unit_cost` (FLOAT, Nullable): Procurement or manufacturing unit cost (used for valuation & Value-at-Risk).
- `unit_price` (FLOAT, Nullable): Sales list price (used for potential revenue loss estimation).

### 1.2 Inventory Records (`inventory_records`)
Point-in-time stock snapshots per product and warehouse.
- `id` (INTEGER, Primary Key): Internal surrogate key.
- `company_id` (INTEGER, Foreign Key -> `companies.id`, Indexed): Multi-tenant ownership identifier.
- `product_id` (INTEGER, Foreign Key -> `products.id`, Indexed): Reference to parent product.
- `warehouse_id` (INTEGER, Foreign Key -> `warehouses.id`, Nullable, Indexed): Location of inventory.
- `date` (DATE, Indexed): Snapshot calendar date.
- `inventory_level` (FLOAT): Actual physical or recorded units on hand.
- `safety_stock` (FLOAT, Nullable): Target minimum safety buffer level.

### 1.3 Warehouses (`warehouses`)
Distribution centers, fulfillment centers, or storage depots.
- `id` (INTEGER, Primary Key): Internal surrogate key.
- `company_id` (INTEGER, Foreign Key -> `companies.id`, Indexed): Multi-tenant ownership identifier.
- `name` (VARCHAR(255)): Facility name (e.g., "Central DC", "Atlanta Hub").
- `region` (VARCHAR(120), Nullable): Geographic territory or metropolitan zone.

### 1.4 Sales Transactions (`sales`)
Historical consumption and sales records used to compute demand distributions.
- `id` (INTEGER, Primary Key): Internal surrogate key.
- `company_id` (INTEGER, Foreign Key -> `companies.id`, Indexed): Multi-tenant ownership identifier.
- `product_id` (INTEGER, Foreign Key -> `products.id`, Indexed): Reference to parent product.
- `date` (DATE, Indexed): Transaction date.
- `quantity` (FLOAT): Units demanded / sold. Days with zero sales are modeled as 0.0 upon reindexing.
- `promotion` (INTEGER, Nullable): Binary indicator (0/1) for marketing promotional discount periods.

### 1.5 Inbound Shipments / Purchase Orders (`shipments`)
Inbound replenishment shipments from suppliers to company warehouses.
- `id` (INTEGER, Primary Key): Internal surrogate key.
- `company_id` (INTEGER, Foreign Key -> `companies.id`, Indexed): Multi-tenant ownership identifier.
- `product_id` (INTEGER, Foreign Key -> `products.id`, Indexed): Product being replenished.
- `supplier_id` (INTEGER, Foreign Key -> `suppliers.id`, Nullable): Source vendor.
- `external_shipment_id` (VARCHAR(120), Nullable): PO or ASN tracking number.
- `quantity` (FLOAT): Inbound units ordered.
- `planned_delivery` (DATE, Nullable): Scheduled baseline arrival date.
- `actual_delivery` (DATE, Nullable): Historical received date. NULL indicates open in-transit PO.
- `transport_mode` (VARCHAR(60)): Transport mode ("Air", "Road", "Sea", "Rail").

---

## 2. Ingestion & Column Mapping Aliases

| Standard Field | Canonical Target | Recognized Input Synonyms / Deterministic Aliases |
|---|---|---|
| Product SKU | `product_id` | `sku`, `sku_id`, `product_code`, `product_id`, `item_id`, `item_no`, `part_number` |
| Stock Quantity | `inventory_level` | `current_stock`, `stock`, `stock_level`, `on_hand`, `qty_on_hand`, `physical_stock` |
| Transaction Date | `date` | `date`, `order_date`, `transaction_date`, `saledate`, `snapshot_date`, `last_updated` |
| Sales Quantity | `quantity` | `quantity`, `qty_sold`, `units_sold`, `demand_units`, `order_qty`, `shipped_qty` |
| Warehouse | `warehouse` | `warehouse`, `warehouse_name`, `dc`, `location`, `distribution_center`, `facility` |
| Unit Cost | `unit_cost` | `cost`, `unit_cost`, `purchase_price`, `procurement_cost`, `cogs_unit` |
| Lead Time | `lead_time` | `lead_time`, `lead_time_days`, `delivery_days`, `vendor_lead_time`, `transit_days` |
| Expected Receipt | `planned_delivery` | `expected_delivery`, `planned_delivery`, `eta`, `due_date`, `delivery_date` |
| PO Identifier | `shipment_id` | `po_number`, `order_id`, `purchase_order_id`, `shipment_id`, `tracking_no` |

---

## 3. Data Validation Rules & Quality Scoring
1. **Product Identifier**: Required, non-empty, stripped alphanumeric string.
2. **Quantities**: Must be non-negative numeric floats ($\ge 0.0$). Negative values trigger validation failure.
3. **Dates**: ISO-8601 (`YYYY-MM-DD`) or standard RFC dates. Chronological consistency enforced ($T_{\text{receipt}} \ge T_{\text{order}}$).
4. **Costs**: Must be positive floats ($> 0.0$) when provided. If missing, treated as `None` rather than fabricated zeros.
