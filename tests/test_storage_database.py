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


def test_database_persists_runtime_state_and_positions(tmp_path) -> None:
    db_path = tmp_path / "state.sqlite3"
    database = Database(str(db_path))

    try:
        snapshot = {"running": True, "selected_profile": "binance_testnet", "loop_count": 2}
        database.save_runtime_state(snapshot)
        database.upsert_position("BTCUSDT", "BUY", 0.01, 65000.0, "testnet")
        loaded = database.load_runtime_state()
        positions = database.list_positions()
        database.delete_position("BTCUSDT")
        empty_positions = database.list_positions()
    finally:
        database.close()

    assert loaded == snapshot
    assert positions[0]["symbol"] == "BTCUSDT"
    assert positions[0]["side"] == "BUY"
    assert empty_positions == []
