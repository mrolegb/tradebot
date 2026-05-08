from app.reporting import readers


def test_read_json_returns_default_for_missing_file(tmp_path) -> None:
    missing = tmp_path / "missing.json"

    assert readers.read_json(missing, default={"ok": True}) == {"ok": True}


def test_read_csv_applies_tail_limit(tmp_path) -> None:
    csv_path = tmp_path / "rows.csv"
    csv_path.write_text("id,value\n1,a\n2,b\n3,c\n", encoding="utf-8")

    rows = readers.read_csv(csv_path, limit=2)

    assert [row["id"] for row in rows] == ["2", "3"]


def test_latest_dashboard_data_handles_missing_reports(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(readers, "REPORT_ROOT", tmp_path)

    data = readers.latest_dashboard_data()

    assert data["summary"] == {}
    assert data["trades"] == []
    assert data["runs"] == []

