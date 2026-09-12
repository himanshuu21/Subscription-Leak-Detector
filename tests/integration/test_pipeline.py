import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, User, Upload, Transaction, Subscription, PriceHikeEvent
from app.services.analysis import run_analysis

@pytest.fixture
def test_db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    yield db
    db.close()

def test_pipeline(test_db):
    user = User(email="test@test.com", hashed_password="123")
    test_db.add(user)
    test_db.commit()

    upload = Upload(user_id=user.id, status='pending', filename='test.csv')
    test_db.add(upload)
    test_db.commit()

    transactions = []
    
    # Netflix: 5 monthly charges, first 3 at 199.0, last 2 at 249.0
    start_date = datetime(2023, 1, 15).date()
    for i in range(5):
        d = start_date + timedelta(days=30 * i)
        amt = 199.0 if i < 3 else 249.0
        transactions.append(Transaction(upload_id=upload.id, date=d, raw_description="Netflix", amount=amt))
        
    # Spotify: 5 monthly charges at 149.0
    start_date = datetime(2023, 1, 10).date()
    for i in range(5):
        d = start_date + timedelta(days=30 * i)
        transactions.append(Transaction(upload_id=upload.id, date=d, raw_description="Spotify", amount=149.0))
        
    # Amazon Prime: 12 monthly charges at 299.0
    start_date = datetime(2022, 6, 5).date()
    for i in range(12):
        d = start_date + timedelta(days=30 * i)
        transactions.append(Transaction(upload_id=upload.id, date=d, raw_description="Amazon Prime", amount=299.0))
        
    # 5 random one-off
    transactions.append(Transaction(upload_id=upload.id, date=datetime(2023, 1, 1).date(), raw_description="Starbucks", amount=500.0))
    transactions.append(Transaction(upload_id=upload.id, date=datetime(2023, 2, 14).date(), raw_description="Uber Eats", amount=350.0))
    transactions.append(Transaction(upload_id=upload.id, date=datetime(2023, 3, 5).date(), raw_description="Zomato", amount=400.0))
    transactions.append(Transaction(upload_id=upload.id, date=datetime(2023, 4, 10).date(), raw_description="Swiggy", amount=250.0))
    transactions.append(Transaction(upload_id=upload.id, date=datetime(2023, 5, 20).date(), raw_description="BookMyShow", amount=800.0))
    
    test_db.add_all(transactions)
    test_db.commit()
    
    run_analysis(test_db, upload.id, user.id)
    
    subs = test_db.query(Subscription).all()
    assert len(subs) >= 3
    
    netflix_sub = next((s for s in subs if 'netflix' in s.merchant_name.lower()), None)
    assert netflix_sub is not None
    assert netflix_sub.price_hike_detected is True
    
    hikes = test_db.query(PriceHikeEvent).filter(PriceHikeEvent.subscription_id == netflix_sub.id).all()
    assert len(hikes) == 1
    assert hikes[0].old_amount == 199.0
    assert hikes[0].new_amount == 249.0
    
    spotify_sub = next((s for s in subs if 'spotify' in s.merchant_name.lower()), None)
    assert spotify_sub is not None
    assert spotify_sub.price_hike_detected is False
    
    amazon_sub = next((s for s in subs if 'amazon' in s.merchant_name.lower() or 'prime' in s.merchant_name.lower()), None)
    assert amazon_sub is not None
    assert amazon_sub.price_hike_detected is False
    
    for s in subs:
        assert 0 <= s.confidence_score <= 1.0

    run_analysis(test_db, upload.id, user.id)

    rerun_subs = test_db.query(Subscription).all()
    rerun_hikes = test_db.query(PriceHikeEvent).all()
    assert len(rerun_subs) == len(subs)
    assert len(rerun_hikes) == 1
