from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{os.path.join(DATA_DIR, 'gym.db')}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class GymUsage(Base):
    __tablename__ = "gym_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    club_name = Column(String, nullable=False, index=True)
    city = Column(String, nullable=False)
    address = Column(String, nullable=True)
    usage_percentage = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    def as_dict(self):
        return {
            "id": self.id,
            "club_name": self.club_name,
            "city": self.city,
            "address": self.address,
            "usage_percentage": self.usage_percentage,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


def init_db():
    Base.metadata.create_all(engine)


def get_session():
    db = SessionLocal()
    try:
        return db
    finally:
        pass


def insert_usage(records: list[dict]):
    db = SessionLocal()
    try:
        for rec in records:
            entry = GymUsage(
                club_name=rec["club_name"],
                city=rec["city"],
                address=rec["address"],
                usage_percentage=rec["usage_percentage"],
                timestamp=rec["timestamp"],
            )
            db.add(entry)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_latest_usage():
    from sqlalchemy import func

    db = SessionLocal()
    try:
        subquery = db.query(
            GymUsage.club_name,
            func.max(GymUsage.timestamp).label("max_ts"),
        ).group_by(GymUsage.club_name).subquery()

        results = (
            db.query(GymUsage)
            .join(
                subquery,
                (GymUsage.club_name == subquery.c.club_name)
                & (GymUsage.timestamp == subquery.c.max_ts),
            )
            .all()
        )
        return [r.as_dict() for r in results]
    finally:
        db.close()


def get_historical_usage(club_name: str, days: int = 7):
    from sqlalchemy import func
    from datetime import timedelta

    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        results = (
            db.query(GymUsage)
            .filter(
                GymUsage.club_name == club_name,
                GymUsage.timestamp >= cutoff,
            )
            .order_by(GymUsage.timestamp)
            .all()
        )
        return [r.as_dict() for r in results]
    finally:
        db.close()


def get_average_usage(club_name: str):
    from sqlalchemy import func

    db = SessionLocal()
    try:
        results = (
            db.query(
                func.strftime("%w", GymUsage.timestamp).label("day_of_week"),
                func.strftime("%H", GymUsage.timestamp).label("hour"),
                func.avg(GymUsage.usage_percentage).label("avg_usage"),
            )
            .filter(GymUsage.club_name == club_name)
            .group_by("day_of_week", "hour")
            .order_by("day_of_week", "hour")
            .all()
        )
        return [
            {
                "day_of_week": int(r.day_of_week),
                "hour": int(r.hour),
                "avg_usage": round(float(r.avg_usage), 1),
            }
            for r in results
        ]
    finally:
        db.close()


def get_club_names():
    db = SessionLocal()
    try:
        results = db.query(GymUsage.club_name).distinct().all()
        return [r[0] for r in results]
    finally:
        db.close()