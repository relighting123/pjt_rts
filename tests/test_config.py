import config


def test_load_conv_groups_returns_config_copy():
    groups = config.load_conv_groups()
    assert groups == config.CONV_GROUPS
    groups["G1"].append("X")
    assert "X" not in config.CONV_GROUPS["G1"]


def test_max_shape_constants():
    # 실제 벤치마크 최대 크기(3 tasks, 2 models)에 여유를 두되 과도한 패딩은 피함
    assert config.MAX_TASKS >= 3
    assert config.MAX_MODELS >= 2
    assert config.SYS_ID == "RL_AGENT"
