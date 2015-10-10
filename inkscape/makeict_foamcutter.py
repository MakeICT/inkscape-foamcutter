#!/usr/bin/env python
# -*- coding: utf-8 -*-

#	cutting depth
#	auto-connect

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

try:
	import serial
except ImportError, e:
	inkex.errormsg(_("pySerial is not installed."
		+ "\n\n1. Download pySerial here (not the \".exe\"!): http://pypi.python.org/pypi/pyserial"
		+ "\n2. Extract the \"serial\" subfolder from the zip to the following folder: C:\\[Program files]\\inkscape\\python\\Lib\\"
		+ "\n3. Restart Inkscape."
	))
	exit()


import pygtk, gtk

class MyEffect(inkex.Effect):
	def __init__(self):
		inkex.Effect.__init__(self, ports)
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
		
		self.serial = None
		self.pos = [0, 0]
		
		self.ports = ports
		
		self.backgroundColors = {}
											
	def effect(self):
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.window.connect("destroy", self.destroy)
		self.window.set_border_width(10)

		container = gtk.VBox(False, 10)
		
		self.portSelector = gtk.combo_box_new_text()
		for p in self.ports:
			self.portSelector.append_text(p)
		self.portSelector.set_active(0)
		
#		bauds = ["110", "300", "600", "1200", "2400", "4800", "9600", "14400", "19200", "28800", "38400", "56000", "57600", "115200"]
#		self.baudSelector = gtk.combo_box_new_text()
#		for i, rate in enumerate(bauds):
#			self.baudSelector.append_text("%s" % rate)
#			if rate == self.options.serialBaudRate:
#				self.baudSelector.set_active(i)
#
#		self.flowControlSelector = gtk.combo_box_new_text()
#		self.flowControlSelector.append_text("XON/XOFF")
#		self.flowControlSelector.append_text("RTS/CTS")
#		self.flowControlSelector.append_text("DSR/DTR + RTS/CTS")
#
		self.serialOptions = gtk.Table(3, 2, False)
		self.serialOptions.attach(gtk.Label("Serial port"), 0, 1, 0, 1)
		self.serialOptions.attach(self.portSelector, 1, 2, 0, 1)
#		self.serialOptions.attach(gtk.Label("Baud rate"), 0, 1, 1, 2)
#		self.serialOptions.attach(self.baudSelector, 1, 2, 1, 2)
#		self.serialOptions.attach(gtk.Label("Flow control"), 0, 1, 2, 3)
#		self.serialOptions.attach(self.flowControlSelector, 1, 2, 2, 3)
#		
		container.add(self.serialOptions)
		
		self.connectButton = gtk.Button("Connect")
		self.connectButton.connect("clicked", self.toggleConnect)
		container.add(self.connectButton)
		
		stepSize = 1
		
		self.controls = gtk.VBox(False, 10)
		
		arrows = gtk.Table(5, 5, True)
		b = gtk.Button("⇑")
		b.connect("clicked", self.moveY, 10 * stepSize)
		arrows.attach(b, 2, 3, 0, 1)
		
		b = gtk.Button("↑")
		b.connect("clicked", self.moveY, stepSize)
		arrows.attach(b, 2, 3, 1 ,2)

		b = gtk.Button("⇐")
		b.connect("clicked", self.moveX, 10 * stepSize)
		arrows.attach(b, 0, 1, 2, 3)

		b = gtk.Button("←")
		b.connect("clicked", self.moveX, stepSize)
		arrows.attach(b, 1, 2, 2, 3)

		b = gtk.Button("→")
		b.connect("clicked", self.moveX, -stepSize)
		arrows.attach(b, 3, 4, 2, 3)

		b = gtk.Button("⇒")
		b.connect("clicked", self.moveX, -10 * stepSize)
		arrows.attach(b, 4, 5, 2, 3)

		b = gtk.Button("↓")
		b.connect("clicked", self.moveY, -stepSize)
		arrows.attach(b, 2, 3, 3, 4)

		b = gtk.Button("⇓")
		b.connect("clicked", self.moveY, -10 * stepSize)
		arrows.attach(b, 2, 3, 4, 5)
		
		self.controls.add(arrows)

		self.homeButtons = gtk.Frame()
		box = gtk.HBox(True)
		self.setHomeButton = gtk.Button("Set Home")
		self.setHomeButton.connect("clicked", self.setHome, None)
		box.add(self.setHomeButton)
		
		self.goHomeButton = gtk.Button("Go Home")
		self.goHomeButton.connect("clicked", self.goHome, None)
		box.add(self.goHomeButton)
		
		self.homeButtons.add(box)
		
		self.controls.add(self.homeButtons)
		
		sendButtons = gtk.HBox(True)
