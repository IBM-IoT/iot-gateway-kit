//------------------------------------------------------------------------------
// Copyright IBM Corp. 2014
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//    http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//------------------------------------------------------------------------------
var SensorTag = require('sensortag');
var url = require('url');
var macUtil = require('getmac');
var connected = false;
var uuid;

monitorSensorTag();

function monitorSensorTag() {
  console.log('Make sure the Sensor Tag is on!');

  SensorTag.discover(function(device){
	console.log('Discovered device with UUID: ' + device['uuid']);
	uuid = device['uuid'];
	device.connect(function(){
	  connected = true;
	  console.log('Connected To Sensor Tag');
	  device.discoverServicesAndCharacteristics(function(callback){
	    //getDeviceInfo();
		initAirSensors();
		initAccelAndGyro();
		initKeys();
	  });
	});

	device.on('disconnect', function(onDisconnect) {
	  connected = false;
	  console.log('Device disconnected.');
	});

	function getDeviceInfo() {
	  device.readDeviceName(function(callback) {
	    console.log('readDeviceName: '+callback);
	  });
	  device.readSystemId(function(callback) {
	    console.log('readSystemId: '+callback);
	  });
	  device.readSerialNumber(function(callback) {
		console.log('readSerialNumber: '+callback);
	  });
	  device.readFirmwareRevision(function(callback) {
	    console.log('readFirmwareRevision: '+callback);
	  });
	  device.readHardwareRevision(function(callback) {
	    console.log('readHardwareRevision: '+callback);
	  });
	  device.readSoftwareRevision(function(callback) {
		console.log('readSoftwareRevision: '+callback);
	  });
	  device.readManufacturerName(function(callback) {
		console.log('readManufacturerName: '+callback);
	  });
	}

	function initKeys() {
	  device.notifySimpleKey(function(left, right) {
	  });
	};

	function initAccelAndGyro() {
	  device.enableAccelerometer();
	  device.notifyAccelerometer(function(){});
	  device.enableGyroscope();
	  device.notifyGyroscope(function(){});
	  device.enableMagnetometer();
	  device.notifyMagnetometer(function(){});
	};

	device.on('gyroscopeChange', function(x, y, z) {
	  var data = {
                     "myName": "TI Sensor Tag",
                     "gyroX" : x,
                     "gyroY" : y,
                     "gyroZ" : z
                  };
	postJson(data);
	});

	device.on('accelerometerChange', function(x, y, z) {
	  var data = {
                     "myName": "TI Sensor Tag",
                     "accelX" : x,
                     "accelY" : y,
                     "accelZ" : z
                  };
	postJson(data);
	});

	device.on('magnetometerChange', function(x, y, z) {
	  var data = {
                     "myName": "TI Sensor Tag",
                     "magX" : x,
                     "magY" : y,
                     "magZ" : z
                  };
	postJson(data);
	});

    var previousClick = {"left" : false, "right" : false};
	device.on('simpleKeyChange', function(left, right) {
	  var data = {
                     "myName": "TI SensorTag",
                     "left" : false,
                     "right" : false
                  };
      if(!previousClick.left && !previousClick.right) {
      	previousClick.left = left;
      	previousClick.right = right;
      	return;
      }
      if(previousClick.right && previousClick.left && !left && !right) {
      	data.d.right = true;
      	data.d.left = true;
      }
      if(previousClick.left && !left) {
      	data.d.left = true;
      }
      if(previousClick.right && !right) {
      	data.d.right = true;
      }

      previousClick.left = false;
      previousClick.right = false;
	  
	postJson(data);
	});

	function initAirSensors() {
		device.enableIrTemperature();
		device.enableHumidity();
		device.enableBarometricPressure();
		var intervalId = setInterval(function() {
		  if(!connected) {
		  	clearInterval(intervalId);
		  	return;
		  }
		  device.readBarometricPressure(function(pressure) {
		  	device.readHumidity(function(temperature, humidity) {
		  	  device.readIrTemperature(function(objectTemperature, ambientTemperature) {
		  	  	var data = {
                     "myName": "TI Sensor Tag",
                     "pressure" : pressure,
                     "humidity" : humidity,
                     "objTemp" : objectTemperature,
                     "ambientTemp" : ambientTemperature,
                     "temp" : temperature
                  };
		postJson(data);
		  	  });
		  	});
		  });
		}, 5000);
	};
	
	function postJson(jsonData) {
		fs = require("fs");
		fs.readFile("./config/configBle.json", function(err, data) {
			if(err) console.log(err);
			var util = require("./util.js");
			macUtil.getMac(function(err, macAddress) {
				if (err) throw err;
				var macAdd = macAddress.replace(/:/gi, '');
				deviceId = macAdd + "." + uuid;
				util.insertDb(data, jsonData, util.getTimeStamp(), deviceId);
			});
		});
	};

  });
}



