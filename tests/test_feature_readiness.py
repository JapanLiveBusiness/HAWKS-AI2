import unittest

from feature_readiness import FEATURES, STATUS_LABELS, feature, implementation_queue


class FeatureReadinessTests(unittest.TestCase):
    def test_feature_keys_and_routes_are_unique(self):
        keys = [item.key for item in FEATURES]
        routes = [item.route for item in FEATURES if item.route]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(routes), len(set(routes)))

    def test_every_status_has_a_label(self):
        self.assertTrue(all(item.status in STATUS_LABELS for item in FEATURES))

    def test_completed_features_are_removed_from_implementation_queue(self):
        queue = implementation_queue()
        self.assertEqual(queue, ())

    def test_feature_lookup(self):
        self.assertEqual(feature("ai_detail").route, "/AI詳細")
        self.assertEqual(feature("ai_detail").status, "live")


if __name__ == "__main__":
    unittest.main()
