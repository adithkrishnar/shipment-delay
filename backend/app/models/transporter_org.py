from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


class TransporterOrganization(Base):
    """
    Independent 3rd-party logistics / carrier organization entity.
    Can service multiple companies via shipment assignments.
    """
    __tablename__ = "transporter_organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=True, index=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    users = relationship("User", back_populates="transporter_org")
    shipments = relationship("Shipment", back_populates="transporter_org")
    invitations = relationship("TransporterInvitation", back_populates="transporter_org")

    def __repr__(self) -> str:
        return f"<TransporterOrganization id={self.id} name={self.name!r}>"


class TransporterInvitation(Base):
    """
    Secure invitation workflow: Company administrator invites a transporter organization
    or driver to partner and gain access to assigned shipments.
    """
    __tablename__ = "transporter_invitations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    transporter_org_id = Column(Integer, ForeignKey("transporter_organizations.id", ondelete="CASCADE"), nullable=True, index=True)
    
    invited_email = Column(String(255), nullable=False, index=True)
    carrier_name = Column(String(255), nullable=False)
    invite_token = Column(String(120), unique=True, nullable=False, index=True)
    status = Column(String(30), default="PENDING", nullable=False)  # PENDING, ACCEPTED, REVOKED, EXPIRED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)

    company = relationship("Company")
    transporter_org = relationship("TransporterOrganization", back_populates="invitations")

    def __repr__(self) -> str:
        return f"<TransporterInvitation id={self.id} email={self.invited_email} status={self.status}>"

