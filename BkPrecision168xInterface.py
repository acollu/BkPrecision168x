import serial
import subprocess
import time

# All voltages in [V] - output voltage settable range 0.8A:18A - resolution 0.1V
# All currents in [A] - output current settable range 0A-20A - resolution 0.1V

class BkPrecision168xInterface():
    def __init__(self, usbPort=None):
        self.ser = BkPrecision168xSerialLink(usbPort)

    def __del__(self):
        del self.ser

    # Voltage setting for constant voltage operation mode
    def SetVoltage(self, voltage):
        command = 'VOLT' + self.__FloatToThreeDigits(voltage)
        self.ser.ExecuteCommand(command)

    # Current setting for constant current operation mode
    def SetCurrent(self, current):
        command = 'CURR' + self.__FloatToThreeDigits(current)
        self.ser.ExecuteCommand(command)

    # Sets upper limit for voltage
    def SetVoltageUpperLimit(self, voltageUpperlimit):
        command = 'SOVP' + self.__FloatToThreeDigits(voltageUpperlimit)
        self.ser.ExecuteCommand(command)

    # Sets upper limit for current
    def SetCurrentUpperLimit(self, currentUpperlimit):
        command = 'SOCP' + self.__FloatToThreeDigits(currentUpperlimit)
        self.ser.ExecuteCommand(command)

    # Sets output ON
    def SetOutputOn(self):
        command = 'SOUT0'
        self.ser.ExecuteCommand(command)

    # Sets output OFF
    def SetOutputOff(self):
        command = 'SOUT1'
        self.ser.ExecuteCommand(command)

    # Sets 3 presets value pairs for the power supply. Argument is list of lists [[V0, I0],[V1, I1],[V2, I2]]
    def SetPresetValues(self, presets):
        if (not isinstance(presets, list) or len(presets) != 3):
            raise InvalidArgumentException
        command = 'PROM' 
        for i in range(0, 3):
            if (not isinstance(presets[i], list) or len(presets[i]) != 2):
                raise InvalidArgumentException
            command = command + self.__FloatToThreeDigits(presets[i][0])
            command = command + self.__FloatToThreeDigits(presets[i][1])
        self.ser.ExecuteCommand(command)

    # Returns the power supply display status (present values for voltage, current and mode of operation)
    def GetDisplayStatus(self):
        command = 'GETD'
        displayStatus = self.ser.ExecuteCommand(command, readbufferDepth = 10)
        voltage = self.__FourDigitsToFloat(displayStatus[0:4])
        current = self.__FourDigitsToFloat(displayStatus[4:8])
        mode    = "CV" if (int(displayStatus[8:9]) == 0) else "CC"
        return voltage, current, mode

    # Returns the output voltage read by the power supply
    def GetVoltage(self):
        voltage, current, mode = self.GetDisplayStatus()
        return voltage

    # Returns the output current read by the power supply
    def GetCurrent(self):
        voltage, current, mode = self.GetDisplayStatus()
        return current

    # Returns the mode of operation of the power supply (either CV or CC)
    def GetMode(self):
        voltage, current, mode = self.GetDisplayStatus()
        return mode

    # Returns the power supply main settings (previously set values for voltage and current)
    def GetVoltageAndCurrentSettings(self):
        command = 'GETS'
        settings = self.ser.ExecuteCommand(command, readbufferDepth = 7)
        voltage = self.__ThreeDigitsToFloat(int(settings[0:3]))
        current = self.__ThreeDigitsToFloat(int(settings[3:6]))
        return voltage, current
    
    # Returns the voltage setting for the CV mode 
    def GetVoltageSetting(self):
        voltage, current = self.GetVoltageAndCurrentSettings()
        return voltage

    # Returns the current setting for the CC mode 
    def GetCurrentSetting(self):
        voltage, current = self.GetVoltageAndCurrentSettings()
        return current

    # Returns the upper limit setting for the voltage
    def GetVoltageUpperLimitSetting(self):
        command = 'GOVP'
        setting = self.ser.ExecuteCommand(command, readbufferDepth = 4)
        vlimitUpper = self.__ThreeDigitsToFloat(setting[0:3])
        return vlimitUpper

    # Returns the upper limit setting for the current
    def GetCurrentUpperLimitSetting(self):
        command = 'GOCP'
        setting = self.ser.ExecuteCommand(command, readbufferDepth = 4)
        ilimitUpper = self.__ThreeDigitsToFloat(setting[0:3])
        return ilimitUpper

    # Gets the max voltage and current values that the power supply can provide
    def GetMaxValues(self):
        command = 'GMAX'
        maxValues  = self.ser.ExecuteCommand(command, readbufferDepth = 7)
        maxVoltage = self.__ThreeDigitsToFloat(maxValues[0:3])
        maxCurrent = self.__ThreeDigitsToFloat(maxValues[3:6])
        return maxVoltage, maxCurrent

    # Gets the preset values for voltages and currents
    def GetPresetValues(self):
        command = 'GETM'
        presetValues = self.ser.ExecuteCommand(command, readbufferDepth = 19)
        presets = [['', ''] for x in range(0, 3)]
        for i in range(0, 3):
            presets[i][0] = self.__ThreeDigitsToFloat(presetValues[i * 6: i * 6 + 3])
            presets[i][1] = self.__ThreeDigitsToFloat(presetValues[i * 6 + 3: i * 6 + 6])
        return presets

    # Sets the output of the power supply according to the values stored in one of its preset memory locations
    def RecallPresetValues(self, presetNumber):
        if int(presetNumber) < 0 or int(presetNumber) > 2:
            raise InvalidArgumentException
        command = 'RUNM' + str(presetNumber)
        self.ser.ExecuteCommand(command) 

    # Datatype conversion methods
    def __FloatToThreeDigits(self, inputFloat):
        float(inputFloat)
        output = str(int(inputFloat * 10) % 200)
        return output.rjust(3, '0')

    def __ThreeDigitsToFloat(self, inputDigits):
        int(inputDigits)
        return float(inputDigits) / 10

    def __FourDigitsToFloat(self, inputDigits):
        int(inputDigits)
        return float(inputDigits) / 100

