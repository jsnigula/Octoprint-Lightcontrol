$(function() {
    function LightControlViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0]
        self.loginState = parameters[1];
        self.settings = undefined;
        self.hasGPIO = ko.observable(undefined);
        self.isLightOn = ko.observable(undefined);
        self.light_indicator = $("#lightcontrol_indicator");

        self.onBeforeBinding = function() {
            self.settings = self.settingsViewModel.settings;
        };

        self.onStartup = function () {
            self.isLightOn.subscribe(function() {
                if (self.isLightOn()) {
                    self.light_indicator.removeClass("off").addClass("on");
                } else {
                    self.light_indicator.removeClass("on").addClass("off");
                }
            });

            $.ajax({
                url: API_BASEURL + "plugin/lightcontrol",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "getLightState"
                }),
                contentType: "application/json; charset=UTF-8"
            }).done(function(data) {
                self.isLightOn(data.isLightOn);
            });
        }

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "lightcontrol") {
                return;
            }

            self.hasGPIO(data.hasGPIO);
            self.isLightOn(data.isLightOn);
        };

        self.toggleLight = function() {
            if (self.isLightOn()) {
                self.turnLightOff();
            } else {
                self.turnLightOn();
            }
        };

        self.turnLightOn = function() {
            $.ajax({
                url: API_BASEURL + "plugin/lightcontrol",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "turnLightOn"
                }),
                contentType: "application/json; charset=UTF-8"
            })
        };

    	self.turnLightOff = function() {
            $.ajax({
                url: API_BASEURL + "plugin/lightcontrol",
                type: "POST",
                dataType: "json",
                data: JSON.stringify({
                    command: "turnLightOff"
                }),
                contentType: "application/json; charset=UTF-8"
            })
        };
    }

    ADDITIONAL_VIEWMODELS.push([
        LightControlViewModel,
        ["settingsViewModel", "loginStateViewModel"],
        ["#navbar_plugin_lightcontrol", "#settings_plugin_lightcontrol"]
    ]);
});
