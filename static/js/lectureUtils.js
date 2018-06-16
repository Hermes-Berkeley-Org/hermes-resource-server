var substringMatcher = function(strs) {
  return function findMatches(q, cb) {

    if (q == '') {
      cb(strs);
    } else {
      var matches, substringRegex;
      matches = [];
      substrRegex = new RegExp(q, 'i');
      $.each(strs, function(i, str) {
        if (substrRegex.test(str)) {
          matches.push(str);
        }
      });
      cb(matches);
    }


  };
};

var convertToSeconds = function(timestamp) {
    var data = timestamp.split(':');
    var hours = data[0];
    var minutes = data[1];
    var seconds = data[2];
    return (parseInt(hours) * 360 + parseInt(minutes) * 60 + parseFloat(seconds))
};

var convertToSecondsTiny = function(timestamp) {
    var data = timestamp.split(':');
    var minutes = data[0];
    var seconds = data[1];
    return (parseInt(minutes) * 60 + parseFloat(seconds))
};

var cleanTimestamp = function(timestamp) {
    var data = timestamp.split(':');
    var hours = data[0];
    var minutes = data[1];
    var seconds = data[2];
    var output = "";
    if (parseInt(hours) > 0) {
        output += hours.toString() + ":";
    }
    output += minutes.toString() + ':';
    var roundedSeconds = Math.round(parseFloat(seconds));
    if (roundedSeconds < 10) {
        output += "0";
    }
    output += roundedSeconds.toString();
    return output;
}

function convertToTimestamp(seconds) {
  var remainder = (seconds % 60) | 0;
  if (seconds < 3600) {
    var minutes = (seconds / 60) | 0;
    if (remainder >= 10) {
      return minutes + ":" + remainder;
    } else {
      return minutes + ":0" + remainder;
    }
  } else {
    var hours = (seconds / 3600) | 0;
    var minutes = ((seconds - hours * 3600) / 60) | 0;
    if (minutes >= 10) {
      if (remainder >= 10) {
        return hours + ":" + minutes + ":" + remainder;
      } else {
        return hours + ":" + minutes + ":0" + remainder;
      }
    } else {
      if (remainder >= 10) {
        return hours + ":0" + minutes + ":" + remainder;
      } else {
        return hours + ":0" + minutes + ":0" + remainder;
      }
    }
  }
}
