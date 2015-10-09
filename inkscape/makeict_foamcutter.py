#!/usr/bin/env python
'''
Copyright (c) 2015 MakeICT

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''
import sys,os
import time
import inkex
from math import *
import getopt
from makeict_foamcutter.context import GCodeContext
from makeict_foamcutter.svg_parser import SvgParser

class MyEffect(inkex.Effect):
	def __init__(self):
		inkex.Effect.__init__(self)
		self.OptionParser.add_option('--serialPort',			action='store', type='string',	dest='serialPort',				default='COM1',		help='Serial port')
		self.OptionParser.add_option('--serialBaudRate',		action='store', type='string',	dest='serialBaudRate',			default='9600',		help='Serial Baud rate')
		self.OptionParser.add_option('--flowControl',			action='store', type='string',	dest='flowControl',				default='0',		help='Flow control')
		self.OptionParser.add_option("--pen-up-angle",			action="store", type="float",	dest="pen_up_angle",			default="180.0",	help="Pen Up Angle")
		self.OptionParser.add_option("--pen-down-angle",		action="store", type="float", 	dest="pen_down_angle",			default="0.0",		help="Pen Down Angle")
		self.OptionParser.add_option("--start-delay",			action="store", type="float",	dest="start_delay", 			default="500.0",	help="Delay after pen down, before movement (ms)")
		self.OptionParser.add_option("--stop-delay",			action="store", type="float",	dest="stop_delay", 				default="500.0",	help="Delay after pen up, before movement (ms)")
		self.OptionParser.add_option("--xy-feedrate",			action="store", type="float",	dest="xy_feedrate", 			default="500.0",	help="XY axes feedrate in mm/min")
		self.OptionParser.add_option("--z-feedrate",			action="store", type="float",	dest="z_feedrate", 				default="150.0",	help="Z axis feedrate in mm/min")
		self.OptionParser.add_option("--z-height",				action="store", type="float",	dest="z_height", 				default="0.0",		help="Z axis print height in mm")
		self.OptionParser.add_option("--finished-height",		action="store", type="float",	dest="finished_height", 		default="0.0",		help="Z axis height after printing in mm")
		self.OptionParser.add_option("--register-pen",			action="store", type="string",	dest="register_pen", 			default="true",		help="Add pen registration check(s)")
		self.OptionParser.add_option("--x-home",				action="store", type="float",	dest="x_home", 					default="0.0",		help="Starting X position")
		self.OptionParser.add_option("--y-home",				action="store", type="float",	dest="y_home", 					default="0.0",		help="Starting Y position")
		self.OptionParser.add_option("--num-copies",			action="store", type="int",		dest="num_copies", 				default="1")
		self.OptionParser.add_option("--continuous",			action="store",	type="string",	dest="continuous", 				default="false",	help="Plot continuously until stopped.")
		self.OptionParser.add_option("--pause-on-layer-change",	action="store", type="string",	dest="pause_on_layer_change",	default="false",	help="Pause on layer changes.")
		self.OptionParser.add_option("--tab",					action="store", type="string",	dest="tab")
											
	def effect(self):
		self.context = GCodeContext(
			self.options.xy_feedrate,
			self.options.z_feedrate, 
			self.options.start_delay, self.options.stop_delay,
			self.options.pen_up_angle, self.options.pen_down_angle,
			self.options.z_height, self.options.finished_height,
			self.options.x_home, self.options.y_home,
			self.options.register_pen,
			self.options.num_copies,
			self.options.continuous,
			self.svg_file
		)
		parser = SvgParser(self.document.getroot(), self.options.pause_on_layer_change)
		parser.parse()
		for entity in parser.entities:
			entity.get_gcode(self.context)
			
		gcodeBuffer = self.context.generate()

		outputFile = open("/tmp/foam-cutter-output.gcode", "w")
		outputFile.write("Output file opened\n")
		outputFile.flush()
		
		try:
			import serial
		except ImportError, e:
			inkex.errormsg(_("pySerial is not installed."
				+ "\n\n1. Download pySerial here (not the \".exe\"!): http://pypi.python.org/pypi/pyserial"
				+ "\n2. Extract the \"serial\" subfolder from the zip to the following folder: C:\\[Program files]\\inkscape\\python\\Lib\\"
				+ "\n3. Restart Inkscape."
			))
			return
				
		# send data to plotter
		mySerial = serial.Serial()
		mySerial.port = self.options.serialPort
		mySerial.baudrate = self.options.serialBaudRate
		mySerial.timeout = 10
		
		if self.options.flowControl == 'xonxoff':
			mySerial.xonxoff = True
		if self.options.flowControl == 'rtscts' or self.options.flowControl == 'dsrdtrrtscts':
			mySerial.rtscts = True
		if self.options.flowControl == 'dsrdtrrtscts':
			mySerial.dsrdtr = True
			
		try:
			outputFile.write("Opening serial port...")
			outputFile.flush()
			mySerial.open()
			readyString = mySerial.read(5)
			if readyString != "ready":
				inkex.errormsg("Invalid ready string: '%s'" % readyString)
				return
			
			outputFile.write("opened.\n")
			outputFile.flush()
		except Exception as inst:
			if 'ould not open port' in inst.args[0]:
				inkex.errormsg(_("Could not open port. Please check that your plotter is running, connected and the settings are correct.\n\n%s" % inst))
				return
			else:
				type, value, traceback = sys.exc_info()
				raise ValueError, ('', type, value), traceback
		
		outputFile.write("Writing data...\n")
		outputFile.flush()
		
		for line in gcodeBuffer:
			if line != "":
				outputFile.write("Sending %s..." % line)
				outputFile.flush()
				mySerial.write("%s\n" % line)
				outputFile.write("sent.\n")
				outputFile.flush()
					
				readInData = mySerial.read(2)
				outputFile.write("    Read size: %d = %s\n" % (len(readInData), readInData))
				outputFile.flush()
				
		outputFile.write("Closing serial port...")
		mySerial.flush()
		mySerial.close()
		outputFile.write("closed.\n")    
		outputFile.close()
		
def get_serial_ports():
	import glob
	import serial
	
	if sys.platform.startswith('win'):
		ports = ['COM' + str(i + 1) for i in range(256)]

	elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
		# this is to exclude your current terminal "/dev/tty"
		ports = glob.glob('/dev/tty[A-Za-z]*')

	elif sys.platform.startswith('darwin'):
		ports = glob.glob('/dev/tty.*')

	else:
		raise EnvironmentError('Unsupported platform')

	result = []
	for port in ports:
		try:
			s = serial.Serial(port)
			s.close()
			result.append(port)
		except (OSError, serial.SerialException):
			pass
			
	return result
		
if __name__ == '__main__':   #pragma: no cover
	e = MyEffect()
	e.affect()
