import zeep
from zeep import Client
import xml.etree.ElementTree as ET
import subprocess
from datetime import datetime, timedelta
import os
import ssl
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter


class CustomHttpAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        context.set_ciphers("DEFAULT:!DH")
        kwargs['ssl_context'] = context
        return super(CustomHttpAdapter, self).init_poolmanager(*args, **kwargs)

# Crear una sesión personalizada
session = Session()
# Montar el adaptador HTTP personalizado en la sesión
session.mount("https://", CustomHttpAdapter())

# Crear el transporte personalizado para zeep utilizando la sesión
transport = Transport(session=session)

base = os.getcwd()

#entorno = 'certificacion_produccion'
entorno = 'certificacion_desarrollo'

MiLoginTicketRequest1 = os.path.join(base,"MiLoginTicketRequest.xml")

MiLoginTicketRequest2 = os.path.join(base,"MiLoginTicketRequest.xml.cms")

certificado_pem = os.path.join(base,entorno,"certificado.pem")

clave_privada = os.path.join(base,entorno,"privada_facturacion.key")

# Url del servicio WSN (se utiliza una vez obtenida la autorizacion)

# PRODUCCION (WSN)
# url2 = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"

# DESARROLLO (WSN):
url2 = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"


def facturador_lotes():

    # URL del servicio web (endpoint) 
    # PRODUCCION (WSAAS)
    # url = 'https://wsaa.afip.gov.ar/ws/services/LoginCms?WSDL'

    # DESARROLLO (WSAAS)
    url = 'https://wsaahomo.afip.gov.ar/ws/services/LoginCms?WSDL'

    #Modificamos el archivo MiLoginTicketRequest.xml para introducirle la hora y fecha actual y sumarle 1 HR:
    tree = ET.parse(MiLoginTicketRequest1)
    
    root = tree.getroot()

    # Obtener el elemento 'generationTime' y actualizar su contenido
    expiration_time_element = root.find(".//expirationTime")
    current_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

    #Script que se ejecuta cuando la hora de expiracion es menor que la hora actual
    # Dentro de la condicional es: expiration_time_element.text < current_time 
    if (expiration_time_element.text < current_time ):

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

    client = Client(url2, transport=transport)
    
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


    # Datos de la factura. (podrían ser varios, acá solo hay que iterarlas)
    facturas = [
        {
            "Concepto": 1,
            "DocTipo": 80,
            "DocNro": 20375182906,
            "CbteDesde": 1,
            "CbteHasta": 1,
            "CbteFch": datetime.now().strftime("%Y%m%d"),
            "ImpTotal": 121.0,
            "ImpTotConc": 0.0,
            "ImpNeto": 100.0,
            "ImpOpEx": 0.0,
            "ImpTrib": 0.0,
            "ImpIVA": 21,
            "FchServDesde": '',
            "FchServHasta": '',
            "FchVtoPago": '',
            "MonId": 'PES',
            "MonCotiz": 1.0,
            "Iva": [
                {
                    "Id": 5,  # 21%
                    "BaseImp": 100.0,
                    "Importe": 21.0
                }
            ]
        },
        # Añade más facturas según sea necesario
    ]

    # Crear el objeto FeCabReq
    FeCabReq = client.get_type('ns0:FECAECabRequest')
    fe_cab_req = FeCabReq(
        CantReg=len(facturas),
        PtoVta=1,
        CbteTipo=1
    )

    # Crear los objetos FECAEDetRequest
    FeDetReq = client.get_type('ns0:ArrayOfFECAEDetRequest')
    FECAEDetRequest = client.get_type('ns0:FECAEDetRequest')

    fe_det_req_list = []
    for factura in facturas:
        iva_list = []
        for iva in factura["Iva"]:
            AlicIva = client.get_type('ns0:AlicIva')
            iva_list.append(AlicIva(
                Id=iva["Id"],
                BaseImp=iva["BaseImp"],
                Importe=iva["Importe"]
            ))

        fe_det_req = FECAEDetRequest(
            Concepto=factura["Concepto"],
            DocTipo=factura["DocTipo"],
            DocNro=factura["DocNro"],
            CbteDesde=factura["CbteDesde"],
            CbteHasta=factura["CbteHasta"],
            CbteFch=factura["CbteFch"],
            ImpTotal=factura["ImpTotal"],
            ImpTotConc=factura["ImpTotConc"],
            ImpNeto=factura["ImpNeto"],
            ImpOpEx=factura["ImpOpEx"],
            ImpTrib=factura["ImpTrib"],
            ImpIVA=factura["ImpIVA"],
            FchServDesde=factura["FchServDesde"],
            FchServHasta=factura["FchServHasta"],
            FchVtoPago=factura["FchVtoPago"],
            MonId=factura["MonId"],
            MonCotiz=factura["MonCotiz"],
            Iva={'AlicIva': iva_list} 
        )
        fe_det_req_list.append(fe_det_req)

    fe_det_req_array = FeDetReq(fe_det_req_list)

    # Crear el objeto FeCAEReq
    FeCAEReq = client.get_type('ns0:FECAERequest')
    fe_cae_req = FeCAEReq(
        FeCabReq=fe_cab_req,
        FeDetReq=fe_det_req_array
    )

    # Llamar a la operación FECAESolicitar
    response = client.service.FECAESolicitar(
        Auth=auth,
        FeCAEReq=fe_cae_req
    )

    print(response)

facturador_lotes()