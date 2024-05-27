# local imports
from reflectivity_ui.interfaces.configuration import Configuration
from reflectivity_ui.interfaces.data_handling.quicknxs_io import read_reduced_file

# 3rd-party imports
import pytest


class TestDataLoader(object):
    @pytest.fixture(autouse=True)
    def _data_dir(self, data_server):
        r"""pass the data_file fixture"""
        self.file = data_server.path_to

    def test_simple_load(self):
        file_path = self.file("REF_M_28613+28614+28615+28616+28617+28618+28619_Specular_++.dat")
        db_list, data_list, _ = read_reduced_file(file_path)
        assert len(db_list) == 7
        assert len(data_list) == 7
        assert data_list[0][2].peak_position == 179.5
        assert data_list[0][2].normalization == 28610

    def test_load_no_db(self):
        file_path = self.file("REF_M_29160_Specular_++.dat")
        db_list, data_list, _ = read_reduced_file(file_path)
        assert len(db_list) == 0
        assert len(data_list) == 1

    def test_load_from_ar(self):
        file_path = self.file("REF_M_29526_Off_Off_combined_autoreduced.dat")
        db_list, data_list, _ = read_reduced_file(file_path)
        assert len(db_list) == 4
        assert len(data_list) == 4

    def test_load_from_quicknxs(self):
        file_path = self.file("REF_M_29526_quicknxs.dat")
        db_list, data_list, _ = read_reduced_file(file_path)
        assert len(db_list) == 4
        assert len(data_list) == 4
        assert Configuration.lock_direct_beam_y is False

    def test_load_from_mismatch(self):
        file_path = self.file("REF_M_29782_empty_db.dat")
        db_list, data_list, _ = read_reduced_file(file_path)
        assert len(db_list) == 5
        assert len(data_list) == 6
        assert data_list[4][2].normalization is None

    def test_load_global_options(self):
        file_path = self.file("REF_M_29526_global_options.dat")
        db_list, data_list = read_reduced_file(file_path)
        assert len(db_list) == 4
        assert len(data_list) == 4
        assert Configuration.lock_direct_beam_y is True


if __name__ == "__main__":
    pytest.main([__file__])
