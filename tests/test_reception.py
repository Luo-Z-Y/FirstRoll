from app.backend.main import reception_summary


def test_reception_summary_blends_douban_and_letterboxd_equally() -> None:
    summary = reception_summary(
        [
            {"provider": "Douban", "normalised": 82.0},
            {"provider": "Letterboxd", "normalised": 74.0},
        ]
    )

    assert summary["aggregate"] == {
        "score": 78.0,
        "scale": 100,
        "method": "50% Douban · 50% Letterboxd",
    }


def test_reception_summary_does_not_invent_an_aggregate_from_one_source() -> None:
    summary = reception_summary([{"provider": "Douban", "normalised": 82.0}])

    assert summary["aggregate"] is None
    assert len(summary["scores"]) == 1
