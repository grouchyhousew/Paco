from webapp.games import FRUITS, MAX_FRUIT_MULTIPLIER, crash_point, fruit_round, simulate_fruit_rtp


def test_crash_is_replayable():
    assert crash_point("server", "client", 1) == crash_point("server", "client", 1)


def test_fruit_round_is_replayable_and_bounded():
    first = fruit_round("server", "client", 1)
    second = fruit_round("server", "client", 1)
    assert first == second
    assert 0 <= first["payout_multiplier"] <= 50
    assert len(first["grid"]) == 6


def test_fruit_cascades_are_replayable_and_structured():
    result = fruit_round("server", "client", 1)
    assert result["version"] == 3
    assert result == fruit_round("server", "client", 1)
    assert result["cascade_count"] == len(result["cascades"])
    for event in result["cascades"]:
        assert len(event["grid_before"]) == result["rows"]
        assert len(event["grid_after"]) == result["rows"]
        assert all(symbol in FRUITS for row in event["grid_after"] for symbol in row)
        assert event["payout_multiplier"] >= 0
    assert result["payout_multiplier"] == result["total_payout_multiplier"]
    assert result["payout_multiplier"] <= MAX_FRUIT_MULTIPLIER


def test_fruit_rtp_simulation_is_deterministic():
    first = simulate_fruit_rtp(rounds=100)
    second = simulate_fruit_rtp(rounds=100)
    assert first == second
    assert first["rounds"] == 100
    assert 0 <= first["rtp"] <= MAX_FRUIT_MULTIPLIER
    assert 0 <= first["hit_rate"] <= 1
    assert 0 <= first["cascade_rate"] <= 1
