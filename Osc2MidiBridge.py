#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
History:
    2015-12-21: 0.0.17: code cleanup; support for CGfootsy on Midi# 15
    2015-12-11: 0.0.16: argparse, various fixes
    2015-12-08: 0.0.15: fixes MCU
    2015-12-07: 0.0.14: MCU messages in dictionary; using "Track" buttons to change ActiveBus
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
VERSION="0.0.17"

import argparse
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
if os.name == 'posix' and os.uname()[1] == 'raspberrypi':
    import RPi_I2C_driver

def ListMidiPort(midi_port ):
    """
    Helper function to open midi device
    """
    i=0
    for port_name in midi_port.ports:
        print "    ",i,": ",port_name
        i=i+1


def OpenMidiPort(name,midi_port, descr="Devices"):
    """
    Helper function to open midi device
    """
    i=0
    port=-1
    if args.verbose == True:
        print "MIDI %s:" % descr
    for port_name in midi_port.ports:
        if port_name.find(name) != -1:
            port=i
            if args.verbose == True:
                print "    ",i,": * ",port_name," *"
            break
        else:
            if args.verbose == True:
                print "    ",i,": ",port_name
        i=i+1

    if port == -1:
        if args.verbose == True:
            print "Device "+name+" not found in Midi %s. Aborting." % descr
        exit()
    return(port)

def lcd_init():
    if os.name == 'posix' and os.uname()[1] == 'raspberrypi':
        mylcd = RPi_I2C_driver.lcd()
    return(mylcd)

def ReadConfig(Section,Option,Type=None):
    retval=""
    try:
        if Type == 'int':
            retval=parser.getint(Section,Option)
        elif Type == 'float':
            retval=parser.getfloat(Section,Option)
        elif Type == 'bool':
            retval=parser.getboolean(Section,Option)
        else:
            retval=parser.get(Section,Option)
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

    if args.verbose == True:
        out="ReadConfig: [%s] %s = " % (Section,Option)
        print out,retval
    return retval

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

def val2key(dic,val):
    """
    takes a dictionary and returns the key with the value specified as input
    """
    return dic.keys()[dic.values().index(val)]

def sendToMCU(fader,val):
    midi_out.send_message([0x90,MidiMessages["Unlock"]+fader,127]) # unlock fader
    midi_out.send_message([MidiMessages["Fader"]+fader-1 ,val,val]) # move fader
    midi_out.send_message([0x90,MidiMessages["Unlock"]+fader ,0])  # lock fader

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
Shift=0
Stat=0
FlipFlop=0
VoiceChannel=0
BassChannel=0
do_exit=False
BusName=["Master","Bus1","Bus2","Bus3","Bus4","Bus5","Bus6"]
FxType=[0,0,0,0]
FxReturn=[ #Fx1, Fx2, Fx3, Fx4, Aux
            [0]*5, # Master
            [0]*5, # Bus1
            [0]*5, # Bus2
        ]
Volume=[ # 16 channels
        [0]*32, # Main LR
        [0]*32, # Bus1
        [0]*32, # Bus2
        [0]*32, # Fx1
        [0]*32, # Fx2
        [0]*32, # Fx3
        [0]*32, # Fx4
       ]

Pan= [0]*32
Mute= [0]*32
Solo= [0]*32
FxParVal=[
            [['i',0]]*32
         ]*4

MAXBUS=8

# MCU Midi (iCon iControlPro):
MidiMessages={"BankL":  0x2e,
              "BankR":  0x2f,
              "Sel":    0x18,
              "Solo":   0x08,
              "Mute":   0x10,
              "Mixer":  0x33,
              "MasterR":0x4a,
              "MasterW":0x4b,
              "Rkr":    0x52,
              "RkrCw":  0x63,
              "RkrAc":  0x62,
              "Fader":  0xe0,
              "Rec":    0x5f,
              "Unlock": 0x68,
              "TrackL": 0x30,
              "TrackR": 0x31,
              "Prev":   0x5b,
              "Next":   0x5c,
              "Arm":    0x00,
              "Zoom":   0x64,
              "Loop":   0x56,
              "Stop":   0x5d,
              "Play":   0x5e,
              "Pan":    0x10
            }

