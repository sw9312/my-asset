from portfolio import goal_projection, history_change


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
