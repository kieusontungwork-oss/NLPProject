# tests/test_classifiers.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from classifiers import detect_aspects, detect_duration_cue, detect_durability_issues


class TestDetectAspects:
    def test_battery_and_anc(self):
        assert detect_aspects("Battery lasts forever and the ANC is incredible.") == {
            "battery",
            "noise_cancelling",
        }

    def test_price_and_fit(self):
        found = detect_aspects("Too expensive for what you get, and it doesn't fit my small ears.")
        assert "price_value" in found and "fit" in found

    def test_no_aspect(self):
        assert detect_aspects("Arrived quickly, packaging was fine.") == set()

    def test_empty(self):
        assert detect_aspects("") == set()
        assert detect_aspects(None) == set()


class TestDetectDurationCue:
    def test_numeric_months(self):
        r = detect_duration_cue("I've had these headphones for 6 months now and the battery still lasts.")
        assert r is not None and abs(r["months"] - 6.0) < 0.1

    def test_numeric_years(self):
        r = detect_duration_cue("Works great after 2 years of daily use.")
        assert r is not None and r["months"] > 20

    def test_word_number_months_in(self):
        r = detect_duration_cue("Three months in and no complaints so far.")
        assert r is not None and abs(r["months"] - 3.0) < 0.1

    def test_a_month(self):
        r = detect_duration_cue("Broke after a month of light use.")
        assert r is not None and abs(r["months"] - 1.0) < 0.2

    def test_update_review(self):
        r = detect_duration_cue("UPDATE: after 14 months of use the left ear cup cracked.")
        assert r is not None and abs(r["months"] - 14.0) < 0.1

    def test_decimal_months(self):
        r = detect_duration_cue("I've had it for 2.5 months and it broke.")
        assert r is not None and abs(r["months"] - 2.5) < 0.01

    def test_decimal_years(self):
        r = detect_duration_cue("Update after 1.5 years of heavy use.")
        assert r is not None and abs(r["months"] - 18.0) < 0.01

    def test_no_number_no_match(self):
        assert detect_duration_cue("Bought recently, works great so far.") is None

    def test_warranty_negative(self):
        assert detect_duration_cue("The warranty is 2 years, which is nice for peace of mind.") is None

    def test_hours_not_matched(self):
        assert detect_duration_cue("The battery lasts 30 hours per charge.") is None

    def test_empty(self):
        assert detect_duration_cue("") is None
        assert detect_duration_cue(None) is None


class TestDetectDurabilityIssues:
    def test_hinge_and_crack(self):
        found = detect_durability_issues("The hinge cracked after a year of use.")
        assert "hinge" in found and "broke_cracked" in found

    def test_battery_degradation(self):
        assert "battery_degradation" in detect_durability_issues(
            "Battery now drains within 2 hours; definitely degraded since new."
        )

    def test_stopped_working(self):
        assert "stopped_working" in detect_durability_issues("It just stopped working one day.")

    def test_worn_out(self):
        assert "worn_out" in detect_durability_issues("The ear pads are completely worn out.")

    def test_healthy_review(self):
        assert detect_durability_issues("Great sound, super comfortable, best purchase!") == set()

    def test_empty(self):
        assert detect_durability_issues("") == set()
        assert detect_durability_issues(None) == set()
