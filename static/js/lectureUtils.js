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
