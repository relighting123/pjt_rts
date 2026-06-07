import config


def test_load_conv_groups_returns_config_copy():
    groups = config.load_conv_groups()
    assert groups == config.CONV_GROUPS
    groups["G1"].append("X")
    assert "X" not in config.CONV_GROUPS["G1"]


def test_max_shape_constants():
    assert config.MAX_TASKS == 5
    assert config.MAX_MODELS == 3
    assert config.SYS_ID == "RL_AGENT"
