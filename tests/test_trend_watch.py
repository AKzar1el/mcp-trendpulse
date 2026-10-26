"""Local Trend Watch evaluation without polling, notifications or credentials."""

import json
from datetime import date, timedelta
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor

import pytest
from click.testing import CliRunner

from mcp_trendpulse.cli import cli
from mcp_trendpulse.trend_watch import WatchStore, parse_evidence


def evidence(keyword, market, scores, *, partial_last=False):
    today = date.today()
    points = [
        {"date": (today - timedelta(days=len(scores) - index - 1)).isoformat(), "value": score}
        for index, score in enumerate(scores)
    ]
    if partial_last:
        points[-1]["isPartial"] = True
    return json.dumps({"keyword": keyword, "market": market, "points": points}).encode()


def test_rule_evaluation_trigger_then_duplicate_and_cooldown(tmp_path):
    store = WatchStore(tmp_path)
    watch = store.create(keyword="AI research", market="US", growth_pct=30, minimum_interest=20, window=2)
    payload = evidence(watch.keyword, "US", [20, 20, 40, 60])
    first = store.evaluate_and_record(watch.id, payload)
    assert first.status == "triggered"
    assert first.growth_pct == 150.0
    assert first.current_interest == 50.0
    assert store.evaluate_and_record(watch.id, payload).status == "duplicate"
    assert store.get(watch.id).last_alert_date == date.today().isoformat()

    expanded = {
        "keyword": watch.keyword,
        "market": "US",
        "points": [
            {"date": (date.today() - timedelta(days=4)).isoformat(), "value": 5},
            {"date": (date.today() - timedelta(days=3)).isoformat(), "value": 10},
            {"date": (date.today() - timedelta(days=2)).isoformat(), "value": 40},
            {"date": (date.today() - timedelta(days=1)).isoformat(), "value": 50},
        ],
    }
    # Historical evidence must not create a duplicate or move the alert backward.
    assert store.evaluate_and_record(watch.id, json.dumps(expanded).encode()).status == "duplicate"


def test_rule_cooldown_prevents_new_alert_on_following_day(tmp_path):
    store = WatchStore(tmp_path)
    rule = store.create(keyword="AI", market="US", window=2, cooldown_days=7)
    with store._connection() as db:
        db.execute(
            "UPDATE rules SET last_alert_date=? WHERE id=?",
            ((date.today() - timedelta(days=1)).isoformat(), rule.id),
        )
    decision = store.evaluate_and_record(rule.id, evidence("AI", "US", [10, 10, 45, 55]))
    assert decision.status == "cooldown"
    assert store.get(rule.id).last_alert_date == (date.today() - timedelta(days=1)).isoformat()


def test_evidence_validation_rejects_mixed_market_and_invalid_data(tmp_path):
    rule = WatchStore(tmp_path).create(keyword="local cafe", market="SI")
    with pytest.raises(ValueError, match="does not match"):
        parse_evidence(evidence("local cafe", "US", [5] * 10), keyword=rule.keyword, market=rule.market)
    with pytest.raises(ValueError, match="invalid 0-100"):
        parse_evidence(evidence(rule.keyword, rule.market, [25] * 9 + [110]), keyword=rule.keyword, market=rule.market)
    with pytest.raises(ValueError, match="256 KiB"):
        parse_evidence(b"x" * (256 * 1024 + 1), keyword=rule.keyword, market=rule.market)
    bad = {"keyword": rule.keyword, "market": rule.market, "points": [
        {"date": date.today().isoformat(), "value": 5},
        {"date": date.today().isoformat(), "value": 10},
    ]}
    with pytest.raises(ValueError, match="duplicate"):
        parse_evidence(json.dumps(bad).encode(), keyword=rule.keyword, market=rule.market)
    bad["points"] = [{"date": date.today().strftime("%Y%m%d"), "value": 5}]
    with pytest.raises(ValueError, match="valid date"):
        parse_evidence(json.dumps(bad).encode(), keyword=rule.keyword, market=rule.market)
    bad["points"] = [{"date": date.today().isoformat(), "value": 5, "isPartial": "false"}]
    with pytest.raises(ValueError, match="boolean"):
        parse_evidence(json.dumps(bad).encode(), keyword=rule.keyword, market=rule.market)


