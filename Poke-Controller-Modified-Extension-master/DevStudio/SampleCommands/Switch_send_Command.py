#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Authored by PokeCon Dev Studio from sample list: Switch_send_Command
from Commands.PythonSampleCommand import PythonSampleCommand
# POKECON_GENERATED_IMPORTS_BEGIN e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

# POKECON_GENERATED_IMPORTS_END

class Switch_send_CommandSampleCommand(PythonSampleCommand):
    NAME = 'Switch_send_Command'
    SAMPLE_LIST = 'Switch_send_Command'
    INCLUDED_SAMPLES = ['etc_sendCommand']
    # POKECON_GENERATED_CLASS_VARIABLES_BEGIN e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

    # POKECON_GENERATED_CLASS_VARIABLES_END

    def do(self):
        self.checkIfAlive()
        self.etc_sendCommand("Lbutton_down")
        # POKECON_USER_DO_BEGIN
        # Compose/call selected sample functions here.
        # POKECON_USER_DO_END


    # POKECON_FRAGMENT_BEGIN 230dae36e6ed696d333a977aed721b20ddc76faa71958dca1795378a50dc7950 etc_sendCommand/etc_sendCommand.pokesample.json
    def etc_sendCommand(self, command_name, wait: float = 0.04):
        Lbutton_down1 = "0x0000 4"
        Lbutton_down2 = "0x0000 8"
        Lbutton_up1 = "0x0000 0"
        Lbutton_up2 = "0x0000 8"
        Lbutton_left1 = "0x0000 6"
        Lbutton_left2 = "0x0000 8"
        Lbutton_right1 = "0x0000 2"
        Lbutton_right2 = "0x0000 8"
        plusbutton1 = "0x0800 8"
        plusbutton2 = "0x0000 8"

        if command_name == "Lbutton_down":
            self._etc_sendCommand_raw(Lbutton_down1, wait)
            self._etc_sendCommand_raw(Lbutton_down2, wait)
        elif command_name == "Lbutton_up":
            self._etc_sendCommand_raw(Lbutton_up1, wait)
            self._etc_sendCommand_raw(Lbutton_up2, wait)
        elif command_name == "Lbutton_up_push":
            self._etc_sendCommand_raw(Lbutton_up1, wait)
        elif command_name == "Lbutton_up_pull":
            self._etc_sendCommand_raw(Lbutton_up2, wait)
        elif command_name == "Lbutton_left":
            self._etc_sendCommand_raw(Lbutton_left1, wait)
            self._etc_sendCommand_raw(Lbutton_left2, wait)
        elif command_name == "Lbutton_right":
            self._etc_sendCommand_raw(Lbutton_right1, wait)
            self._etc_sendCommand_raw(Lbutton_right2, wait)
        elif command_name == "plusbutton":
            self._etc_sendCommand_raw(plusbutton1, wait)
            self._etc_sendCommand_raw(plusbutton2, wait)
        elif command_name == "plusbutton_push":
            self._etc_sendCommand_raw(plusbutton1, wait)
        elif command_name == "plusbutton_release":
            self._etc_sendCommand_raw(plusbutton2, wait)
        else:
            raise ValueError("Unknown Switch command: " + str(command_name))

    def _etc_sendCommand_raw(self, row: str, wait: float = 0.04):
        self.keys.ser.ser.write((row + "\r\n").encode("utf-8"))
        self.wait(wait)
        self.checkIfAlive()
    # POKECON_FRAGMENT_END etc_sendCommand/etc_sendCommand.pokesample.json

    # POKECON_USER_METHODS_BEGIN
    # Add methods that must be preserved across sample updates here.
    # POKECON_USER_METHODS_END
