#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
History:
    2015-12-26: 0.1.00: completely rewritten translatuion engine using a table (tested only on BCR2000)
    2015-12-25: 0.0.18: Footsy support (configure parameters, persistence)
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
VERSION="0.1.00"

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

MidiMsg=[]
OscMsg=[]
ParIndex=[]


def PrepareArray(array):
    """
    takes the Userdefined array and fills up three fast-to-decode simple monodimensional arrays
    """
    global MidiMsg
    global OscMsg
    global ParIndex
#    print array
    for item in array:
        print item
        MidiMsg.append(item[0])
        OscMsg.append(item[1])
        ParIndex.append(item[2])
#        print "%s - %s - %s" % (item[0],item[1],item[2])

def SearchMidi(val):
#    print "SearchMidi: ",val
    if val in MidiMsg:
        return(MidiMsg.index(val))
    else:
        return(-1)

def SearchOsc(val):
    if val in OscMsg:
        return (OscMsg.index(val))
    else:
        #return((-1,-1))
        return(-1)

def SearchParam(val):
    if val in ParIndex:
        return(ParIndex.index(val))
    else:
        return(-1)

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

#    if port == -1:
#        if args.verbose == True:
#            print "Device "+name+" not found in Midi %s. Aborting." % descr
#        exit()
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
    if port_out >= 0:
        midi_out.send_message([0x90,MidiMessages["Unlock"]+fader,127]) # unlock fader
        midi_out.send_message([MidiMessages["Fader"]+fader-1 ,val,val]) # move fader
        midi_out.send_message([0x90,MidiMessages["Unlock"]+fader ,0])  # lock fader

def sendToBCR(channel,slot,val):
    if MidiMode == 'BCR':
        if channel >= 0 and channel <=3:
            cmd=0xB0+channel
        else:
            print "ATTENZIONE: qualcuno sta inviando il CC %d (%d) al MidiChannel %d"%(slot,val,channel)
        if port_out >= 0: 
            midi_out.send_message([cmd,slot,val])
            if DebugMIDIsend > 0:
                print "sendToBCR: send_message(0x%x,%d,%d)"%(cmd,slot,val)



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
FootsyStatus=[[0]*4,[0]*4]
FootsyTimer=0
FxType=[0,0,0,0]
FxReturn=[ #Fx1, Fx2, Fx3, Fx4, Aux
            [0]*5, # Master
            [0]*5, # Bus1
            [0]*5, # Bus2
        ]
MAIN=0
BUS1=1
BUS2=2
FX1=3
FX2=4
FX3=5
FX4=6
PAN=7
MUTE=8
SOLO=9
NAME=10

