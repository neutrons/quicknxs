from enum import IntEnum


class ReductionTableColumn(IntEnum):
    """Column indices in the reduction table."""

    ACTIVE = 0
    RUN_NUMBER = 1
    SCALE_FACTOR = 2
    NUM_LEFT = 3
    NUM_RIGHT = 4
    PEAK_POSITION = 5
    PEAK_WIDTH = 6
    LOW_RES_POSITION = 7
    LOW_RES_WIDTH = 8
    BCK_POSITION = 9
    BCK_WIDTH = 10
    DPIX = 11
    THETA = 12
    DIRECT_BEAM = 13
    BINNING_TYPE = 14
    Q_STEPS = 15


class DirectBeamTableColumn(IntEnum):
    """Column indices in the normalization table."""

    ACTIVE = 0
    RUN_NUMBER = 1
    PEAK_POSITION = 2
    PEAK_WIDTH = 3
    LOW_RES_POSITION = 4
    LOW_RES_WIDTH = 5
    BCK_POSITION = 6
    BCK_WIDTH = 7
    WAVELENGTH = 8
