# PBG Consulting - Reto de ingeniería Telefónica y Marcador
Este repositorio contiene la solución al reto de ingeniería de telefonía para PBG Consulting. El sistema implementa la capa lógica y de gestión de estado crítico de un marcador predictivo, asegurando que la línea de un agente se mantenga activa e independiente mientras gestiona llamadas concurrentes, eventos caóticos y caídas del sistema.

Para resolver las restricciones de un entorno de telefonía real (basado en el archivo de eventos proporcionado), el motor se construyó sobre las siguientes premisas de ingeniería:

Separación de Identidades (Patrón Conference Room): La identidad de la línea del agente (A-1) y la del cliente (C-101, C-102) se modelan como entidades separadas en la base de datos (agents y calls). El agente entra en estado AVAILABLE de forma independiente, permitiendo que la llamada del cliente se enlace o desenlace sin afectar la conexión física/SIP del agente.

Tolerancia a Fallos y Recuperación (Crash Recovery): Se descartó mantener el estado de las llamadas en la memoria RAM del proceso. En su lugar, se utilizó una base de datos SQLite (pbg_telephony.db). Cuando se simula una caída del servidor (evento process.restart en la secuencia 6), el sistema recupera el 100% del estado operativo leyendo la base de datos al reiniciar.

Idempotencia contra Webhooks Duplicados: El sistema registra cada secuencia procesada en la tabla webhook_logs. Cuando un evento llega duplicado (como el seq 3 marcado con "duplicate": true), la capa de persistencia lo intercepta y lo ignora silenciosamente, previniendo corrupciones en la máquina de estados.

Resolución de Eventos Fuera de Orden (Out-of-Order): Se implementó una máquina de estados finita (FSM) estricta. Si un evento rezagado intenta cambiar el estado de una llamada que ya alcanzó un estado terminal (como COMPLETED), la transición es rechazada estructuralmente.

Convergencia de Datos (CRM y Compliance):

Inbound Routing: Cuando ingresa una llamada externa, el sistema cruza en memoria el Caller ID con lead_book.json para resolver la identidad del cliente (ej. identificando a L201 y L202) y la encola correctamente (QUEUED).

Outbound Compliance: Antes de operar, el sistema procesa number_reputation.csv para identificar y enrutar las llamadas salientes únicamente a través de líneas marcadas como clean, mitigando riesgos de bloqueos SIP (como el error 603 Decline).****
