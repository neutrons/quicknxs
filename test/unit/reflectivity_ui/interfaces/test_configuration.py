from quicknxs.interfaces.configuration import Configuration, get_direct_beam_low_res_roi


def test_get_direct_beam_low_res_roi():
    """Test function get_direct_beam_low_res_roi"""
    Configuration.setup_default_values()
    conf_data_run = Configuration()
    conf_data_run.low_res_roi = [90, 110]
    conf_direct_beam = Configuration()
    conf_direct_beam.low_res_roi = [95, 120]
    # test without lock
    roi = get_direct_beam_low_res_roi(conf_data_run, conf_direct_beam)
    assert roi == conf_direct_beam.low_res_roi
    # test with lock
    Configuration.lock_direct_beam_y = True
    roi = get_direct_beam_low_res_roi(conf_data_run, conf_direct_beam)
    assert roi == conf_data_run.low_res_roi
