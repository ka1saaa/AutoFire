import tempfile
import unittest
from pathlib import Path

from autofire.storage import Store


class StoreTests(unittest.TestCase):
    def test_contacts_selection_and_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "autofire.db")
            store.add_contact("小王", "同学")
            store.add_contact("小李")
            contacts = store.list_contacts()
            store.set_selected([contacts[0].id], True)

            self.assertEqual([item.label for item in store.selected_contacts()], ["同学"])
            self.assertTrue(store.needs_selection_confirmation())

            store.confirm_current_selection()
            self.assertFalse(store.needs_selection_confirmation())

            store.set_selected([contacts[1].id], True)
            self.assertTrue(store.needs_selection_confirmation())

    def test_settings_and_run_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "autofire.db")
            self.assertEqual(store.get_setting("url"), "https://www.douyin.com/")
            store.set_setting("reminder_time", "08:30")
            self.assertEqual(store.get_setting("reminder_time"), "08:30")
            store.record_run(2, "manual_completion", "example")


if __name__ == "__main__":
    unittest.main()
