# standard python libs
import os
import re
import json

# custom webxray classes
from webxray.ParseURL import ParseURL

class SingleScan:
	"""
	Loads and analyzes a single page, print outputs to cli
	Very simple and does not require a db being configured
	"""

	def __init__(self):
		self.url_parser		= ParseURL()
		self.domain_owners 	= {}
		self.id_to_owner	= {}
		self.id_to_parent	= {}

		# set up the domain ownership dictionary
		for item in json.load(open('./resources/domain_owners/domain_owners.json', 'r', encoding='utf-8')):
			if item['id'] == '-': continue

			self.id_to_owner[item['id']] 	= item['name']
			self.id_to_parent[item['id']] 	= item['parent_id']
			for domain in item['domains']:
				self.domain_owners[domain] = item['id']
	# end init

	def get_lineage(self, id):
		"""
		Find the upward chain of ownership for a given domain.
		"""
		if self.id_to_parent[id] == None:
			return [id]
		else:
			return [id] + self.get_lineage(self.id_to_parent[id])
	# end get_lineage

	def execute(self, url, config):
		"""
		Main function, loads page and analyzes results.
		"""

		print(f'Single Site Test On: {url}')
		print(f' - Browser type is {config["client_browser_type"]}')
		print(f' - Browser max wait time is {config["client_max_wait"]} seconds')
		print('\nImportant Note: ')
		print('\tIf you run more than one single test at a time ')
		print('\tyou will encounter errors - some of which are silent!')

		# make sure it is an http(s) address
		if not re.match('^https?://', url): 
			print('\tNot a valid url, aborting')
			return None

		# import and set up specified browser driver
		if config['client_browser_type'] == 'chrome':
			from webxray.ChromeDriver	import ChromeDriver
			browser_driver 	= ChromeDriver(config)
		else:
			print('INVALID BROWSER TYPE FOR %s, QUITTING!' % config['client_browser_type'])
			exit()

		# attempt to get the page
		browser_output = browser_driver.get_scan(url)

		# if there was a problem we print the error
		if browser_output['success'] == False:
			print(f'Browser Error: {browser_output["result"]}')
			return
		else:
			browser_output = browser_output['result']

		# get the ip, fqdn, domain, pubsuffix, and tld from the URL
		# we need the domain to figure out if cookies/elements are third-party
		origin_ip_fqdn_domain_pubsuffix_tld	= self.url_parser.get_ip_fqdn_domain_pubsuffix_tld(url)

		# if we can't get page domain info we bail out
		if origin_ip_fqdn_domain_pubsuffix_tld is None:
			print('could not parse origin domain')
			return None

		origin_ip 			= origin_ip_fqdn_domain_pubsuffix_tld[0]
		origin_fqdn 		= origin_ip_fqdn_domain_pubsuffix_tld[1]
		origin_domain 		= origin_ip_fqdn_domain_pubsuffix_tld[2]
		origin_pubsuffix 	= origin_ip_fqdn_domain_pubsuffix_tld[3]
		origin_tld 			= origin_ip_fqdn_domain_pubsuffix_tld[4]

		print('\n------------------{ URL }------------------')
		print(url)
		print('\n------------------{ Final URL }------------------')
		print(browser_output['final_url'])
		print('\n------------------{ Title }------------------')
		print(browser_output['title'])
		print('\n------------------{ Description }------------------')
		print(browser_output['meta_desc'])
		print('\n------------------{ Domain }------------------')
		print(origin_domain)
		print('\n------------------{ Seconds to Complete Download }------------------')
		print(browser_output['load_time'])
		print('\n------------------{ Incognito Mode Status }------------------')
		print(browser_output['browser_incognito'])
		print('\n------------------{ Cookies }------------------')
		# put relevant fields from cookies into list we can sort
		cookie_list = []
		for cookie in browser_output['cookies']:
			cookie_list.append(cookie['domain']+' -> '+cookie['name']+' -> '+cookie['value'])

		cookie_list.sort()
		for count,cookie in enumerate(cookie_list):
			print(f'\t[{count}] {cookie}')
			
		print('\n------------------{ LocalStorage }------------------')
		for item in browser_output['misc_storage']:
			if item['type'] == 'local_storage':	print(f"\t{item['security_origin']}: {item['key']}")

		print('\n------------------{ SessionStorage }------------------')
		for item in browser_output['misc_storage']:
			if item['type'] == 'session_storage':	print(f"\t{item['security_origin']}: {item['key']}")

		print('\n------------------{ IndexedDB }------------------')
		for item in browser_output['misc_storage']:
			if item['type'] == 'indexeddb':	print(f"\t{item['security_origin']}: {item['key']}")

		print('\n------------------{ CacheStorage }------------------')
		for item in browser_output['misc_storage']:
			if item['type'] == 'cache_storage':	print(f"\t{item['security_origin']}: {item['key']}")

		print('\n------------------{ Domains Requested }------------------')
		request_domains = set()

		for request in browser_output['requests']:
			# if the request starts with 'data'/etc we can't parse tld anyway, so skip
			if re.match('^(data|about|chrome|blob|file).+', request['url']):
				continue

			# parse domain from the requested url
			domain_info = self.url_parser.get_parsed_domain_info(request['url'])
			if domain_info['success'] == False:
				print(f'Unable to parse domain info for {request["url"]} with error {domain_info["result"]}')
				continue

			# if origin_domain != domain_info['result']['domain']:
			request_domains.add(domain_info['result']['domain'])
		
		count = 0
		for domain in sorted(request_domains):
			count += 1
			if domain in self.domain_owners:
				lineage = ''
				for item in self.get_lineage(self.domain_owners[domain]):
					lineage += self.id_to_owner[item]+' > '
				print(f'\t{count}) {domain} [{lineage[:-3]}]')
			else:
				print(f'\t{count}) {domain} [Unknown Owner]')

		if len(browser_output['injection_results']) != 0:
			print('\n------------------{ Injection Results }------------------')
			for injection in browser_output['injection_results']:
				print(f"\t{injection['script_name']}")
				print(f"\t\t{injection['result']}")

	# end execute
# end SingleScan
