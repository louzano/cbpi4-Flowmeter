# -*- coding: utf-8 -*-
import os
from aiohttp import web
import logging
import asyncio
import time
import json
from cbpi.api import *
from cbpi.api.base import CBPiBase
from cbpi.api import parameters, Property, action
from cbpi.api.step import StepResult, CBPiStep
from cbpi.api.timer import Timer
from cbpi.api.dataclasses import NotificationType
from cbpi.api.config import ConfigType

logger = logging.getLogger(__name__)

try:
    import RPi.GPIO as GPIO
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BCM)
except Exception as e:
    logger.error(f"Erro ao carregar RPi.GPIO: {e}")
    GPIO = None

class Flowmeter_Config(CBPiExtension):
    def __init__(self, cbpi):
        self.cbpi = cbpi
        self._task = asyncio.create_task(self.init_sensor())

    async def init_sensor(self):
        plugin = await self.cbpi.plugin.load_plugin_list("cbpi4-Flowmeter")
        self.version = plugin[0].get("Version", "0.0.0")
        self.name = plugin[0].get("Name", "cbpi4-Flowmeter")
        
        # CORRIGIDO: Indentação ajustada nesta linha
        self.flowmeter_update = self.cbpi.config.get(self.name + "_update", None)

        unit = self.cbpi.config.get("flowunit", None)
        if unit is None:
            try:
                await self.cbpi.config.add("flowunit", "L", type=ConfigType.SELECT, description="Flowmeter unit", 
                                            source=self.name,
                                            options=[{"label": "L", "value": "L"},
                                                    {"label": "gal(us)", "value": "gal(us)"},
                                                    {"label": "gal(uk)", "value": "gal(uk)"},
                                                    {"label": "qt", "value": "qt"}])
            except Exception as e:
                logger.warning(f'Unable to add config: {e}')
        
        if self.flowmeter_update is None or self.flowmeter_update != self.version:
            try:
                await self.cbpi.config.add(self.name+"_update", self.version, type=ConfigType.STRING,
                                           description="Flowmeter Plugin Version",
                                           source='hidden')
            except Exception as e:
                logger.warning(f'Unable to update version config: {e}')

class FlowMeterData():
    SECONDS_IN_A_MINUTE = 60
    MS_IN_A_SECOND = 1000.0

    def __init__(self):
        self.clicks = 0
        self.lastClick = int(time.time() * FlowMeterData.MS_IN_A_SECOND)
        self.clickDelta = 0
        self.hertz = 0.0
        self.flow = 0.0
        self.pour = 0.0
        self.enabled = True

    def update(self, currentTime, hertzProp):
        self.clicks += 1
        self.clickDelta = max((currentTime - self.lastClick), 1)
        
        if self.enabled is True and self.clickDelta < 1000:
            self.hertz = FlowMeterData.MS_IN_A_SECOND / self.clickDelta
            # Fluxo em Unidades por segundo
            self.flow = self.hertz / (hertzProp)  
            instPour = self.flow * (self.clickDelta / FlowMeterData.MS_IN_A_SECOND)  
            self.pour += instPour
        
        self.lastClick = currentTime

    def clear(self):
        self.pour = 0
        self.clicks = 0
        return str(self.pour)