### Some safe defaults (overloaded in config file)
MIDINAME="BCR2000 port 1"
MIDINAME2="None"
MIDINAME_IN=""
MIDINAME_OUT=""
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
Translation = None


# Argomenti della linea di comando gestiti da argparse
parser = argparse.ArgumentParser(description="Osc2MidiBridge v. %s" % VERSION)
# NB: gli argomenti che iniziano con "--" sono opzionali.
parser.add_argument("-f", "--configfile", help="Config file (defaults to \"osc2midi.ini\")")
parser.add_argument("-v", "--verbose", action="store_true", default=False, help="verbose")
parser.add_argument("-I", "--midiin",  help="Midi-In device (override config file)")
parser.add_argument("-O", "--midiout", help="Midi-Out device (override config file)")
parser.add_argument("-A", "--address", help="OSC address (override config file)")
parser.add_argument("-L", "--listmidi",help="list midi devices and exits", action="store_true",default=False)
args = parser.parse_args()

if args.configfile != None and os.path.exists(args.configfile):
    configfile=args.configfile

if args.listmidi:
    print "Midi IN:"
    midi_in=rtmidi.MidiIn()
    ListMidiPort(midi_in)

    print "Midi OUT:"
    midi_out=rtmidi.MidiOut()
    ListMidiPort(midi_out)
    exit()
if args.verbose == True:
    print 
    print "Osc2MidiBridge v."+VERSION
    print "------------------------------"

if os.name == 'posix' and os.uname()[1] == 'raspberrypi':
    lcd=lcd_init()
    lcd.lcd_display_string("Osc2MidiBridge",1)
    lcd.lcd_display_string("%s by CGsoft"%VERSION,2)
    time.sleep(1)
    lcd.lcd_clear()

# The config file is searched first in the home directory, then in the current working folder.
parser = ConfigParser.SafeConfigParser()
home = os.path.expanduser("~")
if configfile == '':
    if os.path.isfile(home+CONFIGFILE):
        configfile=home+CONFIGFILE
    else:
        configfile=CONFIGFILE

if args.verbose == True:
    print "ConfigFile: ",configfile

if parser.read(configfile) != None:
    MIDINAME=ReadConfig('MIDI', 'DeviceName')
    MIDINAME_IN=ReadConfig('MIDI', 'DeviceNameIn')
    MIDINAME_OUT=ReadConfig('MIDI', 'DeviceNameOut')
    MIDINAME2=ReadConfig('MIDI', 'DeviceName2')
    ADDR=ReadConfig('OSC', 'Address')
    PORT_SRV=ReadConfig('OSC', 'ServerPort','int')
    PORT_CLN=ReadConfig('OSC', 'ClientPort','int')
    WAITOSC=ReadConfig('OSC', 'Wait','float')
    WAITMIDI=ReadConfig('MIDI', 'Wait','float')
    WAITRELOAD=ReadConfig('OSC2Midi', 'WaitReload','float')
    CurrentFx=ReadConfig('OSC2Midi','CurrentFx','int')
    FxParam=ast.literal_eval(ReadConfig('OSC2Midi', "FxParam"))
    NoReload=ReadConfig('OSC2Midi','NoReload','bool')
    MidiMode=ReadConfig('MIDI','Mode')
    Translation=ast.literal_eval(ReadConfig('OSC2Midi','Translation'))
    FxInterpolation=ast.literal_eval(ReadConfig('OSC2Midi','FxInterpolation'))
else:
    print "Config file not found..."
    

# Override config settings from commandline