#		b = gtk.Button("▶ Selection")
#		b.connect("clicked", self.sendSelection, None)
#		sendButtons.add(b)
		
		b = gtk.Button("▶ Send document")
		b.connect("clicked", self.sendAll, None)
		sendButtons.add(b)
		
		self.controls.add(sendButtons)

		container.add(self.controls)
		
		self.window.add(container)
		
		self.serialOptions.show_all()
		self.connectButton.show()
		container.show()
		self.window.show_all()
		
		for i, p in enumerate(self.ports):
			self.portSelector.set_active(i)
			try:
				self.connect()
				break
			except:
				pass
		
		gtk.main()

	def highlight(self, widget, color="#a00"):
		map = widget.get_colormap() 
		color = map.alloc_color(color)

		#copy the current style and replace the background
		style = widget.get_style().copy()
		
		if not widget in self.backgroundColors:
			self.backgroundColors[widget] = style.bg[gtk.STATE_NORMAL]

		style.bg[gtk.STATE_NORMAL] = color

		#set the button's style to the one you created
		widget.set_style(style)
		
	def dehighlight(self, widget, color="#000000"):
		if widget in self.backgroundColors:
			self.highlight(widget, self.backgroundColors[widget])
		else:
			self.highlight(widget, color)

		
	def generateBuffer(self):
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
			
		return self.context.generate()
		
	def send(self, message):
		if self.serial is None:
			self.disconnect()
			raise Exception("Not connected :(")
			
		self.serial.write("%s\n" % message)
		ok = self.serial.read(2)
		if ok != "ok":
			raise Exception("Invalid response: '%s'" % ok)
		
	def destroy(self, widget, data=None):
		gtk.main_quit()

	def toggleConnect(self, widget, data=None):
		if self.serial is None:
			try:
				self.saveOptions()
				self.connect()
				self.connectButton.set_label("Disconnect")
				self.controls.show_all()
			except Exception as exc:
				self.showError(exc)
		else:
			self.disconnect()
			self.connectButton.set_label("Connect")
			self.controls.hide()
		
	def saveOptions(self):
		self.options.serialPort = self.portSelector.get_active_text()
#		self.options.serialBaudRate = self.baudSelector.get_active_text()
#		self.options.flowControl = self.flowControlSelector.get_active_text()
	
	def connect(self):
		try:
			self.serial = serial.Serial()
			self.serial.port = self.options.serialPort
			self.serial.baudrate = self.options.serialBaudRate
			self.serial.timeout = 10

			if self.options.flowControl == 'XON/XOFF':
				self.serial.xonxoff = True
			if self.options.flowControl == 'RTS/CTS' or self.options.flowControl == 'DSR/DTR + RTS/CTS':
				self.serial.rtscts = True
			if self.options.flowControl == 'DSR/DTR + RTS/CTS':
				self.serial.dsrdtr = True
			
			self.serial.open()
			readyString = self.serial.read(26)
			if readyString != "MakeICT Foam Cutter ready!":
				raise Exception("Invalid ready string: '%s'" % readyString)

			self.send("G21 (metric ftw)")
			self.send("G90 (absolute mode)")
			self.send("G92 X0.0 Y0.0")
				
		except Exception as exc:
			self.serial = None
			raise exc
			
	def disconnect(self):
		try:
			self.serial.flush()
			self.serial.close()
		except:
			pass
		finally:
			self.serial = None
		
	def showError(self, msg):
		if isinstance(msg, OSError):
			msg = str(msg)
		elif isinstance(msg, Exception):
			msg = msg.message
			
		message = gtk.MessageDialog(type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE, message_format="Error: %s")
		message.set_markup(msg)
		message.run()
		message.destroy()
		
	def setHome(self, widget, data=None):
		try:
			self.pos = [0, 0]
			self.send("G92 X0.0 Y0.0")
			self.updatePosition()
		except Exception as exc:
			self.showError(exc)
			
	def goHome(self, widget, data=None):
		try:
			self.pos = [0, 0]
			self.updatePosition()
		except Exception as exc:
			self.showError(exc)
		
	def updatePosition(self):
		try:
			if self.pos[0] != 0 or self.pos[1] != 0:
				self.highlight(self.homeButtons)
			else:
				self.dehighlight(self.homeButtons)
			self.send("G1 X%0.2F Y%0.2F F%0.2F" % (self.pos[0], self.pos[1], self.options.xy_feedrate))
		except Exception as exc:
			self.showError(exc)

			
	def moveX(self, widget, data=None):
		step = data
		self.pos[0] += step
		self.updatePosition()

	def moveY(self, widget, data=None):
		step = data
		self.pos[1] += step
		self.updatePosition()

#	def sendSelection(self, widget, data=None):
#		self.showError("Not yet implemented")
#		pass
		
	def sendAll(self, widget, data=None):
		try:
			data = self.generateBuffer()
			for line in data:
				if line != "" and line[0] != "(":
					inkex.debug("SEND: %s" % line)
					self.send(line)
		except Exception as exc:
			self.showError(exc)
		
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
	ports = get_serial_ports()
	if len(ports) == 0:
		inkex.errormsg("No serial ports found :(")
		inkex.errormsg("Please connect your device and try again")
	else:
		e = MyEffect()
		e.affect()		

	
