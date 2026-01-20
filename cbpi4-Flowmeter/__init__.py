# -*- coding: utf-8 -*-
import logging
import asyncio
import time
from cbpi.api import *
from cbpi.api.config import ConfigType

# Configuração de Log
logger = logging.getLogger(__name__)

# Tenta carregar a biblioteca GPIO de forma segura
try:
    import RPi.GPIO as GPIO
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BCM)
    GPIO_AVAILABLE = True
except Exception as e:
    logger.error(f"FLOWMETER: RPi.GPIO não encontrado (Modo Simulação). Erro: {e}")
    GPIO_AVAILABLE = False
    GPIO = None

# --- CLASSE DE DADOS (Lógica Matemática) ---
class FlowMeterData():
    def __init__(self):
        self.clicks = 0
        self.last_click = int(time.time() * 1000)
        self.flow = 0.0
        self.pour = 0.0

    def update(self, hertz_prop):
        current_time = int(time.time() * 1000)
        self.clicks += 1
        # Calcula tempo desde o último pulso
        delta = max((current_time - self.last_click), 1)
        
        # Filtro de ruído: ignora pulsos excessivamente rápidos (<1ms)
        if delta < 1000:
            # Frequência (Hz) = 1000ms / delta_ms
            hertz = 1000.0 / delta
            
            # Vazão (L/s) = Frequência / Fator K / 60
            self.flow = hertz / (60.0 * hertz_prop)
            
            # Volume (L) = Vazão * (tempo_do_pulso / 1000)
            self.pour += self.flow * (delta / 1000.0)
            
        self.last_click = current_time

    def reset(self):
        self.pour = 0.0
        self.flow = 0.0
        self.clicks = 0

# --- SENSOR PRINCIPAL (FlowSensor) ---
@parameters([
    Property.Select(label="GPIO", options=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27], description="Pino BCM (Sinal)"),
    Property.Select(label="Exibição", options=["Volume Total", "Fluxo L/s"], description="Modo de visualização no Dashboard"),
    Property.Number(label="Fator K", configurable=True, default_value=7.5, description="Calibração (Hz para 1 L/min). YF-S201 usa 7.5")
])
class FlowSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(FlowSensor, self).__init__(cbpi, id, props)
        self.value = 0.0
        self.gpio = int(self.props.get("GPIO", 0))
        self.display_mode = self.props.get("Exibição", "Volume Total")
        self.k_factor = float(self.props.get("Fator K", 7.5))
        
        # Inicializa lógica matemática
        self.data = FlowMeterData()

        # Configuração do Hardware
        if GPIO_AVAILABLE:
            try:
                GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                # Remove eventos anteriores para evitar conflitos se o sensor for editado
                try:
                    GPIO.remove_event_detect(self.gpio)
                except:
                    pass
                GPIO.add_event_detect(self.gpio, GPIO.RISING, callback=self.pulse_callback, bouncetime=20)
                logger.info(f"FLOWMETER: GPIO {self.gpio} iniciada com sucesso.")
            except Exception as e:
                logger.error(f"FLOWMETER: Falha ao iniciar GPIO {self.gpio}: {e}")

    # Callback executado a cada pulso elétrico
    def pulse_callback(self, channel):
        self.data.update(self.k_factor)

    # Ação do botão de reset na interface
    @action(key="Zerar Volume", parameters=[])
    async def reset_volume(self, **kwargs):
        self.data.reset()
        self.value = 0.0
        self.push_update(0.0)

    # Loop principal de atualização da interface (roda a cada 1 seg)
    async def run(self):
        while self.running:
            if self.display_mode == "Volume Total":
                val = self.data.pour
            else:
                val = self.data.flow
            
            self.value = round(val, 2)
            self.push_update(self.value)
            await asyncio.sleep(1)

# --- SENSOR DE VOLUME SIMPLES (Opcional) ---
@parameters([
    Property.Select(label="GPIO", options=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27]),
    Property.Number(label="Pulsos por Litro", configurable=True, default_value=450)
])
class VolumeSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(VolumeSensor, self).__init__(cbpi, id, props)
        self.value = 0.0
        self.impulses = 0
        self.gpio = int(self.props.get("GPIO", 0))
        self.pulsos_litro = float(self.props.get("Pulsos por Litro", 450))

        if GPIO_AVAILABLE:
            try:
                GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(self.gpio, GPIO.RISING, callback=self.count, bouncetime=20)
            except Exception as e:
                logger.error(f"VOLUMESENSOR: Erro GPIO {self.gpio}: {e}")

    def count(self, channel):
        self.impulses += 1
        self.value = round(self.impulses / self.pulsos_litro, 3)

    async def run(self):
        while self.running:
            self.push_update(self.value)
            await asyncio.sleep(1)

# --- PASSO AUTOMÁTICO (FlowStep) ---
class FlowStep(CBPiStep):
    @parameters([
        Property.Sensor(label="Sensor de Fluxo"),
        Property.Actor(label="Bomba/Valvula"),
        Property.Number(label="Volume Alvo (L)", configurable=True, default_value=5.0)
    ])
    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)
        self.target = float(self.props.get("Volume Alvo (L)", 5.0))
        self.sensor_id = self.props.get("Sensor de Fluxo")
        self.actor_id = self.props.get("Bomba/Valvula")

    async def run(self):
        # Liga a bomba se houver uma configurada
        if self.actor_id:
            await self.actor_on(self.actor_id)
        
        while self.running:
            try:
                # Lê o valor atual do sensor selecionado
                current_vol = float(self.get_sensor_value(self.sensor_id).get("value", 0))
                
                # Verifica se atingiu o alvo
                if current_vol >= self.target:
                    if self.actor_id:
                        await self.actor_off(self.actor_id)
                    self.cbpi.notify("FlowStep", f"Transferencia de {current_vol}L concluida!", type=NotificationType.SUCCESS)
                    break
            except Exception as e:
                logger.error(f"FLOWSTEP Error: {e}")
            
            await asyncio.sleep(0.5)

# --- REGISTRO DOS PLUGINS ---
def setup(cbpi):
    cbpi.plugin.register("FlowSensor", FlowSensor)
    cbpi.plugin.register("VolumeSensor", VolumeSensor)
    cbpi.plugin.register("FlowStep", FlowStep)