if args.address != None:
    ADDR=args.address


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
    client.send(OSC.OSCMessage("/lr/config/name")) # Name of the master bus
    time.sleep(WAITOSC)
    for i in range(1,7):
            client.send(OSC.OSCMessage("/bus/%d/config/name" % i)) # Name of the bus
            time.sleep(WAITOSC)
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
    for i in range(1,17): 
        # Volume Master
        client.send(OSC.OSCMessage("/ch/%02d/mix/fader" % i)) # Master LR
        time.sleep(WAITOSC)
        client.send(OSC.OSCMessage("/ch/%02d/config/name" % i)) # Name of the channel 
        time.sleep(WAITOSC)
        for j in range(7,11): # 7-10 are the FX busses
            client.send(OSC.OSCMessage("/ch/%02d/mix/%02d/level" % (i,j))) # FX sends
            time.sleep(WAITOSC)

        # Mute
        client.send(OSC.OSCMessage("/ch/%02d/mix/on" % i)) # Mute
        time.sleep(WAITOSC)

        # Pan
        client.send(OSC.OSCMessage("/ch/%02d/mix/pan" % i)) # Pan
        time.sleep(WAITOSC)

        #Solo
        client.send(OSC.OSCMessage("/-stat/solosw/%02d" % i)) # Solo
        time.sleep(WAITOSC)

        # Send levels for Bus1
        client.send(OSC.OSCMessage("/ch/%02d/mix/01/level" % i)) # Phones 1 (Bus1)
        time.sleep(WAITOSC)

        # Send levels for Bus2
        client.send(OSC.OSCMessage("/ch/%02d/mix/02/level" % i)) # Phones 2 (Bus2)
        time.sleep(WAITOSC)

    # FX parameters for the currently selected slot.
    # CurrentFX is the currently selected slot (we can select 1 of 4 different slots with the 4 "User defined" buttons on BCR2000)
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
        client.connect((ADDR, PORT_SRV))
        client.send(OSC.OSCMessage("/xremote"))
        time.sleep(WAITRELOAD)
        if NoReload == False:
            Reload(client)

        try:
            ch=''
            if os.name == 'nt':
                if msvcrt.kbhit():
                    ch=msvcrt.getch() 
            else:
                if kbhit():
                    ch=getch()
            if ch != '': 
                print "hai premuto il tasto",ch
                if ch == 'L':
                    print "Midi IN:"
                    ListMidiPort(midi_in)
                    print "Midi OUT:"
                    ListMidiPort(midi_out)
                if ch == 'D':
                    Dump()
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
        BUS="Master: %s" % BusName[0]
    for Bus in range(1,7):
        if ActiveBus == Bus:
            BUS="Bus%d: %s" %(Bus, BusName[Bus])
    if os.name == 'posix' and os.uname()[1] == 'raspberrypi':
        lcd=lcd_init()
        if Shift == 1:
            lcd.lcd_display_string("Bank=%d Fx=%d Shft"%(Bank,CurrentFx),1)
        else:
            lcd.lcd_display_string("Bank=%d Fx=%d"%(Bank,CurrentFx),1)
        lcd.lcd_display_string(" "*16,2)
        lcd.lcd_display_string("%s"%(BUS),2)

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
    print "D - Dump info"
    print "L - List MIDI devices"
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

