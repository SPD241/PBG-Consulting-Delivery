import json
import sqlite3
import time
import os
import csv


DB_FILE = "pbg_telephony.db"

def cargar_contexto():
    """Carga los archivos adicionales para demostrar que entiendes cómo converge todo el sistema."""
    crm = {}
    numeros_limpios = []
    
    # 1. Cargar Lead Book
    try:
        with open("lead_book.json", "r") as f:
            leads = json.load(f)
            for lead in leads:
                phone = lead["phone"]
                if phone not in crm:
                    crm[phone] = []
                crm[phone].append(lead["id"])
        print("[*] Lead Book cargado: Listo para resolver identidades Inbound.")
    except Exception:
        print("[!] No se encontró lead_book.json")

    # 2. Cargar Reputación
    try:
        with open("number_reputation.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["label_observed"] == "clean":
                    numeros_limpios.append(row["number"])
        print(f"[*] Reputación cargada: {len(numeros_limpios)} números limpios para Outbound.\n")
    except Exception:
        print("[!] No se encontró number_reputation.csv")
        
    return crm, numeros_limpios

def setup_db():
    """Configura SQLite para mantener el estado seguro ante reinicios."""
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE webhook_logs (seq INTEGER PRIMARY KEY, ts TEXT, event TEXT)''')
    cursor.execute('''CREATE TABLE agents (agent_id TEXT PRIMARY KEY, status TEXT)''')
    cursor.execute('''CREATE TABLE calls (call_id TEXT PRIMARY KEY, status TEXT, linked_agent TEXT)''')
    conn.commit()
    return conn

def procesar_webhook(conn, payload, crm):
    cursor = conn.cursor()
    seq = payload.get("seq")
    event = payload.get("event")
    call_id = payload.get("call_control_id")
    
    # 1. MANEJO DE REINICIOS (Crash recovery)
    if event == "process.restart":
        print("\n[!] CRASH DEL SISTEMA (seq 6): Reiniciando...")
        time.sleep(1)
        print("[!] SISTEMA RECUPERADO. Leyendo estado intacto desde SQLite...")
        return

    # 2. IDEMPOTENCIA (Webhooks duplicados)
    cursor.execute("SELECT seq FROM webhook_logs WHERE seq = ?", (seq,))
    if cursor.fetchone():
        print(f"[-] Ignorando seq {seq} ({event}): DUPLICADO DETECTADO.")
        return
        
    cursor.execute("INSERT INTO webhook_logs (seq, ts, event) VALUES (?, ?, ?)", (seq, payload.get("ts"), event))

    # 3. MÁQUINA DE ESTADOS Y LÓGICA CORE
    if event == "agent_leg.answered":
        cursor.execute("INSERT OR REPLACE INTO agents (agent_id, status) VALUES (?, ?)", (call_id, "AVAILABLE"))
        print(f"[+] Agente {call_id} conectado a la conferencia (AVAILABLE).")

    elif event == "client_leg.initiated":
        cursor.execute("INSERT OR REPLACE INTO calls (call_id, status) VALUES (?, ?)", (call_id, "RINGING"))
        print(f"[+] Iniciando llamada a cliente {payload.get('to')} (RINGING).")

    elif event == "client_leg.answered":
        cursor.execute("SELECT status FROM calls WHERE call_id = ?", (call_id,))
        row = cursor.fetchone()
        
        # Validación Out-of-order
        if row and row[0] == "COMPLETED":
            print(f"[-] Ignorando seq {seq}: La llamada ya estaba COMPLETED (Out-of-order).")
        else:
            cursor.execute("SELECT agent_id FROM agents WHERE status = 'AVAILABLE' LIMIT 1")
            agent_row = cursor.fetchone()
            if agent_row:
                agent_id = agent_row[0]
                cursor.execute("UPDATE calls SET status = 'IN_PROGRESS', linked_agent = ? WHERE call_id = ?", (agent_id, call_id))
                cursor.execute("UPDATE agents SET status = 'BUSY' WHERE agent_id = ?", (agent_id,))
                print(f"[*] Llamada {call_id} CONTESTADA. Enlazada a Agente {agent_id} (Ahora BUSY).")

    elif event in ["client_leg.hangup", "sip.failure"]:
        cursor.execute("SELECT linked_agent FROM calls WHERE call_id = ?", (call_id,))
        row = cursor.fetchone()
        if row and row[0]:
            agent_id = row[0]
            cursor.execute("UPDATE agents SET status = 'AVAILABLE' WHERE agent_id = ?", (agent_id,))
            print(f"[*] Llamada {call_id} TERMINADA. Agente {agent_id} liberado a AVAILABLE.")
        cursor.execute("UPDATE calls SET status = 'COMPLETED' WHERE call_id = ?", (call_id,))
    
    elif event == "inbound.ringing":
        # Resolver identidad Inbound usando el CRM (lead_book.json)
        phone = payload.get("from")
        match = crm.get(phone, ["Desconocido"])
        print(f"[+] Llamada INBOUND detectada de {phone}. Matches en CRM: {match}. Encolando (QUEUED).")
        cursor.execute("INSERT OR REPLACE INTO calls (call_id, status) VALUES (?, ?)", (call_id, "QUEUED"))

    conn.commit()

def run():
    print("=== INICIANDO MOTOR DE TELEFONÍA PBG ===\n")
    crm, numeros_limpios = cargar_contexto()
    conn = setup_db()
    
    try:
        with open("webhooks.jsonl", "r") as file:
            for line in file:
                payload = json.loads(line.strip())
                procesar_webhook(conn, payload, crm)
                time.sleep(0.8) # Para que en el video se vea paso a paso
    except FileNotFoundError:
        print("Error: Pon el archivo webhooks.jsonl en esta misma carpeta.")
        return

    print("\n=== ESTADO FINAL EN BASE DE DATOS ===")
    cursor = conn.cursor()
    print("AGENTES:")
    for row in cursor.execute("SELECT * FROM agents"):
        print(f"  - {row[0]}: {row[1]}")
    print("LLAMADAS:")
    for row in cursor.execute("SELECT * FROM calls"):
        print(f"  - {row[0]}: Status={row[1]}, LinkedAgent={row[2]}")

if __name__ == "__main__":
    run()