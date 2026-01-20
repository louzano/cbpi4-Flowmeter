# -*- coding: utf-8 -*-
import asyncio
import logging
import time
from cbpi.api import *

# Configuração do Logger para ver erros no terminal
logger = logging.getLogger(__name__)

# Tenta importar GPIO, se falhar (ex: rodando no PC), não trava o plugin
try:
    import RPi.GPIO as GPIO
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BCM)
    GPIO_AVAILABLE = True
except Exception as e:
    logger.error(f"FLOWMETER: RPi.GPIO não encontrado. O plugin rodará em modo simulado. Erro: {e}")
    GPIO_AVAILABLE = False
    GPIO = None

class FlowMeterData:
    def __init__(self):
        self.clicks = 0
        self.last_click = int(time.time() * 1000)
        self.flow = 0.0
        self.pour = 0.0

    def update(self, hertz_prop):
        current_time = int(time.time() * 1000)
        self.clicks += 1
        delta = max((current_time - self.last_click), 1)
        if delta < 1000:
            hertz = 1000.0 / delta
            self.flow = hertz / (60.0 * hertz_prop)
            self.pour += self.flow * (delta / 1000.0)
        self.last_click = current_time

    def reset(self):
        self.pour = 0.0
        self.flow = 0.0
        self.clicks = 0

@parameters([
    Property.Select(label="GPIO", options=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27], description="GPIO BCM"),
    Property.Select(label="Mode", options=["Volume Total", "Fluxo L/s"], description="Modo de Exibição"),
    Property.Number(label="K Factor", configurable=True, default_value=7.5, description="Frequencia (Hz) para 1 L/min")
])
class FlowSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(FlowSensor, self).__init__(cbpi, id, props)
        self.value = 0.0
        self.gpio = int(self.props.get("GPIO", 0))
        self.mode = self.props.get("Mode", "Volume Total")
        self.k_factor = float(self.props.get("K Factor", 7.5))
        self.data = FlowMeterData()

        if GPIO_AVAILABLE:
            try:
                GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(self.gpio, GPIO.RISING, callback=self.pulse, bouncetime=20)
                logger.info(f"FLOWMETER: GPIO {self.gpio} configurada com sucesso.")
            except Exception as e:
                logger.error(f"FLOWMETER: Erro ao configurar GPIO {self.gpio}: {e}")

    def pulse(self, channel):
        self.data.update(self.k_factor)

    @action(key="Reset", parameters=[])
    async def reset_vol(self, **kwargs):
        self.data.reset()
        self.value = 0.0
        self.push_update(0.0)

    async def run(self):
        while self.running:
            val = self.data.pour if self.mode == "Volume Total" else self.data.flow
            self.value = round(val, 2)
            self.push_update(self.value)
            await asyncio.sleep(1)

# --- ESTA PARTE É CRUCIAL PARA APARECER NO MENU ---
def setup(cbpi):
    cbpi.plugin.register("FlowSensor", FlowSensor)
    pass
