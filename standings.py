import argparse
import time
import requests
import json
from bs4 import BeautifulSoup
import cchardet
import os

class Player:
	def __init__(self):
		self.FirstName = None
		self.LastName = None
		self.Country = None
		self.Division = None
		self.TrainerName = None
		self.TeamList = None
		self.DeckList = None
		self.InternalID = None
		
		self.Dropped = 999
		self.Late = False
		self.DQed = False

		self.Wins = 0
		self.Losses = 0
		self.Ties = 0
		self.Points = 0

		self.topCutPlayed = 0
		self.topCutWon = 0

		self.WinPercentage = 0.25
		self.OppWinPercentage = 0.25
		self.OppOppWinPercentage = 0.25

		self.Rounds = {}


def getPlayerData(soup, table, soupOpp):
	data = {}
	data['dropped'] = False
	data['result'] = None
	if('winner' in soup['class']):
		data['result'] = 3
	if('tie' in soup['class']):
		data['result'] = 1
	if('loser' in soup['class']):
		data['result'] = 0
	if('dropped' in soup['class']):
		data['dropped'] = True
		if(data['result'] == None):
			data['result'] = 0
	name = soup.find('span', attrs={'class':'name'})
	data['country'] = None
	data['late'] = False
	if(name):
		data['name'] = name.text.split(' [')[0]
		if(len(name.text.split(' [')) > 1):
			data['country'] = name.text.split(' [')[1].replace(']', '')
	else:
		data['name'] = 'BYE'
		if(not 'winner' in soupOpp['class'] and not 'tie' in soup['class'] and not 'loser' in soup['class'] and not 'dropped' in soup['class']):
			data['name'] = 'LATE'
	score = soup.text.split(' (')
	data['score'] = [0, 0, 0]
	data['record'] = '0-0-0'
	data['table'] = table
	data['points'] = 0
	data['bye'] = False
	if(soupOpp.find('span', attrs={'class':'name'}) == None):
		if(data['result'] == None):
			data['result'] = 0
			data['late'] = True
		if(data['result'] == 3):
			data['bye'] = True
	if(len(score) > 1):
		score = score[1].split(') ')[0]
		data['record'] = score
		score = score.split('-')
		data['score'] = [score[0], score[1], score[2]]
		data['points'] = int(score[0])*3+int(score[2])
	return data

