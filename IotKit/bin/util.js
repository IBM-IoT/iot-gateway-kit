
module.exports = {
	insertDb: function(config, jsonData, tstamp, id) {
		var http = require("http");
		config = JSON.parse(config);
		var post_options = {
			host: config["post"]["host"],
			port: config["post"]["port"],
			path: config["post"]["url"],
			method: "POST",
		};

		callback = function(response) {
			var str = '';
			response.on('data', function(chunk) {
				str += chunk;
			});
			response.on('end', function() {
				console.log(str);
			});
		} 
		postData = {"id":id, "tstamp":tstamp, "json_data":jsonData};
		stringData = JSON.stringify(postData);
		var post_req = http.request(post_options, callback);
		post_req.write(stringData);
		post_req.end();
	},
	
	getTimeStamp: function() {
		now = new Date();
		date = formatNum(now.getDate());
		month = formatNum(now.getMonth() + 1);
		hours = formatNum(now.getHours());
		minutes = formatNum(now.getMinutes());
		seconds = formatNum(now.getSeconds());

		tstamp = now.getFullYear() + "-" + month + "-" + date + " " + hours + ":" + minutes + ":" + seconds + ".00000";
		return tstamp;
	}

};

function formatNum(num) {
	if(num < 10) {
		num = "0" + num; 
	}
	return num;
}
