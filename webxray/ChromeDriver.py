import datetime
import json
import os
import platform
import random
import re
import subprocess
import tempfile
import time
import urllib.request

# websocket-client library is needed to talk to chrome devtools
# 	the github repo for library is here:
#		https://github.com/websocket-client/websocket-client
# pip3 install websocket-client
from websocket import create_connection

# standard python packages
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

# custom webxray libraries
from webxray.ParseURL  import ParseURL

class ChromeDriver:
	def __init__(self, config, port_offset=0, chrome_path=None):
		# what horrible things have you done so your karma is so low
		#	you must debug this?
		self.debug = False
		
		# unpack config
		if self.debug: print(config)
		self.prewait				= config['client_prewait']
		self.no_event_wait 			= config['client_no_event_wait']
		self.max_wait 				= config['client_max_wait']
		self.return_page_text 		= config['client_get_text']
		self.return_bodies 			= config['client_get_bodies']
		self.return_bodies_base64 	= config['client_get_bodies_b64']
		self.return_screen_shot 	= config['client_get_screen_shot']
		self.reject_redirects		= config['client_reject_redirects']
		self.crawl_depth 			= config['client_crawl_depth']
		self.crawl_retries 			= config['client_crawl_retries']
		self.page_load_strategy		= config['client_page_load_strategy']
		self.min_internal_links		= config['client_min_internal_links']
		self.incognito				= config['client_incognito']
		self.headless 				= config['client_headless']

		# custom library in /webxray
		self.url_parser = ParseURL()

		# prevents get_scan from closing browser
		#	when we are doing a crawl
		self.is_crawl = False

		# gets overwritten once, so we don't have to keep
		#	figuring it out when doing crawls
		self.browser_type		= None
		self.browser_version 	= None
		self.user_agent			= None

		# list of files in ./injections we want to execute
		self.injections			= config['client_injections']

		chrome_commands = []

		# we can override the path here
		if chrome_path:
			chrome_cmd = chrome_cmd
		else:
			# if path is not specified we use the common
			#	paths for each os
			if platform.system() == 'Darwin':
				chrome_commands.append('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
			elif platform.system() == 'Linux':
				chrome_commands.append('/usr/bin/google-chrome')
				# make sure chrome doesnt' access for keychain password
				chrome_commands.append('--password-store=basic')
			elif platform.system() == 'Windows':
				chrome_cmd = 'start chrome '
			else:
				print('Unable to determine Operating System and therefore cannot guess correct Chrome path, see ChromeDriver.py for details.')
				exit()
		
		# no idea what this actually does in a practical sense, but
		#	if something breaks we can try it, just leaving inert
		#	for now
		#chrome_commands.append('--enable-automation')

		# make sure we can open ws connections
		chrome_commands.append('--remote-allow-origins=*')

		# use port offset to avoid collissions between processes
		#	note that if two single scan processes are running they may
		#	end up using the same connection and bad things will
		#	happen
		port = 9222+port_offset
		chrome_commands.append(f'--remote-debugging-port={port}')

		# sets up blank profile
		chrome_commands.append('--guest')

		# not sure this really does anything, but appears in various
		#	examples online and it doesn't hurt anything
		chrome_commands.append('--disable-gpu')

		# in case you want to do these specific tests
		if self.incognito: chrome_commands.append('--incognito')

		# set up headless
		if self.headless: chrome_commands.append('--headless')

		# now things get a bit weird, sometime around 110.0.5481.77
		#	the normal means of getting the devtools websocket address
		#	from http://localhost:port/json stopped working in headless.
		#
		# this turned out ot be a real pain in the ass, but I figured
		#	out an even lower-level work around which works as follows:
		#		1) pull the raw connection address from stderr
		#		2) connect to that
		#		3) from there create a new 'target' in chrome
		#		4) close the 'raw' websocket
		#		5) open a new websocket with the fresh target_id
		#
		# if the above is confusing don't worry about it, just know
		#	it works and there are ways to go deeper into the guts
		#	than the typical /json means

		# open subprocess with stderr directed to a tempfile, this is
		#	where we pull out the address.  note this is a hack so
		#	we can continue execution after we launch the browser,
		#	using the typical PIPE approach gets us stuck.

		with tempfile.NamedTemporaryFile(mode="w", delete=False) as outfile:
			subprocess.Popen(
				chrome_commands, 
				stderr=outfile, 
				stdout=None
			)
			self.launched = True

		# before we run additional commands we give the browser some time 
		#	to boot
		time.sleep(2)

		# if all things are working as they should, we can read the chrome debugger
		#	address from the following url, if we can't that means chrome
		#	never created a target, so we have to do that manually, which is a major
		#	chore.  I hope this is a temporary bug and we can remove this at some point
		try:
			debugger_ws_addr = json.loads(urllib.request.urlopen(f'http://localhost:{port}/json').read().decode())[0]['webSocketDebuggerUrl']
		except:
			# there is a line in stderr which has the devtools address, we have to find it
			#	or we fail
			raw_devtools_ws = None
			with open(outfile.name, "r") as outfile:
				# find the line we're looking for
				for line in outfile.readlines():
					if 'DevTools' in line:
						raw_devtools_ws = line.replace('DevTools listening on ','')
						break

			if not raw_devtools_ws:
				print('Failed to find raw devtools ws address.')
				self.exit()
				return

			if self.debug: print(f'raw devtools connection is {raw_devtools_ws}')

			if self.debug: print('attempting to create target in chrome')

			# open a devtools_connect to the raw_devtools_ws
			try:
				self.current_ws_command_id = 0
				self.devtools_connection = create_connection(raw_devtools_ws)
				self.devtools_connection.settimeout(3)
			except:
				print(f'Failed to open {raw_devtools_ws}, potentially stale copies of Chrome open.  Kill them.')
				self.exit()
				return

			# now we create the target which we really want to connect to
			response = self.get_single_ws_response('Target.createTarget','"url":""')
			if response['success'] == False:
				self.exit()
				print('Target.createTarget failed.')
				return
			else:
				response = response['result']
			if self.debug: print(f'{response}')

			# pull out the new target_id and create a new connection
			try:
				debugger_ws_addr = json.loads(urllib.request.urlopen(f'http://localhost:{port}/json').read().decode())[0]['webSocketDebuggerUrl']
			except:
				print('Failed get to debugger address.')
				return

			# close the low-level connection
			self.devtools_connection.close()

		# try to open our intended ws connection
		try:
			self.current_ws_command_id = 0
			self.devtools_connection = create_connection(debugger_ws_addr)
			self.devtools_connection.settimeout(3)
		except:
			print(f'Failed to open {debugger_ws_addr}, potentially stale copies of Chrome open.  Kill them.')
			self.exit()
			return

		# prevent downloading files, the /dev/null is redundant
		if self.debug: print('going to disable downloading')
		response = self.get_single_ws_response('Page.setDownloadBehavior','"behavior":"deny","downloadPath":"/dev/null"')
		if response['success'] == False:
			self.exit()
			return
		else:
			response = response['result']
		if self.debug: print(f'{response}')

		# done
		return
	# __init__

	def get_single_ws_response(self,method,params=''):
		"""
		Attempt to send ws_command and return response, note this only works
			if you don't have the queue being flooded with network events,
			handles crashes gracefully.
		"""
		self.current_ws_command_id += 1
		try:
			self.devtools_connection.send('{"id":%s,"method":"%s","params":{%s}}' % (self.current_ws_command_id,method,params))
			return ({
				'success'	: True,
				'result'	: json.loads(self.devtools_connection.recv())
			})
		except:
			return ({
				'success'	: False,
				'result'	: 'Crashed on get_single_ws_response.'
			})
	# get_single_ws_response

	def send_ws_command(self,method,params='',override_id=None):
		"""
		Attempt to send ws_command, handle crashes gracefully.
		"""
		self.current_ws_command_id += 1
		try:
			self.devtools_connection.send('{"id":%s,"method":"%s","params":{%s}}' % (self.current_ws_command_id,method,params))
			return ({
				'success'	: True,
				'result'	: self.current_ws_command_id
			})
		except:
			return ({
				'success'	: False,
				'result'	: 'Crashed on send_ws_command.'
			})
	# send_ws_command

	def get_next_ws_response(self):
		"""
		Either get the next ws response or send None on 
			timeout or crash.
		"""
		try:
			return json.loads(self.devtools_connection.recv())
		except:
			return None
	# get_next_ws_response

	def exit(self):
		"""
		Tidy things up before exiting.

		"""
		if self.launched:
			self.send_ws_command('Browser.close')
			self.devtools_connection.close()
	# exit

	def get_crawl(self, url_list):
		"""
		Performs multiple page loads using the same profile,
			which allows cookies to be transferred across loads
			and potentially allow for more tracking.
		"""

		if self.debug: print('Running get_crawl task.')

		# setting this globally prevents the browser
		#	from being closed after get_scan
		self.is_crawl = True

		# we return a list which is all the get_scan
		#	results we find
		results = []

		# do each url
		for url in url_list:
			result = self.get_scan(url)
			if result['success']:
				results.append(result['result'])
			else:
				error = result['result']
				self.exit()
				return ({
					'success': False,
					'result': error
				})

		# now it is ok to close the browser/ws connection
		self.exit()

		# done!
		return ({
			'success': True,
			'result': results
		})
	# get_crawl

	def get_random_crawl(self, seed_url):
		"""
		Based on an intial seed page conducts a first scan to
			get traffic and links, then loads additional pages
			on the same site based on links.

		Note the cookies from each page load carry over, thus we do
			not allow any domain-level redirects on page loads as this
			would skew our ability to categorize cookies as first
			or third-party.
		"""

		if self.debug: print('Running get_random_crawl task.')

		# setting this globally prevents the browser
		#	from being closed after get_scan
		self.is_crawl = True

		# we return a list which is all the get_scan
		#	results we find
		results = []

		# removing trailing /
		seed_url = re.sub('/$', '',seed_url)

		if self.debug: print(f'going to scan seed_url {seed_url}')
		result = self.get_scan(seed_url)

		if not result['success']:
			self.exit()
			return ({
				'success': False,
				'result': result["result"]
			})
		else:
			origin_url 		= result['result']['final_url']
			scanned_urls 	= [seed_url]
			results.append(result['result'])

		if self.debug: print(f'origin url is {origin_url}')

		# holds urls we may scan
		unique_urls = set()

		# look at links from the seed page, we will quit
		#	either when we exceed self.crawl_depth or run out of links
		for link in result['result']['all_links']:

			# only do internal links
			if not link['internal']: continue

			# (re)encode the url
			url = self.idna_encode_url(link['href'], no_fragment=True)

			# idna_encode failure yields a None value, skip
			if not url: continue

			# removing trailing /
			url = re.sub('/$', '',url)

			# make sure it is a real web page
			if not self.is_url_valid(url): continue

			# we already scanned this
			if url == seed_url or url == origin_url: continue

			# yay, it's usable
			unique_urls.add(url)

		# no need to do any scans if we can't find urls
		if len(unique_urls) < self.crawl_depth:
			self.exit()
			return ({
				'success'	: False,
				'result'	: 'did not find enough internal links'
			})

		# we allow a certain number of failed page loads, but eventually
		#	we must give up
		failed_urls = []

		# keep scanning pages until we've done enough
		for url in unique_urls:

			# if we have enough results break
			if len(scanned_urls) == self.crawl_depth: break

			# give up!
			if len(failed_urls) > self.crawl_retries:
				self.exit()
				return ({
					'success'	: False,
					'result'	: 'reached fail limit'
				})

			# do the scan
			result = self.get_scan(url)

			# either keep result or keep track of failures
			if result['success']:
				# reject redirects based on origin_url
				is_redirect = self.is_url_internal(origin_url,result['result']['final_url'])
				if is_redirect == None or is_redirect == False:
					if self.debug: print(f"caught redirect from {url} to {result['result']['final_url']}")
					failed_urls.append(url)
				else:
					results.append(result['result'])
					scanned_urls.append(url)
			else:
				if self.debug: print(f"fail on {result['result']}")
				failed_urls.append(url)

		if self.debug: 
			print('crawled urls:')
			for res in results:
				print(res['start_url'],res['final_url'])

		# now it is ok to close the browser/ws connection
		self.exit()

		# done!
		num_results = len(results)
		if num_results < self.crawl_depth:
			return ({
				'success': False,
				'result': 'unable to crawl specified number of pages'
			})
		else:
			return ({
				'success': True,
				'result': results
			})
	# get_random_crawl

	def get_scan(self, url, get_text_only=False):
		"""
		The primary function for this class, performs a number of tasks based on the config
			including, but not limited to:

			- capture network traffic
			- capture response bodies
			- capture screen shots
			- capture page text using readability
		
		Note that if get_text_only is true we only do basic tasks
			such as getting the policy, and we return far less content which is useful
			for doing text capture.
		"""

		if self.debug: print('Running get_scan task.')

		# let the games begin
		if self.debug: print('starting %s' % url)

		# we can't start Chrome, return error message as result
		if not self.launched:
			return ({
				'success': False,
				'result': 'Unable to launch Chrome instance, check that Chrome is installed in the expected location, see ChromeDriver.py for details.'
			})

		# Network events are stored as lists of dictionaries which are
		#	returned.
		requests  				= []
		request_extra_headers 	= []
		responses 				= []
		response_extra_headers 	= []
		websockets 				= []
		websocket_events 		= []
		event_source_msgs 		= []
		load_finish_events 		= []
		
		# Response bodies are keyed to the request_id when they are
		#	returned to calling function, and we get the response bodies
		#	by issuing websocket commands so we we first keep track
		#	of which command is linked to which ws_id.  Note this data is
		#	for internal processes and not returned
		ws_id_to_req_id = {}

		# When we get the websocket response we stored the body keyed
		#	to the request id, this is returned
		response_bodies = {}

		# We keep dom_storage here, the dict key is a tuple of the securityOrigin
		# 	isLocalStorage, and the domstorage key. This way we can keep only final 
		#	values in cases they are overwritten.  Note this data is
		#	for internal processes and not returned
		dom_storage_holder 	= {}
		
		# "misc_storage" includes local storage, session storage, indexeddb,
		#	and cachestorage.  we can expand this as needed.  each item is
		#	a dict with pertinent details.
		misc_storage = []

		# We merge the following types of websocket events
		websocket_event_types = [
			'Network.webSocketFrameError',
			'Network.webSocketFrameReceived',
			'Network.webSocketFrameSent',
			'Network.webSocketWillSendHandshakeRequest',
			'Network.webSocketHandshakeResponseReceived',
			'Network.webSocketClosed'
		]

		# The timestamps provided by Chrome DevTools are "Monotonically increasing time 
		#	in seconds since an arbitrary point in the past."  What this means is they are
		#	essentially offsets (deltas) and not real timestamps.  However, the Network.requestWillBeSent
		#	also has a "wallTime" which is a UNIX timestamp.  So what we do below is set the
		#	origin_walltime which to be the earliest wallTime we've seen as this allow us to later
		#	use the "timestamps" to determine the real-world time when an event happened.
		origin_walltime  = None
		first_timestamp	 = None

		# keeps track of what ws_id belongs to which type of command, we 
		#	remove entries when we get a response
		pending_ws_id_to_cmd = {}

		# get browser version and user agent
		if self.debug: print('going to get browser version')
		response = self.get_single_ws_response('Browser.getVersion')
		if response['success'] == False:
			self.exit()
			return response
		elif 'result' not in response['result']:
			self.exit()
			return ({
				'success': False,
				'result': 'No result for ws command'
			})
		else:
			response = response['result']
		if self.debug: print(f'ws response: {response}')

		if not self.browser_type:
			self.browser_type		= re.match('^(.+)?/(.+)$',response['result']['product'])[1]
			self.browser_version 	= re.match('^(.+)?/(.+)$',response['result']['product'])[2]
			self.user_agent			= response['result']['userAgent']

		# remove 'Headless' from the user_agent
		if self.headless:
			response = self.get_single_ws_response('Network.setUserAgentOverride','"userAgent":"%s"' % self.user_agent.replace('Headless',''))
			if response['success'] == False:
				self.exit()
				return response
			elif 'result' not in response['result']:
				self.exit()
				return ({
					'success': False,
					'result': 'No result for ws command'
				})
			else:
				response = response['result']
			if self.debug: print(f'ws response: {response}')

		# enable network and domstorage when doing a network_log
		if self.debug: print('going to enable network logging')
		response = self.get_single_ws_response('Network.enable')

		if response['success'] == False:
			self.exit()
			return response
		elif 'result' not in response['result']:
			self.exit()
			return ({
				'success': False,
				'result': 'No result for ws command'
			})
		else:
			response = response['result']
		if self.debug: print(f'ws response: {response}')

		if self.debug: print('going to enable domstorage logging')
		response = self.get_single_ws_response('DOMStorage.enable')
		if response['success'] == False:
			self.exit()
			return response
		else:
			response = response['result']
		if self.debug: print(f'ws response: {response}')

		if self.debug: print('going to enable IndexedDB logging')
		response = self.get_single_ws_response('IndexedDB.enable')
		if response['success'] == False:
			self.exit()
			return response
		else:
			response = response['result']
		if self.debug: print(f'ws response: {response}')

		if self.debug: print('going to disable cache')
		response = self.get_single_ws_response('Network.setCacheDisabled','"cacheDisabled":true')
		if response['success'] == False:
			self.exit()
			return response
		else:
			response = response['result']
		if self.debug: print(f'ws response: {response}')

		# keep track of any/all websocket ids for
		#	injected scripts
		injection_ws_ids 	= []

		# this is how we link the result back to the calling script
		ws_id_to_script 	= {}

		# keep results here to return, holds dicts
		injection_results 	=  []

		# we only want to inject the js once
		sent_injections 	= False
		received_injections = False

		# this is the main loop where we get network log data
		#############################
		# DEVTOOLS NETWORK LOG DATA #
		#############################

		if self.debug: print('##############################')
		if self.debug: print(' Going to process Network Log ')
		if self.debug: print('##############################')

		# Keep track of how long we've been reading ws data
		response_loop_start = datetime.datetime.now()

		# Keetp track of when we last saw a Network event
		time_since_last_response = datetime.datetime.now()

		# Length of time since we last saw a Network event
		elapsed_no_event = 0

		# Keep track of what second we are on so we know
		#	when to scroll, is incremented whenever the second
		# 	changes (eg 1.99 -> 2.10 = 1 -> 2)
		last_second = 0

		# make sure we don't do this more than once
		sent_intial_request = False

		# We keep collecting devtools_responses in this loop until either we haven't seen 
		#	network activity for the no_event_wait value or we exceed the max_wait
		#	time.
		while True:

			# start page load
			if not sent_intial_request: 
				self.send_ws_command('Page.navigate','"url":"%s"' % url)
				sent_intial_request = True

			# update how long we've been going
			loop_elapsed = (datetime.datetime.now()-response_loop_start).total_seconds()

			# perform two scrolls once a second
			if int(loop_elapsed) > last_second:
				last_second = int(loop_elapsed)
				for i in range(0,10):
					if self.debug: print(f'{last_second} : performing scroll #{i}')
					self.do_scroll()
					self.do_scroll()

			# see if time to stop
			elapsed_no_event = (datetime.datetime.now()-time_since_last_response).total_seconds()
			
			if loop_elapsed < self.prewait:
				if self.debug: print(f'{loop_elapsed}: In prewait period')

			if loop_elapsed > self.prewait and (elapsed_no_event > self.no_event_wait or loop_elapsed > self.max_wait):
				if self.debug: print(f'{loop_elapsed} No event for {elapsed_no_event}, max_wait is {self.max_wait}, breaking Network log loop.')
				break

			# wait 3 seconds and inject scripts
			if self.injections and not sent_injections and loop_elapsed > 3:
				if self.debug: print('### JAVASCRIPT INJECTION TIME ###')

				for injection in self.injections:
					if self.debug: print(f'injecting {injection}.js')
					try:
						with open(f'./resources/injections/{injection}', 'r', encoding='utf-8') as json_file:
							js = json.dumps(json_file.read())
					except:
						self.exit()
						return ({
							'success'	: False,
							'result'	: f'Unable to inject {injection}, does the file exist?'
						})

					# don't get return value for load_ scripts
					if injection[:5] == 'load_':
						response = self.send_ws_command('Runtime.evaluate',params=f'"expression":{js},"timeout":1000,"returnByValue":false')
					else:
						response = self.send_ws_command('Runtime.evaluate',params=f'"expression":{js},"timeout":1000,"returnByValue":true')
					
					if response['success'] == False:
						self.exit()
						return response
					else: 
						# store the ws_id if we need a response, otherwise
						#	it executes and we don't bother w/response
						if injection[:5] != 'load_':
							ws_id = response['result']
							injection_ws_ids.append(ws_id)
							ws_id_to_script[ws_id] = injection

				# don't do this again
				sent_injections = True

			# try to get ws response, returns None if no response
			devtools_response = self.get_next_ws_response()

			# determine how long since we last got a response with
			#	a Network event, if we didn't get a response we wait
			#	for a second
			if devtools_response:
				
				# check if we have a response for our injected js
				if 'id' in devtools_response:
					ws_id = devtools_response['id']

					if ws_id in injection_ws_ids:
						# if result is a string this will make it pretty, otherwise just dump the 
						#	raw ouutput
						try:
							injection_results.append({
								'script_name'	: ws_id_to_script[ws_id],
								'result'		: json.dumps(devtools_response['result']['result']['value'])
								})
						except:
							injection_results.append({
								'script_name'	: ws_id_to_script[ws_id],
								'result'		: json.dumps(devtools_response['result']['result'])
								})

				if 'method' in devtools_response:
					if 'Network' in devtools_response['method']:
						time_since_last_response = datetime.datetime.now()
					else:
						if self.debug: print(f'No events for {elapsed_no_event} seconds; main loop running for {loop_elapsed}')
			else:
				if self.debug: print(f'No events for {elapsed_no_event} seconds; main loop running for {loop_elapsed}')
				time.sleep(1)
				continue

			# if we make it this far devtools_response was not None
			if self.debug: print(loop_elapsed,json.dumps(devtools_response)[:100])

			# PRESENCE OF 'METHOD' MEANS WE PROCESS LOG DATA
			if 'method' in devtools_response:
				# REQUEST
				if devtools_response['method'] == 'Network.requestWillBeSent':
					cleaned_request = self.clean_request(devtools_response['params'])
					cleaned_request['event_order'] = len(requests)

					# update global start time to measure page load time and calculate offsets
					if origin_walltime == None or cleaned_request['wall_time'] < origin_walltime:
						origin_walltime = cleaned_request['wall_time']

					if first_timestamp == None or cleaned_request['timestamp'] < first_timestamp:
						first_timestamp = cleaned_request['timestamp']

					# DOCUMENT ME
					if 'redirectResponse' in devtools_response['params']:
						redirect_response = {}
						redirect_response['response'] 		= devtools_response['params']['redirectResponse']
						redirect_response['requestId'] 		= devtools_response['params']['requestId']
						redirect_response['loaderId'] 		= devtools_response['params']['loaderId']
						redirect_response['timestamp']		= devtools_response['params']['timestamp']
						redirect_response['type'] 		 	= devtools_response['params']['type']
						redirect_response['event_order'] 	= len(responses)
						responses.append(self.clean_response(redirect_response))

						cleaned_request['redirect_response_url'] = devtools_response['params']['redirectResponse']['url']
					else:
						cleaned_request['redirect_response_url'] = None

					requests.append(cleaned_request)

				# REQUEST EXTRA INFO
				if devtools_response['method'] == 'Network.requestWillBeSentExtraInfo':
					request_extra_headers.append({
						'request_id'		: devtools_response['params']['requestId'],
						'headers'			: devtools_response['params']['headers'],
						'associated_cookies': devtools_response['params']['associatedCookies']
					})

				# RESPONSE
				if devtools_response['method'] == 'Network.responseReceived':
					responses.append(self.clean_response(devtools_response['params']))

				# RESPONSE EXTRA INFO
				if devtools_response['method'] == 'Network.responseReceivedExtraInfo':
					response_extra_headers.append({
						'request_id'		: devtools_response['params']['requestId'],
						'headers'			: devtools_response['params']['headers'],
						'blocked_cookies'	: devtools_response['params']['blockedCookies'],
					})

				# LOAD FINISHED
				if devtools_response['method'] == 'Network.loadingFinished':
					request_id = devtools_response['params']['requestId']

					load_finish_events.append({
						'encoded_data_length': 	devtools_response['params']['encodedDataLength'],
						'request_id': 			request_id,
						'timestamp': 			devtools_response['params']['timestamp'],
					})

				# WEBSOCKETS
				if devtools_response['method'] == 'Network.webSocketCreated':
					if 'initiator' in devtools_response['params']:
						this_initiator = devtools_response['params']['initiator']
					else:
						this_initiator = None

					websockets.append({
						'request_id'	: devtools_response['params']['requestId'],
						'url'			: devtools_response['params']['url'],
						'initiator'		: this_initiator,
						'event_order'	: len(websockets)
					})

				if devtools_response['method'] in websocket_event_types:
					if 'errorMessage' in devtools_response['params']:
						payload = devtools_response['params']['errorMessage']
					elif 'request' in devtools_response['params']:
						payload = devtools_response['params']['request']
					elif 'response' in devtools_response['params']:
						payload = devtools_response['params']['response']
					else:
						payload = None

					websocket_events.append({
						'request_id'	: devtools_response['params']['requestId'],
						'timestamp'		: devtools_response['params']['timestamp'],
						'event_type'	: devtools_response['method'].replace('Network.',''),
						'payload'		: payload,
						'event_order'	: len(websocket_events)
					})

				# EVENT SOURCE
				if devtools_response['method'] == 'Network.eventSourceMessageReceived':
					event_source_msgs.append({
						'internal_request_id'	: devtools_response['params']['requestId'],
						'timestamp'			: devtools_response['params']['timestamp'],
						'event_name'		: devtools_response['params']['eventName'],
						'event_id'			: devtools_response['params']['eventId'],
						'data'				: devtools_response['params']['data']
					})

				# DOMSTORAGE
				if devtools_response['method'] == 'DOMStorage.domStorageItemAdded' or devtools_response['method'] == 'DOMStorage.domStorageItemUpdated':
					dom_storage_id = devtools_response['params']['storageId']
					ds_key = (
							dom_storage_id['securityOrigin'],
							dom_storage_id['isLocalStorage'],
							devtools_response['params']['key']
					)

					dom_storage_holder[ds_key] = devtools_response['params']['newValue']

		# no need to continue processing if we got nothing back
		if len(responses) == 0:
			self.exit()
			return ({
				'success': False,
				'result': 'No responses for page'
			})

		if len(load_finish_events) == 0:
			self.exit()
			return ({
				'success': False,
				'result': 'No load_finish_events for page'
			})

		# Stop getting additional DOMStorage events
		response = self.send_ws_command('DOMStorage.disable')
		if response['success'] == False:
			self.exit()
			return response

		
		#####################
		# DEVTOOLS COMMANDS #
		#####################

		# only issue body commands for network_log
		if self.return_bodies:
			if self.debug: print('######################################')
			if self.debug: print(' Going to send response body commands ')
			if self.debug: print('######################################')

			# send commands to get response bodies
			for event in load_finish_events:
				request_id = event['request_id']
				response = self.send_ws_command('Network.getResponseBody',f'"requestId":"{request_id}"')
				if response['success'] == False:
					self.exit()
					return response
				else: 
					ws_id = response['result']
				ws_id_to_req_id[ws_id] = request_id
				pending_ws_id_to_cmd[ws_id] = 'response_body'

			if self.debug: print('\tdone')

		# No longer need Network domain enabled
		self.send_ws_command('Network.disable')
		if response['success'] == False:
			self.exit()
			return response

		# to get IndexedDB entries we need to call them based on
		#	the securityOrigin of the frame, so we need to get
		#	the frame tree first
		response = self.send_ws_command('Page.getFrameTree')
		if response['success'] == False:
			self.exit()
			return response
		else: 
			ws_id = response['result']
		
		pending_ws_id_to_cmd[ws_id] = 'frame_tree'

		if self.debug: print('############################################')
		if self.debug: print(' Going to send devtools javascript commands ')
		if self.debug: print('############################################')

		# send the ws commands to get above data
		response = self.send_ws_command('Page.getNavigationHistory')
		if response['success'] == False:
			self.exit()
			return response
		else: 
			ws_id = response['result']

		pending_ws_id_to_cmd[ws_id] = 'page_nav'

		response = self.send_ws_command('Runtime.evaluate',params='"expression":"document.documentElement.outerHTML","timeout":1000')
		if response['success'] == False:
			self.exit()
			return response
		else: 
			ws_id = response['result']
		pending_ws_id_to_cmd[ws_id] = 'page_src'

		response = self.send_ws_command('Runtime.evaluate',params='"expression":"document.documentElement.lang","timeout":1000')
		if response['success'] == False:
			self.exit()
			return response
		else: 
			ws_id = response['result']
		pending_ws_id_to_cmd[ws_id] = 'html_lang'

		# LINKS
		with open(f'./resources/injections/wbxr_links.js', 'r', encoding='utf-8') as json_file:
			js = json.dumps(json_file.read())
		
		response = self.send_ws_command('Runtime.evaluate',params=f'"expression":{js},"timeout":1000,"returnByValue":true')
		if response['success'] == False:
			self.exit()
			return response
		else: 
			ws_id = response['result']
		pending_ws_id_to_cmd[ws_id] = 'links'

		# META_DESC
		js = json.dumps("""
			document.querySelector('meta[name="description" i]').content;
		""")

		response = self.send_ws_command('Runtime.evaluate',params=f'"expression":{js},"timeout":1000,"returnByValue":true')
		if response['success'] == False:
			self.exit()
			return response
		else: 
			ws_id = response['result']
		pending_ws_id_to_cmd[ws_id] = 'meta_desc'

		# PAGE_TEXT / READABILITY_HTML
		#
		# Inject the locally downloaded copy of readability into the page
		#	and extract the content. Note you must download readability on 
		#	your own and place in the appropriate directory
		if self.return_page_text or get_text_only:
			# if we can't load readability it likely isn't installed, raise error
			try:
				with open('./resources/policyxray/Readability.js', 'r', encoding='utf-8') as json_file:
					readability_js = json_file.read()

				js = json.dumps(f"""
					var wbxr_readability = (function() {{
						{readability_js}
						var documentClone = document.cloneNode(true); 
						var article = new Readability(documentClone).parse();
						return (article);
					}}());
					wbxr_readability;
				""")
				response = self.send_ws_command('Runtime.evaluate',params=f'"expression":{js},"timeout":1000,"returnByValue":true')
				if response['success'] == False:
					self.exit()
					return response
				else: 
					ws_id = response['result']
				pending_ws_id_to_cmd[ws_id] = 'page_text'
			except:
				print('\t****************************************************')
				print('\t The Readability.js library is needed for webXray to')
				print('\t  extract text, and it appears to be missing.      ')
				print()
				print('\t Please go to https://github.com/mozilla/readability')
				print('\t  download the file Readability.js and place it     ')
				print('\t  in the directory "webxray/resources/policyxray/"  ')
				print('\t****************************************************')
				self.exit()
				return ({
					'success': False,
					'result': 'Attempting to extract text but Readability.js is not found.'
				})
		else:
			page_text 			= None
			readability_html 	= None

		if self.return_screen_shot:
			# scroll back to top for screen shot
			try:
				self.driver.execute_script('window.scrollTo(0, 0);')
			except:
				pass
			response = self.send_ws_command('Page.captureScreenshot')
			if response['success'] == False:
				self.exit()
				return response
			else: 
				ws_id = response['result']
			pending_ws_id_to_cmd[ws_id] = 'screen_shot'
		else:
			screen_shot = None

		# do cookies last
		response  = self.send_ws_command('Network.getAllCookies')
		if response['success'] == False:
			self.exit()
			return response
		else: 
			ws_id = response['result']
		pending_ws_id_to_cmd[ws_id] = 'cookies'

		# just to let us know how much work to do
		if self.debug: print('Pending ws requests: %s %s' % (url, len(pending_ws_id_to_cmd)))

		# Keep going until we get all the pending responses or 3min timeout
		while True:

			# if result is None we are either out of responses (prematurely) or
			#	we failed
			devtools_response = self.get_next_ws_response()
			if not devtools_response:
				self.exit()
				return ({
					'success': False,
					'result': 'Unable to get devtools response.'
				})

			# update how long we've been going
			loop_elapsed = (datetime.datetime.now()-response_loop_start).total_seconds()

			# if we're still processing responses after 3 min, kill it
			if loop_elapsed > 180:
				self.exit()
				return ({
					'success': False,
					'result': 'Timeout when processing devtools responses.'
				})
			
			if self.debug: print(loop_elapsed,json.dumps(devtools_response)[:250])

			# if response has an 'id' see which of our commands it goes to
			if 'id' in devtools_response:
				ws_id = devtools_response['id']

				# we don't care about this
				if ws_id not in pending_ws_id_to_cmd: continue

				# remove the current one from pending
				# if self.debug: print('Going to remove ws_id %s from pending' % ws_id)
				cmd = pending_ws_id_to_cmd[ws_id]
				del pending_ws_id_to_cmd[ws_id]
				if self.debug: print(f'Removing {ws_id}:{cmd}, pending ws_id count is %s' % len(pending_ws_id_to_cmd))

				# NAV HISTORY/FINAL_URL
				if cmd == 'page_nav':
					try:
						final_url 	= devtools_response['result']['entries'][-1]['url']
						title 		= devtools_response['result']['entries'][-1]['title']
					except:
						self.exit()
						return ({
							'success': False,
							'result': 'Unable to get final_url,title via Devtools'
						})

					# this is the first time we know it is a redirect, return now to save further wasted effort
					is_redirect = self.is_url_internal(url,final_url)
					if self.reject_redirects and (is_redirect == None or is_redirect == False):
						self.exit()
						return ({
							'success': False,
							'result': 'rejecting redirect'
						})

				# PAGE SOURCE
				elif cmd == 'page_src':
					try:
						page_source = devtools_response['result']['result']['value']
					except:
						self.exit()
						return ({
							'success': False,
							'result': 'Unable to get page_source via Devtools'
						})

				# HTML LANG
				elif cmd == 'html_lang':
					try:
						lang = devtools_response['result']['result']['value']
					except:
						self.exit()
						return ({
							'success': False,
							'result': 'Unable to get html lang via Devtools'
						})

				# RESPONSE BODIES
				elif cmd == 'response_body':
					if 'result' not in devtools_response: 
						if self.debug: print('response body error: %s' % devtools_response)
						continue

					# if we are here we already know return_bodies is true so we
					#	just have to check the reponse is either not base64 or we 
					#	do want to return base64
					if devtools_response['result']['base64Encoded'] == False or self.return_bodies_base64:
						response_bodies[ws_id_to_req_id[ws_id]] = {
								'body': 	 devtools_response['result']['body'],
								'is_base64': devtools_response['result']['base64Encoded']
						}

				# SCREENSHOT
				elif cmd == 'screen_shot':
					if 'result' in devtools_response:
						screen_shot = devtools_response['result']['data']

				# COOKIES
				elif cmd == 'cookies':
					try:
						cookies = devtools_response['result']['cookies']
					except:
						self.exit()
						return ({
							'success': False,
							'result': 'Unable to get cookies via Devtools'
						})

				# LINKS
				elif cmd == 'links':
					try:
						js_links = devtools_response['result']['result']['value']
					except:
						js_links = []

				# META_DESC
				elif cmd == 'meta_desc':
					try:
						meta_desc = devtools_response['result']['result']['value']
					except:
						meta_desc = None

				# PAGE_TEXT
				elif cmd == 'page_text':
					# if we don't get a result we don't care
					try:
						page_text 			= devtools_response['result']['result']['value']['textContent']
						readability_html 	= devtools_response['result']['result']['value']['content']
					except:
						page_text 			= None
						readability_html 	= None

				# traverse the frame tree to get all possible securityOrigins
				#	then, issue commands to the IndexedDB and CacheStorage APIs to get the
				#	object names.  at some point we may want the object contents
				#	as well, but that introduces non-trivial complexity and currently
				#	there is not a pressing need.
				elif cmd == 'frame_tree':

					# make sure we only do things once
					security_origins = set()

					# keep track of what ws_id goes to which origin for indexeddb
					pending_ws_id_to_idx_db_sec_origin = {}

					# traverse the frame tree
					security_origins.add(devtools_response['result']['frameTree']['frame']['securityOrigin'])
					if 'childFrames' in devtools_response['result']['frameTree']:
						for item in devtools_response['result']['frameTree']['childFrames']:
							if item['frame']['securityOrigin'] != '://':
								security_origins.add(item['frame']['securityOrigin'])

					# issue our devtools commands
					for security_origin in security_origins:

						# first get the IndexedDB, note we need to double-key this to the sec origin
						response = self.send_ws_command('IndexedDB.requestDatabaseNames',f'"securityOrigin":"{security_origin}"')
						if response['success'] == False:
							self.exit()
							return response
						else: 
							sub_ws_id = response['result']
						
						pending_ws_id_to_cmd[sub_ws_id] = 'idx_db_list'
						pending_ws_id_to_idx_db_sec_origin[sub_ws_id] = security_origin

						# now get the CacheStorage
						response = self.send_ws_command('CacheStorage.requestCacheNames',f'"securityOrigin":"{security_origin}"')
						if response['success'] == False:
							self.exit()
							return response
						else: 
							sub_ws_id = response['result']
						
						pending_ws_id_to_cmd[sub_ws_id] = 'cache_name_list'
					

				# we have the result of our indexeddb database names 
				#	API call, package it up to send back
				elif cmd == 'idx_db_list':
					try:
						# skip any that are empty
						if len(devtools_response['result']['databaseNames']) != 0:
							for db_name in devtools_response['result']['databaseNames']:
								misc_storage.append({
									'security_origin'	: pending_ws_id_to_idx_db_sec_origin[ws_id],
									'key'				: db_name,
									'type'				: 'indexeddb',
									'value'				: None
								})
					except:
						# it appears this can fail, my suspicion is that a frame can dissapear 
						#	before we are able to query it.  since it is a minor issue, just
						#	print warning if in debug, but otherwise ignore
						if self.debug: print('Unable to get databaseNames via Devtools',devtools_response)

				# we have the result of our cachestorage 
				#	API call, package it up to send back
				elif cmd == 'cache_name_list':
					try:
						for cache in devtools_response['result']['caches']:
							misc_storage.append({
								'type'				: 'cache_storage',
								'security_origin'	: cache['securityOrigin'],
								'key'				: cache['cacheName'],
								'value'				: None
							})
					except:
						# it appears this can fail, my suspicion is that a frame can dissapear 
						#	before we are able to query it.  since it is a minor issue, just
						#	print warning if in debug, but otherwise ignore
						if self.debug: print('Unable to get cacheName via Devtools',devtools_response)

			# we've gotten all the reponses we need, break
			if len(pending_ws_id_to_cmd) == 0: 
				if self.debug: print('Got all ws responses!')
				break
		# end ws loop

		# catch redirect to illegal url
		if not self.is_url_valid(final_url):
			self.exit()
			return ({
				'success': False,
				'result': 'Redirected to illegal url: '+final_url
			})

		# process links and mark if internal
		all_links = []
		internal_link_count = 0
		for link in js_links:
			# filtering steps
			if 'href' not in link: continue
			if len(link['href']) == 0: continue
			if link['protocol'][:4] != 'http': continue

			# get rid of trailing # and /
			if link['href'].strip()[-1:] == '#': link['href'] = link['href'].strip()[:-1]
			if link['href'].strip()[-1:] == '/': link['href'] = link['href'].strip()[:-1]

			# sometimes the text will be a dict (very rarely)
			# 	so we convert to string
			link_text = str(link['text']).strip()

			# set up the dict
			if self.is_url_internal(final_url,link['href']):
				internal_link_count += 1
				link = {
					'text'		: link_text,
					'href'		: link['href'].strip(),
					'internal'	: True
				}
			else:
				link = {
					'text'		: link_text,
					'href'		: link['href'].strip(),
					'internal'	: False
				}
			
			# only add unique links
			if link not in all_links:
				all_links.append(link)

		# fail if we don't have enough internal links
		if self.min_internal_links:
			if internal_link_count < self.min_internal_links:
				self.exit()
				return ({
					'success': False,
					'result': 'did not find enough internal links'
				})

		# reprocess domstorage into list of dicts if doing network_log
		if not get_text_only:
			if self.debug: print('Fixing domstorage')
			for ds_key in dom_storage_holder:
				if ds_key[1]:
					misc_storage_type = 'local_storage'
				else:
					misc_storage_type = 'session_storage'

				misc_storage.append({
					'security_origin'	: ds_key[0],
					'type'				: misc_storage_type,
					'key'				: ds_key[2],
					'value'				: dom_storage_holder[ds_key]
				})

		################################################
		# FIX TIMESTAMPS: ONLY NEEDED FOR NETWORK_LOG #
		################################################
		if not get_text_only:
			# See note above regarding how chrome timestamps work, in the below blocks
			#	we fix the timestamps to reflect real world time.
			if self.debug: print('Fixing timestamps')

			# likely nothing was loaded
			if not first_timestamp:
				self.exit()
				return ({
					'success': False,
					'result': 'first_timestamp was None'
				})

			# Page load time is the delta between the origin_walltime and the final_walltime
			#	we initialize final_walltime to None as if it does not get updated nothing
			#	was loaded and we failed.
			final_walltime = None

			# As we update the load_finish_event timestamps we also update the final_walltime.
			for load_finish_event in load_finish_events:
				fixed_timestamp = self.fixed_timestamp(origin_walltime, first_timestamp, load_finish_event['timestamp'])
				load_finish_event['timestamp'] = fixed_timestamp
				if final_walltime == None or fixed_timestamp > final_walltime:
					final_walltime = fixed_timestamp

			# These timestamp fixes are straightforward
			for request in requests:
				request['timestamp'] = self.fixed_timestamp(origin_walltime, first_timestamp, request['timestamp'])

			for response in responses:
				response['timestamp'] = self.fixed_timestamp(origin_walltime, first_timestamp, response['timestamp'])

			for websocket_event in websocket_events:
				websocket_event['timestamp'] = self.fixed_timestamp(origin_walltime, first_timestamp, websocket_event['timestamp'])			

			for event_source_msg in event_source_msgs:
				event_source_msg['timestamp'] = self.fixed_timestamp(origin_walltime, first_timestamp, event_source_msg['timestamp'])	

			# Session cookies have expires of -1 so we sent to None
			for cookie in cookies:
				if cookie['expires']:
					if cookie['expires'] > 0:
						cookie['expires'] = cookie['expires']
					else:
						cookie['expires'] = None

			# If origin_walltime or final_walltime are None that means
			#	we didn't record any Network.requestWillBeSent or 
			#	Network.loadingFinished events, and this was not a successful
			#	page load
			if origin_walltime == None or final_walltime == None:
				self.exit()
				return ({
					'success': False,
					'result': 'Unable to calculate load time, possible nothing was loaded'
				})
			else:
				# get seconds between the last time we got a load finish and
				#	the first request
				load_time = (datetime.datetime.fromtimestamp(final_walltime) - datetime.datetime.fromtimestamp(origin_walltime)).total_seconds()
				#load_time = 0
		else:
			# we only do a prewait if not doing network log
			load_time = self.prewait

		# if all we're doing is getting text we null out the values we don't need here
		#	as this allows us to reduce the size of any data that must go over the wire
		if get_text_only:
			all_links              = None
			requests               = None
			request_extra_headers  = None
			responses              = None
			response_extra_headers = None
			load_finish_events     = None
			websockets             = None
			websocket_events       = None
			event_source_msgs      = None
			response_bodies        = None
			cookies                = None
			misc_storage           = None
			screen_shot            = None

		# other parts of webxray expect this data format, common to all browser drivers used
		if self.debug: print('returning data on %s' % url)
		return_dict = {
			'accessed'				: origin_walltime,
			'all_links'				: all_links,
			'client_timezone'		: '_'.join(time.tzname),
			'browser_type'			: self.browser_type,
			'browser_version'		: self.browser_version,
			'prewait'				: self.prewait,
			'no_event_wait' 		: self.no_event_wait,
			'max_wait' 				: self.max_wait,
			'start_url'				: url, 
			'final_url'				: final_url,
			'title'					: title,
			'meta_desc'				: meta_desc,
			'lang'					: lang,
			'load_time'				: load_time,
			'requests'				: requests,
			'request_extra_headers'	: request_extra_headers,
			'responses'				: responses,
			'response_extra_headers': response_extra_headers,
			'load_finish_events'	: load_finish_events,
			'websockets'			: websockets,
			'websocket_events'		: websocket_events,
			'event_source_msgs'		: event_source_msgs,
			'response_bodies'		: response_bodies,
			'cookies'				: cookies,
			'misc_storage'			: misc_storage,
			'page_source'			: page_source,
			'page_text'				: page_text,
			'readability_html'		: readability_html,
			'screen_shot'			: screen_shot,
			'page_load_strategy'	: self.page_load_strategy,
			'injection_results'		: injection_results,
			'browser_incognito'		: self.incognito
		}

		# Close browser and websocket connection, if doing a crawl
		#	this happens in get_crawl_traffic
		if self.is_crawl == False: self.exit()

		# done!
		return ({
			'success': True,
			'result': return_dict
		})
	# get_scan

	def clean_request(self, request_params):
		"""
		Many of the request fields are optional so we make sure
			we make them None if not present and also normalize
			the naming convention.  Returns a dict.
		"""
		
		cleaned_request = {}

		# get non-optional values first
		cleaned_request['request_id'] 		= request_params['requestId']
		cleaned_request['loader_id'] 		= request_params['loaderId']
		cleaned_request['document_url'] 	= request_params['documentURL']
		cleaned_request['timestamp'] 		= request_params['timestamp']
		cleaned_request['wall_time'] 		= request_params['wallTime']
		cleaned_request['initiator'] 		= request_params['initiator']

		# handle optional values in main params
		if 'type' in request_params:
			cleaned_request['type'] = request_params['type']
		else:
			cleaned_request['type'] = None

		if 'frameId' in request_params:
			cleaned_request['frame_id'] = request_params['frameId']
		else:
			cleaned_request['frame_id'] = None

		if 'hasUserGesture' in request_params:
			cleaned_request['has_user_gesture'] = request_params['hasUserGesture']
		else:
			cleaned_request['has_user_gesture'] = None

		if 'redirectResponse' in request_params:
			cleaned_request['redirect_response_url'] = request_params['redirectResponse']['url']
		else:
			cleaned_request['redirect_response_url'] = None

		# for readability
		this_request = request_params['request']

		# get non-optional values first
		cleaned_request['url'] 				= this_request['url']
		cleaned_request['method'] 			= this_request['method']
		cleaned_request['headers'] 			= this_request['headers']
		cleaned_request['initial_priority'] = this_request['initialPriority']
		cleaned_request['referrer_policy'] 	= this_request['referrerPolicy']

		# handle optional values in request
		if 'urlFragment' in this_request:
			cleaned_request['url_fragment'] = this_request['urlFragment']
		else:
			cleaned_request['url_fragment'] = None

		if 'postData' in this_request:
			cleaned_request['post_data'] = this_request['postData']
		else:
			cleaned_request['post_data'] = None

		if 'mixedContentType' in this_request:
			cleaned_request['mixed_content_type'] = this_request['mixedContentType']
		else:
			cleaned_request['mixed_content_type'] = None

		if 'isLinkPreload' in this_request:
			cleaned_request['is_link_preload'] = this_request['isLinkPreload']
		else:
			cleaned_request['is_link_preload'] = None

		# done!
		return cleaned_request
	# clean_request

	def clean_response(self, response_params):
		"""
		Many of the response fields are optional so we make sure
			we make them None if not present and also normalize
			the naming convention.  Returns a dict.
		"""

		cleaned_response = {}

		# get non-optional param values first
		cleaned_response['request_id'] 	= response_params['requestId']
		cleaned_response['loader_id'] 	= response_params['loaderId']
		cleaned_response['timestamp'] 	= response_params['timestamp']
		cleaned_response['type'] 		= response_params['type']

		# handle optional param values
		if 'frameId' in response_params:
			cleaned_response['frame_id'] = response_params['frameId']
		else:
			cleaned_response['frame_id'] = None

		# handle non-optional reponse values
		this_response = response_params['response']

		cleaned_response['url'] 				= this_response['url']
		cleaned_response['status'] 				= this_response['status']
		cleaned_response['status_text']			= this_response['statusText']
		cleaned_response['response_headers'] 	= this_response['headers']
		cleaned_response['mime_type'] 			= this_response['mimeType']
		cleaned_response['connection_reused'] 	= this_response['connectionReused']
		cleaned_response['connection_id']		= this_response['connectionId']
		cleaned_response['encoded_data_length'] = this_response['encodedDataLength']
		cleaned_response['security_state'] 		= this_response['securityState']

		# handle optional response values
		if 'requestHeaders' in this_response:
			cleaned_response['request_headers'] = this_response['requestHeaders']
		else:
			cleaned_response['request_headers'] = None

		if 'remoteIPAddress' in this_response:
			cleaned_response['remote_ip_address'] = this_response['remoteIPAddress']
		else:
			cleaned_response['remote_ip_address'] = None

		if 'remotePort' in this_response:
			cleaned_response['remote_port'] = this_response['remotePort']
		else:
			cleaned_response['remote_port'] = None

		if 'fromDiskCache' in this_response:
			cleaned_response['from_disk_cache'] = this_response['fromDiskCache']
		else:
			cleaned_response['from_disk_cache'] = None

		if 'fromServiceWorker' in this_response:
			cleaned_response['from_service_worker'] = this_response['fromServiceWorker']
		else:
			cleaned_response['from_service_worker'] = None

		if 'fromPrefetchCache' in this_response:
			cleaned_response['from_prefetch_cache'] = this_response['fromPrefetchCache']
		else:
			cleaned_response['from_prefetch_cache'] = None

		if 'timing' in this_response:
			cleaned_response['timing'] = this_response['timing']
		else:
			cleaned_response['timing'] = None

		if 'protocol' in this_response:
			cleaned_response['protocol'] = this_response['protocol']
		else:
			cleaned_response['protocol'] = None

		if 'securityDetails' in this_response:
			cleaned_response['security_details'] = this_response['securityDetails']
		else:
			cleaned_response['security_details'] = None

		# done!
		return cleaned_response
	# clean_response

	def fixed_timestamp(self,origin_walltime,first_timestamp,timestamp):
		"""
		See notes above for details.
		"""
		# first calculate the timestamp offset
		elapsed_time = timestamp - first_timestamp

		# now add offset to the origin time to get the real time
		return origin_walltime + elapsed_time
	# fixed_timestamp

	def is_url_valid(self, url):
		"""
		Performs checks to verify if the url can actually be
			scanned.
		"""

		# only do http links
		if not (re.match('^https?://.+', url)): return False

		# if we can't get the url_path it is invalid
		try:
			url_path = urlsplit(url.strip().lower()).path
		except:
			return False
		
		# these are common file types we want to avoid
		illegal_extensions = [
			'apk',
			'dmg',
			'doc',
			'docx',
			'exe',
			'ics',
			'iso',
			'pdf',
			'ppt',
			'pptx',
			'rtf',
			'txt',
			'xls',
			'xlsx'
		]

		# if we can't parse the extension it doesn't exist and is
		#	therefore ok by our standards
		try:
			url_extension = re.search('\.([0-9A-Za-z]+)$', url_path).group(1)
			if url_extension in illegal_extensions: return False
		except:
			return True
		
		# it's good
		return True
	# is_url_valid

	def idna_encode_url(self, url, no_fragment=False):
		"""
		Non-ascii domains will crash some browsers, so we need to convert them to 
			idna/ascii/utf-8. This requires splitting apart the url, converting the 
			domain to idna, and pasting it all back together.  Note that this can fail,
			particularly in regards to idna encoding of invalid addresses (eg http://.example.com)
			so we return None in fail event.
		"""
		try:
			split_url = urlsplit(url.strip())
			idna_fixed_netloc = split_url.netloc.encode('idna').decode('utf-8')
			if no_fragment:
				return urlunsplit((split_url.scheme,idna_fixed_netloc,split_url.path,split_url.query,''))
			else:
				return urlunsplit((split_url.scheme,idna_fixed_netloc,split_url.path,split_url.query,split_url.fragment))
		except:
			return None
	# idna_encode_url

	def is_url_internal(self,origin_url,target_url):
		"""
		Given two urls (origin, target) determines if 
			the target is internal to the origin based on
			subsuffix+1 domain.
		"""

		origin_domain 	= self.url_parser.get_parsed_domain_info(origin_url)
		target_domain	= self.url_parser.get_parsed_domain_info(target_url)

		# we return None to signify we couldn't parse the urls
		if not origin_domain['success'] or not target_domain['success']:
			return None
		else:
			origin_domain 	= origin_domain['result']['domain']
			target_domain  	= target_domain['result']['domain']

		if origin_domain != target_domain:
			return False
		else:
			return True
	# is_url_internal

	def do_scroll(self):
		"""
		Performs a random scroll action on Y axis, can be called at regular
			intervals to surface content on pages.
		"""
		self.send_ws_command('Input.dispatchMouseEvent','"x":0,"y":0,"type":"mouseWheel","deltaX":0,"deltaY":%s' % random.randrange(10,100))
	# do_scroll

# ChromeDriver
