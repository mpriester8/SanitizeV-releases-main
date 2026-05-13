import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add parent directory to path to import src
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

from src.logic import move_files_logic, revert_files_logic, clear_cache_logic


class TestLogic(unittest.TestCase):

    @patch('src.logic.os.path.exists')
    @patch('src.logic.os.makedirs')
    @patch('src.logic.shutil.move')
    @patch('src.logic.shutil.rmtree')
    def test_move_files_logic_basic(self, mock_rmtree, mock_move, mock_makedirs, mock_exists):
        # Setup
        mock_exists.return_value = True  # Assume all paths exist
        log_mock = MagicMock()

        # Execute
        result = move_files_logic(
            source_dir="/source",
            folder1_name="mods",
            folder2_name="plugins",
            xml_source_dir="/xml_src",
            xml_filename="settings.xml",
            replacement_xml_path="/new/settings.xml",
            destination_dir="/dest",
            include_mods=True,
            include_plugins=True,
            include_xml=False,
            log_callback=log_mock
        )

        # Assert
        if not result:
            print("\nLOG CALLS (Move):", log_mock.call_args_list)
        self.assertTrue(result)
        # Check moves
        self.assertEqual(mock_move.call_count, 2)

    @patch('src.logic.os.path.exists')
    @patch('src.logic.shutil.rmtree')
    def test_clear_cache_logic(self, mock_rmtree, mock_exists):
        # Setup
        def side_effect(path):
            if path.endswith('data'):
                return True
            # Return False for cache folders - our new code doesn't check exists first
            return False

        mock_exists.side_effect = side_effect
        
        # Mock rmtree to succeed for some, fail for others
        def rmtree_side_effect(path):
            # Only succeed for cache and server-cache, raise FileNotFoundError for server-cache-priv
            if path.endswith('server-cache-priv'):
                raise FileNotFoundError(f"{path} not found")
            # Success for other two
            return None
        
        mock_rmtree.side_effect = rmtree_side_effect
        log_mock = MagicMock()

        # Execute
        with patch('src.logic.load_state', return_value={}), \
                patch('src.logic.save_state'):
            success, timestamp = clear_cache_logic(
                "/source", log_callback=log_mock)

        # Assert
        self.assertTrue(success)
        self.assertIsNotNone(timestamp)
        # Our new implementation attempts to delete all 3, but one raises FileNotFoundError
        self.assertEqual(mock_rmtree.call_count, 3)

    @patch('src.logic.os.path.exists')
    @patch('src.logic.shutil.move')
    @patch('src.logic.shutil.rmtree')
    def test_revert_files_logic(self, mock_rmtree, mock_move, mock_exists):
        # Setup
        mock_exists.return_value = True
        log_mock = MagicMock()

        # Execute
        result = revert_files_logic(
            source_dir="/source",
            folder1_name="mods",
            folder2_name="plugins",
            xml_source_dir="/xml_src",
            xml_filename="settings.xml",
            destination_dir="/dest",
            include_mods=True,
            include_plugins=False,  # Only revert mods
            include_xml=False,
            log_callback=log_mock
        )

        # Assert
        if not result:
            print("\nLOG CALLS (Revert):", log_mock.call_args_list)

        self.assertTrue(result)
        mock_move.assert_called_once()
        args, _ = mock_move.call_args
        self.assertIn("mods", args[0])  # From dest
        self.assertIn("mods", args[1])  # To src


if __name__ == '__main__':
    unittest.main()
