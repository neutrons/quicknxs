# local imports
# 3rd-party imports
import pytest

from quicknxs.interfaces.data_handling.filepath import FilePath, RunNumbers


def assert_equal_arrays(actual, expected):
    assert len(actual) == len(expected)
    assert all([a == b for a, b in zip(actual, expected)])


class TestRunNumber(object):
    def test_init(self):
        assert_equal_arrays(RunNumbers(123).numbers, [123])
        assert_equal_arrays(RunNumbers("123").numbers, [123])
        assert_equal_arrays(RunNumbers(["123", 126, "125"]).numbers, [123, 125, 126])
        assert_equal_arrays(RunNumbers("7:10+3:5+1").numbers, [1, 3, 4, 5, 7, 8, 9, 10])
        assert_equal_arrays(RunNumbers("7:10 + 3:5 + 1").numbers, [1, 3, 4, 5, 7, 8, 9, 10])

    def test_long(self):
        runs = RunNumbers([7, 8, 9, 10, 3, 4, 5, 1])
        assert runs.long == "1+3+4+5+7+8+9+10"

    def test_short(self):
        runs = RunNumbers([7, 8, 9, 10, 3, 4, 5, 1])
        assert runs.short == "1+3:5+7:10"

    def test_statement(self):
        assert RunNumbers([7]).statement == "7"
        assert RunNumbers([7, 8]).statement == "7 and 8"
        assert RunNumbers([7, 8, 9]).statement == "7, 8, and 9"


class TestFilePath(object):
    def test_init(self):
        assert FilePath("/SNS/REF_M_1.nxs").path == "/SNS/REF_M_1.nxs"
        assert FilePath(["/SNS/REF_M_2.nxs", "/SNS/REF_M_1.nxs"]).path == "/SNS/REF_M_1.nxs+/SNS/REF_M_2.nxs"
        assert (
            FilePath(["/SNS/REF_M_2.nxs", "/SNS/REF_M_1.nxs"], sort=False).path == "/SNS/REF_M_2.nxs+/SNS/REF_M_1.nxs"
        )
        assert FilePath("/SNS/REF_M_2.nxs+/SNS/REF_M_1.nxs").path == "/SNS/REF_M_1.nxs+/SNS/REF_M_2.nxs"

    def test_join(self):
        assert FilePath.join("/SNS", "REF_M_1.nxs") == "/SNS/REF_M_1.nxs"
        assert FilePath.join("/SNS", "REF_M_2.nxs+REF_M_1.nxs") == "/SNS/REF_M_1.nxs+/SNS/REF_M_2.nxs"

    def test_unique_dirname(self):
        assert FilePath.unique_dirname("/SNS/REF_M_1.nxs+/SNS/REF_M_2.nxs")
        assert FilePath.unique_dirname("/NSN/REF_M_1.nxs+/SNS/REF_M_2.nxs") is False

    def test_single_paths(self):
        assert_equal_arrays(
            FilePath("/SNS/REF_M_3.nxs+/SNS/REF_M_1.nxs").single_paths, ["/SNS/REF_M_1.nxs", "/SNS/REF_M_3.nxs"]
        )

    def test_is_composite(self):
        assert FilePath("/SNS/REF_M_3.nxs").is_composite is False
        assert FilePath("/SNS/REF_M_3.nxs+/SNS/REF_M_1.nxs").is_composite

    def test_dirname(self):
        assert FilePath("/SNS/REF_M_3.nxs").dirname == "/SNS"
        assert FilePath("/SNS/REF_M_3.nxs+/SNS/REF_M_1.nxs").dirname == "/SNS"

    def test_basename(self):
        assert FilePath("/SNS/REF_M_3.nxs").basename == "REF_M_3.nxs"
        assert FilePath("/SNS/REF_M_3.nxs+/SNS/REF_M_1.nxs").basename == "REF_M_1.nxs+REF_M_3.nxs"

    def test_first_path(self):
        assert FilePath("/SNS/REF_M_3.nxs").first_path == "/SNS/REF_M_3.nxs"
        assert FilePath("/SNS/REF_M_3.nxs+/SNS/REF_M_1.nxs").first_path == "/SNS/REF_M_1.nxs"

    def test_split(self):
        assert_equal_arrays(FilePath("/SNS/REF_M_3.nxs").split(), ("/SNS", "REF_M_3.nxs"))
        assert_equal_arrays(FilePath("/SNS/REF_M_3.nxs+/SNS/REF_M_1.nxs").split(), ("/SNS", "REF_M_1.nxs+REF_M_3.nxs"))

    def test_run_numbers(self):
        assert_equal_arrays(FilePath("/SNS/REF_M_3.nxs+/SNS/REF_M_1.nxs").run_numbers(), [1, 3])
        file_path = FilePath("/SNS/REF_M_3.nxs+/SNS/REF_M_1.nxs+/SNS/REF_M_6.nxs+/SNS/REF_M_2.nxs")
        assert file_path.run_numbers(string_representation="long") == "1+2+3+6"
        assert file_path.run_numbers(string_representation="short") == "1:3+6"


if __name__ == "__main__":
    pytest.main([__file__])