def Progress(incremento=127/15):
    """
    In BCR Mode, show a moving led on MidiChannel3, CC1 (it's a faulty rotary controller on my BCR2000), 
    then update status of ledbutton in MidiChannel1,CC85 (Bank Select): Off=Bank0, On=Bank1, Blink=Bank2
    In MCU Mode show a blinking "Rec" button
    """
    global Stat
    global FlipFlop
    if MidiMode == 'BCR':
        sendToBCR(2,1,int(Stat))
        Stat += incremento
        if Stat > 127:
            Stat = 127/15
        if Stat <= 0:
            Stat = 127
        if Bank == 0:
            sendToBCR(0,85,0)
        if Bank == 1:
            sendToBCR(0,85,127)
        if Bank == 2:
            sendToBCR(0,85,FlipFlop*127)

    elif MidiMode == 'MCU':
        midi_out.send_message([0x90,MidiMessages["Rec"] ,Stat]) # Rec
        if Stat == 0: Stat=127
        else:  Stat=0

    if do_exit != True:
        threading.Timer(1,Progress,()).start()
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
        global BassChannel
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
                if name.lower() in ("basso","bass"):
                    BassChannel=channel
                    if DebugOSCrecv > 0: print "BassChannel=%d" % channel
            elif re.match("/bus/./config/name",addr):
                channel=int(addr[5])
                name=data[0]
                if DebugOSCrecv > 0: print "Bus %d is named %s" %(channel,name)
                if BusName[channel] != name:
                    BusName[channel]=name
                    if channel == ActiveBus:
                        lcd_status()
            elif re.match("/lr/config/name",addr):
                name=data[0]
                if DebugOSCrecv > 0: print "Master Bus is named %s" %(name)
                if BusName[0] != name:
                    BusName[0]=name 
                    if ActiveBus == 0:
                        lcd_status()

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
                    index=2+FxParam[FxType[slot-1]].index(par)-6*Shift
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

            elif re.match("/rtn/./mix/on",addr):
                   val=int(data[0])
                   channel=int(addr[5])
                   if channel >= 1 and channel <= 5:
                       if val == 0:
                           Mute[channel-1+16]=127
                       else:
                           Mute[channel-1+16]=0
                   if Bank == 2:
                       if channel >= 1 and channel <= 5:
                           if int(data[0]) == 0:
                               if MidiMode == 'BCR':
                                   sendToBCR(0,72+channel,127) #MIDI ch. 1
                               elif MidiMode == 'MCU':
                                   RefreshController()
                           else:
                               if MidiMode == 'BCR':
                                   sendToBCR(0,72+channel,0) #MIDI ch. 1
                               elif MidiMode == 'MCU':
                                   RefreshController()
 
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
                                   RefreshController()
                           else:
                               if MidiMode == 'BCR':
                                   sendToBCR(0,72+channel-8*Bank,0) #MIDI ch. 1
                               elif MidiMode == 'MCU':
                                   RefreshController()

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
                            RefreshController()


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
def RefreshController():
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
                    sendToBCR(0,72+i,Mute[i+15]) #MIDI ch. 1
        elif MidiMode == 'MCU':
            if Bank < 2:
                sendToMCU(i,Volume[ActiveBus][i+8*Bank-1])
                #midi_out.send_message([0x90,0x07+i,Solo[i+8*Bank-1]])
                midi_out.send_message([0x90,MidiMessages["Solo"]+i-1,Solo[i+8*Bank-1]])
                #midi_out.send_message([0x90,0x0f+i,Mute[i+8*Bank-1]])
                midi_out.send_message([0x90,MidiMessages["Mute"]+i-1,Mute[i+8*Bank-1]])
            if Bank == 2:
                if i <= 5:
                    sendToMCU(i,FxReturn[0][i-1])
                    midi_out.send_message([0x90,MidiMessages["Mute"]+i-1,Mute[i+15]])

    if MidiMode == 'MCU':
        if ActiveBus == 1:
            midi_out.send_message([0x90,MidiMessages["TrackL"],0])
            midi_out.send_message([0x90,MidiMessages["TrackR"],127])
        elif ActiveBus == 2:
            midi_out.send_message([0x90,MidiMessages["TrackL"],127])
            midi_out.send_message([0x90,MidiMessages["TrackR"],0])
        else:
            midi_out.send_message([0x90,MidiMessages["TrackL"],0])
            midi_out.send_message([0x90,MidiMessages["TrackR"],0])

        if CurrentFx == 1:
            midi_out.send_message([0x90,MidiMessages["Prev"],0])
            midi_out.send_message([0x90,MidiMessages["Next"],0])
        if CurrentFx == 2:
            midi_out.send_message([0x90,MidiMessages["Prev"],127])
            midi_out.send_message([0x90,MidiMessages["Next"],0])
        if CurrentFx == 3:
            midi_out.send_message([0x90,MidiMessages["Prev"],0])
            midi_out.send_message([0x90,MidiMessages["Next"],127])
        if CurrentFx == 4:
            midi_out.send_message([0x90,MidiMessages["Prev"],127])
            midi_out.send_message([0x90,MidiMessages["Next"],127])
