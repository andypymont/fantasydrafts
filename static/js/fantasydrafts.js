function showAllDraftRounds() {
	$("table.draft-table").find("tr").removeClass("collapse out").addClass("collapse in");
	$("button.btn-showallrounds").hide();
};

function getSelectedValues(pickno) {
	var vals = []
	$(".draft-dropdown").each(function() {
		if (this.id.indexOf("pick" + pickno) > 0) {
			vals.push(parseInt($(this).select2("val"), 10));
		}
	});
	return vals;
}

$(document).ready(function(){

	$(".draft-dropdown").each(function() {
		var pickno = $(this).attr("name").split("draftpick")[0].replace("pick", "");

		$(this).select2({
			placeholder: "Select a player",
			ajax: {
				url: JSON_PATH_REMAININGPLAYERS,
				data: function(term, page) {
					return { q: term };
				},
				results: function(data) {
					var results = data.players;
					var alreadypicked = getSelectedValues(pickno);

					for (var i=0; i<results.length; i++) {
						if ($.inArray(results[i].id, alreadypicked) > -1) {
							results[i].disabled = true;
						};
					};

					return {results: results};
				}
			},
			initSelection: function(element, callback) {
				var id = $(element).val();
				if (id !== "") {
					$.ajax(JSON_PATH_GETPLAYERBYID, {
						data: {id: id},
						dataType: "json"
					}).done(function(data) {
						callback(data.players[0]);
					});
				}
			}
		});
	});

	$(".clearpicks").each(function() {
		var pickno = this.id.replace('clearpicks', '');
		$(this).click(function() {
			$(".draft-dropdown").each(function() {
				if (this.id.indexOf("pick" + pickno) > 0) {
					$(this).select2("val", "");
				}
			});
		});
	});
});