def test_zero_baseline_is_not_an_infinite_growth_alert(tmp_path):
    store = WatchStore(tmp_path)
    rule = store.create(keyword="futuristic topic", market="GB", window=2)
    decision = store.evaluate_and_record(rule.id, evidence(rule.keyword, rule.market, [0, 0, 80, 100]))
    assert decision.status == "zero_baseline"
    assert decision.growth_pct is None
    assert store.get(rule.id).last_alert_date is None


def test_partial_rows_are_discarded_and_insufficient_data_not_alerted(tmp_path):
    store = WatchStore(tmp_path)
    rule = store.create(keyword="test", market="US", window=2)
    decision = store.evaluate_and_record(rule.id, evidence("test", "US", [25, 25, 100, 100], partial_last=True))
    assert decision.status == "insufficient_data"
    assert store.get(rule.id).last_alert_date is None


def test_below_threshold_does_not_consume_alert(tmp_path):
    store = WatchStore(tmp_path)
    rule = store.create(keyword="test", market="US", window=2, growth_pct=80)
    decision = store.evaluate_and_record(rule.id, evidence("test", "US", [50, 50, 60, 60]))
    assert decision.status == "below_threshold"
    assert decision.growth_pct == 20.0
    assert store.get(rule.id).last_alert_date is None


def test_cli_watch_create_list_evaluate_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("TRENDPULSE_WATCH_DIR", str(tmp_path))
    runner = CliRunner()
    created = runner.invoke(cli, ["watch", "create", "--keyword", "market opportunity", "--market", "si",
                                  "--window", "2", "--minimum-interest", "20"])
    assert created.exit_code == 0, created.output
    rule_id = json.loads(created.output)["id"]
    listing = runner.invoke(cli, ["watch", "list"])
    assert rule_id in listing.output
    path = tmp_path / "evidence.json"
    path.write_bytes(evidence("market opportunity", "SI", [10, 10, 30, 50]))
    triggered = runner.invoke(cli, ["watch", "evaluate", "--id", rule_id, "--evidence", str(path)])
    assert triggered.exit_code == 0, triggered.output
    assert json.loads(triggered.output)["status"] == "triggered"
    repeated = runner.invoke(cli, ["watch", "evaluate", "--id", rule_id, "--evidence", str(path)])
    assert json.loads(repeated.output)["status"] == "duplicate"
    removed = runner.invoke(cli, ["watch", "remove", "--id", rule_id])
    assert json.loads(removed.output)["deleted"] is True
    assert json.loads(runner.invoke(cli, ["watch", "list"]).output) == []


def test_concurrent_evaluations_issue_only_one_alert(tmp_path):
    store = WatchStore(tmp_path)
    rule = store.create(keyword="AI", market="US", window=2)
    payload = evidence("AI", "US", [20, 20, 80, 90])
    barrier = Barrier(2)

    def worker():
        barrier.wait(timeout=5)
        return WatchStore(tmp_path).evaluate_and_record(rule.id, payload).status

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _x: worker(), range(2)))
    assert sorted(statuses) == ["duplicate", "triggered"]


def test_rule_validation_and_listing(tmp_path):
    store = WatchStore(tmp_path)
    with pytest.raises(ValueError, match="market"):
        store.create(keyword="AI", market="USA")
    with pytest.raises(ValueError, match="threshold"):
        store.create(keyword="AI", market="US", growth_pct=0)
    with pytest.raises(ValueError, match="Unknown watch ID"):
        store.get("nonexistent")
    rule = store.create(keyword="AI", market="US")
    assert store.list_rules() == [rule]
    assert store.delete(rule.id)