##    if MidiMode == 'MCU':
##        if ActiveBus == 0:
##            #midi_out.send_message([0x90,0x33,127])
##            midi_out.send_message([0x90,MidiMessages["Mixer"],127])
##        else:
##            #midi_out.send_message([0x90,0x33,0])
##            midi_out.send_message([0x90,MidiMessages["Mixer"],0])
##        for i in range(1,9):
##            if i == ActiveBus:
##                val=127
##            else:
##                val=0
##            #midi_out.send_message([0x90,0x17+i,val])
##            midi_out.send_message([0x90,MidiMessages["Sel"]+i-1,val])




##    if MidiMode == 'MCU':
##        if ActiveBus == 0:
##            #midi_out.send_message([0x90,0x33,127])
##            midi_out.send_message([0x90,MidiMessages["Mixer"],127])
##        else:
##            #midi_out.send_message([0x90,0x33,0])
##            midi_out.send_message([0x90,MidiMessages["Mixer"],0])
##        for i in range(1,9):
##            if i == ActiveBus:
##                val=127
##            else:
##                val=0
##            #midi_out.send_message([0x90,0x17+i,val])
##            midi_out.send_message([0x90,MidiMessages["Sel"]+i-1,val])


def Dump():
    print "******************************"
    print "Dump internal values:"
    for i in range(0,16):
        print "Channel %02d: Vol=%02x, Pan=%02x, Mute=%02x, Solo=%02x" % (i+1,Volume[0][i],Pan[i], Mute[i], Solo[i])

def RefreshControllerfx():
    for i in range(0,12):
        index=FxParam[FxType[CurrentFx-1]].index(FxParam[CurrentFx-1][i])
        tag=FxParVal[CurrentFx-1][i][0]
        val=FxParVal[CurrentFx-1][i][1]
        if DebugOSCrecv > 1: print "i=%d, index=%d, val=%d (%c)" % (i,index,val,tag)
        if index >= 6*Shift and index <= 5+6*Shift:
            if MidiMode == 'BCR':
                sendToBCR(2,2+index-6*Shift,val) #MIDI ch. 3 NB: in my BCR fx params starts from CC2 (CC1 is faulty!)
                if DebugMIDIsend > 0: print "Midi send: CC=%d, val=%d, Shift=%d" % (2+index-7*Shift,val,Shift)
            elif MidiMode == 'MCU':
                if ActiveBus == BUS_FX_SENDS:
                    sendToMCU(i,index-6*Shift,val)

    RefreshController()

def MidiCallback(message, time_stamp):
    """
    MIDI receiver handler callback
    """
    global LastMidiEvent
    global CurrentFx
    global Bank
    global Shift
    global Volume
    global Pan
    global Mute
    global Solo
    global FxParVal
    global FxReturn
    global ActiveBus
    global do_exit

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
            #if message[1] >= 0x18 and message[1] <= 0x1f: # Sel Button
##            if message[1] >= MidiMessages["Sel"] and message[1] <= MidiMessages["Sel"]+8: # Sel Button
                #ActiveBus=message[1]-0x17
##                ActiveBus=message[1]-MidiMessages["Sel"]+1
##                lcd_status()
##                RefreshController()
            #if message[1] == 0x33:
##            if message[1] == MidiMessages["Mixer"]:
##                ActiveBus=0
##                lcd_status()
##                RefreshController()

            if message[1] == MidiMessages["Rec"] and message[2] == 0x7f:
                if Shift == 0:
                    do_exit=True
                    if os.name == 'posix' and os.uname()[1] == 'raspberrypi':
