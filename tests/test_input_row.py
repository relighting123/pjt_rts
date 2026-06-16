import pytest

from src.db.input_row import InputRow, coerce_input_row, row_from_mapping


def test_row_from_mapping_db_column_names():
    row = row_from_mapping({
        "RULE_TIMEKEY": "2026052922500000",
        "FAC_ID": "ICPRB",
        "BATCH_ID": "B1",
        "PLAN_PROD_KEY": "P1",
        "OPER_ID": "OP10",
        "OPER_SEQ": 1,
        "EQP_MODEL_CD": "M1",
        "GBN_CD": "EQUIP_UPH",
        "ATTR_VAL": "100",
    })
    assert row.rule_timekey == "2026052922500000"
    assert row.fac_id == "ICPRB"
    assert row.eqp_model == "M1"
    assert row.gbn_cd == "EQUIP_UPH"


def test_row_from_mapping_order_independent():
    row = row_from_mapping({
        "gbn_cd": "EXEC_D0_PLAN",
        "attr_val": "300",
        "batch_id": "B1",
        "fac_id": "ICPRB",
        "oper_seq": 2,
        "oper_id": "OP20",
        "plan_prod_key": "P1",
        "eqp_model": "M1",
        "rule_timekey": "20260529",
    })
    assert row.oper_seq == 2
    assert row.attr_val == "300"


def test_coerce_input_row_legacy_tuple():
    row = coerce_input_row(
        ("20260529", "ICPRB", "B1", "P1", "OP10", 1, "M1", "EQUIP_UPH", "100")
    )
    assert isinstance(row, InputRow)
    assert row.gbn_cd == "EQUIP_UPH"


def test_row_from_mapping_missing_field_raises():
    with pytest.raises(ValueError, match="필드 부족"):
        row_from_mapping({"RULE_TIMEKEY": "x", "FAC_ID": "ICPRB"})
