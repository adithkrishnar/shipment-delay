from app.database import Base, engine
from sqlalchemy import text
import app.models

Base.metadata.create_all(bind=engine)

queries = [
    "ALTER TABLE users ADD COLUMN transporter_org_id INTEGER REFERENCES transporter_organizations(id)",
    "ALTER TABLE shipments ADD COLUMN transporter_org_id INTEGER REFERENCES transporter_organizations(id)",
    "ALTER TABLE shipments ADD COLUMN assignment_status VARCHAR(50) DEFAULT 'PENDING'",
    "ALTER TABLE shipments ADD COLUMN current_eta DATE",
    "ALTER TABLE disruption_reports ADD COLUMN transporter_org_id INTEGER REFERENCES transporter_organizations(id)",
    "ALTER TABLE disruption_reports ADD COLUMN idempotency_key VARCHAR(120)",
    "ALTER TABLE disruption_reports ADD COLUMN incident_location VARCHAR(255)",
    "ALTER TABLE disruption_reports ADD COLUMN evidence_url VARCHAR(500)",
    "ALTER TABLE disruption_reports ADD COLUMN status VARCHAR(30) DEFAULT 'SUBMITTED'",
]

with engine.connect() as conn:
    for q in queries:
        try:
            conn.execute(text(q))
            conn.commit()
            print("Applied:", q)
        except Exception as e:
            print("Notice:", e)

print("Migration check finished.")

