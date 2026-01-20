# -*- coding: utf-8 -*-
import time
import json
import logging
from modules import cbpi
from modules.core.hardware import ActorBase, SensorPassive
from modules.core.step import StepBase
from flask import Blueprint, render_template, jsonify, request
from modules.core.props import Property, StepProperty

blueprint = Blueprint('flowmeter', __name__)

try:
    import RPi.GPIO as GPIO
    if GPIO.getmode() is None:
        GPIO.setmode(GPIO.BCM)
except Exception as e:
    print("Erro ao carregar GPIO: %s" % e)

class FlowMeterData():
    MS_IN_A_SECOND = 1000.0
    SECONDS_IN_A_MINUTE = 60

    def __init__(self):
        self.clicks = 0
        self.lastClick = int(time.time() * self.MS_IN_A_SECOND)
        self.hertz = 0.0
        self.flow = 0.0
        self.pour = 0.0
        self.enabled = True

    def update(self, currentTime, hertzProp):
        self.clicks += 1
        clickDelta = max((currentTime - self.lastClick), 1)
        
        if self.enabled and clickDelta < 1000:
            self.hertz = self.MS_IN_A_SECOND / clickDelta
            # Fluxo em L/s (Hertz / 7.5 / 60)
            self.flow = self.hertz / (self.SECONDS_IN_A_MINUTE * hertzProp)
            instPour = self.flow * (clickDelta / self.MS_IN_A_SECOND)
            self.pour += instPour
            
        self.lastClick = currentTime

    def clear(self):
        self.pour = 0.0
        self.clicks = 0
        return str(self.pour)

@cbpi.sensor
class Flowmeter(SensorPassive):
    gpio = Property.Select("GPIO", options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27])
    sensorShow = Property.Select("Flowmeter display", options=["Total volume", "Flow, unit/s"])
    hertzProp = Property.Text("Hertz", configurable=True, default_value="7.5", description="Calibração: Hertz para 1L/min (Padrão 7.5)")

    def init(self):
        # Inicializa os dados específicos desta instância de sensor
        self.fms_data = FlowMeterData()
        
        # Garante que a unidade de medida exista no banco de dados
        if cbpi.get_config_parameter("flowunit", None) is None:
            cbpi.add_config_parameter("flowunit", "L", "select", "Flowmeter unit", options=["L", "gal(us)", "gal(uk)", "qt"])

        try:
            pin = int(self.gpio)
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            
            # Limpa detecções antigas para evitar erros de "Edge already exists"
            try:
                GPIO.remove_event_detect(pin)
            except:
                pass
                
            GPIO.add_event_detect(pin, GPIO.RISING, callback=self.doAClick, bouncetime=20)
        except Exception as e:
            print("Erro ao configurar pino %s: %s" % (self.gpio, e))

    def doAClick(self, channel):
        currentTime = int(time.time() * 1000)
        try:
            hz = float(self.hertzProp)
            self.fms_data.update(currentTime, hz)
        except:
            self.fms_data.update(currentTime, 7.5)

    def convert(self, inputFlow):
        unit = cbpi.get_config_parameter("flowunit", "L")
        f_val = float(inputFlow)
        
        if unit == "gal(us)": f_val *= 0.264172
        elif unit == "gal(uk)": f_val *= 0.219969
        elif unit == "qt": f_val *= 1.056688
        
        return "{0:.2f}".format(f_val)

    def read(self):
        if self.sensorShow == "Total volume":
            val = self.fms_data.pour
        else:
            val = self.fms_data.flow
            
        self.data_received(self.convert(val))

    @cbpi.action("Reset to zero")
    def reset(self):
        self.fms_data.clear()
        self.data_received(0.0)

@cbpi.step
class FlowmeterStep(StepBase):
    sensor = StepProperty.Sensor("Sensor")
    actorA = StepProperty.Actor("Actor")
    volume = Property.Number("Volume", configurable=True)

    def init(self):
        if self.actorA:
            self.actor_on(int(self.actorA))

    def execute(self):
        sensor_id = int(self.sensor)
        # Busca o valor atual lido pelo sensor no cache do CBPi
        sensor_value = cbpi.cache.get("sensors").get(sensor_id).instance.fms_data.pour
        
        if float(sensor_value) >= float(self.volume):
            if self.actorA:
                self.actor_off(int(self.actorA))
            self.next()

@cbpi.initalizer()
def init(cbpi):
    cbpi.app.register_blueprint(blueprint, url_prefix='/api/flowmeter')
