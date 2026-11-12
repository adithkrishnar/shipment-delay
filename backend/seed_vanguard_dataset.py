"""
Large realistic company and transporter dataset generator for SupplyIQ.
Creates a new high-scale enterprise company:
- Company: 'Vanguard Aerospace & Robotics'
- Industry: 'Aerospace & Advanced Defense Systems'
- User (Company Admin): admin@vanguard-aero.com / vanguard123
- Transporter Organization: 'Pacific Intermodal Freightways'
- User (Transporter Admin): ops@pacificintermodal.com / pacific123
- Multi-hub Warehouses & Global Tier-1 Suppliers
- Extensive Products Catalog across avionics, titanium composites, optical LiDAR, robotics actuators
- 150+ realistic multi-modal shipments (ROAD, AIR, SEA, RAIL) with realistic legs, durations, dwell buffers
- Delays, disruption logs, inventory records, and daily sales
"""

import sys
import os
import random
from datetime import datetime, date, timedelta

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import SessionLocal
from app.models import (
    Company,
    User,
    Warehouse,
    Supplier,
    Product,
    Shipment,
    Sale,
    InventoryRecord,
)
from app.models.transporter_org import TransporterOrganization
from app.models.shipment_leg import ShipmentLeg, DisruptionReport
from app.models.shipment_delay import ShipmentDelay
from app.auth.security import get_password_hash
from app.services.collaborative_disruption_service import ensure_shipment_legs

