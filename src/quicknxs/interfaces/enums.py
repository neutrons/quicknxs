from enum import IntEnum


class ReductionTableColumn(IntEnum):
    """Column indices in the reduction table."""

    RUN_NUMBER = 0
    SCALE_FACTOR = 1
    NUM_LEFT = 2
    NUM_RIGHT = 3
    PEAK_POSITION = 4
    PEAK_WIDTH = 5
    LOW_RES_POSITION = 6
    LOW_RES_WIDTH = 7
    BCK_POSITION = 8
    BCK_WIDTH = 9
    DPIX = 10
    THETA = 11
    DIRECT_BEAM = 12
    BINNING_TYPE = 13
    Q_STEPS = 14


class DirectBeamTableColumn(IntEnum):
    """Column indices in the normalization table."""

    RUN_NUMBER = 0
    PEAK_POSITION = 1
    PEAK_WIDTH = 2
    LOW_RES_POSITION = 3
    LOW_RES_WIDTH = 4
    BCK_POSITION = 5
    BCK_WIDTH = 6
    WAVELENGTH = 7
