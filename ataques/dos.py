# -*- coding: utf-8 -*-
import can, time, datetime, logging, random

logging.basicConfig(
    filename=f"bus(flood)-{datetime.datetime.now():%Y%m%d-%H%M%S}.log",
    level=logging.INFO,
    format='%(message)s')

def log_line(msg):
    payload = ''.join(f'{b:02X}' for b in msg.data)
    logging.info(f'({msg.timestamp}) {msg.channel} {msg.arbitration_id:03X}#{payload}')

bus = can.interface.Bus('can0', bustype='socketcan')

try:
    while True:
        # Gera 8 bytes: metade fixos 0xFF, metade aleatórios
        data = [random.randint(0x00, 0xFF) for _ in range(8)]
        msg = can.Message(arbitration_id=0x000, data=data, is_extended_id=False)
        bus.send(msg)
        log_line(msg)
        time.sleep(0.001)          # ~1 k msgs/s
except KeyboardInterrupt:
    pass
