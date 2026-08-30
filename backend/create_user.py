from app.database import SessionLocal, init_db
from app.models.company import Company
from app.models.user import User
from app.auth.security import get_password_hash

def create_admin_user():
    init_db()
    db = SessionLocal()
    
    # Check if demo company exists
    company = db.query(Company).filter_by(name="Demo Company").first()
    if not company:
        company = Company(name="Demo Company", industry="Tech")
        db.add(company)
        db.commit()
        db.refresh(company)
    
    # Create user
    email = "admin@example.com"
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash("admin123"),
            company_id=company.id,
            is_superuser=True
        )
        db.add(user)
        db.commit()
        print("User created successfully: admin@example.com / admin123")
    else:
        # update password just in case
        user.hashed_password = get_password_hash("admin123")
        db.commit()
        print("User already exists. Password reset to: admin123")

if __name__ == "__main__":
    create_admin_user()
