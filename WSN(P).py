from zeep import Client

# URL del servicio web SOAP
url = "https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?WSDL"

# Crear un cliente SOAP
client = Client(url)

# Datos necesarios para la solicitud
token = "PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiIHN0YW5kYWxvbmU9InllcyI/Pgo8c3NvIHZlcnNpb249IjIuMCI+CiAgICA8aWQgc3JjPSJDTj13c2FhLCBPPUFGSVAsIEM9QVIsIFNFUklBTE5VTUJFUj1DVUlUIDMzNjkzNDUwMjM5IiB1bmlxdWVfaWQ9IjEyNTA4MDUyNyIgZ2VuX3RpbWU9IjE2OTE1ODI4MzQiIGV4cF90aW1lPSIxNjkxNjI2MDk0Ii8+CiAgICA8b3BlcmF0aW9uIHR5cGU9ImxvZ2luIiB2YWx1ZT0iZ3JhbnRlZCI+CiAgICAgICAgPGxvZ2luIGVudGl0eT0iMzM2OTM0NTAyMzkiIHNlcnZpY2U9IndzX3NyX2NvbnN0YW5jaWFfaW5zY3JpcGNpb24iIHVpZD0iU0VSSUFMTlVNQkVSPUNVSVQgMjAzNzUxODI5MDUsIENOPWZyYW5jbyIgYXV0aG1ldGhvZD0iY21zIiByZWdtZXRob2Q9IjIyIj4KICAgICAgICAgICAgPHJlbGF0aW9ucz4KICAgICAgICAgICAgICAgIDxyZWxhdGlvbiBrZXk9IjIwMzc1MTgyOTA1IiByZWx0eXBlPSI0Ii8+CiAgICAgICAgICAgIDwvcmVsYXRpb25zPgogICAgICAgIDwvbG9naW4+CiAgICA8L29wZXJhdGlvbj4KPC9zc28+Cg=="  # Reemplaza esto con el valor real del token

sign="E79fBIayhk8+f8tlhLxQmCQSMMBQuC5W265rxJl8eToWxT32YGAqkr7Saa2gF6MkB/zz9PBaALDsa/mYaFqmzCivzWuqWCyPH66XJB+Vd1JuuyyhdArhDFumTDti4lIElxrKtUh2X/BiKq1h1OC07stlBBSvw+QZieeME/qyGe8="  # Reemplaza esto con el valor real del sign

while True:

    entrada = int(input("introduce cuit: "))

    cuitRepresentada = 20375182905  # Reemplaza esto con el valor real del CUIT representado

    idPersona = entrada  # Reemplaza esto con el valor real del ID de persona

    # Llamar a la operación getPersona del servicio web
    responses = client.service.getPersona_v2(token=token, sign=sign, cuitRepresentada=cuitRepresentada, idPersona=idPersona)

    # Imprimir la respuesta
    datos_generales = responses.datosRegimenGeneral.actividad


    print(datos_generales[0].idActividad)