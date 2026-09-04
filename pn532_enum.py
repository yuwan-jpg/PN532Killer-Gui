import enum


@enum.unique
class Command(enum.IntEnum):
    Diagnose = 0x00
    GetFirmwareVersion = 0x02
    GetGeneralStatus = 0x04
    ReadRegister = 0x06
    WriteRegister = 0x08
    ReadGPIO = 0x0C
    WriteGPIO = 0x0E
    SetSerialBaudRate = 0x10
    SetParameters = 0x12
    SAMConfiguration = 0x14
    PowerDown = 0x16
    RFConfiguration = 0x32
    RFRegulationTest = 0x58
    InJumpForDEP = 0x56
    InJumpForPSL = 0x46
    InListPassiveTarget = 0x4A
    InATR = 0x50
    InPSL = 0x4E
    InDataExchange = 0x40
    InCommunicateThru = 0x42
    InDeselect = 0x44
    InRelease = 0x52
    InSelect = 0x54
    InAutoPoll = 0x60
    TgInitAsTarget = 0x8C
    TgGetData = 0x86
    TgSetData = 0x8E
    MF1_CHECK_KEYS_OF_SECTORS = 0x3A


@enum.unique
class Pn532KillerCommand(enum.IntEnum):
    ReadEmulator = 0x1C
    WriteEmulator = 0x1E
    checkPn532Killer = 0xAA
    SetWorkMode = 0xAC
    ReadSniffData = 0x20
    ClearSnifferLog = 0x22
    ReadUserDefData = 0x24

BasicCapabilities = [
    "RootExit",
]

PN532Capabilities = [
    "HWConnect",
    "HWVersion",
    "HWWakeUp",
    "HWRaw",
    "HF14AScan",
    "HF14ARaw",
    "HfMfSetUid",
    "HfMfRdbl",
    "HfMfWrbl",
    "HfMfCview",
    "HfMfDump",
    "HfMfWipe",
    "HfMfRestore",
    "NtagEmulate",
    "NtagReader",
    "HfMfuRdbl",
    "HfMfuWrbl",
    "HfMfuDump",
    "Hf14aGen4Pwd",
    "HfMfuSetUid",
    "HfMfuEread",
]
PN532KillerCapabilities = [
    "HWModeReader",
    "HWModeSniffer",
    "HWModeEmulator",
    "HF15Scan",
    "HF15Info",
    "HF15Rdbl",
    "HF15Wrbl",
    "HF15Dump",
    "HF15Raw",
    "HfSniffSetUid",
    "HF15Gen1Uid",
    "HF15Gen2Uid",
    "HF15Gen2Config",
    "HF15ESetUid",
    "HF15ESetBlock",
    "HF15ESetDump",
    "HF15ESetWriteProtect",
    "HF15ESetResvEasAfiDsfid",
    "HfMfESetUid",
    "HfMfEload",
    "HfMfEread",
    "LfScan",
    "LfEm410xESetId",
]

@enum.unique
class MifareCommand(enum.IntEnum):
    MfReadBlock = 0x30
    MfWriteBlock = 0xA0
    MfWrite4Bytes = 0xA2

class ApduCommand:
    C_APDU_CLA = 0
    C_APDU_INS = 1
    C_APDU_P1 = 2
    C_APDU_P2 = 3
    C_APDU_LC = 4
    C_APDU_DATA = 5
    C_APDU_P1_SELECT_BY_ID = 0x00
    C_APDU_P1_SELECT_BY_NAME = 0x04

    R_APDU_SW1_COMMAND_COMPLETE = 0x90
    R_APDU_SW2_COMMAND_COMPLETE = 0x00
    R_APDU_SW1_NDEF_TAG_NOT_FOUND = 0x6A
    R_APDU_SW2_NDEF_TAG_NOT_FOUND = 0x82
    R_APDU_SW1_FUNCTION_NOT_SUPPORTED = 0x6A
    R_APDU_SW2_FUNCTION_NOT_SUPPORTED = 0x81
    R_APDU_SW1_MEMORY_FAILURE = 0x65
    R_APDU_SW2_MEMORY_FAILURE = 0x81
    R_APDU_SW1_END_OF_FILE_BEFORE_REACHED_LE_BYTES = 0x62
    R_APDU_SW2_END_OF_FILE_BEFORE_REACHED_LE_BYTES = 0x82

    ISO7816_SELECT_FILE = 0xA4
    ISO7816_READ_BINARY = 0xB0
    ISO7816_UPDATE_BINARY = 0xD6


