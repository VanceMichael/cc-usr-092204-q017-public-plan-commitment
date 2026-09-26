import unittest

from src.bridging import BridgeError, convert, restated_value
from src.catalog import load_domain


class BridgingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.bridges = load_domain()["metric_bridges"]

    def test_v1_to_v2_factor(self) -> None:
        value, steps = convert(200000, "DHC-SVC", "v1", "v2", self.bridges)
        self.assertEqual(value, 250000)
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].bridge_id, "BR-DHC-01")

    def test_v2_to_v1_reverse_keeps_comparable(self) -> None:
        value, _ = convert(250000, "DHC-SVC", "v2", "v1", self.bridges)
        self.assertAlmostEqual(value, 200000)

    def test_restated_history_present(self) -> None:
        bridge = self.bridges[0]
        self.assertEqual(restated_value(bridge, "2026-03-31"), 245000)

    def test_same_version_is_identity(self) -> None:
        value, steps = convert(100, "DHC-SVC", "v1", "v1", self.bridges)
        self.assertEqual(value, 100)
        self.assertEqual(steps, [])

    def test_missing_bridge_raises(self) -> None:
        with self.assertRaises(BridgeError):
            convert(1, "DHC-SVC", "v1", "v9", self.bridges)


if __name__ == "__main__":
    unittest.main()
