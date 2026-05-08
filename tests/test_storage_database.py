from app.storage.database import Database
from app.types import Order, SignalSide


def test_database_saves_order(tmp_path) -> None:
    db_path = tmp_path / "orders.sqlite3"
    database = Database(str(db_path))

    try:
        database.save_order(
            Order(
                symbol="BTCUSDT",
                side=SignalSide.BUY,
                quantity=1.0,
                price=100.0,
                status="FILLED",
                mode="simulator",
            )
        )
        count = database.connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    finally:
        database.close()

    assert count == 1