class NdefCommand:
    APPLICATION_NAME_V2 = [0, 0x07, 0xD2, 0x76, 0x00, 0x00, 0x85, 0x01, 0x01]
    NDEF_MAX_LENGTH = 0x64


@enum.unique
class TagFile(enum.IntEnum):
    NONE = 0
    CC = 1
    NDEF = 2


@enum.unique
class Status(enum.IntEnum):
    TimeoutError = -1
    HF_TAG_OK = 0x00  # IC card operation is successful
    HF_TAG_NO = 0x01  # IC card not found
    HF_ERR_STAT = 0x02  # Abnormal IC card communication
    HF_ERR_CRC = 0x03  # IC card communication verification abnormal
    HF_COLLISION = 0x04  # IC card conflict
    HF_ERR_BCC = 0x05  # IC card BCC error
    MF_ERR_AUTH = 0x06  # MF card verification failed
    HF_ERR_PARITY = 0x07  # IC card parity error
    HF_ERR_ATS = 0x08  # ATS should be present but card NAKed, or ATS too large

    # Some operations with low frequency cards succeeded!
    LF_TAG_OK = 0x40
    # Unable to search for a valid EM410X label
    EM410X_TAG_NO_FOUND = 0x41

    # The parameters passed by the BLE instruction are wrong, or the parameters passed
    # by calling some functions are wrong
    PAR_ERR = 0x60
    # The mode of the current device is wrong, and the corresponding API cannot be called
    DEVICE_MODE_ERROR = 0x66
    INVALID_CMD = 0x67
    SUCCESS = 0x68
    NOT_IMPLEMENTED = 0x69
    FLASH_WRITE_FAIL = 0x70
    FLASH_READ_FAIL = 0x71
    INVALID_SLOT_TYPE = 0x72

    def __str__(self):
        if self == Status.HF_TAG_OK:
            return "HF tag operation succeeded"
        elif self == Status.HF_TAG_NO:
            return "HF tag no found or lost"
        elif self == Status.HF_ERR_STAT:
            return "HF tag status error"
        elif self == Status.HF_ERR_CRC:
            return "HF tag data crc error"
        elif self == Status.HF_COLLISION:
            return "HF tag collision"
        elif self == Status.HF_ERR_BCC:
            return "HF tag uid bcc error"
        elif self == Status.MF_ERR_AUTH:
            return "HF tag auth fail"
        elif self == Status.HF_ERR_PARITY:
            return "HF tag data parity error"
        elif self == Status.HF_ERR_ATS:
            return "HF tag was supposed to send ATS but didn't"
        elif self == Status.LF_TAG_OK:
            return "LF tag operation succeeded"
        elif self == Status.EM410X_TAG_NO_FOUND:
            return "EM410x tag no found"
        elif self == Status.PAR_ERR:
            return "API request fail, param error"
        elif self == Status.DEVICE_MODE_ERROR:
            return "API request fail, device mode error"
        elif self == Status.INVALID_CMD:
            return "API request fail, cmd invalid"
        elif self == Status.SUCCESS:
            return "Device operation succeeded"
        elif self == Status.NOT_IMPLEMENTED:
            return "Some api not implemented"
        elif self == Status.FLASH_WRITE_FAIL:
            return "Flash write failed"
        elif self == Status.FLASH_READ_FAIL:
            return "Flash read failed"
        elif self == Status.INVALID_SLOT_TYPE:
            return "Invalid card type in slot"
        return "Invalid status"


