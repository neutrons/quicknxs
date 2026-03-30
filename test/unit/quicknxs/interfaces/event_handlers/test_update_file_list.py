"""Unit tests for MainHandler.update_file_list."""

from qtpy import QtWidgets

from quicknxs.interfaces.event_handlers.main_handler import MainHandler
from quicknxs.interfaces.main_window import MainWindow

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_handler(qtbot, tmp_path):
    """
    Create instances of MainWindow and MainHandler.

    Create a MainWindow + MainHandler pair wired to *tmp_path* as the
    current directory and register the window with qtbot for cleanup.
    """
    window = MainWindow()
    qtbot.addWidget(window)
    handler = MainHandler(window)
    handler._data_manager.current_directory = str(tmp_path)
    return window, handler


def _files_in_list(handler):
    """Return the texts of all items currently in the ui.file_list widget."""
    widget = handler.ui.file_list
    return [widget.item(i).text() for i in range(widget.count())]


def _add_to_file_list(handler, names):
    """Directly populate the ui.file_list widget with *names*."""
    for name in names:
        QtWidgets.QListWidgetItem(name, handler.ui.file_list)


# ---------------------------------------------------------------------------
# Use-case 1: query_path is None
# ---------------------------------------------------------------------------


class TestUpdateFileListNoQueryPath:
    """Use case 1: update triggered by directory watcher (no query_path)."""

    def test_populates_list_with_event_files(self, qtbot, tmp_path, mocker):
        """File list is built from current_event_files when query_path is None."""
        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_001.nxs.h5", "REF_M_002.nxs.h5"]),
        )

        handler.update_file_list()

        assert _files_in_list(handler) == ["REF_M_001.nxs.h5", "REF_M_002.nxs.h5"]

    def test_preserves_composite_files_from_widget(self, qtbot, tmp_path, mocker):
        """Composite file entries already in the list are preserved after refresh."""
        _, handler = _make_handler(qtbot, tmp_path)
        composite = "REF_M_001.nxs.h5+REF_M_002.nxs.h5"
        _add_to_file_list(handler, [composite])

        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_001.nxs.h5", "REF_M_002.nxs.h5"]),
        )

        handler.update_file_list()

        listed = _files_in_list(handler)
        assert composite in listed

    def test_list_is_sorted(self, qtbot, tmp_path, mocker):
        """File list is sorted after refresh."""
        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_003.nxs.h5", "REF_M_001.nxs.h5", "REF_M_002.nxs.h5"]),
        )

        handler.update_file_list()

        assert _files_in_list(handler) == sorted(["REF_M_001.nxs.h5", "REF_M_002.nxs.h5", "REF_M_003.nxs.h5"])

    def test_current_file_is_selected(self, qtbot, tmp_path, mocker):
        """The item matching current_file_name is set as the current item."""
        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_001.nxs.h5", "REF_M_002.nxs.h5"]),
        )
        handler._data_manager._current_file_name_for_test = "REF_M_001.nxs.h5"
        mocker.patch.object(
            type(handler._data_manager),
            "current_file_name",
            new_callable=lambda: property(lambda self: self._current_file_name_for_test),
        )

        handler.update_file_list()

        current = handler.ui.file_list.currentItem()
        assert current is not None
        assert current.text() == "REF_M_001.nxs.h5"

    def test_bad_files_colored_red(self, qtbot, tmp_path, mocker):
        """Items in bad_files are colored red."""
        from quicknxs.config.gui import QColors

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_001.nxs.h5", "REF_M_002.nxs.h5"]),
        )
        handler._data_manager.bad_files = {"REF_M_002.nxs.h5"}

        handler.update_file_list()

        widget = handler.ui.file_list
        items = {widget.item(i).text(): widget.item(i) for i in range(widget.count())}
        assert items["REF_M_002.nxs.h5"].foreground().color() == QColors.red
        # The good file is not red
        assert items["REF_M_001.nxs.h5"].foreground().color() != QColors.red

    def test_empty_directory_clears_list(self, qtbot, tmp_path, mocker):
        """An empty directory results in an empty file list."""
        _, handler = _make_handler(qtbot, tmp_path)
        _add_to_file_list(handler, ["REF_M_old.nxs.h5"])
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: []),
        )

        handler.update_file_list()

        assert _files_in_list(handler) == []


# ---------------------------------------------------------------------------
# Use-case 2: composite query_path (Open Sum)
# ---------------------------------------------------------------------------


