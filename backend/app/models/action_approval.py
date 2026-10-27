from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class ActionApproval(Base):
    __tablename__ = "action_approvals"
    __table_args__ = (
        UniqueConstraint("company_id", "action_id", name="uq_company_action_approval"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    action_id = Column(String(255), nullable=False, index=True)
    action_type = Column(String(100), nullable=False, default="RECOMMENDATION_APPROVAL")
    title = Column(String(255), nullable=True)
    status = Column(String(50), nullable=False, default="APPROVED")
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<ActionApproval company_id={self.company_id} action_id={self.action_id!r} status={self.status!r}>"
