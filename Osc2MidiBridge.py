#!/bin/python
# -*- coding: utf-8 -*-

"""
History:
    2015-11-24: 0.0.6: Bank Switch (Shift) [not yet tested!]
    2015-11-23: 0.0.5: refactoring; english translation
    2015-11-22: 0.0.4: save parameters in array (for future implementation of "Bank Switching"); MCU mode (only for Master faders - WIP)
    2015-11-21: 0.0.3: changed OSC -> Midi engine; Pan parameters
    2015-11-21: 0.0.2: refactoring, configuration file
    2015-11-20: 0.0.1: first working version; FX parameters
"""
VERSION="0.0.6"

import rtmidi_python as rtmidi
import time
import re
import OSC
import threading
import os
if os.name == 'nt':
    import msvcrt
#from ConfigParser import SafeConfigParser,ConfigParser
import ConfigParser
import ast

### Some global variables ###
LastMidiEvent=0
DebugOSCsend=0
DebugOSCrecv=0
DebugMIDIsend=0
DebugMIDIrecv=0
Shift=0
do_exit=False
FxType=[0,0,0,0]
Volume=[
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
        [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
       ]
Pan=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
Mute=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
Solo=[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
FxParVal=[
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16],
            [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
         ]



### Some safe defaults (overloaded in config file)
MIDINAME="BCR2000 port 1"
#MIDINAME="BCR2000"
#MIDINAME="iCON iControls_Pro V1.02 Porta 1"
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
            [1,2,3,4,5,6,7], #13 Stereo Chorus
            [1,2,3,4,5,6,7], #14 Stereo Flanger
            [1,2,3,4,5,6,7], #15 Stereo Phaser
            [1,2,3,4,5,6,7], #16 Dimensional Chorus
            [1,2,3,4,5,6,7], #17 Mood Filter
            [1,2,3,4,5,6,7], #18 Rotary Speaker
            [1,2,3,4,5,6,7], #19 Stereo Tremolo
            [1,2,3,4,5,6,7], #20 Sub Octaver
            [1,2,3,4,5,6,7], #21 Delay + Chamber
            [1,2,3,4,5,6,7], #22 Chorus + Chamber
            [1,2,3,4,5,6,7], #23 Flanger + Chamber
            [1,2,3,4,5,6,7], #24 Delay + Chorus
            [1,2,3,4,5,6,7], #25 Delay + Flanger
            [1,2,3,4,5,6,7], #26 Modulation Delay
            [1,2,3,4,5,6,7], #27 Graphic and Tru EQ
            [1,2,3,4,5,6,7], #28 DeEsser
            [1,2,3,4,5,6,7], #29 Xtec EQ1
            [1,2,3,4,5,6,7], #30 Xtec EQ5
            [1,2,3,4,5,6,7], #31 Wave Designer
            [1,2,3,4,5,6,7], #32 Precision Limiter
            [1,2,3,4,5,6,7], #33 Combinator
            [1,2,3,4,5,6,7], #34 Fair Compressor
            [1,2,3,4,5,6,7], #35 Leisure Compressor
            [1,2,3,4,5,6,7], #36 Ultimo Compressor
            [1,2,3,4,5,6,7], #37 Enhancer
            [1,2,3,4,5,6,7], #38 Exciter
            [1,2,3,4,5,6,7], #39 Stereo Imager
            [1,2,3,4,5,6,7], #40 Edison EX1
            [1,2,3,4,5,6,7], #41 Sound Maxer
            [1,2,3,4,5,6,7], #42 Guitar Amp
            [1,2,3,4,5,6,7], #43 Tube Stage
            [1,2,3,4,5,6,7]  #44 Stereo / Dual Pitch
        ]

parser = ConfigParser.SafeConfigParser()
if parser.read('osc2midi.ini') != None:
    try:
        MIDINAME=parser.get('MIDI', 'DeviceName')
        ADDR=parser.get('OSC', 'Address')
        PORT_SRV=parser.getint('OSC', 'ServerPort')
        PORT_CLN=parser.getint('OSC', 'ClientPort')
        WAITOSC=parser.getfloat('OSC', 'Wait')
        WAITMIDI=parser.getfloat('MIDI', 'Wait')
        WAITRELOAD=parser.getfloat('OSC2Midi', 'WaitReload')
        CurrentFx=parser.getint('OSC2Midi','CurrentFx')
        FxParam=ast.literal_eval(parser.get('OSC2Midi', "FxParam"))
        ReloadMasterLevels=parser.get('OSC2Midi','ReloadMasterLevels')
        ReloadMasterMute=parser.get('OSC2Midi','ReloadMasterMute')
        ReloadMasterPan=parser.get('OSC2Midi','ReloadMasterPan')
        ReloadMasterSolo=parser.get('OSC2Midi','ReloadMasterSolo')
        ReloadBus1Levels=parser.get('OSC2Midi','ReloadBus1Levels')
        ReloadBus2Levels=parser.get('OSC2Midi','ReloadBus2Levels')    
        ReloadFxType=parser.get('OSC2Midi','ReloadFxType')
        ReloadFxParams=parser.get('OSC2Midi','ReloadFxParams')
        MidiMode=parser.get('MIDI','Mode')

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

print "Midi-OSC Bridge v."+VERSION

def Reload(client,force=False):
    """
    Send to XR18 a request for every parameter that we need to show on controller
    """
    if NoReload and force != True:
        print "NoReload!"
        return
    global CurrentFx
    global FxType
    global FxParam
    global ReloadMasterLevels
    global ReloadMasterMute
    global ReloadMasterPan
    global ReloadMasterSolo
    global ReloadBus1Levels
    global ReloadBus2Levels
    global ReloadFxType
    global ReloadFxParams
    
    # Here we are asking some values back from XR18 (an OSC message with an address without value send to XR18 triggers an OSC message back from XR18 with the actual value)
    # Let's start with the Type of effetct loaded in the 4 slot available
    # NB: slot are 1,2,3,4.
    if ReloadFxType:
        for i in range(1,5):
            if DebugOSCsend > 0:
                print "OSCsend: /fx/%d/type" % i
            #oscsend("/fx/%d/type" % i)
            client.send(OSC.OSCMessage("/fx/%d/type" % i)) # FX
            time.sleep(WAITOSC)
    
    for i in range(1,17): # only the fist 8 strips, for the moment. In future will implement a bank switching.
        # Volume Master
        if ReloadMasterLevels:
            #oscsend("/ch/0%d/mix/fader" % i)
            client.send(OSC.OSCMessage("/ch/%02d/mix/fader" % i)) # Master LR
            time.sleep(WAITOSC)

        # Mute
        if ReloadMasterMute:
            #oscsend("/ch/0%d/mix/on" % i) # Mute
            client.send(OSC.OSCMessage("/ch/%02d/mix/on" % i)) # Mute
            time.sleep(WAITOSC)

        # Pan
        if ReloadMasterPan:
            client.send(OSC.OSCMessage("/ch/%02d/mix/pan" % i)) # Pan
            #oscsend("/ch/0%d/mix/pan" % i) # Pan
            time.sleep(WAITOSC)

        #Solo
        if ReloadMasterSolo:
            client.send(OSC.OSCMessage("/-stat/solosw/%02d" % i)) # Solo
            #oscsend("/-stat/solosw/0%d" % i) # Solo
            time.sleep(WAITOSC)

        # Send levels for Bus1
        if ReloadBus1Levels:
            client.send(OSC.OSCMessage("/ch/%02d/mix/01/level" % i)) # Phones 1 (Bus1)
            #oscsend("/ch/0%d/mix/01/level" % i) # Phones 1 (Bus1)
            time.sleep(WAITOSC)

        # Send levels for Bus2
        if ReloadBus2Levels:
            client.send(OSC.OSCMessage("/ch/%02d/mix/02/level" % i)) # Phones 2 (Bus2)
            #oscsend("/ch/0%d/mix/02/level" % i) # Phones 2 (Bus2)
            time.sleep(WAITOSC)
    
    # FX parameters for the currently selected slot.
    # CurrentFX is the currently selected slot (we can select 1 of 4 different slots with the 4 "User defined" buttons on BCR2000)
    if ReloadFxParams:
        for i in FxParam[FxType[CurrentFx-1]]: # here we take the list of parameters for this type of effect loaded in the current slot
            if DebugOSCsend > 0:
                print "OSCsend: /fx/%d/par/%02d" % (CurrentFx,i)
            client.send(OSC.OSCMessage("/fx/%d/par/%02d" % (CurrentFx,i))) # FX parameters
            #oscsend("/fx/%d/par/%02d" % (CurrentFx,i)) # FX parameters
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
        client.send(OSC.OSCMessage("/xremote"))
        #oscsend("/xremote")
        time.sleep(WAITRELOAD)
        if NoReload == False:
            Reload(client)

        if os.name == 'nt': # At the moment this works only in Windows... That's all I need.
            if msvcrt.kbhit():
                ch=msvcrt.getch() 
                print "hai premuto il tasto",ch
                if ch == 'Q':
                    do_exit=True
                    print "-----------------------------------------------"
                    print "Closing threads... LastMidiEvent you can exit with Ctrl-C"
                if ch == 'q':
                    DebugOSCsend=0
                    DebugOSCrecv=0
                    DebugMIDIsend=0
                    DebugMIDIrecv=0
                if ch == 'h':
                    help()
                if ch == 's':
                    status()

                if ch == 'n':
                    NoReload=True
                if ch == 'r':
                    NoReload=False
                if ch == 'o':
                    DebugOSCsend+=1
                    print "Debug=",DebugOSCsend,DebugOSCrecv,DebugMIDIsend,DebugMIDIrecv                    
                if ch == 'O':
                    DebugOSCrecv+=1
                    print "Debug=",DebugOSCsend,DebugOSCrecv,DebugMIDIsend,DebugMIDIrecv                    
                if ch == 'm':
                    DebugMIDIsend+=1
                    print "Debug=",DebugOSCsend,DebugOSCrecv,DebugMIDIsend,DebugMIDIrecv                    
                if ch == 'M':
                    DebugMIDIrecv+=1
                    print "Debug=",DebugOSCsend,DebugOSCrecv,DebugMIDIsend,DebugMIDIrecv

    exit()
def help():
    print "h - this help page"
    print "Q - prepare to quit (close sockets and threads)"
    print "q - quiet: ends debug informations"
    print "n - set to NoReload Mode"
    print "r - set to Reload Mode"
    print "o - increment DebugOSCsend"
    print "O - increment DebugOSCrecv"
    print "m - increment DebugMIDIsend"
    print "M - increment DebugMIDIrecv"
    print "s - prints status info"
    print "-------------------------------------------------"

def status():
    print "Status:"
    # TO BE CONTINUED...
    
def parse_messages():
    """
    Starts the OSC msg_handler thread and initialize bidirectional connection with XR18 via OSC.
    """
    global LastMidiEvent
    global FxType
    global CurrentFx
    global FxParam
    global Volume
    global Pan
    global Mute
    global Solo
    global FxParVal


    def msg_handler(addr, tags, data, client_address):
        """
        Parses the received OSC messages, sends corresponding values to Midi. Ignore non pertinent messages.
        """

        if time.time() - LastMidiEvent > WAITMIDI: # we are parsing OSC messages only if a consistent time is passed from the last Midi event
            if DebugOSCrecv > 0:
                print 'OSCMessage("%s",%s,%s)' % (addr, tags, data)
            val=int(data[0]*127)  # for the moment we take alla parameters value as "float". TO BE FIXED!
            # FX type (es.: "/fx/1/type")
            if re.match("/fx/./type",addr):
                slot=int(addr[4]) # addr[4] is the FX (1 to 4)
                FxType[slot-1]=data[0] 
                if DebugOSCrecv > 0:
                    print "Found FX %d set to %d" % (slot,FxType[slot-1])
            
            elif re.match("/ch/../mix/0./level",addr): # Bus Sends
                  val=int(data[0]*127)
                  channel=int(addr[4:6])
                  bus=int(addr[12])
                  if channel >= (1+8*Shift) and channel <= (8+8*Shift):
                      if bus == 1:
                          if MidiMode == 'BCR':
                              midi_out.send_message([0xB1,channel-8*Shift,val]) #MIDI ch. 2
                          elif MidiMode == 'MCU':
                              pass # Not Yet Implemented
                          Volume[1][channel]=val
                      elif bus == 2:
                          if MidiMode == 'BCR':
                              midi_out.send_message([0xB3,channel-8*Shift,val]) #MIDI ch. 4                  
                          elif MidiMode == 'MCU':
                              pass # Not Yet Implemented
                          Volume[2][channel]=val
                      else:
                        pass # At the moment, the other busses are not mapped...
                          
                  if DebugOSCrecv > 0:
                      print "Bus %d, Channel %d, Val=%d" % (bus,channel,val)
                  

            # FX parameters (es.: "/fx/1/par/06")
            elif re.match("/fx/./par/..",addr): 
                slot=int(addr[4])
                par=int(addr[10:12])
                val=int(data[0]*127)
                if slot == CurrentFx: #  here we are
                    # ie: slot=2, FxType[1]=11, CurrentFx=2, FxParam[11]=[1,4,5,6,7,9,2], par=9 -> send(0xB2,6,val)
                    try:
                        FxParVal[slot-1][par]=val
                        if MidiMode == 'BCR':
                            midi_out.send_message([0xB2,2+FxParam[FxType[slot-1]].index(par),val]) #MIDI ch. 3 NB: in my BCR fx params starts from CC2 (CC1 is faulty!)
                        elif MidiMode == 'MCU':
                            pass # Not Yet Implemented
                    except:
                        pass
         
                if DebugOSCrecv > 0:
                    print "FX: current=%d - slot=%d - par=%d - val=%f" %(CurrentFx,slot,par,data[0])

            # Mixer Channels (es: "/ch/01/mix/03")
            elif re.match("/ch/../mix/fader",addr): # Volume Master
                channel=int(addr[4:6])
                if channel >= (1+8*Shift) and channel <= (8+8*Shift):
                    val=int(data[0]*127)
                    if DebugOSCrecv > 0:
                       print "Channel %d, Val=%d" % (channel,val)
                    if MidiMode == 'BCR':
                        midi_out.send_message([0xB0,channel-8*Shift,val]) #MIDI ch. 1
                    else:
                        midi_out.send_message([0x90,0x67+channel-8*Shift,127])
                        midi_out.send_message([0xDF+channel-8*Shift,val,val])
                        midi_out.send_message([0x90,0x67+channel-8*Shift,0])
                    Volume[0][channel]=val
                
            elif re.match("/ch/0./mix/pan",addr): # Pan Master
                channel=int(addr[4:6])
                if channel >= (1+8*Shift) and channel <= (8+8*Shift):
                    val=int(data[0]*127)
                    if DebugOSCrecv > 0:
                       print "Channel %d, Val=%d" % (channel,val)
                    if MidiMode == 'BCR':
                        midi_out.send_message([0xB0,8+channel-8*Shift,val]) #MIDI ch. 1
                    elif MidiMode == 'MCU':
                        pass # Not Yet Implemented
                    Pan[channel]=val
                  

            elif re.match("/ch/../mix/on",addr):
                   val=int(data[0]*127)
                   channel=int(addr[4:6])
                   if channel >= (1+8*Shift) and channel <= (8+8*Shift):
                       if int(data[0]) == 0:
                           if MidiMode == 'BCR':
                               midi_out.send_message([0xB0,72+channel-8*Shift,127]) #MIDI ch. 1
                           elif MidiMode == 'MCU':
                               pass # Not Yet Implemented
                           Mute[channel]=1
                       else:
                           if MidiMode == 'BCR':
                               midi_out.send_message([0xB0,72+channel-8*Shift,0]) #MIDI ch. 1
                           elif MidiMode == 'MCU':
                               pass # Not Yet Implemented
                           Mute[channel]=0
                       
            
            elif re.match("/-stat/solosw/..",addr):
                channel=int(addr[14-16])
                if channel >= (1+8*Shift) and channel <= (8+8*Shift):
                    val=int(data[0]*127)
                    if DebugOSCrecv > 0:
                        print "Solo channel %d = %d" % (channel,val)
                    if MidiMode == 'BCR':
                        midi_out.send_message([0xB0,64+channel-8*Shift,val]) #MIDI ch. 1, CC 65 - 73
                    elif MidiMode == 'MCU':
                        pass # Not Yet Implemented
                    Solo[channel]=val
                


    # Setup OSC server & client
    server = OSC.OSCServer(("", PORT_SRV))
    server.addMsgHandler("default", msg_handler) # msg_handler() will receive ALL the OSC messages ("default" address)
    client = OSC.OSCClient(server=server) #This makes sure that client and server uses same socket. This has to be this way, as the X32 sends notifications back to same port as the /xremote message came from
    
    client.connect((ADDR, PORT_SRV))

    # Start request notifications thread
    thread = threading.Thread(target=request_notifications, kwargs = {"client": client})
    thread.start()
    client.send(OSC.OSCMessage("/xremote"))
    #oscsend("/xremote")
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
    #client.send(OSC.OSCMessage("/xremote"))
    if DebugOSCsend > 0:
        print "oscsend(",address,",",value
    c = OSC.OSCClient()
    c.connect((ADDR,PORT_SRV))
    oscmsg = OSC.OSCMessage()
    oscmsg.setAddress(address)
    if value != None:
        oscmsg.append(value)
    c.send(oscmsg)

"""
*** BCR2000 implementation chart ***
Midi Channel 1: volume bus Master LR
    CC 1-8 -> /ch/0<CC>/mix/fader

Midi Channel 2: sends Bus1 (Phones1)
    CC 1-8 -> /ch/0<CC>/mix/01/fader

Midi Channel 3: Current FX parameters
    CC 2-8 -> /fx/<CurrentFx>/par/<PAR>

Midi Channel 4: sends Bus2 (Phones2)
    CC 1-8 -> /ch/0<CC>/mix/02/fader

Midi Channel 16: FCB1010 - voice strip (3) -> FX2 return level
    CC 101 -> /ch/03/mix/08/level # FX2 send (Voice)
    CC 102 -> /fx/2/par/01" # FX2 time
"""
def RefreshBCR():
    for in range(1,9):
        if MidiMode == 'BCR':
            midi_out.send_message([0xB0,i,Volume[0][i+8*Shift]]) #MIDI ch. 1
            midi_out.send_message([0xB1,i,Volume[1][i+8*Shift]]) #MIDI ch. 2
            midi_out.send_message([0xB3,i,Volume[2][i+8*Shift]]) #MIDI ch. 4
            midi_out.send_message([0xB0,8+i,Pan[i+8*Shift]]) #MIDI ch. 1
            midi_out.send_message([0xB0,72+i,Mute[i+8*Shift]]) #MIDI ch. 1
            midi_out.send_message([0xB0,64+i,Solo[i+8*Shift]]) #MIDI ch. 1, CC 65 - 73
        elif MidiMode == 'MCU':
            midi_out.send_message([0x90,0x67+i,127])
            midi_out.send_message([0xDF+i,Volume[0][i+8*Shift],Volume[0][i+8*Shift]])
            midi_out.send_message([0x90,0x67+i,0])

def MidiCallback(message, time_stamp):
    """
    MIDI receiver handler callback
    """
    global LastMidiEvent
    global CurrentFx
    global Shift

    if int(message[0]) >= 0xB0 and int(message[0]) <= 0xBF: # at the moment we'll process only ContinousControls (CC).
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
                address="/ch/%02d/mix/fader" % (cc+8*Shift)
            if cc >= 9 and cc <= 16: # Group 2 of Encoders: Pan
                address="/ch/%02d/mix/pan" % (cc-8+8*Shift)
            if cc >= 65 and cc <= 72: # first row buttons: Solo
                address="/-stat/solosw/%02d" % (cc-64+8*Shift)
            elif cc >= 73 and cc <= 80: # second row buttons: Mute
                address="/ch/%02d/mix/on" % (cc-72+8*Shift)
                if val > 0: val=0
                else: val=127

                    
            # 81,82,83,84 are the User Defined buttons: they select the current FX
            if cc >= 81 and cc <=84:
                CurrentFx=cc-80
                if DebugMIDIrecv > 0:
                    print "CurrentFx=%d" % CurrentFx
                oscsend("/fx/%d/type" % CurrentFx) # FX
                #client.send(OSC.OSCMessage("/fx/%d/type" % CurrentFx))
                time.sleep(WAITOSC)
                for i in FxParam[FxType[CurrentFx-1]]:
                    oscsend("/fx/%d/par/%02d" % (CurrentFx,i)) # FX parameters
                    #client.send(OSC.OSCMessage("/fx/%d/par/%02d" % (CurrentFx,i)))
                    time.sleep(WAITOSC)
                    
                # these buttons should be exclusively selectable (selecting one deselect the others)
                for i in range(81,85):
                    if i == cc:
                        midi_out.send_message([0xB0,i,127]) #MIDI ch. 1
                        if DebugMIDIrecv > 1:
                            print "MIDI Send 0xB0,%d,127" %i
                    else:
                        midi_out.send_message([0xB0,i,0]) #MIDI ch. 1
                        if DebugMIDIrecv > 1:
                            print "MIDI Send 0xB0,%d,0" %i
            if cc == 85: # Shift!
                Shift=not Shift
                midi_out.send_message([0xB0,85,127*Shift]) #MIDI ch. 1
                RefreshBCR()

                

####  MIDI Channel 2 ####
        if MidiChannel == 2: # Livelli Bus1
            if cc >= 1 and cc <= 8:
                address="/ch/%02d/mix/01/level" % (cc+8*Shift)

####  MIDI Channel 3 ####
        if MidiChannel == 3: # Parametri FX corrente
           if cc == 1:
                  print "Faulty Controller!"
           if cc >= 2 and cc <= 9:
                address="/fx/%d/par/0%d" %(CurrentFx,FxParam[FxType[CurrentFx-1]][cc-2]) #NB: FxType[CurrentFX-1] is the Parameters List of the currently selected FX slot
                                                                                       # cc-2 is the index in the array we are changing
                # ie: if Type is 11, the row is [1,4,5,6,7,9,2]. If CC is 3, we take the parameter at offset "1" (CC-2), that is "4"

####  MIDI Channel 4 ####
        if MidiChannel == 4: # Livelli Bus2
            if cc >= 1 and cc <= 8:
                address="/ch/%02d/mix/02/level" % (cc+8*Shift)

####  MIDI Channel 16 ####
        if MidiChannel == 16: # FCB1010
            if DebugMIDIrecv > 0:
                print "FCB1010!"
            if cc == 101: # expression A
                if DebugMIDIrecv > 1:
                    print "Exp A"
                address="/ch/03/mix/08/level" # voce -> FX2 # *** QUESTO E' DA RIVEDERE!! ***

            if cc == 102: # expression B
                if DebugMIDIrecv > 1:
                    print "Exp B"
                address="/fx/2/par/01" # FX2 time
# End of MidiCallback

# Ok, if we have an address, we can send an OSC message:
    if address != "":        	
        oscsend(address,float(val)/127)
        #client.send(OSC.OSCMessage(address).append(float(val)/127))
        
def OpenMidiPort(midi_port, descr="Devices"):
    """
    Helper function to open midi device
    """
    i=0
    port=-1
    print "MIDI %s:" % descr
    for port_name in midi_port.ports:
        if port_name.find(MIDINAME) != -1:
            port=i
            print "    ",i,": * ",port_name," *"
        else:
            print "    ",i,": ",port_name
        i=i+1
        
    if port == -1:
        print "Device "+MIDINAME+" not found in Midi %s. Aborting." % descr
        exit()
    return(port)


midi_in=rtmidi.MidiIn()
port_in=OpenMidiPort(midi_in,"Input Devices")
midi_out=rtmidi.MidiOut()
port_out=OpenMidiPort(midi_out,"Output Devices")

midi_in.callback = MidiCallback

midi_in.open_port(port_in)
midi_out.open_port(port_out)
print "====================================="
help()

### Some MIDI initial setup ###
# CurrentFx buttons:
midi_out.send_message([0xB0,81,0])   #MIDI ch. 1, CC81, off
midi_out.send_message([0xB0,82,0])   #MIDI ch. 1, CC82, off
midi_out.send_message([0xB0,83,0])   #MIDI ch. 1, CC83, off
midi_out.send_message([0xB0,84,0])   #MIDI ch. 1, CC84, off
midi_out.send_message([0xB0,80+CurrentFx,127]) #MIDI ch. 1, CC81, on (se CurrentFx = 1)

parse_messages()