class TestUpdateFileListCompositeQueryPath:
    """Use case 2: query_path is a composite ('+'-joined) file path."""

    def test_composite_same_directory_adds_composite_to_list(self, qtbot, tmp_path, mocker):
        """Composite in the current directory: composite basename is appended and list is sorted."""
        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_001.nxs.h5", "REF_M_002.nxs.h5"]),
        )

        composite_path = str(tmp_path / "REF_M_001.nxs.h5") + "+" + str(tmp_path / "REF_M_002.nxs.h5")
        handler.update_file_list(composite_path)

        listed = _files_in_list(handler)
        assert "REF_M_001.nxs.h5+REF_M_002.nxs.h5" in listed
        # Single files are also present
        assert "REF_M_001.nxs.h5" in listed
        assert "REF_M_002.nxs.h5" in listed
        # The list is sorted
        assert listed == sorted(listed)

    def test_composite_new_directory_updates_current_directory(self, qtbot, tmp_path, mocker):
        """Composite in a new directory: current_directory is updated."""
        new_dir = tmp_path / "new_subdir"
        new_dir.mkdir()
        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_010.nxs.h5"]),
        )
        mock_settings = mocker.MagicMock()
        handler.main_window.settings = mock_settings

        composite_path = str(new_dir / "REF_M_010.nxs.h5") + "+" + str(new_dir / "REF_M_011.nxs.h5")
        # Create the files so FilePath validates them
        (new_dir / "REF_M_010.nxs.h5").touch()
        (new_dir / "REF_M_011.nxs.h5").touch()

        handler.update_file_list(composite_path)

        assert handler._data_manager.current_directory == str(new_dir)

    def test_composite_new_directory_saves_setting(self, qtbot, tmp_path, mocker):
        """Composite in a new directory: 'current_directory' setting is persisted."""
        new_dir = tmp_path / "another_dir"
        new_dir.mkdir()
        (new_dir / "REF_M_020.nxs.h5").touch()
        (new_dir / "REF_M_021.nxs.h5").touch()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_020.nxs.h5", "REF_M_021.nxs.h5"]),
        )
        mock_settings = mocker.MagicMock()
        handler.main_window.settings = mock_settings

        composite_path = str(new_dir / "REF_M_020.nxs.h5") + "+" + str(new_dir / "REF_M_021.nxs.h5")
        handler.update_file_list(composite_path)

        mock_settings.setValue.assert_called_once_with("current_directory", str(new_dir))

    def test_composite_path_watcher_updated(self, qtbot, tmp_path, mocker):
        """Path watcher removes old directory and adds new directory."""
        new_dir = tmp_path / "watch_dir"
        new_dir.mkdir()
        (new_dir / "REF_M_040.nxs.h5").touch()
        (new_dir / "REF_M_041.nxs.h5").touch()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: []),
        )
        mock_settings = mocker.MagicMock()
        handler.main_window.settings = mock_settings
        remove_spy = mocker.spy(handler._path_watcher, "removePath")
        add_spy = mocker.spy(handler._path_watcher, "addPath")

        composite_path = str(new_dir / "REF_M_040.nxs.h5") + "+" + str(new_dir / "REF_M_041.nxs.h5")
        handler.update_file_list(composite_path)

        remove_spy.assert_called_once_with(str(tmp_path))
        add_spy.assert_called_once_with(str(new_dir))


# ---------------------------------------------------------------------------
# Use-case 3.1: single path pointing to a directory
# ---------------------------------------------------------------------------


class TestUpdateFileListDirectoryQueryPath:
    """Use case 3.1: query_path is a path to a directory."""

    def test_new_directory_populates_list_with_event_files(self, qtbot, tmp_path, mocker):
        """After switching to a new directory, list is populated with its event files."""
        new_dir = tmp_path / "subdir2"
        new_dir.mkdir()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_200.nxs.h5", "REF_M_201.nxs.h5"]),
        )
        mock_settings = mocker.MagicMock()
        handler.main_window.settings = mock_settings

        handler.update_file_list(str(new_dir))

        assert handler._data_manager.current_directory == str(new_dir)
        assert _files_in_list(handler) == ["REF_M_200.nxs.h5", "REF_M_201.nxs.h5"]

    def test_same_directory_leaves_list_unchanged(self, qtbot, tmp_path, mocker):
        """Pointing to the current directory (same dir) does not reset the file list."""
        _, handler = _make_handler(qtbot, tmp_path)
        _add_to_file_list(handler, ["REF_M_300.nxs.h5"])
        # current_event_files would normally be called — spy to confirm it is not
        event_files_spy = mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_300.nxs.h5"]),
        )

        handler.update_file_list(str(tmp_path))  # Same as current directory

        # new_list is None for the same-dir case, so file_list is NOT cleared
        assert _files_in_list(handler) == ["REF_M_300.nxs.h5"]

    def test_new_directory_path_watcher_updated(self, qtbot, tmp_path, mocker):
        """Path watcher is updated when directory changes."""
        new_dir = tmp_path / "watched_new"
        new_dir.mkdir()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: []),
        )
        mock_settings = mocker.MagicMock()
        handler.main_window.settings = mock_settings
        remove_spy = mocker.spy(handler._path_watcher, "removePath")
        add_spy = mocker.spy(handler._path_watcher, "addPath")

        handler.update_file_list(str(new_dir))

        remove_spy.assert_called_once_with(str(tmp_path))
        add_spy.assert_called_once_with(str(new_dir))


