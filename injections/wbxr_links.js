// extract all links on page
var wbxr_links = (function () {
	var wbxr_processed_links = [];
	var wbxr_links 			 = 
document.links;
	for (var wbxr_i = 0; wbxr_i < wbxr_links.length; wbxr_i++) {
		wbxr_processed_links.push({
			'text'		  : wbxr_links[wbxr_i]['innerText'],
			'href'		  : wbxr_links[wbxr_i]['href'],
			'protocol'	: wbxr_links[wbxr_i]['protocol']
		});
	}
	return (wbxr_processed_links);
}());

wbxr_links;
