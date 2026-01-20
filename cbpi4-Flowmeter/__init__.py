# -*- coding: utf-8 -*-
import logging
import asyncio
import time
from cbpi.api import *
from cbpi.api.config import ConfigType

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BCM)
except Exception as e:
    logger.error(f"Erro ao carregar RPi.GPIO: {e}")
    GPIO = None

class FlowMeterData():
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
            # Hertz calculado pelo tempo entre pulsos
            hertz = 1000.0 / delta
            # Vazão: Hertz / Fator_K (hertz_prop) / 60 segundos
            self.flow = hertz / (60.0 * hertz_prop)
            # Incremento de volume
            self.pour += self.flow * (delta / 1000.0)
            
        self.last_click = current_time

    def reset(self):
        self.pour = 0.0
        self.flow = 0.0
        self.clicks = 0

@parameters([
    Property.Select(label="GPIO", options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27], description="Pino BCM de sinal"),
    Property.Select(label="Exibição", options=["Volume Total", "Fluxo L/s"], description="O que mostrar no painel"),
    Property.Number(label="Fator K (Hertz)", configurable=True, default_value=7.5, description="Frequência para 1 L/min (Padrão YF-S201: 7.5)")
])
class FlowSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(FlowSensor, self).__init__(cbpi, id, props)
        self.value = 0.0
        self.gpio = int(self.props.get("GPIO", 0))
        self.display_mode = self.props.get("Exibição", "Volume Total")
        self.k_factor = float(self.props.get("Fator K (Hertz)", 7.5))
        self.data = FlowMeterData()

        if GPIO:
            try:
                GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(self.gpio, GPIO.RISING, callback=self.pulse_callback, bouncetime=20)
            except Exception as e:
                logger.error(f"Erro no GPIO {self.gpio}: {e}")

    def pulse_callback(self, channel):
        self.data.update(self.k_factor)

    @action(key="Resetar Volume", parameters=[])
    async def reset_volume(self, **kwargs):
        self.data.reset()
        self.value = 0.0
        self.push_update(0.0)

    async def run(self):
        while self.running:
            if self.display_mode == "Volume Total":
                self.value = round(self.data.pour, 2)
            else:
                self.value = round(self.data.flow, 3)
            
            self.push_update(self.value)
            await asyncio.sleep(1)

    def get_unit(self):
        return "L" if self.display_mode == "Volume Total" else "L/s"

class FlowStep(CBPiStep):
    @parameters([
        Property.Sensor(label="Sensor de Fluxo"),
        Property.Actor(label="Bomba/Válvula"),
        Property.Number(label="Volume Alvo (L)", configurable=True, default_value=10)
    ])
    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self.target = float(self.props.get("Volume Alvo (L)", 10))
        self.sensor_id = self.props.get("Sensor de Fluxo")
        self.actor_id = self.props.get("Bomba/Válvula")

    async def run(self):
        if self.actor_id:
            await self.actor_on(self.actor_id)
        
        while self.running:
            # Obtém valor atual do sensor
            current_vol = self.get_sensor_value(self.sensor_id).get("value", 0)
            
            if current_vol >= self.target:
                if self.actor_id:
                    await self.actor_off(self.actor_id)
                break
            
            await asyncio.sleep(0.5)

def setup(cbpi):
    cbpi.plugin.register("FlowSensor", FlowSensor)
    cbpi.plugin.register("FlowStep", FlowStep)