class Standings:
	def __init__(self, rk9id, retrieve_decklists):
		self.RK9_id = rk9id
		self.Retrieve_decklists = retrieve_decklists
		self.Tournament_started = {}
		
		self.Variant = 'TCG2'
		self.Rounds_data = {}
		self.official_standings = {}
		"""
		Pods:
		0 = Juniors
		2 = Masters
		9 = Seniors
		"""
		self.last_InternalID = 0
		self.lookup_table_names = {}
		self.lookup_table_players = {}
		self.players = {}
		#Pods:
		#0 = Junior
		#2 = Masters
		#9 = Senior			
		self.pods = ['0', '2', '9']
		for pod in self.pods:
			self.Tournament_started[pod] = False
			self.Rounds_data[pod] = {}
			self.Rounds_data[pod]['rounds'] = {}
			self.Rounds_data[pod]['structure'] = {}
			self.Rounds_data[pod]['structure']['day1'] = 0
			self.Rounds_data[pod]['structure']['day2'] = 0
			self.Rounds_data[pod]['structure']['topcut'] = 0
			self.official_standings[pod] = []
			self.players[pod] = []
	

	def GetWinPercentage(self, player, pod, round, round_data, type):
		start = 0
		stop = 0
		if(player['Dropped'] >= round):
			if(round <= round_data[pod]['structure']['day1']):
				start = 1
				stop = round_data[pod]['structure']['day1']+1
			if(round > round_data[pod]['structure']['day1'] and round <= round_data[pod]['structure']['day1']+round_data[pod]['structure']['day2']):
				start = round_data[pod]['structure']['day1']+1
				stop = round_data[pod]['structure']['day1']+round_data[pod]['structure']['day2']+1

		if(type == 0):#Win percentage
			wins = 0
			losses = 0
			ties = 0
			for r in range(start, stop):
				if(r in player['Rounds'] and player['Rounds'][r]['bye'] == False):
					if(player['Rounds'][r]['result'] == 3):
						wins += 1
					if(player['Rounds'][r]['result'] == 0):
						losses += 1
					if(player['Rounds'][r]['result'] == 1):
						ties += 1
			if(wins+ties+losses == 0):
				return 0.25
			percentage = (wins+ties*0.5)/(wins+ties+losses)
			if(percentage < 0.25):
				return 0.25
			if(player['Dropped'] != 999 and percentage > 0.75):
				return 0.75
			return percentage
		
		if(type == 1):#Opps' Win percentage
			count = 0
			percentage = 0
			for r in range(start, stop):
				if(r in player['Rounds'] and player['Rounds'][r]['bye'] == False and player['Rounds'][r]['late'] == False):
					pl = self.lookup_table_players[player['Rounds'][r]['opp']]
					percentage += pl['WinPercentage']
					count += 1
			if(count > 0):
				return percentage/count
			return player['OppWinPercentage']

		if(type == 2):#Opps' Opps' Win percentage
			count = 0
			percentage = 0
			for r in range(start, stop):
				if(r in player['Rounds'] and player['Rounds'][r]['bye'] == False and player['Rounds'][r]['late'] == False):
					pl = self.lookup_table_players[player['Rounds'][r]['opp']]
					percentage += pl['OppWinPercentage']
					count += 1
			if(count > 0):
				return percentage/count
			return player['OppOppWinPercentage']
		return 0.25
	
	def Compute(self, pod, current_round, rounds_data):
		self.lookup_table_players = {}
		for player in self.players[pod]:
			self.lookup_table_players[player['InternalID']] = player
			#if(player['Dropped'] == False and player['FirstName'] != 'BYE' and player['FirstName'] != 'LATE' and round in player['Rounds']):
			if(player['FirstName'] != 'BYE' and player['FirstName'] != 'LATE' and current_round in player['Rounds']):
				player['Rounds'][current_round]['points'] = player['Rounds'][current_round]['result']
				if(current_round > 1):
					player['Rounds'][current_round]['points'] += player['Rounds'][current_round-1]['points']
				player['Points'] = player['Rounds'][current_round]['points']
				player['Wins'] = player['Ties'] = player['Losses'] = player['topCutPlayed'] = player['topCutWon'] = 0
				for r in range(1, current_round+1):
					if(r > rounds_data[pod]['structure']['day1']+rounds_data[pod]['structure']['day2']):
						player['topCutPlayed'] += 1
						if(player['Rounds'][r]['result'] == 3):
							player['topCutWon'] += 1
					if(player['Rounds'][r]['result'] == 3):
						player['Wins'] += 1
					if(player['Rounds'][r]['result'] == 1):
						player['Ties'] += 1
					if(player['Rounds'][r]['result'] == 0):
						player['Losses'] += 1
				player['WinPercentage'] = self.GetWinPercentage(player, pod, current_round, rounds_data, 0)
		#compute resistances only if before topcut
		if(current_round <= rounds_data[pod]['structure']['day1']+rounds_data[pod]['structure']['day2']):
			for player in self.players[pod]:
				player['OppWinPercentage'] = self.GetWinPercentage(player, pod, current_round, rounds_data, 1)
			for player in self.players[pod]:
				player['OppOppWinPercentage'] = self.GetWinPercentage(player, pod, current_round, rounds_data, 2)
		self.players[pod] = sorted(self.players[pod], key=lambda k: (k['DQed'], -(k['topCutWon']), -(k['topCutPlayed']), -(k['Points']), (k['Late']), -(round(k['OppWinPercentage'], 4)), -(round(k['OppOppWinPercentage'], 4))))

	def addData(self, pod, p1, p2, table, round, official_standings):
		player1 = None
		player2 = None
		p1InternalID = p2InternalID = 0
		
		for player in self.players[pod]:
			if(player1 == None and (player['FirstName']+player['LastName']).replace(' ', '') == p1['name'].replace(' ', '')):
				if(p1['country'] == None or p1['country'] == player['Country']):
					if(round == 1 or (round-1 in player['Rounds'] and ((p1['result'] == None and player['Rounds'][round-1]['record'] == p1['record']) or (p1['points']-p1['result'] == player['Rounds'][round-1]['points'])))):
						if(round not in player['Rounds'] or p2['name'] == self.lookup_table_names[player['Rounds'][round]['opp']]):
							player1 = player
							p1InternalID = player['InternalID']
			if(player2 == None and (player['FirstName']+' '+player['LastName']).replace(' ', '') == p2['name'].replace(' ', '')):
				if(p2['country'] == None or p2['country'] == player['Country']):
					if(round == 1 or (round-1 in player['Rounds'] and ((p2['result'] == None and player['Rounds'][round-1]['record'] == p2['record']) or (p2['points']-p2['result'] == player['Rounds'][round-1]['points'])))):
						if(round not in player['Rounds'] or p1['name'] == self.lookup_table_names[player['Rounds'][round]['opp']]):
							player2 = player
							p2InternalID = player['InternalID']
			if(player1 != None and player2 != None):
				break
		
		if(player1 == None and round == 1 and p1['name'] != 'BYE' and p1['name'] != 'LATE'):
			player = Player()
			player.FirstName = ' '.join(p1['name'].split(' ')[:-1])
			player.LastName = p1['name'].split(' ')[-1]
			player.Country = p1['country']
			player.InternalID = self.last_InternalID
			self.last_InternalID += 1
			self.players[pod].append(player.__dict__)
			player1 = self.players[pod][len(self.players[pod])-1]
			p1InternalID = player1['InternalID']
			self.lookup_table_names[p1InternalID] = p1['name']
		if(player2 == None and round == 1 and p2['name'] != 'BYE' and p2['name'] != 'LATE'):
			player = Player()
			player.FirstName = ' '.join(p2['name'].split(' ')[:-1])
			player.LastName = p2['name'].split(' ')[-1]
			player.Country = p2['country']
			player.InternalID = self.last_InternalID
			self.last_InternalID += 1
			self.players[pod].append(player.__dict__)
			player2 = self.players[pod][len(self.players[pod])-1]
			p2InternalID = player2['InternalID']
			self.lookup_table_names[p2InternalID] = p2['name']
		
		if(player1 != None):
			if(p1['dropped'] == True):
				player1['Dropped'] = round
			if(p1['late'] == True and round == 1):
				player1['Late'] = True
			if(len(official_standings[pod])> 0):
				if(not player1['FirstName']+' '+player1['LastName'] in official_standings[pod]):
					player1['DQed'] = True
			player1['Rounds'][round] = {'dropped':p1['dropped'],'opp':p2InternalID,'bye':p1['bye'],'late':p1['late'],'table':table, 'result':p1['result'], 'record':p1['record'], 'points':p1['points']}
		if(player2 != None):
			if(p2['dropped'] == True):
				player2['Dropped'] = round
			if(p2['late'] == True and round == 1):
				player2['Late'] = True
			if(len(official_standings[pod])> 0):
				if(not player2['FirstName']+' '+player2['LastName'] in official_standings[pod]):
					player2['DQed'] = True
				player2['Rounds'][round] = {'dropped':p2['dropped'],'opp':p1InternalID,'bye':p2['bye'],'late':p2['late'],'table':table, 'result':p2['result'], 'record':p2['record'], 'points':p2['points']}
				
	def Save(self, pod, round, path):
		if(not os.path.exists(path)):
			os.mkdir(path)
		if(not os.path.exists(path + '/' + self.RK9_id)):
			os.mkdir(path + '/' + self.RK9_id)
		if(not os.path.exists(path + '/' + self.RK9_id + '/' + str(pod))):
			os.mkdir(path + '/' + self.RK9_id + '/' + str(pod))
		with open(path + '/' + self.RK9_id + '/' + str(pod) + '/' + str(round) + '.json', "w", encoding='utf-8') as f:
			f.write(json.dumps(self.players[pod], indent=4, ensure_ascii=False))
	
	def CompareStandings(self, pod, officials, path):
		if(not os.path.exists(path)):
			os.mkdir(path)
		if(not os.path.exists(path + '/' + self.RK9_id)):
			os.mkdir(path + '/' + self.RK9_id)
		if(not os.path.exists(path + '/' + self.RK9_id + '/' + str(pod))):
			os.mkdir(path + '/' + self.RK9_id + '/' + str(pod))
		with open(path + '/' + self.RK9_id + '/' + str(pod) + '/discrepancies.txt', "w", encoding='utf-8') as f:
			counter = 1
			for p1, p2 in zip(self.players[pod], officials[pod]):
				if(p1['FirstName'] + ' ' + p1['LastName'] != p2):
					f.write(str(counter) + '\tcomputed : ' + p1['FirstName'] + ' ' + p1['LastName'] + '\tofficial : '+ p2 + '\n')
				counter += 1


	def GetRounds(self, content, pod):
		soup = BeautifulSoup(content, 'lxml')
		nbPlayers = len(soup.find_all('span', attrs={'class':'name'}))
		if(self.Variant == 'TCG2' or self.Variant == 'VGC2'):
			if(4 <= nbPlayers <= 8):
				self.Rounds_data[pod]['structure']['day1'] = 3
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 0
			if(9 <= nbPlayers <= 12):
				self.Rounds_data[pod]['structure']['day1'] = 4
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 2
			if(13 <= nbPlayers <= 20):
				self.Rounds_data[pod]['structure']['day1'] = 5
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 2
			if(21 <= nbPlayers <= 32):
				self.Rounds_data[pod]['structure']['day1'] = 5
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(33 <= nbPlayers <= 64):
				self.Rounds_data[pod]['structure']['day1'] = 6
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(65 <= nbPlayers <= 128):
				self.Rounds_data[pod]['structure']['day1'] = 7
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(129 <= nbPlayers <= 226):
				self.Rounds_data[pod]['structure']['day1'] = 8
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(227 <= nbPlayers <= 799):
				self.Rounds_data[pod]['structure']['day1'] = 9
				self.Rounds_data[pod]['structure']['day2'] = 5
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(nbPlayers >= 800):
				self.Rounds_data[pod]['structure']['day1'] = 9
				self.Rounds_data[pod]['structure']['day2'] = 6
				self.Rounds_data[pod]['structure']['topcut'] = 3
		if(self.Variant == "TCG1"):
			if(4 and nbPlayers < 9):
				self.Rounds_data[pod]['structure']['day1'] = 3
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 0
			if(9 <= nbPlayers <= 12):
				self.Rounds_data[pod]['structure']['day1'] = 4
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 2
			if(13 <= nbPlayers <= 20):
				self.Rounds_data[pod]['structure']['day1'] = 5
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 2
			if(21 <= nbPlayers <= 32):
				self.Rounds_data[pod]['structure']['day1'] = 5
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(33 <= nbPlayers <= 64):
				self.Rounds_data[pod]['structure']['day1'] = 6
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(65 <= nbPlayers <= 128):
				self.Rounds_data[pod]['structure']['day1'] = 7
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(129 <= nbPlayers <= 226):
				self.Rounds_data[pod]['structure']['day1'] = 8
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(227 <= nbPlayers <= 409):
				self.Rounds_data[pod]['structure']['day1'] = 9
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(410 <= nbPlayers):
				self.Rounds_data[pod]['structure']['day1'] = 10
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
		if(self.Variant == "VGC1"):
			if(4 and nbPlayers < 8):
				self.Rounds_data[pod]['structure']['day1'] = 3
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 0
			if(nbPlayers == 8):
				self.Rounds_data[pod]['structure']['day1'] = 3
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 1
			if(9 <= nbPlayers <= 16):
				self.Rounds_data[pod]['structure']['day1'] = 4
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 2
			if(17 <= nbPlayers <= 32):
				self.Rounds_data[pod]['structure']['day1'] = 5
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(33 <= nbPlayers <= 64):
				self.Rounds_data[pod]['structure']['day1'] = 6
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(65 <= nbPlayers <= 128):
				self.Rounds_data[pod]['structure']['day1'] = 7
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(129 <= nbPlayers <= 226):
				self.Rounds_data[pod]['structure']['day1'] = 8
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 3
			if(227 <= nbPlayers <= 256):
				self.Rounds_data[pod]['structure']['day1'] = 8
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 4
			if(257 <= nbPlayers <= 409):
				self.Rounds_data[pod]['structure']['day1'] = 9
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 4
			if(410 <= nbPlayers <= 512):
				self.Rounds_data[pod]['structure']['day1'] = 9
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 5
			if(nbPlayers >= 513):
				self.Rounds_data[pod]['structure']['day1'] = 10
				self.Rounds_data[pod]['structure']['day2'] = 0
				self.Rounds_data[pod]['structure']['topcut'] = 5
		for r in range(1, self.Rounds_data[pod]['structure']['day1']+self.Rounds_data[pod]['structure']['day2']+self.Rounds_data[pod]['structure']['topcut']+1):
			self.Rounds_data[pod]['rounds'][r] = {}
			self.Rounds_data[pod]['rounds'][r]['data'] = None

	def update(self, standings):
		if(standings):
			r = requests.get('https://rk9.gg/pairings/'+self.RK9_id, timeout=60) #check if Masters (P2) round 1 has started yet
			if(r.status_code == 200):
				if(len(r.content) > 0):
					soup = BeautifulSoup(r.content, 'lxml')
					for pod in self.pods:
						official_standing = soup.find('div', attrs={'id':'P'+pod+'-standings'})
						if(official_standing != None):
							self.official_standings[pod] = []
							rank = 1
							for i in range(0, len(official_standing.contents), 2):
								s = official_standing.contents[i].text.strip().replace(str(rank)+'. ', '')
								rank += 1
								s = s.split(' ')
								n = ""
								country = 0
								if(s[len(s)-1][0] == '[' and len(s[len(s)-1]) == 4 and s[len(s)-1][3] == ']'):
									country = 1
								for j in range(0, len(s)-country):
									n += s[j] + ' '
								n = n.strip()
								self.official_standings[pod].append(n)		
		for pod in self.pods:
			r = None
			if(not self.Tournament_started[pod]):
				r = requests.get('https://rk9.gg/pairings/'+self.RK9_id+'?pod='+str(pod)+'&rnd=1', timeout=60) #check if Masters (P2) round 1 has started yet
				if(r.status_code == 200):
					if(len(r.content) > 0):
						self.GetRounds(r.content, pod)
						self.Tournament_started[pod] = True
			if(self.Tournament_started[pod]):
				for round in self.Rounds_data[pod]['rounds']:
					start = time.time()
					if(not round+1 in self.Rounds_data[pod]['rounds'] or self.Rounds_data[pod]['rounds'][round+1]['data'] == None):
						r = requests.get('https://rk9.gg/pairings/'+self.RK9_id+'?pod='+pod+'&rnd='+str(round), timeout=60)
						end = time.time()
						print('P'+pod+'R'+str(round)+' getting page data in : '+str(end - start))
						if(r.status_code == 200 and len(r.content)> 0):
							if(self.Rounds_data[pod]['rounds'][round]['data'] != r.content):
								self.Rounds_data[pod]['rounds'][round]['data'] = r.content
								soup = BeautifulSoup(r.content, "lxml")
								matches = soup.find_all('div', attrs={'class':'match','class':'row-cols-3'})
								tournamentEnded = False
								if(len(matches) == 2):
									tournamentEnded = True
								for match in matches:
									divs = match.find_all('div')
									table = 0
									tableNumber = divs[1].find('span')
									if(tableNumber):
										table = int(tableNumber.text)
									p1 = getPlayerData(divs[0], table, divs[2])
									p2 = getPlayerData(divs[2], table, divs[0])
									self.addData(pod, p1, p2, table, round, self.official_standings)
									if(tournamentEnded and p1['result'] == None):
										tournamentEnded = False
								self.Compute(pod, round, self.Rounds_data)
								self.Save(pod, round, 'Standings')
								if(tournamentEnded):
									self.CompareStandings(pod, self.official_standings, 'Standings')
					end = time.time()
					print('P'+pod+'R'+str(round)+' treated in : '+str(end - start))

if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--id", default='DOR1mfyTo79MGongLsND')
	parser.add_argument("--decklists", default=False, action="store_true", help="read decklists from /roster/ page")
	
	args = parser.parse_args()

	rk9_id = args.id
	retrieve_decklists = args.decklists

	"""exemple: (Dortmund)
	--id DOR1mfyTo79MGongLsND --decklists True
	"""


	standings = Standings(rk9_id, retrieve_decklists)
	starttime = time.time()
	while True:
		try:
			standings.update(True) #true : reading rk9-standings
		except Exception as e:
			print(e)
		sleepTime = 240.0 - ((time.time() - starttime) % 120.0)
		print("waiting " + str(sleepTime) + ' seconds')
		time.sleep(sleepTime)