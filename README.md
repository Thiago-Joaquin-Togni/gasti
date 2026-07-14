Gasti es un bot para gestion de gastos / ingresos.

El proyecto esta pensado para usar una arquitectura de 3 capas:

receivers --> core <--> ia

en receivers se centralizan todos los canales de información.

core (Processer.py) es el encargado de definir el tipo de mensaje recibido (texto, audio, imagen o doc), llamar a los metodos base de extracción según tipo, informar al usuario datos extraidos y esperar confirmación, y posteriormente insertar el registro confirmado en la BD.
Encapsula las clases BaseAIExtractor y DAO.