from btle import UUID, Peripheral, DefaultDelegate
import struct
import math
import json
import requests
import thread
import time

def _TI_UUID(val):
    return UUID("%08X-0451-4000-b000-000000000000" % (0xF0000000+val))

class SensorBase:
    # Derived classes should set: svcUUID, ctrlUUID, dataUUID
    sensorOn  = struct.pack("B", 0x01)
    sensorOff = struct.pack("B", 0x00)

    def __init__(self, periph):
        self.periph = periph
        self.service = None
        self.ctrl = None
        self.data = None

    def enable(self):
        if self.service is None:
            self.service = self.periph.getServiceByUUID(self.svcUUID)
        if self.ctrl is None:
            self.ctrl = self.service.getCharacteristics(self.ctrlUUID) [0]
        if self.data is None:
            self.data = self.service.getCharacteristics(self.dataUUID) [0]
        if self.sensorOn is not None:
            self.ctrl.write(self.sensorOn,withResponse=True)

    def read(self):
        return self.data.read()

    def disable(self):
        if self.ctrl is not None:
            self.ctrl.write(self.sensorOff)

    # Derived class should implement _formatData()

def calcPoly(coeffs, x):
    return coeffs[0] + (coeffs[1]*x) + (coeffs[2]*x*x)

class IRTemperatureSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA00)
    dataUUID = _TI_UUID(0xAA01)
    ctrlUUID = _TI_UUID(0xAA02)

    zeroC = 273.15 # Kelvin
    tRef  = 298.15
    Apoly = [1.0,      1.75e-3, -1.678e-5]
    Bpoly = [-2.94e-5, -5.7e-7,  4.63e-9]
    Cpoly = [0.0,      1.0,      13.4]

    def __init__(self, periph):
        SensorBase.__init__(self, periph)
        self.S0 = 6.4e-14

    def read(self):
        '''Returns (ambient_temp, target_temp) in degC'''

        # See http://processors.wiki.ti.com/index.php/SensorTag_User_Guide#IR_Temperature_Sensor
        (rawVobj, rawTamb) = struct.unpack('<hh', self.data.read())
        tAmb = rawTamb / 128.0
        Vobj = 1.5625e-7 * rawVobj

        tDie = tAmb + self.zeroC
        S   = self.S0 * calcPoly(self.Apoly, tDie-self.tRef)
        Vos = calcPoly(self.Bpoly, tDie-self.tRef)
        fObj = calcPoly(self.Cpoly, Vobj-Vos)

        tObj = math.pow( math.pow(tDie,4.0) + (fObj/S), 0.25 )
	json_data = {"ambient": tAmb, "target": tObj - self.zeroC}
	return json_data


class AccelerometerSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA10)
    dataUUID = _TI_UUID(0xAA11)
    ctrlUUID = _TI_UUID(0xAA12)

    def __init__(self, periph):
        SensorBase.__init__(self, periph)

    def read(self):
        '''Returns (x_accel, y_accel, z_accel) in units of g'''
        x_y_z = struct.unpack('bbb', self.data.read())
        return tuple([ (val/64.0) for val in x_y_z ])

class HumiditySensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA20)
    dataUUID = _TI_UUID(0xAA21)
    ctrlUUID = _TI_UUID(0xAA22)

    def __init__(self, periph):
        SensorBase.__init__(self, periph)

    def read(self):
        '''Returns (ambient_temp, rel_humidity)'''
        (rawT, rawH) = struct.unpack('<HH', self.data.read())
        temp = -46.85 + 175.72 * (rawT / 65536.0)
        RH = -6.0 + 125.0 * ((rawH & 0xFFFC)/65536.0)
	json_data = {"ambient": temp, "rel_humidity": RH}
        return json_data


class MagnetometerSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA30)
    dataUUID = _TI_UUID(0xAA31)
    ctrlUUID = _TI_UUID(0xAA32)

    def __init__(self, periph):
        SensorBase.__init__(self, periph)

    def read(self):
        '''Returns (x, y, z) in uT units'''
        x_y_z = struct.unpack('<hhh', self.data.read())
        return tuple([ 1000.0 * (v/32768.0) for v in x_y_z ])
        # Revisit - some absolute calibration is needed

class BarometerSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA40)
    dataUUID = _TI_UUID(0xAA41)
    ctrlUUID = _TI_UUID(0xAA42)
    calUUID  = _TI_UUID(0xAA43)
    sensorOn = None

    def __init__(self, periph):
       SensorBase.__init__(self, periph)

    def enable(self):
        SensorBase.enable(self)
        self.calChr = self.service.getCharacteristics(self.calUUID) [0]

        # Read calibration data
        self.ctrl.write( struct.pack("B", 0x02), True )
        (c1,c2,c3,c4,c5,c6,c7,c8) = struct.unpack("<HHHHhhhh", self.calChr.read())
        self.c1_s = c1/float(1 << 24)
        self.c2_s = c2/float(1 << 10)
        self.sensPoly = [ c3/1.0, c4/float(1 << 17), c5/float(1<<34) ]
        self.offsPoly = [ c6*float(1<<14), c7/8.0, c8/float(1<<19) ]
        self.ctrl.write( struct.pack("B", 0x01), True )


    def read(self):
        '''Returns (ambient_temp, pressure_millibars)'''
        (rawT, rawP) = struct.unpack('<hH', self.data.read())
        temp = (self.c1_s * rawT) + self.c2_s
        sens = calcPoly( self.sensPoly, float(rawT) )
        offs = calcPoly( self.offsPoly, float(rawT) )
        pres = (sens * rawP + offs) / (100.0 * float(1<<14))
	json_data = {"ambient": temp, "pressure": press}
	return json_data

class GyroscopeSensor(SensorBase):
    svcUUID  = _TI_UUID(0xAA50)
    dataUUID = _TI_UUID(0xAA51)
    ctrlUUID = _TI_UUID(0xAA52)
    sensorOn = struct.pack("B",0x07)

    def __init__(self, periph):
       SensorBase.__init__(self, periph)

    def read(self):
        '''Returns (x,y,z) rate in deg/sec'''
        x_y_z = struct.unpack('<hhh', self.data.read())
        return tuple([ 250.0 * (v/32768.0) for v in x_y_z ])

class KeypressSensor(SensorBase):
    svcUUID = UUID(0xFFE0)
    dataUUID = UUID(0xFFE1)

    def __init__(self, periph):
        SensorBase.__init__(self, periph)
 
    def enable(self):
        self.periph.writeCharacteristic(0x60, struct.pack('<bb', 0x01, 0x00))

    def disable(self):
        self.periph.writeCharacteristic(0x60, struct.pack('<bb', 0x00, 0x00))

class SensorTag(Peripheral):
    def __init__(self,addr):
        Peripheral.__init__(self,addr)
        # self.discoverServices()
        self.IRtemperature = IRTemperatureSensor(self)
        self.accelerometer = AccelerometerSensor(self)
        self.humidity = HumiditySensor(self)
        self.magnetometer = MagnetometerSensor(self)
        self.barometer = BarometerSensor(self)
        self.gyroscope = GyroscopeSensor(self)
        self.keypress = KeypressSensor(self)


class KeypressDelegate(DefaultDelegate):
    BUTTON_L = 0x02
    BUTTON_R = 0x01
    ALL_BUTTONS = (BUTTON_L | BUTTON_R)

    _button_desc = { 
        BUTTON_L : "Left button",
        BUTTON_R : "Right button",
        ALL_BUTTONS : "Both buttons"
    } 

    def __init__(self):
        DefaultDelegate.__init__(self)
        self.lastVal = 0

    def handleNotification(self, hnd, data):
        # NB: only one source of notifications at present
        # so we can ignore 'hnd'.
        val = struct.unpack("B", data)[0]
        down = (val & ~self.lastVal) & self.ALL_BUTTONS
        if down != 0:
            self.onButtonDown(down)
        up = (~val & self.lastVal) & self.ALL_BUTTONS
        if up != 0:
            self.onButtonUp(up)
        self.lastVal = val

    def onButtonUp(self, but):
        print ( "** " + self._button_desc[but] + " UP")

    def onButtonDown(self, but):
        print ( "** " + self._button_desc[but] + " DOWN")

def readTemp( id, threadName, delay ):
	while True:
		time.sleep(delay)
		uuid = id + ".1"
		try:
			data = {"id": uuid, "json_data": tag.IRtemperature.read()}
			postData(data)
		except:
			pass

def readHumidity( id, threadName, delay ):
	while True:
		time.sleep(delay)
		uuid = id + ".2"
		try:
			data = {"id": uuid, "json_data": tag.humidity.read()}
			postData(data)
		except:
			pass

def readBarometer( id, threadName, delay ):
	while True:
		time.sleep(delay)
		uuid = id + ".3"
		try:
			data = {"id": uuid, "json_data": tag.barometer.read()}
			postData(data)
		except:
			pass

