from enum import IntEnum, StrEnum, auto


class NexusDataType(IntEnum):
    """Types of data that can be loaded."""

    REFLECTED = 0
    DIRECT_BEAM = 1
    UNDEFINED = -1


class OffSpecXAxis(IntEnum):
    """Choices of axes for off-specular binning."""

    QX_VS_QZ = 0
    KZI_VS_KZF = 1
    DELTA_KZ_VS_QZ = 3


class QBinningType(IntEnum):
    """Enum for binning types."""

    NONE = 0
    NORMAL = 1
    CONST_Q = 2

    def __str__(self):
        """
        Return a user-friendly string representation of the binning type for UI display.

        Returns
        -------
        str
            The name of the binning type ("None", "Normal", or "Const Q").
        """
        return {
            QBinningType.NONE: "None",
            QBinningType.NORMAL: "Normal",
            QBinningType.CONST_Q: "Const Q",
        }[self]


### Table column and result code enums for direct beam and reduction tables


class AddToDirectBeamResult(StrEnum):
    """Result codes for adding a run to the direct beam list."""

    SUCCESS = auto()
    SUCCESS_REFLECTED = auto()
    ALREADY_IN_LIST = auto()
    INCOMPATIBLE = auto()
    OTHER_ERROR = auto()


class AddToReductionResult(StrEnum):
    """Result codes for adding a run to the reduction list."""

    SUCCESS = auto()
    SUCCESS_DIRECT_BEAM = auto()
    ALREADY_IN_LIST = auto()
    INCOMPATIBLE = auto()
    OTHER_ERROR = auto()


class DirectBeamTableColumn(IntEnum):
    """Column indices in the direct beam table."""

    ACTIVE = 0
    RUN_NUMBER = 1
    PEAK_POSITION = 2
    PEAK_WIDTH = 3
    LOW_RES_POSITION = 4
    LOW_RES_WIDTH = 5
    BCK_POSITION = 6
    BCK_WIDTH = 7
    WAVELENGTH = 8


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
