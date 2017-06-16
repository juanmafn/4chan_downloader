#!/usr/bin/env python2
# coding: utf-8
__author__ = "Juan Manuel Fernández Nácher"

# Librerías del sistema
import platform, subprocess, sys, os

# Librerías web
import requests

# Librerías hilos
import threading

# Utils
import re, json, shutil

############################################
#    Obtener Dimensiones de la ventana     #
############################################

# Fuente: http://www.iteramos.com/pregunta/10039/como-obtener-la-ventana-de-la-consola-de-ancho-en-python

__all__=['getTerminalSize']

def getTerminalSize():
	current_os = platform.system()
	tuple_xy=None
	if current_os == 'Windows':
		tuple_xy = _getTerminalSize_windows()
		if tuple_xy is None:
			tuple_xy = _getTerminalSize_tput()
			# needed for window's python in cygwin's xterm!
	if current_os == 'Linux' or current_os == 'Darwin' or  current_os.startswith('CYGWIN'):
		tuple_xy = _getTerminalSize_linux()
	if tuple_xy is None:
		print "default"
		tuple_xy = (80, 25)      # default value
	return tuple_xy

def _getTerminalSize_windows():
	res=None
	try:
		from ctypes import windll, create_string_buffer
		h = windll.kernel32.GetStdHandle(-12)
		csbi = create_string_buffer(22)
		res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
	except:
		return None
	if res:
		import struct
		(bufx, bufy, curx, cury, wattr, left, top, right, bottom, maxx, maxy) = struct.unpack("hhhhHhhhhhh", csbi.raw)
		sizex = right - left + 1
		sizey = bottom - top + 1
		return sizex, sizey
	else:
		return None

def _getTerminalSize_tput():
	try:
		proc=subprocess.Popen(["tput", "cols"],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
		output=proc.communicate(input=None)
		cols=int(output[0])
		proc=subprocess.Popen(["tput", "lines"],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
		output=proc.communicate(input=None)
		rows=int(output[0])
		return (cols,rows)
	except:
		return None


def _getTerminalSize_linux():
	def ioctl_GWINSZ(fd):
		try:
			import fcntl, termios, struct
			cr = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ,'1234'))
		except:
			return None
		return cr
	cr = ioctl_GWINSZ(0) or ioctl_GWINSZ(1) or ioctl_GWINSZ(2)
	if not cr:
		try:
			fd = os.open(os.ctermid(), os.O_RDONLY)
			cr = ioctl_GWINSZ(fd)
			os.close(fd)
		except:
			pass
	if not cr:
		try:
			cr = (env['LINES'], env['COLUMNS'])
		except:
			return None
	return int(cr[1]), int(cr[0])


def clearScreen():
	current_os = platform.system()
	if current_os == 'Windows':
		os.system("cls")
	else:
		os.system("clear")
	

#===================================================================#


##################################################################
#    Función que obtiene las url de los hilos de un catálogo     #
##################################################################
def es_catalogo(url):
	# Descargamos la página
	pagina = requests.get(url).text
	
	# Comprobamos si tiene el objeto JSON del catálogo
	jsonObject = re.findall("var catalog = (.*?});", pagina)
	
	if len(jsonObject) > 0:
		jsonObject = json.loads(jsonObject[0])
	else:
		return None
	
	urlBase = url.replace("catalog", "thread/")
	urlThreads = []
	
	for th in jsonObject["threads"]:
		try:
			thread = "{0}{1}".format(urlBase, th)
			urlThreads.append(thread)
		except:
			None
	
	return urlThreads

###############################################################################
#    Función que obtiene las url de las imágenes de un hilo de 4chan dado     #
###############################################################################
def obtener_imagenes(url):
	# Descargamos la página
	pagina = requests.get(url).text
	
	# Extraemos las imágenes de la página
	imagenes = re.findall('href="//([a-zA-Z0-9./-_]+(jpg|png|webm|gif))"',pagina)
	
	# Las convertimos en enlaces válidos, añadiéndoles la cabecera http://
	imagenes = map(lambda x: "http://"+x[0], imagenes)
	
	# Eliminamos imágenes duplicadas
	imagenes = list(set(imagenes))
	
	return imagenes


################################################################
#    Función que asigna a cada hilo una imagen a descargar     #
################################################################
def descargarImagenes(imagenes, directorio):
	id_hilos=[]
	global stop
	
	# Creamos directorio si no existe
	if not os.path.exists(directorio):
		os.makedirs(directorio)
	
	try:
		for i in imagenes:
			nombre = i.split("/")[-1]
			idh = threading.Thread(target=descargarImagen,args=(i,directorio,nombre))
			idh.start()
			id_hilos.append(idh)
		for idh in id_hilos:
			idh.join()
	except KeyboardInterrupt:
		print "Programa interrumpido por el usuario"
		stop=True


