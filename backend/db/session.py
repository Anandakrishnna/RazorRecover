import os
from sqlmodel import SQLModel, create_engine, Session, select
from backend.db.models import Merchant, Customer, Transaction, RecoveryCase, AgentDecision, AuditLog

DB_FILE = "data/razorrecover.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    SQLModel.metadata.create_all(engine)
    print(f"Database initialized cleanly at: {DB_FILE}")

def get_session():
    with Session(engine) as session:
        yield session

if __name__ == "__main__":
    init_db()
    
    # Test DB insertion & query
    with Session(engine) as session:
        # Check or insert default merchant
        merchant = session.get(Merchant, "merch_demo_01")
        if not merchant:
            merchant = Merchant(id="merch_demo_01", name="Razorpay Demo Store")
            session.add(merchant)
            session.commit()
            session.refresh(merchant)
            print(f"Created default merchant: {merchant.name} ({merchant.id})")
        else:
            print(f"Existing merchant found: {merchant.name} ({merchant.id})")
            
        # Verify all tables
        print("SQLModel Schema Verification:")
        for table in [Merchant, Customer, Transaction, RecoveryCase, AgentDecision, AuditLog]:
            count = session.exec(select(table)).all()
            print(f" - Table '{table.__tablename__}' ready ({len(count)} records)")
