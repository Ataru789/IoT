import os
import time
import paho.mqtt.client as mqtt

HOST = os.getenv("MQTT_HOST", "localhost")
PORT = int(os.getenv("MQTT_PORT", "1883"))
ROOM = os.getenv("ROOM", "room1")
INTERVAL = float(os.getenv("PUBLISH_INTERVAL_SEC", "1"))

# Stan środowiska
temperature = 21.0
aqi = 80.0

# Stany urządzeń
ac_on = False   # True = CHŁODZENIE (gdy za ciepło), False i grzanie sterujemy tą samą linią (AC)
heating_on = False  # True = GRZANIE (gdy za zimno)
purifier_on = False

# Parametry dynamiki (na sekundę)
COOL_RATE = 0.10
HEAT_RATE = 0.10
PURIFY_RATE = 1.5
AIR_DECAY = -0.25

TARGET = 21.0
EPS = 0.05  # strefa martwa

client = mqtt.Client()

def publish_states():
    client.publish(f"home/{ROOM}/state/ac", "ON" if (ac_on or heating_on) else "OFF", retain=True)
    # Dodatkowo rozróżnijmy tryb dla Node-RED (COOLING/HEATING/OFF)
    if ac_on:
        mode = "COOLING"
    elif heating_on:
        mode = "HEATING"
    else:
        mode = "OFF"
    client.publish(f"home/{ROOM}/state/hvac_mode", mode, retain=True)
    client.publish(f"home/{ROOM}/state/airpurifier", "ON" if purifier_on else "OFF", retain=True)

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT, rc=", rc)
    # Komendy urządzeń (z Node-RED)
    client.subscribe(f"home/{ROOM}/cmd/ac")              # 'ON'/'OFF' -> chłodzenie/grzanie włączone (tryb zależy od temp)
    client.subscribe(f"home/{ROOM}/cmd/heating")         # 'ON'/'OFF' (na wszelki wypadek, jeśli chcesz rozdzielić)
    client.subscribe(f"home/{ROOM}/cmd/airpurifier")     # 'ON'/'OFF'

    # Wstrzyknięcia aktualnych wartości z UI
    client.subscribe(f"home/{ROOM}/inject/temperature")  # np. "22.0"
    client.subscribe(f"home/{ROOM}/inject/aqi")          # 0-100

    publish_states()

def on_message(client, userdata, msg):
    global ac_on, heating_on, purifier_on, temperature, aqi

    topic = msg.topic
    payload = (msg.payload.decode() if msg.payload else "").strip().upper()

    if topic.endswith("/cmd/ac"):
        if payload == "ON":
            ac_on = True        # ← WŁĄCZ chłodzenie
            heating_on = False  # i wyłącz grzanie
        elif payload == "OFF":
            ac_on = False
            heating_on = False
        publish_states()

    elif topic.endswith("/cmd/heating"):
        if payload == "ON":
            heating_on = True
            ac_on = False
        elif payload == "OFF":
            heating_on = False
        publish_states()

    elif topic.endswith("/cmd/airpurifier"):
        purifier_on = (payload == "ON")
        publish_states()

    elif topic.endswith("/inject/temperature"):
        try:
            temperature = float(msg.payload.decode())
        except Exception:
            pass

    elif topic.endswith("/inject/aqi"):
        try:
            aqi = float(msg.payload.decode())
            aqi = max(0.0, min(100.0, aqi))
        except Exception:
            pass

client.on_connect = on_connect
client.on_message = on_message
client.connect(HOST, PORT, 60)
client.loop_start()

try:
    while True:
        # Symulacja temperatury
        if ac_on and not heating_on:
            temperature -= COOL_RATE
        elif heating_on and not ac_on:
            temperature += HEAT_RATE
        else:
            temperature += 0.0  # brak dryfu

        # Symulacja jakości powietrza
        if purifier_on:
            aqi += PURIFY_RATE
        else:
            aqi += AIR_DECAY

        # Zakresy
        temperature = max(15.0, min(30.0, temperature))
        aqi = max(0.0, min(100.0, aqi))

        # Publikacje
        client.publish(f"home/{ROOM}/temperature", f"{temperature:.2f}")
        client.publish(f"home/{ROOM}/aqi", f"{aqi:.0f}")

        time.sleep(INTERVAL)
except KeyboardInterrupt:
    pass
finally:
    client.loop_stop()
    client.disconnect()
