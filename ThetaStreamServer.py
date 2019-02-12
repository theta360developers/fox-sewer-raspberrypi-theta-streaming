import threading, sys, time, subprocess
import	 tty, termios, socket
import requests,json
from threading import Thread
from requests.auth import HTTPDigestAuth
from multiprocessing import Process
from multiprocessing import Value
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

sys.path.append('/home/pi/cyclope')

class ThetaStreamServer(ThreadingMixIn, HTTPServer):

def initChargement(self,adresseIp,mode):
	self.nbClients = Value('i',0)
	self.thetaGetLivePreview = ThetaGetLivePreview(adresseIp,mode,self.nbClients)
	self.mode = mode
	self.thetaGetLivePreview.start()	
		
class ThetaHandler(BaseHTTPRequestHandler):

def do_GET(self):
	print("do_GET")
	with self.server.nbClients.get_lock():
		self.server.nbClients.value += 1
		print("nbClients :"		+ str(self.server.nbClients.value))
	try:	
		time.sleep(1)
		self.send_response(200)
		self.send_header('Access-Control-Allow-Origin', '*')
		self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--osclive')
		self.send_header("Pragma-directive", "no-cache")
		self.send_header("Cache-directive", "no-cache")
		#self.send_header("Cache-control", "no-cache")
		self.send_header("Cache-control", "no-cache, no-store, must-revalidate")
		self.send_header("Pragma", "no-cache")
		#self.send_header("Expires", "0")

		image=b''
		timeStampImage = ''
		
		#while (self.server.mode.value == 2 ):
		while True:
			if (timeStampImage != self.server.thetaGetLivePreview.timeStampImage):
				#print("NEW IMAGE SENT")
				timeStampImage = self.server.thetaGetLivePreview.timeStampImage
				self.end_headers()
				image= self.server.thetaGetLivePreview.image
				self.wfile.write('--osclive'.encode())
				self.end_headers()
				self.send_header('Content-type', 'image/jpeg')
				self.send_header('Content-length', len(image))
				self.end_headers()
				self.wfile.write(image)
			time.sleep(0.1)
		
		with self.server.nbClients.get_lock():
			self.server.nbClients.value = self.server.nbClients.value - 1
			
		print ("end DO GEtttttttttttttttttttttttttttt")
	except Exception as err:			
		print("Exception do_GET")
		print(err)
		with self.server.nbClients.get_lock():
			self.server.nbClients.value = self.server.nbClients.value - 1
		

		

class ThetaGetLivePreview(Thread):

def __init__(self, adresseIp,mode,nbClients):
	print("init ThetaGetLivePreview")
	super(ThetaGetLivePreview, self).__init__()
	self.stopRequest = threading.Event()
	self.adresseIp = adresseIp
	self.image=b''
	self.timeStampImage=time.time()
	self.isChargingImage = False
	self.mode = mode
	self.nbClients = nbClients

def _appel(self):
	print("_appel ThetaGetLivePreview")
	print(str(self.mode.value))
	
	url = "".join(("http://", self.adresseIp, ":80/osc/commands/execute"))
	body = json.dumps({"name": "camera.getLivePreview"})
	try:
		response = requests.post(url, data=body, headers={'content-type': 'application/json'},auth=HTTPDigestAuth('THETAYL00108440', '00108440'), stream=True,timeout=5)
		print("chargement _appel - response")
		if response.status_code == 200:
			self.isChargingImage = True
			bytes = ''
			jpg=''
			i = 0
			for block in response.iter_content(chunk_size=10000):
				if (self.nbClients.value == 0):
						print("ARRET _appel")
						response.close()
						raise StopIteration()
						
				if (bytes == ''):
					bytes = block
				else: 	
					bytes = bytes + block
				
				# Search the current block of bytes for the jpq start and end
				a = bytes.find(b'\xff\xd8')
				b = bytes.find(b'\xff\xd9')

				# If you have a jpg
				if a != - 1 and b != -1:
					print("image - chargement")
					self.image = bytes[a:b + 2]
					self.timeStampImage=time.time()
					bytes = bytes[b + 2:]					
					
		else:
			print("theta response.status_code _appel: {0}".format(response.status_code))
			response.close()
			self.isChargingImage = False	
	except Exception as err:
		print("theta erreur _appel: {0}".format(err))
		self.isChargingImage = False		

def run(self):
	while not self.stopRequest.is_set():
		if (self.mode.value == 2 and self.nbClients.value > 0):
			if (self.isChargingImage == False):
				self._appel()
		else:
			self.isChargingImage = False	
		time.sleep(0.5)