Volume=[ # 16 channels
        [0]*32, # Main LR
        [0]*32, # Bus1
        [0]*32, # Bus2
        [0]*32, # Fx1
        [0]*32, # Fx2
        [0]*32, # Fx3
        [0]*32, # Fx4
        [0]*32, # Pan
        [0]*32, # Mute
        [0]*32, # Solo
        [""]*32, # Name
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
parser.add_argument("-I", "--midiin",  help="Midi-In device(s) (override config file)")
parser.add_argument("-O", "--midiout", help="Midi-Out device(s) (override config file)")
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
    if os.path.isfile(home+CONFIGFILE): # home dir
        configfile=home+CONFIGFILE
    elif os.path.isfile(CONFIGFILE): # working dir
        configfile=CONFIGFILE
    elif os.path.isfile(os.path.split(os.path.abspath(__file__))[0]+os.sep+CONFIGFILE): # file dir
        configfile=os.path.split(os.path.abspath(__file__))[0]+os.sep+CONFIGFILE

if args.verbose == True:
    print "ConfigFile: ",configfile

if os.path.isfile(configfile) and parser.read(configfile) != None:
    MIDINAME=ReadConfig('MIDI', 'DeviceName')
    MIDINAME_IN=ReadConfig('MIDI', 'DeviceNameIn')
    MIDINAME_OUT=ReadConfig('MIDI', 'DeviceNameOut')
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

    for i in Translation:
        #for j in 1,2,3:
        #    if i[j] != "":
            if i[1] != "":
                if DebugOSCsend > 0:
                    #print "OSCsend: ",i[j]
                    print "OSCsend: ",i[1]
                #client.send(OSC.OSCMessage(i[j]))
                client.send(OSC.OSCMessage(i[1]))
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
        #BUS="Master: %s" % BusName[0]
        BUS="Master: %s" % Volume[NAME][21]
    for Bus in range(1,7):
        if ActiveBus == Bus:
            #BUS="Bus%d: %s" %(Bus, BusName[Bus])
            BUS="Bus%d: %s" %(Bus, Volume[NAME][16+Bus])
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
    print "BassChannel=%d" % BassChannel
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
        if Stat == 0: Stat=127
        else:  Stat=0
        if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Rec"] ,Stat]) # Rec

    if do_exit != True:
        threading.Timer(1,Progress,()).start()
    FlipFlop=not FlipFlop

    #if footsy_port >= 0: footsy_out.send_message([0xBE,5,FlipFlop*127])

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
            elif tags == 'i':
                val=127*int(data[0])
            elif tags == 's':
                val=data[0]

            index=SearchOsc(addr)
            if index >= 0:
                if Translation[index][0] != "":
                    remotebank=int(Translation[index][0].split(',')[0])
                    MidiChannel=int(Translation[index][0].split(',')[1])
                    MidiCC=int(Translation[index][0].split(',')[2])
                else:
                    MidiChannel=-1
                    MidiCC=-1
                Bus=int(eval(Translation[index][2].split(',')[0]))
                Channel=int (Translation[index][2].split(',')[1])
                Min=int(eval(Translation[index][2].split(',')[2]))
                Max=int(eval(Translation[index][2].split(',')[3]))
                if tags == 'f':
                    val=interpolate(int(data[0]*127),0,127,Min,Max)
                elif tags == 'i':
                    val=interpolate(127*int(data[0]),0,127,Min,Max)
                elif tags == 's':
                    val=data[0]
                Volume[Bus][Channel]=val
                if DebugOSCrecv: 
                    if tags == "s":
                        print "Translation:(%d:%d) send CC %d on Midi# %d and set Volume[%d][%d] to %s" %(remotebank,index,MidiChannel,MidiCC,Bus,Channel,val)
                    else:
                        print "Translation:(%d:%d) send CC %d on Midi# %d and set Volume[%d][%d] to %d" %(remotebank,index,MidiChannel,MidiCC,Bus,Channel,val)
                if MidiChannel != -1 and MidiCC != -1:
                    if MidiMode == 'BCR':
                        if Bank == remotebank:
                            if DebugMIDIsend > 0:
                                print "Send MIDI: %d,%d,%d"%(MidiChannel,MidiCC,val)
                            sendToBCR(MidiChannel-1,MidiCC,val)
                    elif MidiMode == 'MCU':
                        if ActiveBus == Bus:
                            if Bank == remotebank:
                                sendToMCU(MidiCC,val)
                RefreshController()

            else:
                # FX type (es.: "/fx/1/type")
                if re.match("/fx/./type",addr):
                    slot=int(addr[4]) # addr[4] is the FX (1 to 4)
                    FxType[slot-1]=data[0] 
                    if DebugOSCrecv > 0:
                        print "Found FX %d set to %d" % (slot,FxType[slot-1])

                # FX parameters (es.: "/fx/1/par/06")
                if re.match("/fx/./par/..",addr): 
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
    global VoiceChannel
    global BassChannel

    if footsy_port >= 0:
        for i in range(1,5):
            footsy_out.send_message([0xBE,i,FootsyStatus[0][i-1]])
        for i in range(6,10):
            footsy_out.send_message([0xBE,i,FootsyStatus[1][i-6]])
    
    for i in Translation:
        if i[0] != "":
            bank=int(i[0].split(',')[0])
            chan=int(i[0].split(',')[1])
            cc=int(i[0].split(',')[2])
            bus=int(eval(i[2].split(',')[0]))
            pos=int(i[2].split(',')[1])
            if int(bank) == Bank:
                if MidiMode == 'BCR':
                    sendToBCR(chan-1,cc,Volume[bus][pos])
                elif MidiMode == 'MCU':
                    if bus == ActiveBus:
                        sendToMCU(cc,Volume[bus][pos])

    for index,name in enumerate(Volume[NAME]):
        if name.lower() in ("basso","bass"):
            BassChannel=index+1
            #print "BassChannel=",BassChannel
        if name.lower() in ("voce","voce1","vox","vox1","voice","voice1"):
            VoiceChannel=index+1
            #print "VoiceChannel=",VoiceChannel
    if MidiMode == 'MCU':
        if ActiveBus == 1:
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["TrackL"],0])
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["TrackR"],127])
        elif ActiveBus == 2:
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["TrackL"],127])
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["TrackR"],0])
        else:
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["TrackL"],0])
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["TrackR"],0])

        if CurrentFx == 1:
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Prev"],0])
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Next"],0])
        if CurrentFx == 2:
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Prev"],127])
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Next"],0])
        if CurrentFx == 3:
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Prev"],0])
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Next"],127])
        if CurrentFx == 4:
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Prev"],127])
            if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Next"],127])

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

