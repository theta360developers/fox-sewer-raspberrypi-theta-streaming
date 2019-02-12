import threading, sys, time, subprocess
import	 tty, termios, socket
import requests,json
from threading import Thread
from requests.auth import HTTPDigestAuth
from multiprocessing import Process
from multiprocessing import Value

sys.path.append('/home/pi/cyclope')
from ThetaStreamServerV1 import ThetaStreamServer
from ThetaStreamServerV1 import ThetaHandler
from RepertoireV1 import Repertoire
	
	
class Theta(Thread):

	HEADERS = {'content-type': 'application/json'}
	ALERTES = ["Caméra 360 non connectée"]
	ALERTES_COPIE = ["Traitement fichier 360 en cours"]
	AUTH = HTTPDigestAuth('THETAYL00108440', '00108440')
	ARP = "sudo arp-scan -I wlan0 10.0.1.10-10.0.1.50"
	RICOH = "RICOH COMPANY"
	FICHIER_CORRESPONDANCE = "/home/pi/cyclope/fichiersTheta.json"
	
	def __init__(self,tempsBoucle=3,tempsReconnexion=3):
		
		super(Theta, self).__init__()
		self.stopRequest = threading.Event()
		self.tempsBoucle = tempsBoucle
		self.tempsReconnexion = tempsReconnexion
		self.adresseIp = ""
		self.alertes = Theta.ALERTES
		self.niveauBatterie = 0.
		self.fichiersThetaJson = json.loads(' { "fichiers" : [] }')
		self.recordingIndicator = False
		self.nomFichier = ""
		self.list = []
		""" Modes de la theta :
			0 : adresse IP non trouvée
			1 : IP trouvee , serveur stream demare , mais pas de connexion active
			2 : au repos, live autorise
			3 : en enregistrement
			4 : en transfert de fichier
		"""
		self.mode = Value('i',0)
		self.lireFichiersTheta()
		
		self.methodeSend360 = "0"
		self.listefichiersSend360 = ""

	def getAlertes(self):
		return self.alertes
		
	def getMode(self):
		return self.mode.value

	def getAdresseIp(self):
		output = (subprocess.check_output(Theta.ARP, shell=True )).decode("utf-8").split("\n")
		for line in output:
			if (line.find(Theta.RICOH) != -1):
				self.adresseIp = line.split()[0]
				with self.mode.get_lock():
					self.mode.value = 1
				self.startLive()
					
					
	def _live(self):	
		print("_live")
		serveurLive =  ThetaStreamServer(('',9091),ThetaHandler)	
		serveurLive.initChargement(self.adresseIp,self.mode)
		serveurLive.serve_forever()


	def startLive(self):
		try:
			print("startLive")
			self.p = Process(target=self._live)
			self.p.start()
		except Exception as err :
			print("EXCEPTION startLive")
			print(err)
			pass

	def setOptions1(self):
		url = "".join(("http://", self.adresseIp, ":80/osc/commands/execute"))		
		body = json.dumps({"name": "camera.setOptions",	"parameters": {	"options": {
							"captureMode": "video",	"sleepDelay": 1200, "offDelay": 600, "videoStitching" : "none",
								"_microphoneChannel": "1ch", "_gain" : "mute",	"_shutterVolume" : 100,
								"previewFormat" : {"width": 1024, "height": 512, "framerate": 8}}}})
		try:
			req = requests.post(url, data=body,headers=Theta.HEADERS,auth=Theta.AUTH,timeout=3)
		except Exception:
			pass

	def setOptions2(self):
		url = "".join(("http://", self.adresseIp, ":80/osc/commands/execute"))
		
		body = json.dumps({"name": "camera.setOptions",	"parameters": {	"options": {							
								"fileFormat": {"type": "mp4", "width": 1920, "height": 960, "_codec": "H.264/MPEG-4 AVC"},
								"_maxRecordableTime" : 1500, "_bitrate" : "Normal",	"whiteBalance": "auto"	}}})
		try:
			req = requests.post(url, data=body,headers=Theta.HEADERS,auth=Theta.AUTH,timeout=3)
		except Exception:
			pass				
	

	def startRecording(self,nomFichier):		
		if (self.mode.value == 2):
			url = "".join(("http://", self.adresseIp, ":80/osc/commands/execute"))		
			body = json.dumps({	"name": "camera.startCapture"})
			try:
				req = requests.post(url, data=body,headers=Theta.HEADERS,auth=Theta.AUTH,timeout=3)
				self.recordingIndicator = True
				self.nomFichier = nomFichier
				with self.mode.get_lock():
					self.mode.value = 3
			except Exception:
				pass
			
			

	def stopRecording(self):
		if (self.mode.value == 3):
			url = "".join(("http://", self.adresseIp, ":80/osc/commands/execute"))		
			body = json.dumps({"name": "camera.stopCapture"})
			try:
				req = requests.post(url, data=body,headers=Theta.HEADERS,auth=Theta.AUTH,timeout=3)
				print(req.content.decode('UTF-8'))
				with self.mode.get_lock():
					self.mode.value = 2
			except Exception:
				pass		

			
	def getState(self):
		url = "".join(("http://", self.adresseIp, ":80/osc/state"))
		print ("THETA getState\n")
		try:
			req = requests.post(url,headers=Theta.HEADERS,auth=Theta.AUTH,timeout=10)
			if (req.status_code == 200):
				if (self.mode.value == 1):
					self.setOptions1()
					self.setOptions2()			
					with self.mode.get_lock():
						self.mode.value = 2
					
			
				donneeJson = json.loads(req.content.decode('UTF-8'))
				self.niveauBatterie = donneeJson["state"]["batteryLevel"]
				#TODO erreur internes + alrte temps enregistrment
				self.alertes = []
				print("req.status_code 200")
				#if (self.mode.value == 4):
				#	print("Theta.ALERTES_COPIE")
				#	self.alertes=Theta.ALERTES_COPIE
					
				capture = donneeJson["state"]["_captureStatus"]
				fileUrl = donneeJson["state"]["_latestFileUrl"]
				recordableTime= donneeJson["state"]["_recordableTime"]
				print("recordableTime")
				print(recordableTime)
				print("capture")
				print(capture)
				print(fileUrl)
				if ((self.recordingIndicator == True) and (capture == "idle")):	
					print(fileUrl)
					fileUrlSplit=fileUrl.split("/")

					self.ajoutFichiersTheta(fileUrlSplit[-1])
					self.nomFichier = ""
					self.recordingIndicator = False
				#if (capture == "shooting"):

		
		except Exception as err:
				print ("THETA getState Exception \n")
				print(err)
				with self.mode.get_lock():
					self.mode.value = 1
				self.alertes = Theta.ALERTES
				self.niveauBatterie = 0.
	
			
			

	
			
			
	def lireFichiersTheta(self):
		print("lireFichiersTheta")
		date = time.strftime("%Y-%m-%d",time.localtime(time.time()-60*60*24*30))
		try:
			with open(Theta.FICHIER_CORRESPONDANCE, "rt") as fichier:
				listeAvantTri = fichier.read()
				listeAvantTriJson = json.loads(listeAvantTri)
				for chunk in listeAvantTriJson["fichiers"]:
					if (chunk["date"] > date):
						self.fichiersThetaJson["fichiers"].append(chunk)			
		except Exception:
			print("Exception lireFichiersTheta")
			pass
			
			
	def ecrireFichiersTheta(self):
		print("ecrireFichiersTheta")
		try:
			with open(Theta.FICHIER_CORRESPONDANCE, "wt") as fichier:
				#fichier.write("[ ")
				#fichier.write(",".join(self.fichiersThetaJson))
				#fichier.write("]")		
				fichier.write( json.dumps(self.fichiersThetaJson))
		except Exception:
			print("Exception ecrireFichiersTheta")
			pass	
	
	
	def ajoutFichiersTheta(self,name):
		print("ajoutFichiersTheta")
		print(name)
		date = time.strftime("%Y-%m-%d",time.localtime())
		#ajout = json.dumps({ "name" : name , "nom" : self.nomFichier , "date" : date })
		ajout = { "name" : name , "nom" : self.nomFichier, "date" :  date  }
		if (self.nomFichier != ''):
			self.fichiersThetaJson["fichiers"].append(ajout)
			self.ecrireFichiersTheta()
			




	def join (self, timeout=2):
		self.p.join(timeout)
		self.stopRequest.set()
		super(Theta, self).join(timeout)			
			

	def listFiles(self,targetDir,espaceDisponible):
		print("listFiles")
		print(targetDir)
		print((espaceDisponible))
		listeFichiersJson = json.loads(' { "fichiers" : [], "espaceDisponible" : "", "message" : "" }')
		listeFichiers = ""
		
		message = ""
		limit = 0
		
		if (targetDir == Repertoire.CHEMIN_CARTE):
			message = "Clé USB non présente"
			limit = 1
		
		
		
		if (self.mode.value == 2):
			url = "".join(("http://", self.adresseIp, ":80/osc/commands/execute"))
			body = json.dumps({"name": "camera.listFiles",
						"parameters": {
								"fileType": "all",
								"entryCount": 128,
								"_detail" : False,
								"maxThumbSize": 0
						}
			})
			try:
				req = requests.post(url, data=body,headers=Theta.HEADERS,auth=Theta.AUTH,timeout=3)
				listeFichiers = req.content.decode('UTF-8')				
				entries = json.loads(listeFichiers)["results"]["entries"]
				self.list = entries
				for chunck in entries:
						name = chunck["name"]
						info = chunck["name"] + " (" + str(int(chunck["size"]/1000000)) + " Mo)"
						for chunck2 in self.fichiersThetaJson["fichiers"]:
							if (name == chunck2["name"]):
								info = chunck2["nom"] + " (" + str(int(chunck["size"]/1000000)) + " Mo)"
							
						ajout = { "name" : name , "info" : info, "size" : int(chunck["size"]/1000000) }
						listeFichiersJson["fichiers"].append(ajout)
			except Exception:
				pass		
					
		else:
			limit=2
			message = "Caméra 360 non disponible"
		
		print("listFiles2")
		listeFichiersJson["espaceDisponible"]=int(espaceDisponible)/1000 -1
		listeFichiersJson["message"]=message
		listeFichiersJson["limit"]=limit
		print("listFiles3")
		return json.dumps(listeFichiersJson)


	def sendFichiers360(self,methode,listefichiers):
		self.methodeSend360 = methode
		self.listefichiersSend360 = listefichiers


	def _sendFichiers360(self):
		print("sendFichiers360")
		methode= self.methodeSend360
		self.methodeSend360 = "0"
		print(methode)
		print(self.methodeSend360)
		self.alertes=Theta.ALERTES_COPIE
		for x in self.listefichiersSend360.split("_"):
			fileUrl = ""
			nomFichierDestination = x
			for y in self.list:
				if (y["name"] == x):
					fileUrl= y["fileUrl"]
			for z in self.fichiersThetaJson["fichiers"]:
				if (z["name"] == x):
					nomFichierDestination= z["nom"]
			
			if (fileUrl != ""):
				if (methode == "1"):				
					self.deleteFile(fileUrl)
				if (methode == "2"):
					print(nomFichierDestination)
					self.getFile(fileUrl,Repertoire.CHEMIN_CLE,nomFichierDestination)
				if (methode == "3"):	
					result = self.getFile(fileUrl,Repertoire.CHEMIN_CLE,nomFichierDestination)
					if (result == 0):
						self.deleteFile(fileUrl)



	def deleteFile(self,fileUrl):
		print ("deleteFile")
		print (fileUrl)
		fileUrls = []
		fileUrls.append(fileUrl)
		url = "".join(("http://", self.adresseIp, ":80/osc/commands/execute"))
		body = json.dumps({"name": "camera.delete",
						"parameters": {
								"fileUrls": 	fileUrls		}
			})
		try:
			req = requests.post(url, data=body,headers=Theta.HEADERS,auth=Theta.AUTH,timeout=5)	
			print (str(req.status_code))
		except Exception:
			pass
		
	def getFile(self,fileUrl,repertoireDestination,nomFichierDestination):
		print("getFile")
		print("fileUrl:" + fileUrl)
		print("repertoireDestination:" + repertoireDestination)
		print("nomFichierDestination:" + nomFichierDestination)
		exit_code = 0
		sequence = (repertoireDestination,"/",nomFichierDestination)
		fichier = "".join(sequence)
		
		print ("fichier:"  + fichier)
		
		if (self.mode.value == 2):
			with self.mode.get_lock():
					self.mode.value = 4
					
			#self.alertes = Theta.ALERTES_COPIE
			try:
				print ("getFile : " + fileUrl + " vers " + fichier)
				mon_fichier = open(fichier, "wb")
						
				response = requests.get(fileUrl,headers=Theta.HEADERS,auth=Theta.AUTH,stream=True,timeout=5)
				if response.status_code == 200:
					for block in response.iter_content(chunk_size=100000):
						if block:
							mon_fichier.write(block)
				
				mon_fichier.close()
				#self.alertes = []
			except Exception as err:
				print("Exception getFile")
				print (err)
				#self.alertes = ["Exception getFile"]
				exit_code = 1
				pass
			
			with self.mode.get_lock():
					self.mode.value = 2
			return exit_code
			
	
	
	def run(self) :		
		while not self.stopRequest.is_set():		
			if (self.mode.value == 0):
				self.getAdresseIp()	
		
			if (self.mode.value > 0):
				self.getState()
				if (self.methodeSend360 != "0"):
					self._sendFichiers360()

					
			if (self.mode.value == 0):
				time.sleep(self.tempsReconnexion)
			else:
				time.sleep(self.tempsBoucle)