#                                               1234567890123456
                        lcd.lcd_display_string("Exiting...      ",1)
                        lcd.lcd_display_string("Bye             ",2)
                    time.sleep(1)
                    os.system("killall Osc2MidiBridge.py")
                    exit()
                else:
                    if os.name == 'posix' and os.uname()[1] == 'raspberrypi':
#                                               1234567890123456
                        lcd.lcd_display_string("Halting...      ",1)
                        lcd.lcd_display_string("Bye             ",2)
                        time.sleep(1)
                        os.system("sudo halt")
                    exit()

            if message[1] == MidiMessages["Next"] and message[2] == 0x7f:
                CurrentFx += 1
                if CurrentFx > 4:
                    CurrentFx=1
                lcd_status()
                oscsend("/fx/%d/type" % CurrentFx) # FX
                RefreshControllerfx()
                for i in FxParam[FxType[CurrentFx-1]]:
                    oscsend("/fx/%d/par/%02d" % (CurrentFx,i)) # FX parameters request
                    time.sleep(WAITOSC)

            if message[1] == MidiMessages["Prev"] and message[2] == 0x7f:
                CurrentFx -= 1
                if CurrentFx < 1:
                    CurrentFx=4
                lcd_status()
                print "CurrentFx=%d" % CurrentFx
                oscsend("/fx/%d/type" % CurrentFx) # FX
                RefreshControllerfx()
                for i in FxParam[FxType[CurrentFx-1]]:
                    oscsend("/fx/%d/par/%02d" % (CurrentFx,i)) # FX parameters request
                    time.sleep(WAITOSC)

            if message[1] == MidiMessages["Stop"] and message[2] == 0x7f:
                if Shift == 1:
                    Shift=0
                    midi_out.send_message([0x90,MidiMessages["Stop"],0])
                else:
                    Shift=1
                    midi_out.send_message([0x90,MidiMessages["Stop"],127])
                lcd_status()
                RefreshControllerfx()

            if message[1] == MidiMessages["TrackL"] and message[2] == 0x7f: # Track <<
                ActiveBus-=1
                if ActiveBus < 0: ActiveBus = MAXBUS
                lcd_status()
                RefreshController()
            if message[1] == MidiMessages["TrackR"] and message[2] == 0x7f: # Track >>
                ActiveBus+=1
                if ActiveBus > MAXBUS: ActiveBus = 0
                lcd_status()
                RefreshController()

            #if message[1] == 0x2e and message[2] == 0x7f: # Bank <<
            if message[1] == MidiMessages["BankL"] and message[2] == 0x7f: # Bank <<
                Bank-=1
                if Bank < 0: Bank = 0
                lcd_status()
                RefreshController()
            #if message[1] == 0x2f and message[2] == 0x7f: # Bank >>
            if message[1] == MidiMessages["BankR"] and message[2] == 0x7f: # Bank >>
                Bank+=1
                if Bank > 2: Bank = 2
                lcd_status()
                RefreshController()
            #if message[1] >= 0x8 and message[1] <= 0xf and message[2] == 0x7f: # solo

            if message[1] >= MidiMessages["Solo"] and message[1] < MidiMessages["Solo"]+8 and message[2] == 0x7f: # solo
                if Bank < 2:
                    #cc=message[1]-0x7
                    cc=message[1]-MidiMessages["Solo"]+1
                    val=Solo[cc+8*Bank-1]
                    if val == 0: val = 127
                    else: val = 0
                    address="/-stat/solosw/%02d" % (cc+8*Bank)
                    Solo[cc+8*Bank-1]=val
                    lcd_status()
                    RefreshController()

            #if message[1] >= 0x10 and message[1] <= 0x17 and message[2] == 0x7f: # Mute
            if message[1] >= MidiMessages["Mute"] and message[1] < MidiMessages["Mute"]+8 and message[2] == 0x7f: # Mute
                 #cc=message[1]-0x0f
                cc=message[1]-MidiMessages["Mute"]+1
                val=Mute[cc+8*Bank-1]
               # if val == 0: val = 127
               # else: val = 0
               # if val > 0: val=0
               # else: val=127
                Mute[cc+8*Bank-1]=val
                lcd_status()
                RefreshController()
                if Bank < 2:
                    address="/ch/%02d/mix/on" % (cc+8*Bank)
                elif Bank == 2: # FxReturn!
                    if cc >= 1 and cc <= 5:
                        address="/rtn/%d/mix/on" % (cc)

        if message[0] == 0xb0:
            if message[1] >= MidiMessages["Pan"] and message[1] < MidiMessages["Pan"]+8: # Pan
                cc=message[1] - MidiMessages["Pan"]+1
                if message[2] < 0x40:
                    val=message[2]
                else:
                    val=0x40-message[2]
                Pan[cc+8*Bank -1] += val
                address="/ch/%02d/mix/pan" % (cc+8*Bank)
                val=Pan[cc+8*Bank-1]


        #if message[0] >= 0xe0 and message[0] <= 0xe8: # Fader
        if message[0] >= MidiMessages["Fader"] and message[0] < MidiMessages["Fader"]+8: # Fader
            #cc=message[0]-0xdf
            cc=message[0]-MidiMessages["Fader"]+1
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
            if DebugMIDIsend > 0:
                print "address=",address

            RefreshController()
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
                    Shift=1
                else: # release
                    Shift=0
                RefreshControllerfx()
                for i in FxParam[FxType[CurrentFx-1]]:
                    oscsend("/fx/%d/par/%02d" % (CurrentFx,i)) # FX parameters request
                    time.sleep(WAITOSC)

            if cc == 85: # Bank!
                Bank += 1
                if Bank > 2:
                    Bank=0
                lcd_status()

                RefreshController()



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
                par=FxParam[FxType[CurrentFx-1]][cc-2+6*Shift]
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