def FootsyConfigure(cc):
    if cc <= 4: 
        status=FootsyStatus[0][cc-1]
        val=Volume[2+cc][VoiceChannel-1]
        if status == 127:
            FxInterpolation[0][cc-1][1]=float(val)/127
        else:
            FxInterpolation[0][cc-1][0]=float(val)/127

    else: 
        status=FootsyStatus[1][cc-6]
        val=Volume[cc-3][BassChannel-1]
        if status == 127:
            FxInterpolation[1][cc-6][1]=float(val)/127
        else:
            FxInterpolation[1][cc-6][0]=float(val)/127
    print "Configure cc %d (status: %d - Val=%f)" % (cc,status,val)
    FxInterpolationString="[[\n[%f,%f]\n,[%f,%f]\n,[%f,%f]\n,[%f,%f]\n]\n,[[%f,%f]\n,[%f,%f]\n,[%f,%f]\n,[%f,%f]\n]]" % (
                                                FxInterpolation[0][0][0],FxInterpolation[0][0][1],
                                                FxInterpolation[0][1][0],FxInterpolation[0][1][1],
                                                FxInterpolation[0][2][0],FxInterpolation[0][2][1],
                                                FxInterpolation[0][3][0],FxInterpolation[0][3][1],
                                                FxInterpolation[1][0][0],FxInterpolation[1][0][1],
                                                FxInterpolation[1][1][0],FxInterpolation[1][1][1],
                                                FxInterpolation[1][2][0],FxInterpolation[1][2][1],
                                                FxInterpolation[1][3][0],FxInterpolation[1][3][1])
    print FxInterpolationString
    parser.set("OSC2Midi","FxInterpolation",FxInterpolationString)
    with open(configfile, 'wb') as cf:
        parser.write(cf)
    
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
    global FootsyStatus
    global FootsyTimer

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
            if message[1] == MidiMessages["Rec"] and message[2] == 0x7f:
                if Shift == 0:
                    do_exit=True
                    if os.name == 'posix' and os.uname()[1] == 'raspberrypi':
                        lcd.lcd_display_string("Exiting...      ",1)
                        lcd.lcd_display_string("Bye             ",2)
                    time.sleep(1)
                    os.system("killall Osc2MidiBridge.py")
                    exit()
                else:
                    if os.name == 'posix' and os.uname()[1] == 'raspberrypi':
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
                    if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Stop"],0])
                else:
                    Shift=1
                    if port_out >= 0: midi_out.send_message([0x90,MidiMessages["Stop"],127])
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

        index=SearchMidi("%d,%d,%d"%(Bank,MidiChannel,cc))
        if index>= 0:
            address=Translation[index][1]
            if address != "":
                Bus=int(eval(Translation[index][2].split(',')[0]))
                Channel=int (Translation[index][2].split(',')[1])
                Min=int(eval(Translation[index][2].split(',')[2]))
                Max=int(eval(Translation[index][2].split(',')[3]))
                Volume[Bus][Channel]=val
                val=interpolate(val, 0, 127, Min, Max)
                if DebugMIDIrecv: print "Translation:(%d) send %s and set Volume[%d][%d] to %s" %(index,address,Bus,Channel,val)
        else:

