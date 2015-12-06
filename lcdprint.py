#!/usr/bin/python


import RPi_I2C_driver
import sys
lcd=RPi_I2C_driver.lcd()
if len(sys.argv) > 1:
    str1=sys.argv[1] 
    if len(sys.argv) > 2:
        str2=sys.argv[2]
    else:
        str2=""
    lcd.lcd_display_string(str1,1)
    lcd.lcd_display_string(str2,2)
else:
    lcd.lcd_clear()
