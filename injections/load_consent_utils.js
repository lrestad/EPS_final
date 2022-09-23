//	with the latest updates webxray allows for injecting
//	 abitrary javascript into a website during the page loading
//	 loop which allows for observation of page behavior
//	 based on anything you'd like to accomplish

//	this example file shows how this can be
//	 used to manipulate and audit cookie consent
//	 flows

// note the naming prefix of any file with "load"
//  means no return data is expected and is
//  ignored

// the standard methods of cookie consent flows
//	typically have three elements of interest
//	during the privacy audit phase:
//		1) is a consent prompt present?
//		2) what behaviors are exhibited on an 'accept' action?
//		3) what behaviors are exhibited on a 'reject' action?

// this file should be your first injection after which
//	you should then inject 'consent_prompt_exists.js',
//	'reject_consent.js', and 'accept_consent.js'


// function waits until page is loaded, checks for
// 	presence of consent prompt represented by the
//	ID 'consent_prompt'.  note that this is specific
//  to the demo page refernced above

function consent_prompt_exists_by_id(id){
  if (document.readyState == 'complete'){
    if (document.getElementById(id)){
      return true;
    } else{
      return false;
    }
  } else{
    setTimeout(consent_prompt_exists, 1000);
  }
}

// similar to above, with click action for
//	accept, returns true if it works,
//  false if not

function accept_consent_by_id(id){
  if (document.readyState == 'complete'){
    try{
    	document.getElementById(id).click();
    	return true;
    } catch {
		return false;
    }
  } else{
    setTimeout(accept_consent, 1000);
  }
}

// same as above, with reject

function reject_consent_by_id(id){
  if (document.readyState == 'complete'){
    try{
    	document.getElementById(id).click();
    	return true;
    } catch {
		  return false;
    }
  } else{
    setTimeout(accept_consent, 1000);
  }
}

// try to find anything with 'accept' text that
//    looks clickable, and then...click it
function find_and_click_potential_accept_elements(){
  var click_sent = false;
  var element_types = ['button','a','span','div'];

  for (const element_type of element_types) {
    for (const div of document.querySelectorAll(element_type)) {
      var text = div.textContent;
      const tokens = text.split(" ");
      if (tokens.length < 5 && (text.toLowerCase().includes('accept'))){
        div.click();
        click_sent = true;
      }
    }
  }
  return click_sent;
}

// try to find anything with 'reject' text that
//    looks clickable, and then...click it
function find_and_click_potential_reject_elements(){
  var click_sent = false;
  var element_types = ['button','a','span','div'];

  for (const element_type of element_types) {
    for (const div of document.querySelectorAll(element_type)) {
      var text = div.textContent;
      const tokens = text.split(" ");
      if (tokens.length < 5 && (text.toLowerCase().includes('reject'))){
        div.click();
        click_sent = true;
      }
    }
  }
  return click_sent;
}