####  MIDI Channel 1 ####
            if MidiChannel == 1: # Master LR Volume
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
            if MidiChannel == 15 and val == 127: # CGfootsy
                FootsyTimer=time.time()
            if MidiChannel == 15 and val == 0:
                FOOTSYTIMEOUT=3
                if FootsyTimer > 0 and time.time() - FootsyTimer > FOOTSYTIMEOUT:
                    FootsyConfigure(cc)
                    FootsyTimer=0
                else:
                    FootsyTimer=0
                    if DebugMIDIrecv > 0:
                        print "CGfootsy!"
                    if cc >= 1 and cc <= 4: #fila inferiore (Voice)
                        if FootsyStatus[0][cc-1] == 0:
                            FootsyStatus[0][cc-1]=127
                            val=127
                        else:
                            FootsyStatus[0][cc-1]=0
                            val=0
                        address="/ch/%02d/mix/%02d/level" % (VoiceChannel,cc+6) # Send of Voice on Fx1-4
                        interpolation=(FxInterpolation[0][cc-1][0],FxInterpolation[0][cc-1][1])
                        Volume[cc+2][VoiceChannel-1]=127*interpolate(float(val),0,127,interpolation[0],interpolation[1])
                        print "Footsy status for cc %d is %s" %(cc, FootsyStatus[0][cc-1])

                    if cc >= 6 and cc <=9: # fila superiore (Bass)
                        if FootsyStatus[1][cc-6] == 0:
                            FootsyStatus[1][cc-6]=127
                            val=127
                        else:
                            FootsyStatus[1][cc-6]=0
                            val=0
                        address="/ch/%02d/mix/%02d/level" % (BassChannel,cc+1) # Send of Voice on Fx1-4
                        interpolation=(FxInterpolation[1][cc-5][0],FxInterpolation[1][cc-5][1])
                        Volume[cc-3][BassChannel-1]=127*interpolate(float(val),0,127,interpolation[0],interpolation[1])
                        print "Footsy status for cc %d is %s" %(cc, FootsyStatus[1][cc-6])
                RefreshController()
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


#### Midi In ###
midi_in=[0]*10
port_in=[0]*10
index=0
for i in MIDINAME_IN.split(','):
    midi_in[index]=rtmidi.MidiIn()
    port_in[index]=OpenMidiPort(i,midi_in[index],"Input Devices")
    if port_in[index]  >= 0: 
        midi_in[index].open_port(port_in[index])
        midi_in[index].callback = MidiCallback
    index += 1

#### Midi Out ####
midi_out=rtmidi.MidiOut()
for i in MIDINAME_OUT.split(','):
    port_out=OpenMidiPort(i,midi_out,"Output Devices")
    if port_out  >= 0: 
        midi_out.open_port(port_out)
        break # we'll take only the first valid MIDI Out

footsy_out=rtmidi.MidiOut()
footsy_port=OpenMidiPort("Teensy",footsy_out,"Footsy")
if footsy_port >= 0:
    footsy_out.open_port(footsy_port)

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

PrepareArray(Translation)
threading.Timer(1,Progress,()).start()
RefreshController()
lcd_status()
parse_messages()