@enum.unique
class SlotNumber(enum.IntEnum):
    SLOT_1 = 1
    SLOT_2 = 2
    SLOT_3 = 3
    SLOT_4 = 4
    SLOT_5 = 5
    SLOT_6 = 6
    SLOT_7 = 7
    SLOT_8 = 8

    @staticmethod
    def to_fw(index: int):  # can be int or SlotNumber
        # SlotNumber() will raise error for us if index not in slot range
        return SlotNumber(index).value - 1

    @staticmethod
    def from_fw(index: int):
        # SlotNumber() will raise error for us if index not in fw range
        return SlotNumber(index + 1)


@enum.unique
class TagSenseType(enum.IntEnum):
    # Unknown
    UNDEFINED = 0
    # 125 kHz
    LF = 1
    # 13.56 MHz
    HF = 2


@enum.unique
class MfcKeyTypeLegacy(enum.IntEnum):
    A = 0x60
    B = 0x61


@enum.unique
class PN532KillerMode(enum.IntEnum):
    READER = 1
    EMULATOR = 2
    SNIFFER = 3

    def __str__(self):
        if self == PN532KillerMode.READER:
            return "Reader"
        elif self == PN532KillerMode.EMULATOR:
            return "Emulator"
        elif self == PN532KillerMode.SNIFFER:
            return "Sniffer"
        return "Unknown"

@enum.unique
class PN532KillerSnifferMode(enum.IntEnum):
    WITHOUT_TAG = 0  # 无标签嗅探
    WITH_TAG = 1     # 带标签嗅探

    def __str__(self):
        if self == PN532KillerSnifferMode.WITHOUT_TAG:
            return "无标签嗅探"
        elif self == PN532KillerSnifferMode.WITH_TAG:
            return "带标签嗅探"
        return "未知"

@enum.unique
class PN532KillerTagType(enum.IntEnum):
    MFC = 1
    MFU = 2
    EM4100 = 3
    ISO15693 = 4
    T5557 = 5

    def __str__(self):
        if self == PN532KillerTagType.MFC:
            return "Mifare Classic"
        elif self == PN532KillerTagType.MFU:
            return "Mifare Ultralight"
        elif self == PN532KillerTagType.EM4100:
            return "EM4100"
        elif self == PN532KillerTagType.ISO15693:
            return "ISO15693"
        elif self == PN532KillerTagType.T5557:
            return "T5557"
        return "Unknown"

@enum.unique
class ButtonType(enum.IntEnum):
    SINGLE_CLICK = 0x01
    DOUBLE_CLICK = 0x02
    LONG_PRESS = 0x03

@enum.unique
class ButtonPressFunction(enum.IntEnum):
    NONE = 0x00
    SCAN_TAG = 0x01
    EMULATE_TAG = 0x02
    CLONE_TAG = 0x03
    CUSTOM_FUNCTION = 0xFF

    def __str__(self):
        if self == ButtonPressFunction.NONE:
            return "None"
        elif self == ButtonPressFunction.SCAN_TAG:
            return "Scan Tag"
        elif self == ButtonPressFunction.EMULATE_TAG:
            return "Emulate Tag"
        elif self == ButtonPressFunction.CLONE_TAG:
            return "Clone Tag"
        elif self == ButtonPressFunction.CUSTOM_FUNCTION:
            return "Custom Function"
        return f"Unknown({self.value})"

@enum.unique
class MifareClassicDarksideStatus(enum.IntEnum):
    SUCCESS = 0x00
    FAIL = 0x01
    IN_PROGRESS = 0x02

@enum.unique
class MfcKeyType(enum.IntEnum):
    KEY_A = 0x60
    KEY_B = 0x61

@enum.unique
class MfcValueBlockOperator(enum.IntEnum):
    DECREMENT = 0xC0
    INCREMENT = 0xC1
    RESTORE = 0xC2

    def __str__(self):
        if self == MfcValueBlockOperator.DECREMENT:
            return "Decrement"
        elif self == MfcValueBlockOperator.INCREMENT:
            return "Increment"
        elif self == MfcValueBlockOperator.RESTORE:
            return "Restore"
        return "None"
