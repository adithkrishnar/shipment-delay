from sqlalchemy import Column, Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        Index("ix_sales_company_product_date", "company_id", "product_id", "date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)

    date = Column(Date, nullable=False, index=True)
    quantity = Column(Float, nullable=False)  # units sold (demand)

    region = Column(String(120), nullable=True)
    price = Column(Float, nullable=True)
    promotion = Column(Integer, default=0, nullable=False)  # 0/1 flag

    company = relationship("Company", back_populates="sales")
    product = relationship("Product", back_populates="sales")

    def __repr__(self) -> str:
        return f"<Sale product_id={self.product_id} date={self.date} qty={self.quantity}>"
