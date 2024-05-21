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
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from reportlab.lib import colors
from PIL import Image
import json
import base64
import qrcode

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


def ultimo_autorizado():
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
   
    # Crear el objeto AuthRequest
    Auth = client.get_type('ns0:FEAuthRequest')

    auth = Auth(
        Token=token,
        Sign=sign,
        Cuit=cuitRepresentada
    )

    # Llamar a la operación FECAESolicitar
    response = client.service.FECompUltimoAutorizado(
        Auth=auth,
        PtoVta = 1, # tiene que tener WS habilitado.
        CbteTipo = 6 # Facturas A (las C, son 11)
    )
    
    print(response['CbteNro'])

    return response['CbteNro']

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

    utlimo_comprobante = ultimo_autorizado()

    # Datos de la factura. (podrían ser varios, acá solo hay que iterarlas)
    facturas = [
        {
            "Concepto": 1,
            "DocTipo": 80,
            "DocNro": 23389116394,
            "CbteDesde": utlimo_comprobante +1,
            "CbteHasta": utlimo_comprobante +1,
            "CbteFch": datetime.now().strftime("%Y%m%d"),
            "ImpTotal": 121.0,
            "ImpTotConc": 0.0,
            "ImpNeto": 100.0,
            "ImpOpEx": 0.0,
            "ImpTrib": 0.0,
            "ImpIVA": 21.0,
            "FchServDesde": '',
            "FchServHasta": '',
            "FchVtoPago": '',
            "MonId": 'PES',
            "MonCotiz": 1.0,
            "Iva": [
                {
                    "Id": 5,  # 21%
                    "BaseImp": 100.00,
                    "Importe": 21.00
                }
            ]
        },
        # Añade más facturas según sea necesario
    ]

    # Crear el objeto FeCabReq TIPO DE COMPROBANTE Y PTO DE VENTA (FACT C = 11, PTO.VTA = 1)
    FeCabReq = client.get_type('ns0:FECAECabRequest')
    fe_cab_req = FeCabReq(
        CantReg=len(facturas),
        PtoVta=1,
        CbteTipo=6
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

def generar_factura_pdf(datos_factura, logo_path, output_path, afip_logo_img, disclaimer_img):
    c = canvas.Canvas(output_path, pagesize=A4)
    ancho, alto = A4

    # Colores y estilos
    color_azul = colors.HexColor("#0B5394")
    color_gris_claro = colors.HexColor("#F2F2F2")
    c.setFillColor(color_azul)
    c.rect(0, alto - 3 * cm, ancho, 3 * cm, fill=True, stroke=False)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, alto - 1.8 * cm, "Factura")
    c.setFont("Helvetica-Bold", 30)
    c.drawString(10 * cm, alto - 1.8 * cm, "A")
    c.setFont("Helvetica", 9)
    c.drawString(9.6 * cm, alto - 2.2 * cm, "COD. 001")

    # Agregar el logo de la empresa
    logo = Image.open(logo_path)
    logo_width, logo_height = logo.size
    logo_ratio = logo_width / logo_height
    logo_display_width = 3 * cm
    logo_display_height = logo_display_width / logo_ratio
    c.drawImage(logo_path, x=ancho - 5 * cm, y=alto - .5 * cm - logo_display_height, width=logo_display_width, height=logo_display_height)

    # Agregar una línea recta horizontal
    c.setStrokeColor(color_azul)
    c.setLineWidth(1)  # Ancho de la línea
    c.line(2 * cm, alto - 7 * cm, ancho - 2 * cm, alto - 7 * cm)

    # Datos de la empresa
    c.setFillColor(colors.white)
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, alto - 3.5 * cm, "Nombre de la Empresa")
    c.drawString(2 * cm, alto - 4 * cm, "Dirección de la Empresa")
    c.drawString(2 * cm, alto - 4.5 * cm, "Ciudad, Estado, ZIP")
    c.drawString(2 * cm, alto - 5 * cm, "Teléfono: +123456789")
    c.drawString(2 * cm, alto - 5.5 * cm, "Correo: empresa@example.com")

    # Datos de la factura
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, alto - 4 * cm,"Punto de venta:")
    c.setFont("Helvetica", 10)
    c.drawString(4.7 * cm, alto - 4 * cm,"00001")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(6 * cm, alto - 4 * cm,"Comp. Nro:")
    c.setFont("Helvetica", 10)
    c.drawString(8 * cm, alto - 4 * cm,"00000008")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, alto - 4.6 * cm, "Fecha de Emisión: ")
    c.setFont("Helvetica", 10)
    c.drawString(5.2 * cm, alto - 4.6 * cm, "31/07/2024")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, alto - 5.6 * cm, "CUIT: ")
    c.setFont("Helvetica", 10)
    c.drawString(3.1 * cm, alto - 5.6 * cm, "20375182905")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, alto - 6.1 * cm, "Ingresos Brutos: ")
    c.setFont("Helvetica", 10)
    c.drawString(5.1 * cm, alto - 6.1 * cm, "933137")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(2 * cm, alto - 6.6 * cm, "Fecha de Inicio de Actividades: ")
    c.setFont("Helvetica", 10)
    c.drawString(7.4 * cm, alto - 6.6 * cm, "01/12/2022")

    # Datos del cliente
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(12 * cm, alto - 4 * cm, "Razón Social")
    c.setFont("Helvetica", 10)
    c.drawString(12 * cm, alto - 4.5 * cm, "BONAFFINI FRANCO")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(12 * cm, alto - 5 * cm, "Dirección Comercial")
    c.setFont("Helvetica", 10)
    c.drawString(12 * cm, alto - 5.5 * cm, "Los Olivos, Casa 13 13 - Las Heras,Mendoza")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(12 * cm, alto - 6 * cm, "Condicion frente al IVA")
    c.setFont("Helvetica", 10)
    c.drawString(12 * cm, alto - 6.5 * cm, "Responsable Monotributo")

    # Detalles de la factura
    c.setFillColor(colors.HexColor("#F2F2F2"))
    c.rect(0, alto - 8.2 * cm, ancho, 0.7 * cm, fill=True, stroke=False)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(color_azul)
    c.drawString(2 * cm, alto - 8 * cm, "Descripción")
    c.drawString(8 * cm, alto - 8 * cm, "Cantidad")
    c.drawString(15 * cm, alto - 8 * cm, "Precio Unitario")
    c.drawString(18 * cm, alto - 8 * cm, "Total")

    c.setFont("Helvetica", 10)
    y = alto - 9 * cm
    for item in datos_factura['items']:
        c.drawString(2 * cm, y, item['descripcion'])
        c.drawString(8 * cm, y, str(item['cantidad']))
        c.drawString(15 * cm, y, f"${item['precio_unitario']:.2f}")
        c.drawString(18 * cm, y, f"${item['total']:.2f}")
        y -= 0.5 * cm

    # Totales
    y -= 0.5 * cm
    c.setFillColor(color_gris_claro)
    c.rect(13 * cm, y - 3 * cm, 6 * cm, 2.5 * cm, fill=True, stroke=False)
    c.setFillColor(colors.black)
    c.drawString(14 * cm, y - 1.3 * cm, "Subtotal:")
    c.drawString(17 * cm, y - 1.2 * cm, f"${datos_factura['subtotal']:.2f}")
    c.drawString(14 * cm, y - 1.8 * cm, "IVA:")
    c.drawString(17 * cm, y - 1.7 * cm, f"${datos_factura['iva']:.2f}")
    c.drawString(14 * cm, y - 2.3 * cm, "Total:")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(17 * cm, y - 2.2 * cm, f"${datos_factura['total']:.2f}")
    
    # Comenzamos el proceso de armado de QR:

    # Estos datos son los que te pide para armar el QR, desde la documentación de AFIP
    datos_cmp = {
        "ver": 1,
        "fecha": "2020-10-13",
        "cuit": 30000000007,
        "ptoVta": 10,
        "tipoCmp": 1,
        "nroCmp": 94,
        "importe": 12100,
        "moneda": "DOL",
        "ctz": 65,
        "tipoDocRec": 80,
        "nroDocRec": 20000000001,
        "tipoCodAut": "E",
        "codAut": 70417054367476
    }

    datos_cmp_str = json.dumps(datos_cmp)
    datos_cmp_base64 = base64.b64encode(datos_cmp_str.encode()).decode()

    url_qr = f"https://www.afip.gob.ar/fe/qr/?p={datos_cmp_base64}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    qr.add_data(url_qr)
    qr.make(fit=True)

    img_qr = qr.make_image(fill='black', back_color='white')
    img_qr_path = "qr_code.png"
    img_qr.save(img_qr_path)

    # Agregar el código QR
    qr_size = 3 * cm
    c.drawImage(img_qr_path, x=2 * cm, y=1 * cm, width=qr_size, height=qr_size)

    c.drawImage(afip_logo_img, x=5.5  * cm, y=3 * cm , width=4 *cm, height=1*cm)

    c.drawImage(disclaimer_img, x=5.5 * cm, y=1.5 * cm , width=10 *cm, height=1*cm )

    c.drawString(15 * cm, 3.5 * cm, "CAE N°:")
    c.setFont("Helvetica", 10)
    c.drawString(16.5 * cm, 3.5 * cm, "73365326440110")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(12.6 * cm, 2.8 * cm, "Fecha de Vto. de CAE:")
    c.setFont("Helvetica", 10)
    c.drawString(16.5 * cm, 2.8 * cm, "20/05/2024")

    c.showPage()
    c.save()

# Datos de ejemplo para crear el PDF
datos_factura = {
    "cliente_nombre": "Juan Pérez",
    "cliente_direccion": "Calle Falsa 123",
    "cliente_cuit": "20375182906",
    "fecha": "2024-05-19",
    "factura_nro": "0001-00000001",
    "condicion_venta": "Contado",
    "items": [
        {"descripcion": "Producto A", "cantidad": 2, "precio_unitario": 41.32, "total": 82.64},
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36}
        ,
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36}
        ,
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36},
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36},
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36},
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36},
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36},
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36},
        {"descripcion": "Producto B", "cantidad": 1, "precio_unitario": 17.36, "total": 17.36}
    ],
    "subtotal": 100.0,
    "iva": 17.36,
    "total": 117.36
}

# Generar la factura

# Ejecucion de funciones: >

generar_factura_pdf(datos_factura, "logo.png", "factura.pdf", "afip.png", "disclaimer.png")

# facturador_lotes()

# ultimo_autorizado()