#############################################################
#    Función que descarga una imagen al directorio dado     #
#############################################################
def descargarImagen(imagen, directorio, nombre):
	global semaforo
	global stop
	global descargadas
	
	semaforo.acquire()
	
	# si el usuario no ha parado el programa, y la imagen no está ya descargada, se descarga
	if not stop and not os.path.isfile(directorio+"/"+nombre):
		try:
			r = requests.get(imagen, stream=True)
			if r.status_code == 200:
				with open(directorio+"/"+nombre, 'wb') as f:
					r.raw.decode_content = True
					shutil.copyfileobj(r.raw, f)
		except KeyboardInterrupt:
			print "Programa interrumpido por el usuario"
			stop=True
		except:
			None
	elif stop:
		sys.exit(0)
	descargadas += 1
	__print__(directorio.split("/")[-1])
	semaforo.release()


#######################################
#    Función que descarga un hilo     #
#######################################
def descargarHilo4chan(url, directorio):
	global stop
	global nImagenes
	global descargadas
	global hilosDescargados
	
	# Obtenemos el nombre de la carpeta donde se van a almacenar las imágenes
	carpeta = url.split("/")[-1]
	
	# Añadimos la carpeta al directorio
	directorio += "/"+carpeta
	
	# Obtenemos las url de las imágenes del hilo de 4chan
	imagenes = obtener_imagenes(url)
	nImagenes = len(imagenes)
	descargadas = 0
	
	# Descargamos las imágenes obtenidas (si hay), al directorio dado
	if nImagenes > 0:
		descargarImagenes(imagenes, directorio)
	
	hilosDescargados += 1


def __print__(hilo):
	global tipo
	global nImagenes
	global descargadas
	global hilosTotales
	global hilosDescargados
	global semaforo_print
	
	semaforo_print.acquire()
	clearScreen()
	sizex,sizey=getTerminalSize()
	
	if tipo == None:
		print_hilo(hilo, nImagenes, descargadas, sizex)
	else:
		print_categoria(tipo, hilosTotales, hilosDescargados+1, hilo, nImagenes, descargadas, sizex)
	semaforo_print.release()
		

def print_categoria(catalogo, n_hilos, hilos_descargados, hilo, n_imagenes, imagenes_descargadas, sizex):
	sys.stdout.write("Downloading catalog {0}\n{1} Threads\n{2}\n\n".format(catalogo, n_hilos, progreso(n_hilos, hilos_descargados, sizex)))
	print_hilo(hilo, n_imagenes, imagenes_descargadas, sizex)

def print_hilo(hilo, n_imagenes, imagenes_descargadas, sizex):
	sys.stdout.write("Downloading thread {0}\n{1} Images\n{2}\n".format(hilo, n_imagenes, progreso(n_imagenes, imagenes_descargadas, sizex)))

def progreso(N,n,size):
	return "{0}{1}".format(progreso_porcentaje(N, n), progreso_string(N, n, size - 6))

def progreso_porcentaje(N, n):
	return "{0}%".format(n*100/N).ljust(5)

def progreso_string(N, n, sizex):
	res = ""
	completado = n*sizex/N
	for i in range(completado):
		res += "#"
	for i in range(completado, sizex):
		res += "-"
	return res


#######################
#    Función main     #
#######################
def main():
	if len(sys.argv) < 3:
		sys.stderr.write("USO: {0} [URL] [Directorio] [opcional: número de hilos, por defecto 25]\n".format(sys.argv[0]))
		sys.exit(-1)
	
	# Definimos las variables globales
	global semaforo
	global semaforo_print
	global stop
	global tipo
	global nImagenes
	global descargadas
	global hilosTotales
	global hilosDescargados
	
	# Número de hilos para descargar cada imagen
	nHilos = 25
	if len(sys.argv) == 4:
		nHilos = int(sys.argv[3])

	# Semáforo
	semaforo = threading.Semaphore(nHilos)
	semaforo_print = threading.Semaphore(1)

	# Variable de control para parar los hilos de descarga al hacer control+c
	stop = False

	# Obtenemos url y directorio de los argumentos del programa
	url = sys.argv[1]
	directorio = sys.argv[2]
	
	urlThreads = es_catalogo(url)
	if urlThreads != None:
		hilosTotales = len(urlThreads)
		hilosDescargados = 0
		tipo = url.split("/")[-2]
		directorio += "/"+tipo
		for urlThread in urlThreads:
			if not stop:
				descargarHilo4chan(urlThread, directorio)
			else:
				sys.exit(0)
	else:
		tipo = None
		hilosDescargados = 0
		descargarHilo4chan(url, directorio)

if __name__ == "__main__":
    main()
