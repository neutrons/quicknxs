from quicknxs.utils.filepath import FilePath


class CrossSectionError(Exception):
    """Exception raised when no valid cross section data can be loaded"""

    def __init__(self, file_path: str | list[str] | None = None, message: str | None = None, min_num_evts: int = 100):
        self.min_num_events = min_num_evts
        self.file_path = file_path
        self.file_name = FilePath(file_path, sort=True).basename if file_path else None

        if message is None:
            message = f"No valid cross-sections found in file: {file_path}"
        self.message = message
        super().__init__(message)


class NormalizeToUnityQCutoffError(Exception):
    """When normalizing to unity fails due to no data below Q cutoff."""

    pass