####   MIDI Channel 15 (CG footsy)  ####
            """
            FxInterpolation=[
                            [ # Voice Channel
                                [0.0,1.0], # Fx1
                                [0.0,1.0], # Fx2
                                [0.0,1.0], # Fx3
                                [0.0,1.0]  # Fx4
                            ],
                            [ # Bass Channel
                                [0.0,1.0], # Fx1
                                [0.0,1.0], # Fx2
                                [0.0,1.0], # Fx3
                                [0.0,1.0]  # Fx4
                            ]
                        ]
            """
        if MidiChannel == 15: # CGfootsy
            if DebugMIDIrecv > 0:
                print "CGfootsy!"
            if cc >= 1 and cc <= 4: #fila inferiore (Voice)
                address="/ch/%02d/mix/%02d/level" % (VoiceChannel,cc+6) # Send of Voice on Fx1-4
                interpolation=(FxInterpolation[0][cc-1][0],FxInterpolation[0][cc-1][1])

            if cc >= 6 and cc <=9: # fila superiore (Bass)
                address="/ch/%02d/mix/%02d/level" % (BassChannel,cc+1) # Send of Voice on Fx1-4
                interpolation=(FxInterpolation[1][cc-5][0],FxInterpolation[1][cc-5][1])
#


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

if args.midiin != None:
    MIDINAME_IN=args.midiin

if args.midiout != None:
    MIDINAME_OUT=args.midiout

if MIDINAME_IN == "":
    MIDINAME_IN=MIDINAME

if MIDINAME_OUT == "":
    MIDINAME_OUT=MIDINAME

midi_in=rtmidi.MidiIn()
port_in=OpenMidiPort(MIDINAME_IN,midi_in,"Input Devices")
midi_out=rtmidi.MidiOut()
port_out=OpenMidiPort(MIDINAME_OUT,midi_out,"Output Devices")

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


if args.verbose == True:
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
elif MidiMode == 'MCU':
    #for i in range(0,8): midi_out.send_message([0x90,MidiMessages["Arm"]+i,127])
    #midi_out.send_message([0x90,MidiMessages["Zoom"],127])
    pass
threading.Timer(1,Progress,()).start()
RefreshController()
lcd_status()
parse_messages()

