def generate_situation_explanation(kpis, risk_counts, inventory_summary, recommendations):
    """
    Generates a plain English summary of the current supply chain situation based on dashboard metrics.
    Uses a strong rule-based string builder as the reliable fallback.
    """
    sections = []

    # 1. Overall Health Summary
    health = kpis.get("supply_chain_health", 0)
    health_status = "healthy"
    if health < 50:
        health_status = "at critical risk"
    elif health < 80:
        health_status = "showing signs of strain"
        
    sections.append(f"### Overall Supply Chain Health\nYour overall supply chain health is currently **{health}%**, which is {health_status}. The system is monitoring {kpis.get('products', 0)} products across {kpis.get('supplier_count', 0)} active suppliers.")

    # 2. Inventory Status
    inv_units = kpis.get('inventory_units', 0)
    stockouts = kpis.get('stockout_risks', 0)
    overstock = inventory_summary.get('overstock', 0)
    healthy = inventory_summary.get('healthy', 0)
    
    inv_text = f"### Inventory Status\nYou currently hold {inv_units:,.0f} units in stock. "
    if stockouts > 0:
        inv_text += f"**Critical Warning:** There are {stockouts} products at high risk of stockout. "
    else:
        inv_text += "There are no immediate high-risk stockouts. "
        
    if overstock > 0:
        inv_text += f"Additionally, {overstock} products are currently overstocked, tying up excess capital. "
    
    inv_text += f"Overall, {healthy} products maintain healthy inventory levels."
    sections.append(inv_text)

    # 3. Shipment Risk
    high_risk = risk_counts.get("HIGH", 0) + risk_counts.get("CRITICAL", 0)
    total_shipments = kpis.get("shipments", 0)
    
    ship_text = f"### Shipment Delay Risk\nOut of {total_shipments} active shipments, "
    if high_risk > 0:
        ship_text += f"**{high_risk} are flagged as high or critical risk** for delays. These require immediate attention to prevent downstream inventory shortages."
    else:
        ship_text += "none are currently flagged as high risk, indicating a stable inbound flow."
    sections.append(ship_text)

    # 4. Actionable Suggestions
    sections.append("### Recommended Actions")
    if recommendations and len(recommendations) > 0:
        for rec in recommendations[:3]:
            sections.append(f"- **{rec['title']}**: {rec['reason']}")
    else:
        sections.append("- No urgent actions are recommended at this time. Continue monitoring.")

    return "\n\n".join(sections)
