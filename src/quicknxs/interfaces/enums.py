from enum import IntEnum, StrEnum, auto


class NexusDataType(IntEnum):
    """Types of data that can be loaded."""

    REFLECTED = 0
    DIRECT_BEAM = 1
    UNDEFINED = -1


class ReductionTableColumn(IntEnum):
    """Column indices in the reduction table."""

    ACTIVE = 0
    RUN_NUMBER = 1
    SLICE = 2
    SCALE_FACTOR = 3
    NUM_LEFT = 4
    NUM_RIGHT = 5
    PEAK_POSITION = 6
    PEAK_WIDTH = 7
    LOW_RES_POSITION = 8
    LOW_RES_WIDTH = 9
    BCK_POSITION = 10
    BCK_WIDTH = 11
    DPIX = 12
    THETA = 13
    DIRECT_BEAM = 14
    BINNING_TYPE = 15
    Q_STEPS = 16


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


class AddToReductionResult(StrEnum):
    """Result codes for adding a run to the reduction list."""

    SUCCESS = auto()
    SUCCESS_DIRECT_BEAM = auto()
    ALREADY_IN_LIST = auto()
    INCOMPATIBLE = auto()
    OTHER_ERROR = auto()


class AddToDirectBeamResult(StrEnum):
    """Result codes for adding a run to the direct beam list."""

    SUCCESS = auto()
    SUCCESS_REFLECTED = auto()
    ALREADY_IN_LIST = auto()
    INCOMPATIBLE = auto()
    OTHER_ERROR = auto()
