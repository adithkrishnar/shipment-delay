import pytest
from datetime import date
from app.models import Company, Shipment, Product, Supplier
from app.models.shipment_leg import ShipmentLeg, DisruptionReport
from app.services.collaborative_disruption_service import ensure_shipment_legs, simulate_downstream_impact

def test_collaborative_multi_leg_disruption_pipeline(db_session):
    # 1. Create realistic fixtures in the fresh test DB
    company = Company(name="Test Logistics Enterprise", industry="Automotive")
    db_session.add(company)
    db_session.commit()
    db_session.refresh(company)

    supplier = Supplier(
        company_id=company.id,
        external_supplier_id="SUPP-001",
        name="Tier-1 Global Supplier",
        lead_time_days=10,
        reliability=0.92
    )
    product = Product(
        company_id=company.id,
        external_product_id="SKU-AUTO-01",
        name="High-Pressure Fuel Pump",
        category="Engine Components",
        unit_price=180.0
    )
    db_session.add(supplier)
    db_session.add(product)
    db_session.commit()
    db_session.refresh(product)
    db_session.refresh(supplier)

    shipment = Shipment(
        company_id=company.id,
        product_id=product.id,
        supplier_id=supplier.id,
        external_shipment_id="SH-EXP-2026",
        origin="Chennai Assembly Plant",
        destination="Pune Regional DC",
        carrier="Apex Logistics Express",
        transport_mode="ROAD",
        distance_km=1100.0,
        planned_delivery=date.today(),
        quantity=350.0
    )
    db_session.add(shipment)
    db_session.commit()
    db_session.refresh(shipment)

    # 2. Test Multimodal Leg Generation
    legs = ensure_shipment_legs(db_session, shipment)
    assert len(legs) == 3, "Expected 3 multimodal legs provisioned"
    assert legs[0].sequence == 1
    assert legs[0].mode == "ROAD"
    assert legs[1].sequence == 2

    # 3. Test Disruption Reporting on Leg 1
    target_leg = legs[0]
    test_delay_hrs = 24.0

    result = simulate_downstream_impact(
        db=db_session,
        shipment=shipment,
        leg_id=target_leg.id,
        reported_delay_hrs=test_delay_hrs,
        reason="Vehicle Breakdown",
        notes="Engine breakdown on highway NH48",
        reporter_id=None
    )

    # 4. Verify downstream simulation output
    assert result["shipment_id"] == shipment.id
    assert result["total_delay_hours"] >= test_delay_hrs
    assert "inventory_simulation" in result
    assert "financial_impact" in result
    assert "prescriptive_mitigations" in result
    assert len(result["prescriptive_mitigations"]) > 0

    # 5. Verify database persistence of report
    report = db_session.query(DisruptionReport).filter(DisruptionReport.id == result["report_id"]).first()
    assert report is not None
    assert report.delay_hours == test_delay_hrs
    assert report.disruption_reason == "Vehicle Breakdown"