class BkPrecision168xSerialLink():
    def __init__(self, usbPort=None):
        if usbPort == None:
           usbPort = self.__GetDevicePath()
        self.ser = serial.Serial(
            port=usbPort,
            baudrate=9600,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS)
        self.timeout = 1. # [s]

    def __del__(self):
        self.ser.close()

    # Sends a command to power supply and collect the incoming data, strip and check ack ("OK" substring must be present)
    def ExecuteCommand(self, command, readbufferDepth = 0):
        self.ser.write(command + '\r') 
        readBuffer = self.ReadBuffer(readbufferDepth + 3)
        if readBuffer[readbufferDepth: readbufferDepth + 2] != "OK": # Data is corrupted, report
            raise NoAckException
        else:
            return readBuffer[0: readbufferDepth]

    # Reads a given number of bytes (bufferDepth) from the serial interface
    def ReadBuffer(self, readbufferDepth): 
        int(readbufferDepth)
        t = 0.
        while t < self.timeout:
            numBytesAvailable = self.ser.inWaiting()
            if numBytesAvailable == readbufferDepth:
                return self.ser.read(readbufferDepth)
            time.sleep(0.02)
            t = t + 0.02
        raise TimeoutException

    def __GetDevicePath(self):
        return "/dev/" + self.__GetDeviceUsbPort()

    def __GetDeviceUsbPort(self):
        listOfDevices = self.__GetListOfDevices()
        if len(listOfDevices) == 0:
            print "Power supply not connected to the computer, connect and retry"
            sys.exit()
        if len(listOfDevices) > 1:
            print "More than one device of the required type, disconnect one of them or switch to manual USB configuration"
            sys.exit()

        return listOfDevices[0]

    def __GetListOfDevices(self):
        listOfUsbDevices = subprocess.Popen("find /sys/bus/usb/devices/usb*/ -name dev", shell = True, stdout=subprocess.PIPE)
        listOfDevices = []
        for path in listOfUsbDevices.stdout.readlines():
            path = path.split('\n')[0][0:-4]
            device = (subprocess.Popen("udevadm info -q name -p " + path, shell = True, stdout=subprocess.PIPE).stdout.readline()).split('\n')[0]
            model = subprocess.Popen("udevadm info -q property --export -p " + path + " | grep \"ID_MODEL=\'CP2102_USB_to_UART_Bridge_Controller\'\"", \
                                     shell = True, stdout=subprocess.PIPE).stdout.readline().split('\n')[0]
            if device.split('/')[0] == "bus" or not model:
               continue
            listOfDevices.append(device)
        return listOfDevices

# Typical errors
class InvalidArgumentException(Exception):
    pass

class NoAckException(Exception):
    pass

class TimeoutException(Exception):
    pass
