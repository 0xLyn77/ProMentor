"""Layered black-box behavioral tests for ch01-kv-ttl."""

from pathlib import Path
import sys
import unittest

CHAPTER_DIR = Path(__file__).resolve().parent
if str(CHAPTER_DIR) not in sys.path:
    sys.path.insert(0, str(CHAPTER_DIR))

from store import KVStore
from ttl import compute_deadline, is_expired


class FakeClock:
    def __init__(self, start: float = 100.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# Part A: 基础行为
class TestPartACoreBehavior(unittest.TestCase):
    def test_put_get_delete_without_ttl(self) -> None:
        store = KVStore(clock=FakeClock())
        store.put("a", "1")
        store.put("b", "2")
        self.assertEqual(store.get("a"), "1")
        self.assertEqual(store.keys(), ["a", "b"])
        self.assertTrue(store.delete("a"))
        self.assertIsNone(store.get("a"))

    def test_ttl_helpers(self) -> None:
        self.assertIsNone(compute_deadline(10.0, None))
        deadline = compute_deadline(10.0, 5.0)
        self.assertEqual(deadline, 15.0)
        self.assertFalse(is_expired(deadline, 14.9))
        self.assertTrue(is_expired(deadline, 15.0))


# Part B: 边界与异常
class TestPartBEdgeCases(unittest.TestCase):
    def test_empty_key_raises(self) -> None:
        store = KVStore(clock=FakeClock())
        with self.assertRaises(ValueError):
            store.put("", "v")

    def test_non_positive_ttl_does_not_persist(self) -> None:
        store = KVStore(clock=FakeClock())
        store.put("temp", "v", ttl_seconds=0)
        self.assertIsNone(store.get("temp"))
        self.assertFalse(store.delete("temp"))


# Part C: 过期淘汰一致性
class TestPartCExpirationConsistency(unittest.TestCase):
    def test_expired_key_hidden_across_get_delete_keys(self) -> None:
        clk = FakeClock(10.0)
        store = KVStore(clock=clk)
        store.put("short", "x", ttl_seconds=3.0)
        store.put("long", "y", ttl_seconds=20.0)
        clk.advance(3.0)
        self.assertIsNone(store.get("short"))
        self.assertFalse(store.delete("short"))
        self.assertEqual(store.keys(), ["long"])


if __name__ == "__main__":
    unittest.main()