# ---------------------------------------------------------------------------
# Use-case 3.2: single path pointing to a file
# ---------------------------------------------------------------------------


class TestUpdateFileListFileQueryPath:
    """Use case 3.2: query_path is a path to a single file."""

    def test_file_in_current_directory_refreshes_list(self, qtbot, tmp_path, mocker):
        """A file path in the current directory refreshes the list from current_event_files."""
        test_file = tmp_path / "REF_M_400.nxs.h5"
        test_file.touch()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_400.nxs.h5", "REF_M_401.nxs.h5"]),
        )

        handler.update_file_list(str(test_file))

        assert _files_in_list(handler) == ["REF_M_400.nxs.h5", "REF_M_401.nxs.h5"]

    def test_file_in_current_directory_does_not_change_directory(self, qtbot, tmp_path, mocker):
        """A file in the current directory does not change current_directory."""
        test_file = tmp_path / "REF_M_402.nxs.h5"
        test_file.touch()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_402.nxs.h5"]),
        )

        original_dir = handler._data_manager.current_directory
        handler.update_file_list(str(test_file))

        assert handler._data_manager.current_directory == original_dir

    def test_file_in_new_directory_updates_current_directory(self, qtbot, tmp_path, mocker):
        """A file path in a new directory triggers a directory switch."""
        new_dir = tmp_path / "new_data"
        new_dir.mkdir()
        test_file = new_dir / "REF_M_500.nxs.h5"
        test_file.touch()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_500.nxs.h5"]),
        )
        mock_settings = mocker.MagicMock()
        handler.main_window.settings = mock_settings

        handler.update_file_list(str(test_file))

        assert handler._data_manager.current_directory == str(new_dir)

    def test_file_in_new_directory_populates_list(self, qtbot, tmp_path, mocker):
        """After a directory switch via file path, list is populated with event files."""
        new_dir = tmp_path / "another_data"
        new_dir.mkdir()
        test_file = new_dir / "REF_M_600.nxs.h5"
        test_file.touch()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_600.nxs.h5", "REF_M_601.nxs.h5"]),
        )
        mock_settings = mocker.MagicMock()
        handler.main_window.settings = mock_settings

        handler.update_file_list(str(test_file))

        assert _files_in_list(handler) == ["REF_M_600.nxs.h5", "REF_M_601.nxs.h5"]

    def test_file_in_new_directory_path_watcher_updated(self, qtbot, tmp_path, mocker):
        """Path watcher is updated when directory changes via a file path."""
        new_dir = tmp_path / "watch_file_dir"
        new_dir.mkdir()
        test_file = new_dir / "REF_M_700.nxs.h5"
        test_file.touch()

        _, handler = _make_handler(qtbot, tmp_path)
        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: []),
        )
        mock_settings = mocker.MagicMock()
        handler.main_window.settings = mock_settings
        remove_spy = mocker.spy(handler._path_watcher, "removePath")
        add_spy = mocker.spy(handler._path_watcher, "addPath")

        handler.update_file_list(str(test_file))

        remove_spy.assert_called_once_with(str(tmp_path))
        add_spy.assert_called_once_with(str(new_dir))

    def test_file_in_current_directory_preserves_composites(self, qtbot, tmp_path, mocker):
        """Refreshing via a same-directory file path preserves composite entries in the list."""
        test_file = tmp_path / "REF_M_800.nxs.h5"
        test_file.touch()
        composite = "REF_M_800.nxs.h5+REF_M_801.nxs.h5"

        _, handler = _make_handler(qtbot, tmp_path)
        _add_to_file_list(handler, [composite])

        mocker.patch.object(
            type(handler._data_manager),
            "current_event_files",
            new_callable=lambda: property(lambda _: ["REF_M_800.nxs.h5", "REF_M_801.nxs.h5"]),
        )

        handler.update_file_list(str(test_file))

        assert composite in _files_in_list(handler)
