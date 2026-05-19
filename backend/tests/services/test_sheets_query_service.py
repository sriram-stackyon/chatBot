import pandas as pd
import pytest

from app.services.sheets_query_service import InvalidSourceError, load_dataframe_for_source


def test_load_dataframe_for_source_csv_success(tmp_path) -> None:
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text(" name ,age\nAlice,30\n,\nBob,25\n", encoding="utf-8")

    dataframe, metadata = load_dataframe_for_source("csv", str(csv_path))

    assert list(dataframe.columns) == ["name", "age"]
    assert metadata.columns == ["name", "age"]
    assert metadata.row_count == 2
    assert dataframe.iloc[0]["name"] == "Alice"


def test_load_dataframe_for_source_invalid_source_type() -> None:
    with pytest.raises(InvalidSourceError) as exc:
        load_dataframe_for_source("json", "ignored")

    assert exc.value.code == "invalid_source"
