#class Decklists
from bs4 import BeautifulSoup
import requests
import re
import concurrent.futures

class Player:
	def __init__(self, surname, lastname, country, level, decklist):
		self.FirstName = surname
		self.LastName = lastname
		self.Division = level
		self.Country = country
		self.json_decklist = RK9ToJSON(decklist)

def RK9ToJSON(page):
	output = '{'
	soup = BeautifulSoup(page.content, "lxml")
	table = soup.find("table", {"class":"decklist"})
	pokemonList = table.find("ul", {"class":"pokemon"})
	trainerList = table.find("ul", {"class":"trainer"})
	energyList = table.find("ul", {"class":"energy"})
	pokemons = None
	if pokemonList != None:
		pokemons = pokemonList.find_all("li")
	trainers = None
	if trainerList != None:
		trainers = trainerList.find_all("li")
	energies = None
	if energyList != None:
		energies = energyList.find_all("li")
	output = output + '"pokemon":['
	groupData = ""
	if pokemons != None:
		for card in pokemons:
			count = card.get("data-quantity")
			name = card.get("data-cardname")
			setnumber = card.get("data-setnum")
			number = setnumber.split("-")[1]
			set = setnumber.split("-")[0]
			data = '{"count":' + count + ', "name": "' + name + '", "number":"' + number + '", "set": "' + set + '"}'
			if(len(groupData) > 0):
				groupData = groupData + ","
			groupData = groupData + data
	output = output + groupData
	output = output + ']'

	output = output + ',"trainer":['
	groupData = ""
	if trainers != None:
		for card in trainers:
			count = card.get("data-quantity")
			name = card.get("data-cardname")
			setnumber = card.get("data-setnum")
			if len(setnumber) > 0:
				number = setnumber.split("-")[1]
				set = setnumber.split("-")[0]
				data = '{"count":' + count + ', "name": "' + name + '", "number":"' + number + '", "set": "' + set + '"}'
				if(len(groupData) > 0):
					groupData = groupData + ","
				groupData = groupData + data
	output = output + groupData
	output = output + ']'
	
	output = output + ',"energy":['
	groupData = ""
	if energies != None:
		for card in energies:
			count = card.get("data-quantity")
			name = card.get("data-cardname")
			setnumber = card.get("data-setnum")
			number = 'null'
			set = 'null'
			if(len(setnumber) > 0):
				number = setnumber.split("-")[1]
				set = setnumber.split("-")[0]
			data = '{"count":' + count + ', "name": "' + name + '", "number":"' + number + '", "set": "' + set + '"}'
			if(len(groupData) > 0):
				groupData = groupData + ","
			groupData = groupData + data
	output = output + groupData
	output = output + ']'

	output = output + '}'
	return output

def get_status(url, surname, lastname, country, level):
	return Player(surname, lastname, country, level, requests.get(url=url))

class Decklists:
	def __init__(self, url):
		self.players = []
		urls = []
		surnames = []
		lastnames = []
		countries = []
		levels = []
		url = 'https://rk9.gg/roster/' + url
		page = requests.get(url)
		soup = BeautifulSoup(page.content, "lxml")
		table = soup.find("table", {"id":"dtLiveRoster"})
		thead = table.find("thead")
		tr = thead.find('tr')
		ths = tr.find_all('th')
		idIndex = -1
		fnIndex = -1
		lnIndex = -1
		cnIndex = -1
		divIndex = -1
		dlIndex = -1
		currentIndex = 0
		for th in ths:
			if th != None:
				if 'ID' in th.text.upper():
					idIndex = currentIndex
				if 'FIRST' in th.text.upper():
					fnIndex = currentIndex
				if 'LAST' in th.text.upper():
					lnIndex = currentIndex
				if 'COUNTRY' in th.text.upper():
					cnIndex = currentIndex
				if 'DIV' in th.text.upper():
					divIndex = currentIndex
				if 'LIST' in th.text.upper():
					dlIndex = currentIndex
				currentIndex += 1
		tbody = table.find("tbody")
		trs = tbody.find_all("tr")
		for tr in trs:
			if tr != None:
				tds = tr.find_all("td")
				surname = ''
				if(fnIndex > -1):
					surname = tds[fnIndex].text.replace("\n\n", " ").strip()
				lastname = ''
				if(lnIndex > -1):
					lastname = tds[lnIndex].text.replace("\n\n", " ").strip()
				country = ''
				if(cnIndex > -1):
					country = tds[cnIndex].text.replace("\n\n", " ").strip()
				level = ''
				if(divIndex > -1):
					level = tds[divIndex].text.replace("\n\n", " ").strip()
				if(level == "Junior"):
					level = "Juniors"
				if(level == "Senior"):
					level = "Seniors"
				listText = ''
				if(dlIndex > -1):
					listText = tds[dlIndex].text.strip().replace(" ", "").replace("\n\n", " ")
				if(listText == "View"):
					a = tds[dlIndex].find('a', href=True)
					urls.append("https://rk9.gg/" + a['href'])
					surnames.append(surname)
					lastnames.append(lastname)
					countries.append(country)
					levels.append(level)
		#threading
		with concurrent.futures.ThreadPoolExecutor() as executor:
			futures = []
			for i in range(0, len(urls)):
				futures.append(executor.submit(get_status, url=urls[i], surname=surnames[i], lastname=lastnames[i], country=countries[i], level=levels[i]))

			for future in concurrent.futures.as_completed(futures):
				self.players.append(future.result())