def seed_large_company():
    db = SessionLocal()
    try:
        print("[*] Starting high-fidelity realistic company & transporter dataset generation...")

        # 1. Check or Create Company
        company_name = "Vanguard Aerospace & Robotics"
        existing_company = db.query(Company).filter(Company.name == company_name).first()
        if existing_company:
            print(f"[!] Company '{company_name}' already exists (ID: {existing_company.id}). Reusing company...")
            company = existing_company
        else:
            company = Company(
                name=company_name,
                industry="Aerospace & Advanced Robotics",
                is_demo=0,
                default_currency="USD",
                notes="Global manufacturer of avionics, aerospace composite structures, and precision autonomous navigation systems."
            )
            db.add(company)
            db.commit()
            db.refresh(company)
            print(f"[+] Created Company: {company.name} (ID: {company.id})")

        # 2. Check or Create Transporter Organization
        carrier_org_name = "Pacific Intermodal Freightways"
        carrier_code = "PAC-INTERMODAL"
        existing_org = db.query(TransporterOrganization).filter(TransporterOrganization.name == carrier_org_name).first()
        if existing_org:
            carrier_org = existing_org
            print(f"[!] Transporter Org '{carrier_org_name}' already exists (ID: {carrier_org.id}). Reusing...")
        else:
            carrier_org = TransporterOrganization(
                name=carrier_org_name,
                code=carrier_code,
                contact_email="ops@pacificintermodal.com",
                contact_phone="+1-800-722-4344",
                is_active=True
            )
            db.add(carrier_org)
            db.commit()
            db.refresh(carrier_org)
            print(f"[+] Created Transporter Org: {carrier_org.name} (ID: {carrier_org.id})")

        # 3. Create Users
        # Company Admin: admin@vanguard-aero.com / vanguard123
        company_admin_email = "admin@vanguard-aero.com"
        comp_user = db.query(User).filter(User.email == company_admin_email).first()
        if not comp_user:
            comp_user = User(
                email=company_admin_email,
                hashed_password=get_password_hash("vanguard123"),
                is_active=True,
                is_superuser=False,
                role="company",
                company_id=company.id
            )
            db.add(comp_user)
            print(f"[+] Created Company User: {company_admin_email}")
        else:
            comp_user.hashed_password = get_password_hash("vanguard123")
            comp_user.company_id = company.id
            comp_user.role = "company"

        # Transporter User: ops@pacificintermodal.com / pacific123
        transporter_email = "ops@pacificintermodal.com"
        trans_user = db.query(User).filter(User.email == transporter_email).first()
        if not trans_user:
            trans_user = User(
                email=transporter_email,
                hashed_password=get_password_hash("pacific123"),
                is_active=True,
                is_superuser=False,
                role="transporter",
                carrier_name=carrier_org_name,
                transporter_org_id=carrier_org.id,
                company_id=company.id
            )
            db.add(trans_user)
            print(f"[+] Created Transporter User: {transporter_email}")
        else:
            trans_user.hashed_password = get_password_hash("pacific123")
            trans_user.role = "transporter"
            trans_user.carrier_name = carrier_org_name
            trans_user.transporter_org_id = carrier_org.id
            trans_user.company_id = company.id

        db.commit()

        # 4. Create Regional Fulfillment Centers / Warehouses
        warehouse_data = [
            ("Seattle Assembly Plant DC-1", "Northwest USA"),
            ("Long Beach Maritime Terminal WH-2", "West Coast USA"),
            ("Tokyo Haneda High-Tech Air Hub", "East Asia"),
            ("Rotterdam Europort Gateway", "Western Europe"),
            ("Singapore Changi Intermodal Depot", "Southeast Asia"),
            ("Dallas Fort-Worth Central Logistics Hub", "Central USA"),
        ]
        warehouses = []
        for name, region in warehouse_data:
            wh = db.query(Warehouse).filter(Warehouse.company_id == company.id, Warehouse.name == name).first()
            if not wh:
                wh = Warehouse(company_id=company.id, name=name, region=region)
                db.add(wh)
                db.flush()
            warehouses.append(wh)
        db.commit()
        print(f"[+] Configured {len(warehouses)} Global Warehouses.")

        # 5. Create Tier-1 Specialized Suppliers
        supplier_data = [
            ("SUP-VA-01", "Kyoto Precision Semiconductor Ltd", 14.0, 0.96, 1.25, 0.008),
            ("SUP-VA-02", "Titanium Aerospace Forgings GmbH", 28.0, 0.88, 1.45, 0.015),
            ("SUP-VA-03", "Silicon Valley Micro-Photonics", 7.0, 0.94, 1.10, 0.010),
            ("SUP-VA-04", "Singapore Advanced Composites Corp", 21.0, 0.91, 1.05, 0.012),
            ("SUP-VA-05", "Bavaria Guidance Systems AG", 18.0, 0.85, 1.35, 0.020),
            ("SUP-VA-06", "Seoul High-Torque Servos Inc", 12.0, 0.93, 1.15, 0.014),
            ("SUP-VA-07", "Texas Avionics Fabrication", 10.0, 0.92, 1.00, 0.018),
        ]
        suppliers = []
        for ext_id, name, lt, rel, ci, df in supplier_data:
            sup = db.query(Supplier).filter(Supplier.company_id == company.id, Supplier.external_supplier_id == ext_id).first()
            if not sup:
                sup = Supplier(
                    company_id=company.id,
                    external_supplier_id=ext_id,
                    name=name,
                    lead_time_days=lt,
                    reliability=rel,
                    cost_index=ci,
                    defect_rate=df
                )
                db.add(sup)
                db.flush()
            suppliers.append(sup)
        db.commit()
        print(f"[+] Configured {len(suppliers)} Specialized Suppliers.")

        # 6. Create Product Catalog
        product_data = [
            ("SKU-AV-1001", "Solid-State LiDAR Optical Transceiver", "Optoelectronics", 1850.0, 3200.0),
            ("SKU-AV-1002", "Titanium Alloy Structural Wing Rib", "Airframe Components", 4200.0, 7800.0),
            ("SKU-AV-1003", "Tri-Core Inertial Guidance Navigation Unit", "Avionics", 8900.0, 14500.0),
            ("SKU-AV-1004", "High-Voltage Drone Brushless Actuator", "Robotics Propulsion", 450.0, 890.0),
            ("SKU-AV-1005", "Carbon Fiber Cryogenic Fuel Liner", "Composites", 3100.0, 5600.0),
            ("SKU-AV-1006", "FPGA Radiation-Hardened Mission Controller", "Avionics", 6200.0, 11200.0),
            ("SKU-AV-1007", "Hydraulic Servo Flow Regulating Valve", "Pneumatics & Hydraulics", 780.0, 1420.0),
            ("SKU-AV-1008", "Multispectral Autonomous Target Tracker", "Optoelectronics", 5400.0, 9800.0),
            ("SKU-AV-1009", "Ceramic Thermal Barrier Tile Set", "Thermal Protection", 1250.0, 2400.0),
            ("SKU-AV-1010", "Ultra-Torque Planetary Harmonic Drive", "Robotics Propulsion", 980.0, 1850.0),
            ("SKU-AV-1011", "High-Gain Ka-Band Phased Array Antenna", "Telemetry & Comms", 3600.0, 6700.0),
            ("SKU-AV-1012", "Lithium-Sulfur High-Density Power Cell", "Energy Systems", 320.0, 650.0),
            ("SKU-AV-1013", "Beryllium Copper Gimbal Bearing Ring", "Precision Mechanical", 640.0, 1150.0),
            ("SKU-AV-1014", "Edge-Compute GPU Vision Processor Module", "Avionics", 2700.0, 4900.0),
            ("SKU-AV-1015", "Tungsten Kinetic Balance Counterweight", "Airframe Components", 520.0, 920.0),
        ]
        products = []
        for ext_id, name, cat, uc, up in product_data:
            prod = db.query(Product).filter(Product.company_id == company.id, Product.external_product_id == ext_id).first()
            if not prod:
                prod = Product(
                    company_id=company.id,
                    external_product_id=ext_id,
                    name=name,
                    category=cat,
                    unit_cost=uc,
                    unit_price=up
                )
                db.add(prod)
                db.flush()
            products.append(prod)
        db.commit()
        print(f"[+] Configured {len(products)} High-Tech Aerospace Products.")

        # 7. Generate Daily Sales Demand (Historical 60 days)
        today = date.today()
        start_date = today - timedelta(days=60)
        sales_to_insert = []
        for prod in products:
            base_demand = random.uniform(5.0, 25.0)
            cur = start_date
            while cur <= today:
                # Add weekly seasonality and occasional bumps
                dow = cur.weekday()
                mult = 1.2 if dow < 5 else 0.4
                promo = 1 if random.random() < 0.08 else 0
                qty = max(1.0, round(base_demand * mult * (1.5 if promo else 1.0) + random.gauss(0, 2.5), 1))
                sales_to_insert.append(Sale(
                    company_id=company.id,
                    product_id=prod.id,
                    date=cur,
                    quantity=qty,
                    region=random.choice(["Americas", "EMEA", "APAC"]),
                    price=prod.unit_price,
                    promotion=promo
                ))
                cur += timedelta(days=1)
        
        # Batch insert sales
        db.bulk_save_objects(sales_to_insert)
        db.commit()
        print(f"[+] Generated {len(sales_to_insert)} Daily Sales/Demand records.")

        # 8. Generate Inventory Records
        inv_to_insert = []
        for prod in products:
            for wh in warehouses:
                # Varied safety stock and current level
                safety = round(random.uniform(30.0, 80.0))
                # 25% of warehouse inventories at risk/low to trigger realistic control tower alerts
                risk_profile = random.random()
                if risk_profile < 0.2:
                    current_level = round(random.uniform(5.0, safety * 0.4)) # Low/Critical
                elif risk_profile < 0.4:
                    current_level = round(random.uniform(safety * 0.8, safety * 1.1)) # Borderline
                else:
                    current_level = round(random.uniform(safety * 1.5, safety * 3.5)) # Healthy
                
                inv_to_insert.append(InventoryRecord(
                    company_id=company.id,
                    product_id=prod.id,
                    warehouse_id=wh.id,
                    date=today,
                    inventory_level=current_level,
                    safety_stock=safety
                ))
        db.bulk_save_objects(inv_to_insert)
        db.commit()
        print(f"[+] Generated {len(inv_to_insert)} Warehouse Inventory Records.")

        # 9. Generate Large Varied Corpus of Shipments (120+ shipments)
        corridors = [
            ("Kyoto Logistics Hub, Japan", "Seattle Assembly Plant DC-1, USA", "SEA", 8500.0),
            ("Tokyo Haneda Air Facility, Japan", "Seattle Assembly Plant DC-1, USA", "AIR", 7800.0),
            ("Munich Industrial Park, Germany", "Dallas Fort-Worth Central Hub, USA", "AIR", 8300.0),
            ("Hamburg Port Freightway, Germany", "Long Beach Maritime Terminal, USA", "SEA", 12500.0),
            ("Singapore Jurong Logistics Park", "Long Beach Maritime Terminal, USA", "SEA", 14200.0),
            ("Changi Air Cargo Center, Singapore", "Seattle Assembly Plant DC-1, USA", "AIR", 12800.0),
            ("Incheon High-Tech Corridor, Korea", "Long Beach Maritime Terminal, USA", "SEA", 9600.0),
            ("Dallas Fort-Worth Central Hub, USA", "Seattle Assembly Plant DC-1, USA", "ROAD", 3450.0),
            ("Chicago Rail Transfer Terminal, USA", "Seattle Assembly Plant DC-1, USA", "RAIL", 3300.0),
            ("Long Beach Maritime Terminal, USA", "Dallas Fort-Worth Central Hub, USA", "RAIL", 2350.0),
            ("Austin Micro-Fab Complex, USA", "Seattle Assembly Plant DC-1, USA", "ROAD", 3600.0),
        ]

        assignment_statuses = ["IN_TRANSIT", "IN_TRANSIT", "ACCEPTED", "IN_TRANSIT", "PENDING", "DELIVERED"]
        delay_reasons = [
            "Traffic congestion",
            "Severe weather front",
            "Port congestion & container dwell",
            "Customs / export compliance verification",
            "Equipment / engine diagnostic check",
            "Missed intermodal rail connection window",
            "Dock appointment rescheduled"
        ]

        shipments = []
        now_dt = datetime.utcnow()

        print("[*] Generating 120 varied multimodal shipments across global corridors...")
        for i in range(1, 121):
            prod = random.choice(products)
            sup = random.choice(suppliers)
            corridor = random.choice(corridors)
            origin, dest, mode, dist = corridor

            order_days_ago = random.randint(3, 35)
            order_d = today - timedelta(days=order_days_ago)
            
            # Transit lead time based on mode and distance
            transit_days = max(2, int(dist / (700 if mode == "AIR" else (80 if mode == "RAIL" else (350 if mode == "ROAD" else 450)))))
            planned_d = order_d + timedelta(days=transit_days)
            
            # Status distribution
            if planned_d < today - timedelta(days=3):
                status = "DELIVERED"
                actual_d = planned_d + timedelta(days=random.choice([0, 0, 1, 2]))
            else:
                status = random.choice(["IN_TRANSIT", "IN_TRANSIT", "IN_TRANSIT", "ACCEPTED", "PENDING"])
                actual_d = None

            # Current ETA
            is_delayed = (random.random() < 0.38) and status != "DELIVERED"
            delay_hrs = random.choice([4.0, 8.0, 12.0, 18.0, 24.0, 48.0]) if is_delayed else 0.0
            cur_eta = planned_d + timedelta(days=int(delay_hrs // 24) + (1 if (delay_hrs % 24) > 0 else 0)) if is_delayed else planned_d

            ext_id = f"VAN-SHP-{10000 + i}"
            qty = random.randint(15, 300)
            weight = round(qty * random.uniform(2.5, 35.0), 1)

            shipment = Shipment(
                company_id=company.id,
                product_id=prod.id,
                supplier_id=sup.id,
                external_shipment_id=ext_id,
                origin=origin,
                destination=dest,
                carrier=carrier_org.name,
                transport_mode=mode.lower(),
                transporter_org_id=carrier_org.id,
                assignment_status=status,
                current_eta=cur_eta,
                distance_km=dist,
                weight_kg=weight,
                quantity=qty,
                order_date=order_d,
                planned_delivery=planned_d,
                actual_delivery=actual_d
            )
            db.add(shipment)
            db.flush()
            shipments.append((shipment, is_delayed, delay_hrs))

        db.commit()
        print(f"[+] Persisted {len(shipments)} Shipments.")

        # 10. Automatically provision multi-modal legs and inject realistic delays / disruptions
        disruptions_count = 0
        delays_count = 0

        for shipment, is_delayed, delay_hrs in shipments:
            # Generate legs via robust service
            legs = ensure_shipment_legs(db, shipment)
            
            if is_delayed and delay_hrs > 0 and len(legs) > 0:
                # Pick leg to disrupt
                affected_leg = legs[0] if len(legs) == 1 else (legs[1] if len(legs) >= 2 and random.random() < 0.65 else legs[0])
                affected_leg.delay_hours = delay_hrs
                affected_leg.status = "DELAYED"
                
                reason = random.choice(delay_reasons)
                
                # Create ShipmentDelay record
                prev_eta_dt = datetime.combine(shipment.planned_delivery, datetime.min.time())
                new_eta_dt = prev_eta_dt + timedelta(hours=delay_hrs)
                
                delay_record = ShipmentDelay(
                    shipment_id=shipment.id,
                    transporter_org_id=carrier_org.id,
                    reported_by_user_id=trans_user.id,
                    previous_eta=prev_eta_dt,
                    new_eta=new_eta_dt,
                    delay_hours=delay_hrs,
                    reason=reason,
                    notes=f"Active carrier incident reported on Leg #{affected_leg.sequence} ({affected_leg.mode}). {reason}. Rescheduling downstream intermodal link.",
                    created_at=now_dt - timedelta(hours=random.randint(1, 48))
                )
                db.add(delay_record)
                delays_count += 1

                # Also create DisruptionReport for multimodal cascade feed
                disruption = DisruptionReport(
                    leg_id=affected_leg.id,
                    shipment_id=shipment.id,
                    reporter_id=trans_user.id,
                    transporter_org_id=carrier_org.id,
                    incident_location=affected_leg.origin,
                    status="SUBMITTED",
                    delay_hours=delay_hrs,
                    disruption_reason=reason,
                    notes=f"Active carrier incident reported on Leg #{affected_leg.sequence} ({affected_leg.mode}). {reason}.",
                    total_impact_delay_days=round(delay_hrs / 24.0, 1),
                    stockout_predicted=1 if random.random() < 0.4 else 0,
                    unmet_demand_units=round(random.uniform(10.0, 150.0), 1) if random.random() < 0.4 else 0.0,
                    estimated_cost_loss=round(random.uniform(500.0, 12000.0), 2) if random.random() < 0.4 else 0.0,
                    prescribed_mitigation=random.choice([
                        "Expedite backup air freight consignment",
                        "Transfer safety stock from Regional DC",
                        "Reprioritize customer production batch",
                        "Buffer Stock Sufficient — Active Monitoring"
                    ])
                )
                db.add(disruption)
                disruptions_count += 1

        db.commit()
        print(f"[+] Provisioned Legs for all shipments with {delays_count} ShipmentDelay records and {disruptions_count} DisruptionReports.")

        print("\n" + "="*70)
        print(" SUCCESS: LARGE REALISTIC ENTERPRISE DATASET INITIALIZED")
        print("="*70)
        print(f" COMPANY NAME        : {company.name}")
        print(f" COMPANY ID          : {company.id}")
        print(f" COMPANY LOGIN       : {company_admin_email}")
        print(f" COMPANY PASSWORD    : vanguard123")
        print("-" * 70)
        print(f" TRANSPORTER ORG     : {carrier_org.name} ({carrier_org.code})")
        print(f" TRANSPORTER LOGIN   : {transporter_email}")
        print(f" TRANSPORTER PASSWORD: pacific123")
        print("-" * 70)
        print(f" STATS:")
        print(f"  • Global Warehouses : {len(warehouses)}")
        print(f"  • Tier-1 Suppliers  : {len(suppliers)}")
        print(f"  • High-Tech SKUs    : {len(products)}")
        print(f"  • Shipments Created : {len(shipments)}")
        print(f"  • Active Delays/Feeds: {delays_count}")
        print("="*70)

    except Exception as e:
        db.rollback()
        print(f"[!] Error generating dataset: {e}")
        import traceback
        traceback.print_exc()
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_large_company()
