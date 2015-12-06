#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
History:
    2015-12-06: 0.0.13: other MCU, fixes
    2015-12-05: 0.0.12: added other MCU implementations; LCD support
    2015-12-04: 0.0.11: refactoring, some MCU implementation
    2015-11-27: 0.0.10: Fx Sends in PushEncoders Group 3; interpolation
    2015-11-26: 0.0.9: Fx/Aux Return Level in Bank2
    2015-11-26: 0.0.8: status leds on BCR2000; offline values from BCR; FX return level
    2015-11-25: 0.0.7: tests, fixes and offline loading of non active bank; FX parameters Shift
    2015-11-24: 0.0.6: Bank Switch
    2015-11-23: 0.0.5: refactoring; english translation
    2015-11-22: 0.0.4: save parameters in array (for future implementation of "Bank Switching"); MCU mode (only for Master faders - WIP)
    2015-11-21: 0.0.3: changed OSC -> Midi engine; Pan parameters
    2015-11-21: 0.0.2: refactoring, configuration file
    2015-11-20: 0.0.1: first working version; FX parameters
"""
VERSION="0.0.13"
LCD_I2C=False
RPI_I2C=True
PYLCDLIB=False

import rtmidi_python as rtmidi
import time
import re
import OSC
import threading
import sys
import os
if os.name == 'nt':
    import msvcrt
else:
    import sys, termios, atexit,time
    from select import select
import ConfigParser
import ast
import string
import RPi_I2C_driver

### Some global variables ###
CONFIGFILE='osc2midi.ini'
configfile=''
LastMidiEvent=0
DebugOSCsend=0
DebugOSCrecv=0
DebugMIDIsend=0
DebugMIDIrecv=0
Bank=0
ActiveBus=0
BUS_FX_RETURN=-1 # Not Yet Implemented
BUS_AUX_RETURN=-1 # Not Yet Implemented
BUS_MASTER=0
BUS_FX_SENDS=-1 # Not Yet Implemented
FxShift=0
Stat=0
FlipFlop=0
VoiceChannel=0
do_exit=False
BusName=["Master","Bus1","Bus2","Bus3","Bus4","Bus5","Bus6"]
FxType=[0,0,0,0]
FxReturn=[ #Fx1, Fx2, Fx3, Fx4, Aux
            [0,0,0,0,0], # Master
            [0,0,0,0,0], # Bus1
            [0,0,0,0,0]  # Bus2
        ]
Volume=[ # 16 channels
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16], # Main LR
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16], # Bus1
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16], # Bus2
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16], # Fx1
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16], # Fx2
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16], # Fx3
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16], # Fx4
       ]
Pan=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16] # 16 channels
Mute=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
Solo=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
FxParVal=[ # [type, value] for 16 parameters
            [['i',1],['i',2],['i',3],['i',4],['i',5],['i',6],['i',7],['i',8],['i',9],['i',10],['i',11],['i',12],['i',13],['i',14],['i',15],['i',16]], # Fx1
            [['i',1],['i',2],['i',3],['i',4],['i',5],['i',6],['i',7],['i',8],['i',9],['i',10],['i',11],['i',12],['i',13],['i',14],['i',15],['i',16]], # Fx2
            [['i',1],['i',2],['i',3],['i',4],['i',5],['i',6],['i',7],['i',8],['i',9],['i',10],['i',11],['i',12],['i',13],['i',14],['i',15],['i',16]], # Fx3
            [['i',1],['i',2],['i',3],['i',4],['i',5],['i',6],['i',7],['i',8],['i',9],['i',10],['i',11],['i',12],['i',13],['i',14],['i',15],['i',16]], # Fx4
         ]



### Some safe defaults (overloaded in config file)
MIDINAME="BCR2000 port 1"
MIDINAME2="None"
MidiMode='BCR'
ADDR='192.168.0.12'
PORT_SRV=10024
PORT_CLN=10023
WAITOSC=0.01 # seconds to wait between an OSC request and another (comunication is UDP)
WAITMIDI=0.02 # seconds to wait between a Midi Receive and the OSC parsing (to eliminate Midi feedbak)
WAITRELOAD=2 # seconds to wait between reloads requests
CurrentFx=1

NoReload=False
ReloadMasterLevels=True
ReloadMasterMute=True
ReloadMasterPan=True
ReloadMasterSolo=True
ReloadBus1Levels=True
ReloadBus2Levels=True    
ReloadFxType=True
ReloadFxParams=True

# This list contains the OSC parameters to map to midi for every type of fx
# The index in the inner list is the midi controller, the number at that index is the OSC parameter.
# i.e.: effect type 11 (3-Tap delay) is:
#     [1,4,5,6,7,9,2]
# that means: controller 0 (in my BCR2000 is CC2 on midi channel 3, because CC1 is faulty)
#   is OSC parameter 1. Controller 1 (CC3) is OSC parameter 4, and so on.
# NB: all values are considered as float! This is not the real situation, some parameters have integer values!! TO BE FIXED!!!
FxParam=[
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #00 Hall Reverb - 1: PreDelay, 2:Decay, 3:Size, 4: Damping, 5: Diffuse, 6: Level, 7: LoCut, 8: HiCut, 9: BassMulti, 10: Spread, 11: Shape, 12: ModSpeed
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #01 Ambience Reverb - 1: PreDelay, 2:Decay, 3:Size, 4: Damping, 5: Diffuse, 6: Level, 7: LoCut, 8: HiCut, 9: Modulate, 10: TailGain
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #02 Rich Plate Reverb - 1: PreDelay, 2:Decay, 3:Size, 4: Damping, 5: Diffuse, 6: Level, 7: LoCut, 8: HiCut, 9: BassMulti, 10: Spread, 11: Attack, 12: Spin, 13: EchoL, 14: EchoR, 15: EchoFeedL, 16: EchoFeedR
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #03 Room Reverb - 1: PreDelay, 2:Decay, 3:Size, 4: Damping, 5: Diffuse, 6: Level, 7: LoCut, 8: HiCut, 9: BassMulti, 10: Spread, 11: Attack, 12: Spin, 13: EchoL, 14: EchoR, 15: EchoFeedL, 16: EchoFeedR
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #04 Chamber Reverb - 1: PreDelay, 2:Decay, 3:Size, 4: Damping, 5: Diffuse, 6: Level, 7: LoCut, 8: HiCut, 9: BassMulti, 10: Spread, 11: Attack, 12: Spin, 13: ReflectionL, 14: ReflectionR, 15: ReflectionGainL, 16: ReflectionGainR
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #05 Plate Reverb - 1: PreDelay, 2:Decay, 3:Size, 4: Damping, 5: Diffuse, 6: Level, 7: LoCut, 8: HiCut, 9: BassMulti, 10: XOver, 11: Mod, 12: ModSpeed
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #06 Vintage Reverb
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #07 Vintage Room
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #08 Gated Reverb
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #09 Reverse Reverb
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #10 Stereo Delay
            [1,4,5,6,7,9,2,8,9,10,11,12,13,14], #11 3-Tap Delay - 1: Time, 2: ?, 3: ?, 4: Feed, 5: LoCut, 6: HiCut, 7: FactorA, 8: GainA, 9: PanA, 10: FactorB, 11: GainB, 12: PanB
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #12 Rhythm Delay
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #13 Stereo Chorus
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #14 Stereo Flanger
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #15 Stereo Phaser
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #16 Dimensional Chorus
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #17 Mood Filter
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #18 Rotary Speaker
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #19 Stereo Tremolo
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #20 Sub Octaver
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #21 Delay + Chamber
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #22 Chorus + Chamber
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #23 Flanger + Chamber
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #24 Delay + Chorus
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #25 Delay + Flanger
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #26 Modulation Delay
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #27 Graphic and Tru EQ
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #28 DeEsser
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #29 Xtec EQ1
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #30 Xtec EQ5
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #31 Wave Designer
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #32 Precision Limiter
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #33 Combinator
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #34 Fair Compressor
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #35 Leisure Compressor
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #36 Ultimo Compressor
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #37 Enhancer
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #38 Exciter
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #39 Stereo Imager
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #40 Edison EX1
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #41 Sound Maxer
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #42 Guitar Amp
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14], #43 Tube Stage
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14]  #44 Stereo / Dual Pitch
        ]

if len(sys.argv) > 2:
    if sys.argv[1] == '-f':
         configfile=sys.argv[2] 

def lcd_init():
    mylcd = RPi_I2C_driver.lcd()
    return(mylcd)

def ReadConfig(Section,Option,Type=None):
    if Type == 'int':
        retval=parser.getint(Section,Option)
    elif Type == 'float':
        retval=parser.getfloat(Section,Option)
    elif Type == 'bool':
        retval=parser.getboolean(Section,Option)
    else:
        retval=parser.get(Section,Option)
    out="ReadConfig: [%s] %s = " % (Section,Option)
    print out,retval
    return retval


print 
print "Osc2MidiBridge v."+VERSION
print "------------------------------"
#           1234567890123456
lcd=lcd_init()
lcd.lcd_display_string("Osc2MidiBridge",1)
lcd.lcd_display_string("%s by CGsoft"%VERSION,2)
time.sleep(1)
lcd.lcd_clear()

# The config file is searched firs#t in the home directory, then in the current working folder.
parser = ConfigParser.SafeConfigParser()
home = os.path.expanduser("~")
if configfile == '':
    if os.path.isfile(home+CONFIGFILE):
        configfile=home+CONFIGFILE
    else:
        configfile=CONFIGFILE

print "ConfigFile: ",configfile
        
if parser.read(configfile) != None:
    try:
        MIDINAME=ReadConfig('MIDI', 'DeviceName')
        MIDINAME2=ReadConfig('MIDI', 'DeviceName2')
        ADDR=ReadConfig('OSC', 'Address')
        PORT_SRV=ReadConfig('OSC', 'ServerPort','int')
        PORT_CLN=ReadConfig('OSC', 'ClientPort','int')
        WAITOSC=ReadConfig('OSC', 'Wait','float')
        WAITMIDI=ReadConfig('MIDI', 'Wait','float')
        WAITRELOAD=ReadConfig('OSC2Midi', 'WaitReload','float')
        CurrentFx=ReadConfig('OSC2Midi','CurrentFx','int')
        FxParam=ast.literal_eval(ReadConfig('OSC2Midi', "FxParam"))
        ReloadMasterLevels=ReadConfig('OSC2Midi','ReloadMasterLevels','bool')
        ReloadMasterMute=ReadConfig('OSC2Midi','ReloadMasterMute','bool')
        ReloadMasterPan=ReadConfig('OSC2Midi','ReloadMasterPan','bool')
        ReloadMasterSolo=ReadConfig('OSC2Midi','ReloadMasterSolo','bool')
        ReloadBus1Levels=ReadConfig('OSC2Midi','ReloadBus1Levels','bool')
        ReloadBus2Levels=ReadConfig('OSC2Midi','ReloadBus2Levels','bool')    
        ReloadFxType=ReadConfig('OSC2Midi','ReloadFxType','bool')
        ReloadFxParams=ReadConfig('OSC2Midi','ReloadFxParams','bool')
        NoReload=ReadConfig('OSC2Midi','NoReload','bool')
        MidiMode=ReadConfig('MIDI','Mode')

    except ConfigParser.NoSectionError,err:
        print "Exception raised when a specified section is not found."
        print "ERROR:",err
        pass

    except ConfigParser.DuplicateSectionError,err:
        print "Exception raised if add_section() is called with the name of a section that is already present."
        print "ERROR:",err
        pass

    except ConfigParser.NoOptionError,err:
        print "Exception raised when a specified option is not found in the specified section."
        print "ERROR:",err
        pass
else:
    print "Config file not found..."
    
"""
Esempio di "osc2midi.ini":
    [MIDI]
    DeviceName = BCR 2000 port 1
    Wait = 0.02

    [OSC]
    Address = 192.168.0.12
    Port = 10024
    Wait = 0.02

    [OSC2Midi]
    WaitReload = 2
    FxParam = [
            [1,2,3,4,5,6,7], #00 Hall Reverb
            [1,2,3,4,5,6,7], #01 Ambience Reverb
            [1,2,3,4,5,6,7], #02 Rich Plate Reverb
            [1,2,3,4,5,6,7], #03 Room Reverb
            [1,2,3,4,5,6,7], #04 Chamber Reverb
            [1,2,3,4,5,6,7], #05 Plate Reverb
            [1,2,3,4,5,6,7], #06 Vintage Reverb
            [1,2,3,4,5,6,7], #07 Vintage Room
            [1,2,3,4,5,6,7], #08 Gated Reverb
            [1,2,3,4,5,6,7], #09 Reverse Reverb
            [1,2,3,4,5,6,7], #10 Stereo Delay
            [1,4,5,6,7,9,2], #11 3-Tap Delay - 1: Time, 2: ?, 3: ?, 4: Feed, 5: LoCut, 6: HiCut, 7: FactorA, 8: GainA, 9: PanA, 10: FactorB, 11: GainB, 12: PanB
            [1,2,3,4,5,6,7], #12 Rhythm Delay
            ....
            ]

