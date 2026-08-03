"""Tests for pco/report.py write function."""
import csv
import json

from pco.report import write


def test_write_creates_all_files(tmp_path):
    records = [{"name": "John", "count": 5}, {"name": "Jane", "count": 3}]
    result_dir = write(
        name="test_report",
        records=records,
        fields=["name", "count"],
        summary_lines=["Total: 2"],
        scope="Test Service",
        date_range=("2024-01-01", "2024-06-30"),
        output_dir=tmp_path,
    )
    assert result_dir == tmp_path
    assert (tmp_path / "test_report.json").exists()
    assert (tmp_path / "test_report.csv").exists()
    assert (tmp_path / "test_report.md").exists()


def test_write_json_content(tmp_path):
    records = [{"id": "1", "name": "Alice"}]
    write("r", records, ["id", "name"], [], output_dir=tmp_path)
    with open(tmp_path / "r.json") as f:
        data = json.load(f)
    assert data == records


def test_write_csv_content(tmp_path):
    records = [{"id": "1", "name": "Alice"}, {"id": "2", "name": "Bob"}]
    write("r", records, ["id", "name"], [], output_dir=tmp_path)
    with open(tmp_path / "r.csv") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["name"] == "Alice"
    assert rows[1]["name"] == "Bob"


def test_write_md_header(tmp_path):
    write("r", [], [], ["line1", "line2"], scope="Test", output_dir=tmp_path)
    content = (tmp_path / "r.md").read_text()
    assert "# Report: r" in content
    assert "Scope: Test" in content
    assert "line1" in content
    assert "line2" in content


def test_write_md_date_range(tmp_path):
    write("r", [], [], [], date_range=("2024-01-01", "2024-12-31"), output_dir=tmp_path)
    content = (tmp_path / "r.md").read_text()
    assert "2024-01-01" in content
    assert "2024-12-31" in content


def test_write_md_no_date_range(tmp_path):
    write("r", [], [], [], output_dir=tmp_path)
    content = (tmp_path / "r.md").read_text()
    assert "Date range" not in content


def test_write_returns_output_dir(tmp_path):
    result = write("r", [], [], [], output_dir=tmp_path)
    assert result == tmp_path


def test_write_creates_output_dir(tmp_path):
    new_dir = tmp_path / "sub" / "dir"
    write("r", [], [], [], output_dir=new_dir)
    assert new_dir.exists()
