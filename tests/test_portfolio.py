from portfolio import clamp_goal_controls, goal_projection, history_change


def test_history_change_uses_latest_snapshot():
    assert history_change([{"total": 100}], 130) == 30


def test_goal_projection_never_returns_negative_gap():
    result = goal_projection({
        "target_amount": 100,
        "target_date": "2099-12-01",
        "current_amount": 200,
        "monthly_contribution": 0,
        "expected_return": 0,
    })
    assert result["gap"] == 0


def test_goal_controls_clamp_legacy_out_of_range_values():
    assert clamp_goal_controls(25_000_000, 99) == (10_000_000, 12.0)
    assert clamp_goal_controls(-100_000, -5) == (0, 0.0)