"""
if os.name != 'nt':
# save the terminal settings
    try:
        fd = sys.stdin.fileno()
        new_term = termios.tcgetattr(fd)
        old_term = termios.tcgetattr(fd)

# new terminal setting unbuffered
        new_term[3] = (new_term[3] & ~termios.ICANON & ~termios.ECHO)

# switch to normal terminal
        def set_normal_term():
            termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)

# switch to unbuffered terminal
        def set_curses_term():
            termios.tcsetattr(fd, termios.TCSAFLUSH, new_term)

        def putch(ch):
            sys.stdout.write(ch)

        def getch():
            return sys.stdin.read(1)

        def getche():
            ch = getch()
            putch(ch)
            return ch

        def kbhit():
            dr,dw,de = select([sys.stdin], [], [], 0)
            return dr <> []


        atexit.register(set_normal_term)
        set_curses_term()
    except:
        pass

def sendToMCU(fader,val):
    midi_out.send_message([0x90,0x67+fader,127]) # unlock fader
    midi_out.send_message([0xDF+fader ,val,val]) # move fader
    midi_out.send_message([0x90,0x67+fader ,0])  # lock fader

def sendToBCR(channel,slot,val):
    if MidiMode == 'BCR':
        if channel >= 0 and channel <=3:
            cmd=0xB0+channel
        midi_out.send_message([cmd,slot,val])


def interpolate(value, inMin, inMax, outMin, outMax):
    """
    map the value, originally in range (inMin, inMax), to proportional value in range (outMin,outMax)
    """
    # Figure out how 'wide' each range is
    inSpan = inMax - inMin
    outSpan = outMax - outMin

    # Convert the in range into a 0-1 range (float)
    valueScaled = float(value - inMin) / float(inSpan)

    # Convert the 0-1 range into a value in the out range.
    return outMin + (valueScaled * outSpan)

def Reload(client,force=False):
    """
    Send to XR18 a request for every parameter that we need to show on controller
    """
    if NoReload and force != True:
        print "NoReload!"
        return

    
    # Here we are asking some values back from XR18 (an OSC message with an address without value send to XR18 triggers an OSC message back from XR18 with the actual value)
    # Let's start with the Type of effect loaded in the 4 slot available and the return levels.
    # NB: slot are 1,2,3,4.
    if ReloadFxType:
        for i in range(1,5):
            if DebugOSCsend > 0:
                print "OSCsend: /fx/%d/type" % i
            client.send(OSC.OSCMessage("/fx/%d/type" % i)) # FX type
            client.send(OSC.OSCMessage("/rtn/%d/mix/fader" % i)) # FX return level (Master)
            time.sleep(WAITOSC)
            client.send(OSC.OSCMessage("/rtn/%d/mix/01/level" % i)) # FX return level (Bus1)
            time.sleep(WAITOSC)
            client.send(OSC.OSCMessage("/rtn/%d/mix/02/level" % i)) # FX return level (Bus2)
            time.sleep(WAITOSC)
    client.send(OSC.OSCMessage("/lr/config/name")) # Name of the master bus
    time.sleep(WAITOSC)
    for i in range(1,7):
            client.send(OSC.OSCMessage("/bus/%d/config/name" % i)) # Name of the bus
            time.sleep(WAITOSC)
    for i in range(1,17): 
        # Volume Master
        if ReloadMasterLevels:
            client.send(OSC.OSCMessage("/ch/%02d/mix/fader" % i)) # Master LR
            time.sleep(WAITOSC)
            client.send(OSC.OSCMessage("/ch/%02d/config/name" % i)) # Name of the channel 
            time.sleep(WAITOSC)
            for j in range(7,11): # 7-10 are the FX busses
                client.send(OSC.OSCMessage("/ch/%02d/mix/%02d/level" % (i,j))) # FX sends
                time.sleep(WAITOSC)


        # Mute
        if ReloadMasterMute:
            client.send(OSC.OSCMessage("/ch/%02d/mix/on" % i)) # Mute
            time.sleep(WAITOSC)

        # Pan
        if ReloadMasterPan:
            client.send(OSC.OSCMessage("/ch/%02d/mix/pan" % i)) # Pan
            time.sleep(WAITOSC)

        #Solo
        if ReloadMasterSolo:
            client.send(OSC.OSCMessage("/-stat/solosw/%02d" % i)) # Solo
            time.sleep(WAITOSC)

        # Send levels for Bus1
        if ReloadBus1Levels:
            client.send(OSC.OSCMessage("/ch/%02d/mix/01/level" % i)) # Phones 1 (Bus1)
            time.sleep(WAITOSC)

        # Send levels for Bus2
        if ReloadBus2Levels:
            client.send(OSC.OSCMessage("/ch/%02d/mix/02/level" % i)) # Phones 2 (Bus2)
            time.sleep(WAITOSC)
    # FX parameters for the currently selected slot.
    # CurrentFX is the currently selected slot (we can select 1 of 4 different slots with the 4 "User defined" buttons on BCR2000)
    if ReloadFxParams:
        for j in range(1,5):
            for i in FxParam[FxType[j-1]]:
                if DebugOSCsend > 0:
                    print "OSCsend: /fx/%d/par/%02d" % (j,i)
                client.send(OSC.OSCMessage("/fx/%d/par/%02d" % (j,i))) # FX parameters
                time.sleep(WAITOSC)
                
def request_notifications(client):
    """
    Sends /xremote repeatedly to mixing desk to make sure changes are transmitted to our server; take care of user interaction; calls Reload.
    """
    global do_exit
    global DebugOSCsend
    global DebugOSCrecv
    global DebugMIDIsend
    global DebugMIDIrecv
    
    global NoReload

    while do_exit == False:
        #lcd_status()
        client.send(OSC.OSCMessage("/xremote"))
        time.sleep(WAITRELOAD)
        if NoReload == False:
            Reload(client)

        try:
            ch=''
            if os.name == 'nt': # At the moment this works only in Windows... That's all I need.
                if msvcrt.kbhit():
                    ch=msvcrt.getch() 
            else:
                if kbhit():
                    ch=getch()
            if ch != '': 
                print "hai premuto il tasto",ch
                if ch == 'Q':
                    do_exit=True
                    print "-----------------------------------------------"
                    print "Closing threads... Now you can exit with Ctrl-C"
                if ch == 'q':
                    DebugOSCsend=0
                    DebugOSCrecv=0
                    DebugMIDIsend=0
                    DebugMIDIrecv=0
                    status()
                if ch == 'h':
                    help()
                if ch == 's':
                    status()
                if ch == 'n':
                    NoReload=True
                    status()
                if ch == 'r':
                    NoReload=False
                    status()
                if ch == 'o':
                    DebugOSCsend+=1
                    status()
                if ch == 'O':
                    DebugOSCrecv+=1
                    status()
                if ch == 'm':
                    DebugMIDIsend+=1
                    status()
                if ch == 'M':
                    DebugMIDIrecv+=1
                    status()
                if ch == 'R':
                    Reload(client,True)

        except:
            pass
    exit()

def lcd_status(MidiChannel=0, cc=0, val=0):
    if ActiveBus == 0:
        BUS="MASTER: %s" % BusName[0]
    for Bus in range(1,7):
        if ActiveBus == Bus:
            BUS="Bus%d: %s" %(Bus, BusName[Bus])
    lcd=lcd_init()
   #lcd.lcd_clear()
    lcd.lcd_display_string("Bank=%d Fx=%d"%(Bank,CurrentFx),1)
    lcd.lcd_display_string(" "*16,2)
    lcd.lcd_display_string("%s"%(BUS),2)
    #if MidiChannel < 16 and MidiChannel > 0 and cc < 0x100 and cc >= 0 and val < 0x100 and val >= 0 and time.time() - LastMidiEvent > 1: 
    #    lcd.lcd_display_string("Ch%x CC%02x v:%02x"%(MidiChannel,cc,val),2)
def help():
    print "h - this help page"
    print "Q - prepare to quit (close sockets and threads)"
    print "q - quiet: ends debug informations"
    print "n - set to NoReload Mode"
    print "r - set to Reload Mode"
    print "R - Reload NOW!"
    print "o - increment DebugOSCsend"
    print "O - increment DebugOSCrecv"
    print "m - increment DebugMIDIsend"
    print "M - increment DebugMIDIrecv"
    print "s - prints status info"
    print "-------------------------------------------------"

def status():
    print "-------------------------------"
    print "Status:"
    print "Debug: OSCsend=%d, OSCrecv=%d, MIDIsend=%d, MIDIrecv=%d" % (DebugOSCsend,DebugOSCrecv,DebugMIDIsend,DebugMIDIrecv)
    print "NoReload=%d" % NoReload
    print "VoiceChannel=%d" % VoiceChannel
    print "CurrentFx=%d" % CurrentFx
    print "Bank=%d" % Bank
    print "ActiveBus=%d" % AciveBus
    print "-------------------------------"
    # TO BE CONTINUED...

def Progress(incremento=127/15):
    """
    Show a moving led on MidiChannel3, CC1 (it's a faulty rotary controller on my BCR2000), 
    then update status of ledbutton in MidiChannel1,CC85 (Bank Select): Off=Bank0, On=Bank1, Blink=Bank2
    """
    global Stat
    global FlipFlop
    sendToBCR(2,1,int(Stat))
    Stat += incremento
    if Stat > 127:
        Stat = 127/15
    if Stat <= 0:
        Stat = 127
    if do_exit != True:
        threading.Timer(1,Progress,()).start()
    if Bank == 0:
        sendToBCR(0,85,0)
    if Bank == 1:
        sendToBCR(0,85,127)
    if Bank == 2:
        sendToBCR(0,85,FlipFlop*127)
        FlipFlop=not FlipFlop

    
def parse_messages():
    """
    Starts the OSC msg_handler thread and initialize bidirectional connection with XR18 via OSC.
    """

    def msg_handler(addr, tags, data, client_address):
        """
        Parses the received OSC messages, sends corresponding values to Midi. Ignore non pertinent messages.
        """
        global VoiceChannel
        global LastMidiEvent
        global FxType
        global CurrentFx
        global FxParam
        global Volume
        global Pan
        global Mute
        global Solo
        global FxParVal
        global FxReturn        
        global BusName

        if time.time() - LastMidiEvent > WAITMIDI: # we are parsing OSC messages only if a consistent time is passed from the last Midi event
            if DebugOSCrecv > 0:
                print 'OSCMessage("%s",%s,%s)' % (addr, tags, data)
  
            if data[0] != data[0]: # take care of the "NaN" situation
                data[0]=0

            val=0
            if tags == 'f':
                val=int(data[0]*127)
            if tags == 'i':
                val=int(data[0])
                
            # FX type (es.: "/fx/1/type")
            if re.match("/fx/./type",addr):
                slot=int(addr[4]) # addr[4] is the FX (1 to 4)
                FxType[slot-1]=data[0] 
                if DebugOSCrecv > 0:
                    print "Found FX %d set to %d" % (slot,FxType[slot-1])
                    
            # We need to know which channel is the Main Vocal, so we can map the Expression Pedal (on FCB1010)
            # to the right Send for Fx.
            elif re.match("/ch/../config/name",addr):
                channel=int(addr[4:6])
                name=data[0]
                if DebugOSCrecv > 0: print "Channel %d is named %s" %(channel,name)
                if name.lower() in ("voce","voce1","vox","vox1","voice","voice1"):
                    VoiceChannel=channel
                    if DebugOSCrecv > 0: print "VoiceChannel=%d" % channel
            elif re.match("/bus/./config/name",addr):
                channel=int(addr[5])
                name=data[0]
                if DebugOSCrecv > 0: print "Bus %d is named %s" %(channel,name)
                BusName[channel]=name 
            elif re.match("/lr/config/name",addr):
                name=data[0]
                if DebugOSCrecv > 0: print "Master Bus is named %s" %(name)
                BusName[0]=name 
                    
            elif re.match("/ch/../mix/../level",addr): # Bus Sends
            # The busses 7-10 are the Fx Return Busses
                  val=int(data[0]*127)
                  channel=int(addr[4:6])
                  bus=int(addr[11:13])
                  if channel >= 1 and channel <= 16:
                      if bus == 1:
                        Volume[1][channel-1]=val
                      if bus == 2:
                        Volume[2][channel-1]=val
                      if bus >=7 and bus <= 10:
                          Volume[bus-4][channel-1]=val
                  if channel >= (1+8*Bank) and channel <= (8+8*Bank):
                      if bus == 1:
                          if MidiMode == 'BCR':
                              sendToBCR(1,channel-8*Bank,val)
                          elif MidiMode == 'MCU':
                              if ActiveBus == bus:
                                  sendToMCU(channel-8*Bank,val)
                      
                      elif bus == 2:
                          if MidiMode == 'BCR':
                              sendToBCR(3,channel-8*Bank,val)
                          elif MidiMode == 'MCU':
                              if ActiveBus == bus:
                                  sendToMCU(channel-8*Bank,val)
                      if bus >=7 and bus <= 10:
                          if MidiMode == 'BCR':
                              if bus == CurrentFx+6:
                                  sendToBCR(0,16+channel-8*Bank,val)
                              elif MidiMode == 'MCU':
                                  if ActiveBus == bus:
                                      sendToMCU(channel-8*Bank,val)
                      else:
                        pass # At the moment, the other busses are not mapped...
                          
                  if DebugOSCrecv > 0:
                      print "Bus %d, Channel %d, Val=%d" % (bus,channel,val)
                  

            # FX parameters (es.: "/fx/1/par/06")
            elif re.match("/fx/./par/..",addr): 
                slot=int(addr[4])
                par=int(addr[10:12])
                
                if tags == 'f':
                    val=int(data[0]*127)
                if tags == 'i':
                    val=int(data[0])

                if par <= len(FxParVal):
                    FxParVal[slot-1][par-1][0]=tags
                    FxParVal[slot-1][par-1][1]=val
                if slot == CurrentFx: #  here we are
                    index=2+FxParam[FxType[slot-1]].index(par)-6*FxShift
                    if index >=2 and index <= 7:
                        # ie: slot=2, FxType[1]=11, CurrentFx=2, FxParam[11]=[1,4,5,6,7,9,2], par=9 -> send(0xB2,6,val)
                        try:
                            if MidiMode == 'BCR':
                                sendToBCR(2,index,val) #MIDI ch. 3 NB: in my BCR fx params starts from CC2 (CC1 is faulty!)
                            elif MidiMode == 'MCU':
                                if ActiveBus == bus:
                                    sendToMCU(index,val)
                        except:
                            pass
         
                if DebugOSCrecv > 0:
                    print "FX: current=%d - slot=%d - par=%d - val=%f" %(CurrentFx,slot,par,data[0])

            # Fx Return Levels (Master)
            elif re.match("/rtn/./mix/fader",addr):
                slot=int(addr[5])
                val=int(data[0]*127)
                FxReturn[0][slot-1]=val
         
                if DebugOSCrecv > 0:
                    print "FX return: current=%d - slot=%d - val=%f" %(CurrentFx,slot,val)
                
                if Bank == 2:
                    if MidiMode == 'BCR':
                        sendToBCR(0,slot,val)
                    elif MidiMode == 'MCU':
                        if ActiveBus == BUS_FX_RETURN:
                            sendToMCU(channel,val)

            # Aux Return Levels (Master)
            elif re.match("/rtn/aux/mix/fader",addr):
                slot=5
                val=int(data[0]*127)
                FxReturn[0][slot-1]=val
         
                if DebugOSCrecv > 0:
                    print "Aux return: current=%d - slot=%d - val=%f" %(CurrentFx,slot,val)
                
                if Bank == 2:
                    if MidiMode == 'BCR':
                        sendToBCR(0,slot,val)
                    elif MidiMode == 'MCU':
                        if ActiveBus == BUS_AUX_RETURN:
                            sendToMCU(channel,val)



            # Fx Return Levels
            elif re.match("/rtn/./mix/../level",addr):
                slot=int(addr[5])
                val=int(data[0]*127)
                bus=int(addr[11:13])
                if bus >= 1 and bus <= 2:
                    FxReturn[bus][slot-1]=val

                if DebugOSCrecv > 0:
                    print "FX return: current=%d - slot=%d - bus=%d - val=%f" %(CurrentFx,slot,bus,val)

                if Bank == 2:
                    if MidiMode == 'BCR':
                        if bus==1:
                            sendToBCR(1,slot,val)
                        if bus==2:
                            sendToBCR(3,slot,val)
                    elif MidiMode == 'MCU':
                        if ActiveBus == bus:
                            sendToMCU(slot,val)


            # Aux Return Levels
            elif re.match("/rtn/aux/mix/../level",addr):
                slot=5
                val=int(data[0]*127)
                bus=int(addr[11:13])
                FxReturn[bus][slot-1]=val

                if DebugOSCrecv > 0:
                    print "FX return: current=%d - slot=%d - bus=%d - val=%f" %(CurrentFx,slot,bus,val)

                if Bank == 2:
                    if MidiMode == 'BCR':
                        if bus==1:
                            sendToBCR(1,slot,val)
                        if bus==2:
                            sendToBCR(3,slot,val)
                    elif MidiMode == 'MCU':
                        if ActiveBus == bus:
                            sendToMCU(slot,val)


            # Mixer Channels (es: "/ch/01/mix/03")
            elif re.match("/ch/../mix/fader",addr): # Volume Master
                channel=int(addr[4:6])
                val=int(data[0]*127)
                if channel >= 1 and channel <= 16:
                    Volume[0][channel-1]=val
                if Bank < 2:
                    if channel >= (1+8*Bank) and channel <= (8+8*Bank):
                        if DebugOSCrecv > 0:
                           print "Channel %d, Val=%d (Bank=%d)" % (channel,val,Bank)
                        if MidiMode == 'BCR':
                            sendToBCR(0,channel-8*Bank,val)
                        elif MidiMode == 'MCU':
                            if ActiveBus == BUS_MASTER:
                                sendToMCU(channel-8*Bank,val)

            elif re.match("/ch/../mix/pan",addr): # Pan Master
                channel=int(addr[4:6])
                val=int(data[0]*127)
                if channel >= 1 and channel <= 16:
                    Pan[channel-1]=val
                if Bank < 2:
                    if channel >= (1+8*Bank) and channel <= (8+8*Bank):
                        if DebugOSCrecv > 0:
                           print "Channel %d, Val=%d" % (channel,val)
                        if MidiMode == 'BCR':
                            sendToBCR(0,8+channel-8*Bank,val) #MIDI ch. 1
                        elif MidiMode == 'MCU':
                            pass # Not Yet Implemented

            elif re.match("/ch/../mix/on",addr):
                   val=int(data[0])
                   channel=int(addr[4:6])
                   if channel >= 1 and channel <= 16:
                       if val == 0:
                           Mute[channel-1]=127
                       else:
                           Mute[channel-1]=0
                   if Bank < 2:
                       if channel >= (1+8*Bank) and channel <= (8+8*Bank):
                           if int(data[0]) == 0:
                               if MidiMode == 'BCR':
                                   sendToBCR(0,72+channel-8*Bank,127) #MIDI ch. 1
                               elif MidiMode == 'MCU':
                                   pass # Not Yet Implemented
                           else:
                               if MidiMode == 'BCR':
                                   sendToBCR(0,72+channel-8*Bank,0) #MIDI ch. 1
                               elif MidiMode == 'MCU':
                                   pass # Not Yet Implemented                       
            
            elif re.match("/-stat/solosw/..",addr):
                channel=int(addr[14:16])
                val=int(data[0])
                if channel >= 1 and channel <= 16:
                    Solo[channel-1]=val*127
                if Bank < 2:
                    if channel >= (1+8*Bank) and channel <= (8+8*Bank):
                        if DebugOSCrecv > 0:
                            print "Solo channel %d = %d" % (channel,val)
                        if MidiMode == 'BCR':
                            sendToBCR(0,64+channel-8*Bank,val*127) #MIDI ch. 1, CC 65 - 73
                        elif MidiMode == 'MCU':
                            pass # Not Yet Implemented
                

    # Setup OSC server & client
    server = OSC.OSCServer(("", PORT_SRV))
    server.addMsgHandler("default", msg_handler) # msg_handler() will receive ALL the OSC messages ("default" address)
    client = OSC.OSCClient(server=server) #This makes sure that client and server uses same socket. This has to be this way, as the X32 sends notifications back to same port as the /xremote message came from
    
    client.connect((ADDR, PORT_SRV))

    # Start request notifications thread
    thread = threading.Thread(target=request_notifications, kwargs = {"client": client})
    thread.start()
    client.send(OSC.OSCMessage("/xremote"))
    LastMidiEvent=0
    Reload(client,True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # Ctrl+C was hit - exit program
        do_exit = True

def oscsend(address, value=None):
    """
    Helper function to simply send OSC messages
    """
    if DebugOSCsend > 0:
        print "oscsend(",address,",",value
    c = OSC.OSCClient()
    c.connect((ADDR,PORT_SRV))
    oscmsg = OSC.OSCMessage()
    oscmsg.setAddress(address)
    if value != None:
        if value == value:
            oscmsg.append(value)
        else:
            oscmsg.append(0)
    c.send(oscmsg)

"""
*** BCR2000 implementation chart ***
Midi Channel 1: volume bus Master LR
    CC 1-8 -> /ch/<CC>/mix/fader

Midi Channel 2: sends Bus1 (Phones1)
    CC 1-8 -> /ch/<CC>/mix/01/fader

Midi Channel 3: Current FX parameters
    CC 2-8 -> /fx/<CurrentFx>/par/<PAR>

Midi Channel 4: sends Bus2 (Phones2)
    CC 1-8 -> /ch/<CC>/mix/02/fader

Midi Channel 16: FCB1010 - voice strip (3) -> FX2 return level
    CC 101 -> /ch/03/mix/08/level # FX2 send (Voice)
    CC 102 -> /fx/2/par/01" # FX2 time
"""
def RefreshBCR():
    for i in range(1,9):
        if MidiMode == 'BCR':
            if Bank < 2:
                sendToBCR(0,i,Volume[0][i+8*Bank-1]) #MIDI ch. 1
                sendToBCR(1,i,Volume[1][i+8*Bank-1]) #MIDI ch. 2
                sendToBCR(3,i,Volume[2][i+8*Bank-1]) #MIDI ch. 4
                sendToBCR(0,8+i,Pan[i+8*Bank-1]) #MIDI ch. 1
                sendToBCR(0,16+i,Volume[2+CurrentFx][i+8*Bank-1]) #MIDI ch. 1
                sendToBCR(0,72+i,Mute[i+8*Bank-1]) #MIDI ch. 1
                sendToBCR(0,64+i,Solo[i+8*Bank-1]) #MIDI ch. 1, CC 65 - 73
            if Bank == 2:
                if i <= 5:
                    sendToBCR(0,i,FxReturn[0][i-1])
                    sendToBCR(1,i,FxReturn[1][i-1])
                    sendToBCR(3,i,FxReturn[2][i-1])
        elif MidiMode == 'MCU':
            if Bank < 2:
                sendToMCU(i,Volume[ActiveBus][i+8*Bank-1])
            if Bank == 2:
                if i <= 5:
                    sendToMCU(i,FxReturn[0][i-1])

    if MidiMode == 'MCU':
        if ActiveBus == 0:
            midi_out.send_message([0x90,0x33,127])
        else:
            midi_out.send_message([0x90,0x33,0])
        for i in range(1,9):
            if i == ActiveBus:
                val=127
            else:
                val=0
            midi_out.send_message([0x90,0x17+i,val])

 
   

def RefreshBCRfx():
    for i in range(0,12):
        index=FxParam[FxType[CurrentFx-1]].index(FxParam[CurrentFx-1][i])
        tag=FxParVal[CurrentFx-1][i][0]
        val=FxParVal[CurrentFx-1][i][1]
        if DebugOSCrecv > 1: print "i=%d, index=%d, val=%d (%c)" % (i,index,val,tag)
        if index >= 6*FxShift and index <= 5+6*FxShift:
            if MidiMode == 'BCR':
                sendToBCR(2,2+index-6*FxShift,val) #MIDI ch. 3 NB: in my BCR fx params starts from CC2 (CC1 is faulty!)
                if DebugMIDIsend > 0: print "Midi send: CC=%d, val=%d, FxShift=%d" % (2+index-7*FxShift,val,FxShift)
            elif MidiMode == 'MCU':
                if ActiveBus == BUS_FX_SENDS:
                    sendToMCU(i,index-6*FxShift,val)

    RefreshBCR()

def MidiCallback(message, time_stamp):
    """
    MIDI receiver handler callback
    """
    global LastMidiEvent
    global CurrentFx
    global Bank
    global FxShift
    global Volume
    global Pan
    global Mute
    global Solo
    global FxParVal
    global FxReturn
    global ActiveBus
    
    cc=0
    val=0
    address=""
    MidiChannel=0
    interpolation=None

    if DebugMIDIrecv > 0:
        print "0x%02x, 0x%02x, 0x%02x" % (message[0],message[1],message[2])

##### iControlPro ####
    if MidiMode == 'MCU':
        if message[0] == 0x90:
            if message[1] >= 0x18 and message[1] <= 0x1f: # Sel Button
                ActiveBus=message[1]-0x17
                lcd_status()
                RefreshBCR()
            if message[1] == 0x33:
                ActiveBus=0
                lcd_status()
                RefreshBCR()
            if message[1] == 0x2e and message[2] == 0x7f: # Bank <<
                Bank-=1
                if Bank < 0: Bank = 0
                lcd_status()
                RefreshBCR()
            if message[1] == 0x2f and message[2] == 0x7f: # Bank >>
                Bank+=1
                if Bank > 2: Bank = 2
                lcd_status()
                RefreshBCR()

        if message[0] >= 0xe0 and message[0] <= 0xe8: # Fader
            cc=message[0]-0xdf
            val=message[1]
            if DebugMIDIrecv > 0:
                print "#",cc," =",val
            if ActiveBus == 0: # Master Volume
                if Bank < 2:
                    address="/ch/%02d/mix/fader" % (cc+8*Bank)
                    Volume[0][cc+8*Bank-1]=val
                if Bank == 2:
                    if cc < 5:
                        address="/rtn/%d/mix/fader" % cc
                    if cc == 5:
                        address="/rtn/aux/mix/fader"
                    FxReturn[0][cc-1]=val
            if ActiveBus >=1 and ActiveBus <= 2: # Livelli Bus1
                if Bank < 2:
                    address="/ch/%02d/mix/01/level" % (cc+8*Bank)
                    Volume[1][cc+8*Bank-1]=val
                if Bank == 2:
                    if cc < 5:
                        address="/rtn/%d/mix/01/level" % cc
                    if cc == 5:
                        address="/rtn/aux/mix/01/level" 
                    FxReturn[1][cc-1]=val
            if DebugMIDIrecv > 0:
                print "address=",address

            RefreshBCR()
###### BCR2000 ######

    if MidiMode == 'BCR' and int(message[0]) >= 0xB0 and int(message[0]) <= 0xBF: # at the moment we'll process only ContinousControls (CC).
        LastMidiEvent=time.time()
        MidiChannel=message[0]-0xAF # (0xB0 is Channel 1, 0xBF is Channel 16)
        cc=message[1]
        val=message[2]
        
        if DebugMIDIrecv > 0:
            print "Ch.",MidiChannel," #",cc," =",val
        address=""

####  MIDI Channel 1 ####
        if MidiChannel == 1: # Master LR Volume
            if cc >= 1 and cc <= 8:
                if Bank < 2:
                    address="/ch/%02d/mix/fader" % (cc+8*Bank)
                    Volume[0][cc+8*Bank-1]=val
                if Bank == 2:
                    if cc < 5:
                        address="/rtn/%d/mix/fader" % cc
                    if cc == 5:
                        address="/rtn/aux/mix/fader"
                    FxReturn[0][cc-1]=val

            if Bank < 2:
                if cc >= 9 and cc <= 16: # Group 2 of Encoders: Pan
                    address="/ch/%02d/mix/pan" % (cc-8+8*Bank)
                    Pan[cc-8+8*Bank-1]=val
                if cc >= 17 and cc <= 24:
                    address="/ch/%02d/mix/%02d/level" %(cc-16+8*Bank,6+CurrentFx)
                    Volume[2+CurrentFx][cc-16+8*Bank]=val
                if cc >= 65 and cc <= 72: # first row buttons: Solo
                    address="/-stat/solosw/%02d" % (cc-64+8*Bank)
                    Solo[cc-64+8*Bank-1]=val
                elif cc >= 73 and cc <= 80: # second row buttons: Mute
                    address="/ch/%02d/mix/on" % (cc-72+8*Bank)
                    if val > 0: val=0
                    else: val=127
                    Mute[cc-72+8*Bank-1]=val

            # 81,82,83,84 are the User Defined buttons: they select the current FX
            if cc >= 81 and cc <=84:
                CurrentFx=cc-80

                # these buttons should be exclusively selectable (selecting one deselect the others)
                if MidiMode == 'BCR':
                    for i in range(81,85):
                        if i == cc:
                            sendToBCR(0,i,127) #MIDI ch. 1
                            if DebugMIDIrecv > 1:
                                print "MIDI Send 0xB0,%d,127" %i
                        else:
                            sendToBCR(0,i,0) #MIDI ch. 1
                            if DebugMIDIrecv > 1:
                                print "MIDI Send 0xB0,%d,0" %i
                if DebugMIDIrecv > 0:
                    lcd_status()
                    print "CurrentFx=%d" % CurrentFx

                if val == 127: # press
                    oscsend("/fx/%d/type" % CurrentFx) # FX
                    FxShift=1
                else: # release
                    FxShift=0
                RefreshBCRfx()
                for i in FxParam[FxType[CurrentFx-1]]:
                    oscsend("/fx/%d/par/%02d" % (CurrentFx,i)) # FX parameters request
                    time.sleep(WAITOSC)

            if cc == 85: # Bank!
                Bank += 1
                if Bank > 2:
                    Bank=0
                lcd_status()

                RefreshBCR()



####  MIDI Channel 2 ####
        if MidiChannel == 2: # Livelli Bus1
            if cc >= 1 and cc <= 8:
                if Bank < 2:
                    address="/ch/%02d/mix/01/level" % (cc+8*Bank)
                    Volume[1][cc+8*Bank-1]=val
                if Bank == 2:
                    if cc < 5:
                        address="/rtn/%d/mix/01/level" % cc
                    if cc == 5:
                        address="/rtn/aux/mix/01/level" 
                    FxReturn[1][cc-1]=val
                    

####  MIDI Channel 3 ####
        if MidiChannel == 3: # Parametri FX corrente
           if cc == 1:
                  print "Faulty Controller!"
           if cc >= 2 and cc <= 7:
                par=FxParam[FxType[CurrentFx-1]][cc-2+6*FxShift]
                address="/fx/%d/par/%02d" %(CurrentFx,par) #NB: FxType[CurrentFX-1] is the Parameters List of the currently selected FX slot
                                                                                       # cc-2 is the index in the array we are changing
                # ie: if Type is 11, the row is [1,4,5,6,7,9,2]. If CC is 3, we take the parameter at offset "1" (CC-2), that is "4"
                FxParVal[CurrentFx-1][par-1][1]=val
           if cc == 8:
               # TO BE REALLOCATED!!
               pass



####  MIDI Channel 4 ####
        if MidiChannel == 4: # Livelli Bus2
            if cc >= 1 and cc <= 8:
                if Bank < 2:
                    address="/ch/%02d/mix/02/level" % (cc+8*Bank)
                    Volume[2][cc+8*Bank-1]=val
                if Bank == 2:
                    FxReturn[2][cc-1]=val
                    if cc < 5:
                        address="/rtn/%d/mix/01/level" % cc
                    if cc == 5:
                        address="/rtn/aux/mix/01/level" 


####  MIDI Channel 16 ####
        if MidiChannel == 16: # FCB1010
            if DebugMIDIrecv > 0:
                print "FCB1010!"
            if cc == 101: # expression A
                if DebugMIDIrecv > 1:
                    print "Exp A"
                address="/ch/%02d/mix/08/level" % VoiceChannel# voce -> FX2 # *** QUESTO E' DA RIVEDERE!! ***
                interpolation=(0.2,0.8)

            if cc == 102: # expression B
                if DebugMIDIrecv > 1:
                    print "Exp B"
                address="/fx/2/par/01" # FX2 time

# End of MidiCallback

# Ok, if we have an address, we can send an OSC message:
    if address != "":
        try:
            if interpolation != None:
                oscsend(address,interpolate(float(val)/127,0,1.0,interpolation[0],interpolation[1]))
            else:
                oscsend(address,float(val)/127)
        except:
            oscsend(address,int(val))
        
def OpenMidiPort(name,midi_port, descr="Devices"):
    """
    Helper function to open midi device
    """
    i=0
    port=-1
    print "MIDI %s:" % descr
    for port_name in midi_port.ports:
        if port_name.find(name) != -1:
            port=i
            print "    ",i,": * ",port_name," *"
            break
        else:
            print "    ",i,": ",port_name
        i=i+1
        
    if port == -1:
        print "Device "+name+" not found in Midi %s. Aborting." % descr
        exit()
    return(port)


midi_in=rtmidi.MidiIn()
port_in=OpenMidiPort(MIDINAME,midi_in,"Input Devices")
midi_out=rtmidi.MidiOut()
port_out=OpenMidiPort(MIDINAME,midi_out,"Output Devices")

midi_in.callback = MidiCallback

midi_in.open_port(port_in)
midi_out.open_port(port_out)


# A second midi input device (midiloop) with same callback.
#       That means I will be able to pilot XR18 from Ableton Live too!
if MIDINAME2 != "None":
    midi_in2=rtmidi.MidiIn()
    port_in2=OpenMidiPort(MIDINAME2,midi_in2,"Input Devices")
    midi_in2.open_port(port_in2)
    midi_in2.callback = MidiCallback 


print "====================================="
help()

### Some MIDI initial setup ###
# CurrentFx buttons:
if MidiMode == 'BCR':
    sendToBCR(0,81,0)   #MIDI ch. 1, CC81, off
    sendToBCR(0,82,0)   #MIDI ch. 1, CC82, off
    sendToBCR(0,83,0)   #MIDI ch. 1, CC83, off
    sendToBCR(0,84,0)   #MIDI ch. 1, CC84, off
    sendToBCR(0,80+CurrentFx,127) #MIDI ch. 1, CC81, on (se CurrentFx = 1)
    sendToBCR(0,85,0)   # Bank status

threading.Timer(1,Progress,()).start()
RefreshBCR()
lcd_status()
parse_messages()

