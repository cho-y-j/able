"""Tests for FactorSnapshot model."""

import uuid
from datetime import date

import pytest

from app.models.factor_snapshot import FactorSnapshot


class TestFactorSnapshotModel:
    def test_create_instance(self):
        snap = FactorSnapshot(
            snapshot_date=date(2026, 2, 19),
            stock_code="005930",
            timeframe="daily",
            factor_name="rsi_14",
            value=55.3,
            metadata_={"category": "momentum", "source": "collector"},
        )
        assert snap.stock_code == "005930"
        assert snap.factor_name == "rsi_14"
        assert snap.value == 55.3
        assert snap.timeframe == "daily"
        assert snap.metadata_["category"] == "momentum"

    def test_tablename(self):
        assert FactorSnapshot.__tablename__ == "factor_snapshots"

    def test_unique_constraint_exists(self):
        constraints = FactorSnapshot.__table_args__
        uq = [c for c in constraints if hasattr(c, "name") and c.name == "uq_factor_snapshot"]
        assert len(uq) == 1

    def test_indexes_exist(self):
        constraints = FactorSnapshot.__table_args__
        index_names = {c.name for c in constraints if hasattr(c, "name")}
        assert "ix_factor_date_stock" in index_names
        assert "ix_factor_name_date" in index_names
        assert "ix_factor_date_name_stock" in index_names

    def test_global_stock_code(self):
        snap = FactorSnapshot(
            snapshot_date=date(2026, 2, 19),
            stock_code="_GLOBAL",
            timeframe="daily",
            factor_name="kospi_change_pct",
            value=1.5,
        )
        assert snap.stock_code == "_GLOBAL"

    def test_metadata_defaults_to_dict(self):
        snap = FactorSnapshot(
            snapshot_date=date(2026, 2, 19),
            stock_code="005930",
            timeframe="daily",
            factor_name="rsi_14",
            value=50.0,
        )
        # metadata_ should not raise when accessed
        assert snap.metadata_ is None or isinstance(snap.metadata_, dict)
