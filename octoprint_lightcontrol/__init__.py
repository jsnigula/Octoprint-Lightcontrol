# coding=utf-8
from __future__ import absolute_import

__author__ = "Jan Snigula <jsnigula@mac.com>"
# __license__ = "GNU Affero General Public License " \
# "http://www.gnu.org/licenses/agpl.html"
# __copyright__ = "Copyright (C) 2017 Shawn Bruce - " \
#    "Released under terms of the AGPLv3 License"

import octoprint.plugin
from octoprint.server import user_permission
# import time
# import subprocess
# import threading
# import os
from flask import make_response, jsonify

from octoprint.util import ResettableTimer


class LightControl(octoprint.plugin.StartupPlugin,
                   octoprint.plugin.TemplatePlugin,
                   octoprint.plugin.AssetPlugin,
                   octoprint.plugin.SettingsPlugin,
                   octoprint.plugin.SimpleApiPlugin):

    def __init__(self):
        global GPIO
        import RPi.GPIO as GPIO

        self._pin_to_gpio_rev1 = [-1, -1, -1, 0, -1, 1, -1, 4, 14, -1, 15, 17,
                                  18, 21, -1, 22, 23, -1, 24, 10, -1, 9, 25,
                                  11, 8, -1, 7, -1, -1, -1, -1, -1, -1, -1,
                                  -1, -1, -1, -1, -1, -1, -1]
        self._pin_to_gpio_rev2 = [-1, -1, -1, 2, -1, 3, -1, 4, 14, -1, 15, 17,
                                  18, 27, -1, 22, 23, -1, 24, 10, -1, 9, 25,
                                  11, 8, -1, 7, -1, -1, -1, -1, -1, -1, -1,
                                  -1, -1, -1, -1, -1, -1, -1]
        self._pin_to_gpio_rev3 = [-1, -1, -1, 2, -1, 3, -1, 4, 14, -1, 15, 17,
                                  18, 27, -1, 22, 23, -1, 24, 10, -1, 9, 25,
                                  11, 8, -1, 7, -1, -1, 5, -1, 6, 12, 13, -1,
                                  19, 16, 26, 20, -1, 21]

        self.GPIOMode = ''
        self.onoffGPIOPin = 0
        self.invertonoffGPIOPin = False
        self.powerOffWhenIdle = False
        self.isLightOn = False
        self._idleTimer = None
        self._configuredGPIOPins = []

    def on_settings_initialized(self):
        self.onoffGPIOPin = self._settings.get_int(["onoffGPIOPin"])
        self._logger.debug("onoffGPIOPin: %s" % self.onoffGPIOPin)

        self.invertonoffGPIOPin = \
            self._settings.get_boolean(["invertonoffGPIOPin"])
        self._logger.debug("invertonoffGPIOPin: %s" % self.invertonoffGPIOPin)

        self.powerOffWhenIdle = \
            self._settings.get_boolean(["powerOffWhenIdle"])
        self._logger.debug("powerOffWhenIdle: %s" % self.powerOffWhenIdle)

        self.idleTimeout = self._settings.get_int(["idleTimeout"])
        self._logger.debug("idleTimeout: %s" % self.idleTimeout)

        self._configure_gpio()

        self._start_idle_timer()

    def _gpio_board_to_bcm(self, pin):
        if GPIO.RPI_REVISION == 1:
            pin_to_gpio = self._pin_to_gpio_rev1
        elif GPIO.RPI_REVISION == 2:
            pin_to_gpio = self._pin_to_gpio_rev2
        else:
            pin_to_gpio = self._pin_to_gpio_rev3

        return pin_to_gpio[pin]

    def _gpio_bcm_to_board(self, pin):
        if GPIO.RPI_REVISION == 1:
            pin_to_gpio = self._pin_to_gpio_rev1
        elif GPIO.RPI_REVISION == 2:
            pin_to_gpio = self._pin_to_gpio_rev2
        else:
            pin_to_gpio = self._pin_to_gpio_rev3

        return pin_to_gpio.index(pin)

    def _gpio_get_pin(self, pin):
        if (GPIO.getmode() == GPIO.BOARD and self.GPIOMode == 'BOARD') \
           or (GPIO.getmode() == GPIO.BCM and self.GPIOMode == 'BCM'):
            return pin
        elif GPIO.getmode() == GPIO.BOARD and self.GPIOMode == 'BCM':
            return self._gpio_bcm_to_board(pin)
        elif GPIO.getmode() == GPIO.BCM and self.GPIOMode == 'BOARD':
            return self._gpio_board_to_bcm(pin)
        else:
            return 0

    def _configure_gpio(self):

        self._logger.info("Running RPi.GPIO version %s" % GPIO.VERSION)
        if GPIO.VERSION < "0.6":
            self._logger.error("RPi.GPIO version 0.6.0 or greater required.")

        GPIO.setwarnings(False)

        for pin in self._configuredGPIOPins:
            self._logger.debug("Cleaning up pin %s" % pin)
            try:
                GPIO.cleanup(self._gpio_get_pin(pin))
            except (RuntimeError, ValueError) as e:
                self._logger.error(e)
        self._configuredGPIOPins = []

        if GPIO.getmode() is None:
            if self.GPIOMode == 'BOARD':
                GPIO.setmode(GPIO.BOARD)
            elif self.GPIOMode == 'BCM':
                GPIO.setmode(GPIO.BCM)
            else:
                return

        self._logger.info("Using GPIO for On/Off")
        self._logger.info("Configuring GPIO for pin %s" % self.onoffGPIOPin)
        try:
            if not self.invertonoffGPIOPin:
                initial_pin_output = GPIO.LOW
            else:
                initial_pin_output = GPIO.HIGH
            GPIO.setup(self._gpio_get_pin(self.onoffGPIOPin), GPIO.OUT,
                       initial=initial_pin_output)
            self._configuredGPIOPins.append(self.onoffGPIOPin)
        except (RuntimeError, ValueError) as e:
            self._logger.error(e)

    def _start_idle_timer(self):
        if self._idleTimer:
            self._reset_idle_timer()
        else:
            if self.powerOffWhenIdle and self.isLightOn:
                self._idleTimer = ResettableTimer(self.idleTimeout * 60,
                                                  self._idle_poweroff)
            self._idleTimer.start()

    def _stop_idle_timer(self):
        if self._idleTimer:
            self._idleTimer.cancel()
            self._idleTimer = None

    def _reset_idle_timer(self):
        try:
            if self._idleTimer.is_alive():
                self._idleTimer.reset()
            else:
                raise Exception()
        except Exception:
            self._start_idle_timer()

    def _idle_poweroff(self):
        if not self.powerOffWhenIdle:
            return

        self._logger.info("Idle timeout reached after %s minute(s). "
                          "shutting off Light." % self.idleTimeout)
        self.turn_light_off(True)

    def turn_light_on(self):
        self._logger.debug("Switching Light On Using GPIO: %s"
                           % self.onoffGPIOPin)
        if not self.invertonoffGPIOPin:
            pin_output = GPIO.HIGH
        else:
            pin_output = GPIO.LOW

        try:
            GPIO.output(self._gpio_get_pin(self.onoffGPIOPin), pin_output)
            self.isLightOn = True
            self._plugin_manager.send_plugin_message(self._identifier,
                                                     {'hasGPIO': True,
                                                      'isPSUOn': True})

            self._start_idle_timer()
        except (RuntimeError, ValueError) as e:
            self._logger.error(e)

    def turn_light_off(self, idleOff=False):
        self._logger.debug("Switching Light Off Using GPIO: %s"
                           % self.onoffGPIOPin)
        if not self.invertonoffGPIOPin:
            pin_output = GPIO.LOW
        else:
            pin_output = GPIO.HIGH

        try:
            GPIO.output(self._gpio_get_pin(self.onoffGPIOPin), pin_output)
            self.isLightOn = False
            self._plugin_manager.send_plugin_message(self._identifier,
                                                     {'hasGPIO': True,
                                                      'isPSUOn': False})
            if not idleOff:
                self._stop_idle_timer()
        except (RuntimeError, ValueError) as e:
            self._logger.error(e)

    def get_api_commands(self):
        return dict(
            turnLightOn=[],
            turnLightOff=[],
            toggleLight=[],
            getLightState=[]
        )

    def on_api_command(self, command, data):
        if not user_permission.can():
            return make_response("Insufficient rights", 403)

        if command == 'turnLightOn':
            self.turn_light_on()
        elif command == 'turnLightOff':
            self.turn_light_off()
        elif command == 'toggleLight':
            if self.isLightOn:
                self.turn_light_off()
            else:
                self.turn_light_on()
        elif command == 'getLightState':
            return jsonify(isLightOn=self.isLightOn)

    def get_settings_defaults(self):
        return dict(
            GPIOMode='BOARD',
            onoffGPIOPin=0,
            invertonoffGPIOPin=False,
            powerOffWhenIdle=False,
            idleTimeout=5,
        )

    def on_settings_save(self, data):
        old_GPIOMode = self.GPIOMode
        old_onoffGPIOPin = self.onoffGPIOPin

        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)

        self.GPIOMode = self._settings.get(["GPIOMode"])
        self.onoffGPIOPin = self._settings.get_int(["onoffGPIOPin"])
        self.invertonoffGPIOPin = \
            self._settings.get_boolean(["invertonoffGPIOPin"])
        self.powerOffWhenIdle = \
            self._settings.get_boolean(["powerOffWhenIdle"])
        self.idleTimeout = self._settings.get_int(["idleTimeout"])

        if old_GPIOMode != self.GPIOMode or old_onoffGPIOPin != self.onoffGPIOPin:
            self._configure_gpio()

        self._start_idle_timer()

    def get_settings_version(self):
        return 1

    def on_settings_migrate(self, target, current=None):
        pass

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=True)
        ]

    def get_assets(self):
        return {
            "js": ["js/lightcontrol.js"],
            "less": ["less/lightcontrol.less"],
            "css": ["css/lightcontrol.min.css"]
        }


__plugin_name__ = "Light Control"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = LightControl()