def readAccelerometer( id, threadName, delay ):
	while True:
		time.sleep(delay)
		uuid = id + ".4"
		try:
			accel = tag.accelerometer.read()
			data = {"id": uuid, "json_data": { "accelx": accel[0], "accely": accel[1], "accelz": accel[2]  }}
			postData(data)	
		except:
			pass

def readMagnetometer( id, threadName, delay ):
	while True:
		time.sleep(delay)
		uuid = id + ".5"
		try:
			mag = tag.magnetometer.read()
			data = {"id": uuid, "json_data": { "magx": mag[0], "magy": mag[1], "magz": mag[2] }}
			postData(data)
		except:
			pass

def readGyroscope( id, threadName, delay ):
	while True:
		time.sleep(delay)
		uuid = id + ".6"
		#try:
		gyro = tag.gyroscope.read()
		data = {"id": uuid, "json_data": { "gyrox": gyro[0], "gyroy": gyro[1], "gyroz": gyro[2] }}
		postData(data)
		#except:
		#	pass
	
def postData( data ):
	import json
	import requests
	import datetime

	ts = str(datetime.datetime.now())[:-6]
	ts = ts + "00000"
	data["tstamp"] = ts
	json_data = json.dumps(data)
	with open("sensortagConfig.json") as file:
		data_file = json.load(file)
		url = "http://" + data_file["post"]["ip"] + ":" + data_file["post"]["port"] + "/" + data_file["post"]["url"]
		try:
			requests.post(url, data=json_data)
		except:
			print("Unable to post data")

if __name__ == "__main__":
    from uuid import getnode as get_mac
    import time
    import sys
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument('host', action='store',help='MAC of BT device')
    parser.add_argument('-n', action='store', dest='count', default=0,
            type=int, help="Number of times to loop data")
    parser.add_argument('-t',action='store',type=float, default=5.0, help='time between polling')
    parser.add_argument('-T','--temperature', action="store_true",default=False)
    parser.add_argument('-A','--accelerometer', action='store_true',
            default=False)
    parser.add_argument('-H','--humidity', action='store_true', default=False)
    parser.add_argument('-M','--magnetometer', action='store_true',
            default=False)
    parser.add_argument('-B','--barometer', action='store_true', default=False)
    parser.add_argument('-G','--gyroscope', action='store_true', default=False)
    parser.add_argument('-K','--keypress', action='store_true', default=False)
    parser.add_argument('--all', action='store_true', default=False)

    arg = parser.parse_args(sys.argv[1:])

    print('Connecting to ' + arg.host)
    tag = SensorTag(arg.host)
    mac = hex(get_mac())
    id = str(mac[2:13]) + "." + str(arg.host).replace(":", "").lower()
    # Enabling selected sensors
if arg.temperature or arg.all:
	tag.IRtemperature.enable()
else:
	pass
if arg.humidity or arg.all:
	tag.humidity.enable()
else:
	pass
if arg.barometer or arg.all:
	tag.barometer.enable()
else:
	pass
if arg.accelerometer or arg.all:
	tag.accelerometer.enable()
else:
	pass
if arg.magnetometer or arg.all:
	tag.magnetometer.enable()
else:
	pass
if arg.gyroscope or arg.all:
	tag.gyroscope.enable()
else:
	pass
if arg.keypress or arg.all:
	tag.keypress.enable()
	tag.setDelegate(KeypressDelegate())
else:
	pass

    # Some sensors (e.g., temperature, accelerometer) need some time for initialization.
    # Not waiting here after enabling a sensor, the first read value might be empty or incorrect.
print("Reading in...")
with open('sensortagConfig.json') as data_file:
	data = json.load(data_file)
	if arg.temperature or arg.all:
		thread.start_new_thread( readTemp, (id, "Temp-thread", data["temperature"]["interval"] ) )
	else:
		pass
	if arg.humidity or arg.all:
		thread.start_new_thread( readHumidity, (id, "Humidity-thread", data["humidity"]["interval"] ) )
	else:
		pass
	if arg.barometer or arg.all:
		thread.start_new_thread( readBarometer, (id, "Barometer-thread", data["barometer"]["interval"] ) )
	else:
		pass
	if arg.accelerometer or arg.all:
		thread.start_new_thread( readAccelerometer, (id, "Accel-thread", data["accelerometer"]["interval"] ) )
	else:
		pass
	if arg.magnetometer or arg.all:
		thread.start_new_thread( readMagnetometer, (id, "Mag-thread", data["magnetometer"]["interval"] ) )
	else:
		pass
	if arg.gyroscope or arg.all:
		thread.start_new_thread( readGyroscope, (id, "Gyro-thread", data["gyroscope"]["interval"] ) ) 
	else:
		pass

	while 1:
		pass
