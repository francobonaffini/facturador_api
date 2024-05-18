import zeep
from zeep import Client
import xml.etree.ElementTree as ET
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import time
import os
import ssl

context = ssl.create_default_context()
context.set_ciphers("DEFAULT@SECLEVEL=1")

base = r"C:\Users\Franco Bonaffini\Desktop\produccion_certificados"

entorno = 'certificacion_produccion'
#entorno = 'certificacion_desarrollo'

MiLoginTicketRequest1 = os.path.join(base,"MiLoginTicketRequest.xml")

MiLoginTicketRequest2 = os.path.join(base,"MiLoginTicketRequest.xml.cms")

certificado_pem = os.path.join(base,entorno,"certificado.pem")

clave_privada = os.path.join(base,entorno,"privada_facturacion.key")

# Url del servicio WSN (se utiliza una vez obtenida la autorizacion)

# PRODUCCION (WSN)
url2 = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"

# DESARROLLO (WSN):
# url2 = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"


def facturador_lotes():

    # URL del servicio web (endpoint) 
    # PRODUCCION (WSAAS)
    url = 'https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL'

    # DESARROLLO (WSAAS)
    # url = 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL'

    #Modificamos el archivo MiLoginTicketRequest.xml para introducirle la hora y fecha actual y sumarle 1 HR:
    tree = ET.parse(MiLoginTicketRequest1)
    
    root = tree.getroot()

    # Obtener el elemento 'generationTime' y actualizar su contenido
    expiration_time_element = root.find(".//expirationTime")
    current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    #Script que se ejecuta cuando la hora de expiracion es menor que la hora actual
    if (True):

        print("La hora de expiracion es menor que la hora actual ejecuta codigo de actualizacion de token")
        # Calcular la hora de expiración
    
        generation_time = datetime.strptime(current_time, '%Y-%m-%dT%H:%M:%S')
        expiration_time = generation_time + timedelta(hours=1)
        expiration_time_str = expiration_time.strftime('%Y-%m-%dT%H:%M:%S')

        expiration_time_element = root.find(".//expirationTime")
        expiration_time_element.text = expiration_time_str

        # Obtén la etiqueta <generationTime>
        generation_time_element = root.find(".//generationTime")

        # Obtiene la fecha y hora actual
        current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

        # Actualiza el contenido de la etiqueta <generationTime>
        generation_time_element.text = current_time
        # Guardar los cambios de vuelta al archivo
        tree.write(MiLoginTicketRequest1)

        # Contenido del CMS que deseas enviar
        # Aquí debes poner el contenido del CMS en formato base64

        command = [
            'openssl', 'cms', '-sign',
            '-in', MiLoginTicketRequest1,
            '-out', MiLoginTicketRequest2,
            '-signer', certificado_pem,
            '-inkey', clave_privada,
            '-nodetach', '-outform', 'PEM'
        ]

        try:
            subprocess.run(command, check=True)
            print("Comando OpenSSL ejecutado exitosamente.")
        except subprocess.CalledProcessError as e:
            print("Error al ejecutar el comando OpenSSL:", e)

        # Ya tenemos el "MiLoginTicketRequest2" producto del comando anterior.

        # FUNCION para el contenido del archivo y limpia los ---BEGIN y END CMS---
        def read_cms_file(file_path):
            with open(file_path, 'r') as file:
                lines = file.readlines()
            
            content = ''
            inside_cms = False
            
            for line in lines:

                if line.strip() == '-----BEGIN CMS-----':
                    inside_cms = True
                    continue

                elif line.strip() == '-----END CMS-----':
                    inside_cms = False
                    continue
                
                if inside_cms:
                    content += line
            
            return content

        #Aqui tenemos el CMS formateado sin el --BEGIN-- ni --END--
        cms_content = read_cms_file(MiLoginTicketRequest2)
        
        # Crear un cliente SOAP
        client = zeep.Client(url)

        try:
            response = client.service.loginCms(cms_content)
        
        except zeep.exceptions.Fault as e:
            print(f"Error en la respuesta: {e}")

        root = ET.fromstring(response)

        token = root.find('.//token').text
        sign = root.find('.//sign').text

        #Grabamos los archivos .TXT para que se mantengan en el disco local para cada peticion lo tengamos en el disco duro 

        nombre_archivo1 = os.path.join(base,"token.txt")

        with open(nombre_archivo1, 'w') as archivo:
            # Escribe el contenido en el archivo
            archivo.write(token)

        nombre_archivo2 = os.path.join(base,"sign.txt")

        with open(nombre_archivo2, 'w') as archivo:
            # Escribe el contenido en el archivo
            archivo.write(sign)

    else:

        # El tiempo de expiracion no está expirado, solo toma el token y el sign y cre las variables para utilizar luego en el WSN.

        nombre_archivo1 = os.path.join(base,"token.txt")
        with open(nombre_archivo1, 'r') as archivo:
            # Lectura del contenido
            token = archivo.read()

        nombre_archivo2 = os.path.join(base,"sign.txt")
        with open(nombre_archivo2, 'r') as archivo:
            # Lectura del contenido
            sign = archivo.read()


    # # # # # # W S N # # # # # # 

    client = Client(url2)
    
    cuitRepresentada = 20375182905  # Reemplaza esto con el valor real del CUIT representado

    # Ponemos las variables que irán en la consulta.

    # Llamar a la operación getPersona del servicio web
    # try:
    print("Se envia la solicitud a la afip:")
    # Crear el objeto AuthRequest
    Auth = client.get_type('ns0:FEAuthRequest')

    auth = Auth(
        Token=token,
        Sign=sign,
        Cuit=cuitRepresentada
    )

    responses = client.service.FECompUltimoAutorizado (
        Auth = auth,
        PtoVta = 1,
        CbteTipo=1
        
    )
    print("Solicitud recibida")
    # Imprimir la respuesta

    datos_generales = responses

    print("SI ENCONTRADA POR API")
    print(datos_generales)

    return datos_generales

    # except:
    #     print("No encontrada desde API AFIP")
        
    #     return "No encontrada EN API"

facturador_lotes()