@parameters([
    Property.Select(label="GPIO", options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27], description="GPIO do sinal"),
    Property.Select(label="Formato da leitura", options=["Total volume", "Flow, unit/s"], description="Exibição no painel"),
    Property.Number(label="Frequência", configurable=True, default_value=7.5, description="Fator K do sensor (Hz por L/min)")
])
class FlowSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(FlowSensor, self).__init__(cbpi, id, props)
        self.value = 0
        self.gpio = int(self.props.get("GPIO", 0))
        # CORRIGIDO: Chaves batendo com o label do @parameters
        self.sensorShow = self.props.get("Formato da leitura", "Total volume")
        self.hertzProp = float(self.props.get("Frequência", 7.5))
        
        # CORRIGIDO: Inicialização do objeto antes do GPIO para evitar KeyError
        self.fms = {self.gpio: FlowMeterData()}

        try:
            if GPIO is not None:
                GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.remove_event_detect(self.gpio)
                GPIO.add_event_detect(self.gpio, GPIO.RISING, callback=self.doAClick, bouncetime=20)
        except Exception as e:
            logger.error(f"Erro GPIO FlowSensor: {e}")

    @action(key="Reset Sensor", parameters=[])
    async def Reset(self, **kwargs):
        self.reset()

    def doAClick(self, channel):
        currentTime = int(time.time() * 1000)
        if self.gpio in self.fms:
            self.fms[self.gpio].update(currentTime, self.hertzProp)

    def convert(self, inputFlow):
        unit = self.cbpi.config.get("flowunit", "L")
        if unit == "gal(us)": inputFlow *= 0.264172
        elif unit == "gal(uk)": inputFlow *= 0.219969
        elif unit == "qt": inputFlow *= 1.056688
        return round(float(inputFlow), 2)

    async def run(self):
        while self.running is True:
            if self.gpio in self.fms:
                if self.sensorShow == "Total volume":
                    val = self.fms[self.gpio].pour
                else:
                    val = self.fms[self.gpio].flow
                
                self.value = self.convert(val)
                self.push_update(self.value)
            await asyncio.sleep(1)

    def reset(self):
        if self.gpio in self.fms:
            self.fms[self.gpio].clear()
        self.value = 0
        self.push_update(self.value)

@parameters([
    Property.Select(label="GPIO", options=[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27]),
    Property.Number(label="impulsesPerVolumeUnit", configurable=True, default_value=450)
])
class VolumeSensor(CBPiSensor):
    def __init__(self, cbpi, id, props):
        super(VolumeSensor, self).__init__(cbpi, id, props)
        self.value = 0
        self.impulses = 0
        self.gpio = int(self.props.get("GPIO", 0))
        self.IperL = float(self.props.get("impulsesPerVolumeUnit", 450))

        try:
            if GPIO is not None:
                GPIO.setup(self.gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(self.gpio, GPIO.RISING, callback=self.impulseDetected, bouncetime=20)
        except Exception as e:
            logger.error(f"Erro GPIO VolumeSensor: {e}")

    def impulseDetected(self, channel):
        self.impulses += 1
        self.value = round(self.impulses / self.IperL, 3)

    async def run(self):
        while self.running:
            self.push_update(self.value)
            await asyncio.sleep(1)

    def reset(self):
        self.impulses = 0
        self.value = 0
        self.push_update(self.value)

class FlowStep(CBPiStep):
    @parameters([
        Property.Number(label="Volume", configurable=True),
        Property.Actor(label="Actor"),
        Property.Sensor(label="Sensor"),
        Property.Select(label="Reset", options=["Yes","No"])
    ])
    def __init__(self, cbpi, id, props):
        super().__init__(cbpi, id, props)

    async def on_start(self):
        self.target_volume = float(self.props.get("Volume", 0))
        self.actor_id = self.props.get("Actor")
        self.sensor_id = self.props.get("Sensor")
        self.resetsensor = self.props.get("Reset", "Yes")
        
        if self.actor_id: await self.actor_on(self.actor_id)
        
    async def run(self):
        while self.running:
            current_vol = self.get_sensor_value(self.sensor_id).get("value", 0)
            if current_vol >= self.target_volume:
                if self.actor_id: await self.actor_off(self.actor_id)
                self.cbpi.notify("FlowStep", "Volume atingindo!", NotificationType.SUCCESS)
                break
            await asyncio.sleep(0.5)

def setup(cbpi):
    cbpi.plugin.register("FlowStep", FlowStep)
    cbpi.plugin.register("VolumeSensor", VolumeSensor)
    cbpi.plugin.register("FlowSensor", FlowSensor)
    cbpi.plugin.register("Flowmeter_Config", Flowmeter_Config)
