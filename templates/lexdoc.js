(function(){
  var filterset = document.getElementById("filterset");
  var toc = document.getElementById("toc");
  var apiKinds = {"query":true,"procedure":true,"subscription":true};
  if (filterset == null) {
    console.log("no filterset");
    return;
  }
  if (toc == null) {
    console.log("no toc");
    return;
  }
  var filterSpans = filterset.getElementsByClassName("filter");
  var tocRows = toc.getElementsByTagName("tr");
  /*var kindCount = {};
  for (var i = 0, row; row = tocRows[i]; i++) {
    var rk = row.dataset.k;
    kindCount[rk] = (kindCount[rk] || 0) + 1;
  }
  for (var k in kindCount) {
    console.log(k + ": " + kindCount[k]);
    }*/
  var chListener = function(event) {
    var chName = this.name;
    if (!this.checked) {
      return;
    }
    // chName == filterAll|filterAPI|filterData
    for (var fsi = 0, fs; fs = filterSpans[fsi]; fsi++) {
      var filterCheckbox = fs.getElementsByTagName("input")[0];
      if (filterCheckbox.name != chName) {
	filterCheckbox.checked = false;
      }
    }
    for (var i = 0, row; row = tocRows[i]; i++) {
      if (chName == 'filterAll') {
	row.classList.remove("hidden");
      } else if (chName == 'filterAPI') {
	if (apiKinds[row.dataset.k]) {
	  row.classList.remove("hidden");
	} else {
	  row.classList.add("hidden");
	}
      } else if (chName == 'filterData') {
	if (apiKinds[row.dataset.k]) {
	  row.classList.add("hidden");
	} else {
	  row.classList.remove("hidden");
	}
      }
    }
  };
  for (var fsi = 0, fs; fs = filterSpans[fsi]; fsi++) {
    var filterCheckbox = fs.getElementsByTagName("input")[0];
    filterCheckbox.addEventListener('change', chListener);
  }
  console.log("wat");
})();
