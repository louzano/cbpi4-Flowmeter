# -*- coding: utf-8 -*-
import logging
import asyncio
import time
from cbpi.api import *
from cbpi.api.config import ConfigType

# Configuração de Log
logger = logging.getLogger(__name__)

# Tenta carregar a biblioteca gpiozero (Padrão no RPi 5)
try:
    from gpiozero import DigitalInputDevice
    GPIO_AVAILABLE = True
except ImportError:
    logger.error("FLOWMETER: Biblioteca 'gpiozero' não encontrada. O plugin rodará em modo simulado.")
    GPIO_AVAILABLE = False

# --- CLASSE DE DADOS (Matemática) ---
class FlowMeterData():
    def __init__(self):
        self.clicks = 0
        self.last_click = int(time.time() * 1000)
        self.flow = 0.0
        self.pour = 0.0

    def update(self, hertz_prop):
        current_time = int(time.time() * 1000)
        self.clicks += 1
        
        # Calcula delta em ms
        delta = max((current_time - self.last_click), 1)
        
        # Filtro de ruído: ignora pulsos absurdamente rápidos (<1ms)
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
    Property.Select(label="GPIO", options=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27], description="Pino BCM"),
    Property.Select(label="Exibição", options=["Volume Total", "Fluxo L/s"], description="Modo de visualização"),
    Property.Number(label="Fator K", configurable=True, default_value=7.5, description="Calibração (Hz para 1 L/min)")
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
        self.sensor_device = None

        # Configuração do Hardware (GPIOZERO)
        if GPIO_AVAILABLE:
            try:
                # DigitalInputDevice lida com pull_up=True por padrão para sensores tipo switch/hall
                # bounce_time=0.02 é o equivalente a bouncetime=20 do RPi.GPIO
                self.sensor_device = DigitalInputDevice(self.gpio, pull_up=True, bounce_time=0.02)
                
                # Define o callback. 
                # when_activated corresponde a borda de descida (Falling) no pull-up
                # when_deactivated corresponde a borda de subida (Rising) no pull-up
                # Para contagem de fluxo, qualquer um serve, desde que consistente.
                self.sensor_device.when_deactivated = self.pulse_callback
                
                logger.info(f"FLOWMETER: GPIO {self.gpio} iniciada com sucesso (backend gpiozero).")
            except Exception as e:
                logger.error(f"FLOWMETER: Falha ao iniciar GPIO {self.gpio}: {e}")

    # Callback executado a cada pulso
    def pulse_callback(self):
        self.data.update(self.k_factor)

    # Ação do botão de reset na interface
    @action(key="Zerar Volume", parameters=[])
    async def reset_volume(self, **kwargs):
        self.data.reset()
        self.value = 0.0
        self.push_update(0.0)

    # Loop principal de atualização da interface
    async def run(self):
        while self.running:
            if self.display_mode == "Volume Total":
                val = self.data.pour
            else:
                val = self.data.flow
            
            self.value = round(val, 2)
            self.push_update(self.value)
            await asyncio.sleep(1)
            
    # Cleanup ao desligar o plugin
    def stop(self):
        if self.sensor_device:
            self.sensor_device.close()

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
        self.sensor_device = None

        if GPIO_AVAILABLE:
            try:
                self.sensor_device = DigitalInputDevice(self.gpio, pull_up=True, bounce_time=0.02)
                self.sensor_device.when_deactivated = self.count
            except Exception as e:
                logger.error(f"VOLUMESENSOR: Erro GPIO {self.gpio}: {e}")

    def count(self):
        self.impulses += 1
        self.value = round(self.impulses / self.pulsos_litro, 3)

    async def run(self):
        while self.running:
            self.push_update(self.value)
            await asyncio.sleep(1)
            
    def stop(self):
        if self.sensor_device:
            self.sensor_device.close()

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
        if self.actor_id:
            await self.actor_on(self.actor_id)
        
        while self.running:
            try:
                current_vol = float(self.get_sensor_value(self.sensor_id).get("value", 0))
                
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
