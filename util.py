# Python port of the C++ Util class

BIT0 = 1
BIT1 = 2
BIT2 = 4
BIT3 = 8
BIT4 = 16
BIT5 = 32
BIT6 = 64
BIT7 = 128

class Util:
    @staticmethod
    def hbyte(value):
        return f"{value & 0xFF:02X}"

    @staticmethod
    def hword(value):
        return f"{value & 0xFFFF:04X}"

    @staticmethod
    def hbool(value):
        return "True" if value != 0 else "False"

    @staticmethod
    def endian_flip(value):
        b = value.to_bytes(4, byteorder='little')
        return int.from_bytes(b[::-1], byteorder='little')
