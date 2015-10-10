#!/usr/bin/env python
# -*- coding: utf-8 -*-

#	cutting depth
#	button blink
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


import gtk
import ConfigParser

class MyEffect(inkex.Effect):
	def __init__(self):
		inkex.Effect.__init__(self, ports)

		self.configFile = 'makeict_foamcutter/config.ini'
		self.config = ConfigParser.ConfigParser({
			'serialPort': '/dev/ttyUSB0',
			'serialBaudRate': '9600',
			'flowControl': 'None',
			'penUpAngle': '180.0',
			'penDownAngle': '0.0',	
			'startDelay': '500.0',
			'stopDelay': '500.0',
			'xyFeedrate': '500.0',
			'zFeedrate': '150.0',
			'zHeight': '0.0',
			'finishedHeight': '0.0',
			'registerPen': 'False',
			'xHome': '0.0',
			'yHome': '0.0',
			'numCopies': '1',
			'continuous': 'False',
			'pauseOnLayerChange': 'False',
			
		})
		self.config.read(self.configFile)
		self.preset = "Foam Cutter Defaults"
		try:
			self.config.add_section(self.preset)
		except: pass
		
		self.serial = None
		self.pos = [0, 0]
		
		self.ports = ports
		
	def getOption(self, option):
		return self.config.get(self.preset, option)
											
	def getFloatOption(self, option):
		return float(self.getOption(option))
											
	def getIntOption(self, option):
		return int(self.getOption(option))
											
	def getBooleanOption(self, option):
		return self.getOption(option) in ['True', 'true', '1', 'Yes', 'yes', 'T', 't', 'Y', 'y']
											
	def setOption(self, option, value):
		return self.config.set(self.preset, option, str(value))
		
	def saveOptions(self):
		f = open(self.configFile, 'w')
		self.config.write(f)
		f.close()

	def effect(self):
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.window.connect("destroy", self.destroy)
		self.window.set_border_width(10)

		'''
			Basic Controls Page
		'''
		basicControlsPage = gtk.VBox(False, 10)

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

		homeButtons = gtk.HBox(True)
		b = gtk.Button("Set Home")
		b.connect("clicked", self.setHome, None)
		homeButtons.add(b)
		
		b = gtk.Button("Go Home")
		b.connect("clicked", self.goHome, None)
		homeButtons.add(b)
		
		self.controls.add(homeButtons)
		
		sendButtons = gtk.HBox(True)
#		b = gtk.Button("▶ Selection")
#		b.connect("clicked", self.sendSelection, None)
#		sendButtons.add(b)
		
		b = gtk.Button("▶ Send document")
		b.connect("clicked", self.sendAll, None)
		sendButtons.add(b)
		
		self.controls.add(sendButtons)

		basicControlsPage.add(self.controls)

		'''
			Serial controls
		'''
		serialControlsPage = gtk.VBox(False, 10)
		
		self.portSelector = gtk.combo_box_new_text()
		for i,p in enumerate(self.ports):
			self.portSelector.append_text(p)
			if p == self.getOption('serialPort'):
				self.portSelector.set_active(i)

		bauds = [110, 300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 56000, 57600, 115200]
		baudSelector = gtk.combo_box_new_text()
		for i, rate in enumerate(bauds):
			baudSelector.append_text("%s" % rate)
			if rate == self.getFloatOption('serialBaudRate'):
				baudSelector.set_active(i)

		flowOptions = ["None", "XON/XOFF", "RTS/CTS", "DSR/DTR + RTS/CTS"]
		flowControlSelector = gtk.combo_box_new_text()
		for i, opt in enumerate(flowOptions):
			flowControlSelector.append_text("%s" % opt)
			if opt == self.getOption('flowControl'):
				flowControlSelector.set_active(i)

		controls = [
			{
				"label": "Serial Port",
				"id": "serialPort",
				"control": self.portSelector,
			},{
				"label": "Baud Rate",
				"id": "serialBaudRate",
				"control": baudSelector,
			},{
				"label":"Flow Control",
				"id": "flowControl",
				"control": flowControlSelector,
			},
		]

		serialOptions = gtk.Table(3, 2, False)
		for i,c in enumerate(controls):
			serialOptions.attach(gtk.Label(c['label']), 0, 1, i, i+1)
			serialOptions.attach(c['control'], 1, 2, i, i+1)
			c['control'].connect('changed', self.optionChanged, c)

		serialControlsPage.add(serialOptions)
		
		self.connectButton = gtk.Button("Connect")
		self.connectButton.connect("clicked", self.toggleConnect)
		serialControlsPage.add(self.connectButton)
		
		'''
			Plotter Setup
		'''
		setupPage = gtk.Table(8, 2, False)
		
		gtk.Adjustment(value=0, lower=0, upper=0, step_incr=0, page_incr=0, page_size=0)
		
		controls = [
			{
				"label": "Pen up angle",
				"id": "penUpAngle",
				"control": gtk.SpinButton(gtk.Adjustment(180, 0, 180, 1, 10, 0)),
			},{
				"label": "Pen down angle",
				"id": "penDownAngle",
				"control": gtk.SpinButton(gtk.Adjustment(0, 0, 180, 1, 10, 0)),
			},{
				"label":"Start delay",
				"id": "startDelay",
				"control": gtk.SpinButton(gtk.Adjustment(500, 0, 1000, 10, 100, 0)),
			},{
				"label": "Stop delay",
				"id": "stopDelay",
				"control": gtk.SpinButton(gtk.Adjustment(500, 0, 1000, 10, 100, 0)),
			},{
				"label": "X-Y feedrate",
				"id": "xyFeedrate",
				"control": gtk.SpinButton(gtk.Adjustment(500, 100, 5000, 10, 100, 0)),
#			},{
#				"label": "Z feedrate",
#				"control": gtk.SpinButton(gtk.Adjustment(500, 0, 1000, 10, 100, 0)),
#			},{
#				"label": "Z print height",
#				"control": gtk.SpinButton(gtk.Adjustment(0, 0, 110, 1, 10, 0)),
#			},{
#				"label": "Z finish height",
#				"control": gtk.SpinButton(gtk.Adjustment(0, 0, 110, 1, 10, 0)),
			}
		]
		
		for i,c in enumerate(controls):
			setupPage.attach(gtk.Label(c['label']), 0, 1, i, i+1)
			setupPage.attach(c['control'], 1, 2, i, i+1)
			c['control'].set_value(self.getFloatOption(c['id']))
			c['control'].connect('value-changed', self.optionChanged, c)
			
		
		'''
			Add tabs
		'''
		self.notebook = gtk.Notebook()

		self.notebook.append_page(basicControlsPage, gtk.Label("Controls"))
		self.notebook.append_page(serialControlsPage, gtk.Label("Port options"))
		self.notebook.append_page(setupPage, gtk.Label("Setup"))
		self.window.add(self.notebook)
		
		'''
			Display
		'''
		
		#self.serialOptions.show_all()
		self.connectButton.show()
		self.window.show_all()
		
		'''
			Auto-connect
		'''
		for i, p in enumerate(self.ports):
			self.portSelector.set_active(i)
			try:
				self.connect()
				break
			except:
				pass
		
		gtk.main()
		
	def generateBuffer(self):
		self.context = GCodeContext(
			self.getFloatOption('xyFeedrate'),
			self.getFloatOption('zFeedrate'),
			self.getFloatOption('startDelay'), self.getFloatOption('stopDelay'),
			self.getFloatOption('penUpAngle'), self.getFloatOption('penDownAngle'),
			self.getFloatOption('zHeight'), self.getFloatOption('finishedHeight'),
			self.getFloatOption('xHome'), self.getFloatOption('yHome'),
			self.getBooleanOption('registerPen'),
			self.getIntOption('numCopies'),
			self.getBooleanOption('continuous'),
			self.svg_file
		)
		parser = SvgParser(self.document.getroot(), self.getBooleanOption('pauseOnLayerChange'))
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
		
	def optionChanged(self, widget, data=None):
		if isinstance(data['control'], gtk.ComboBox):
			self.setOption(data['id'], data['control'].get_active_text())
		else:
			self.setOption(data['id'], data['control'].get_value())
			self.showError("%s = %s" % (data['id'], data['control'].get_value()))
			
	def destroy(self, widget, data=None):
		gtk.main_quit()

	def toggleConnect(self, widget, data=None):
		if self.serial is None:
			try:
				self.saveOptions()
				self.connect()
				self.connectButton.set_label("Disconnect")
				self.controls.show_all()
				self.notebook.set_current_page(0)
			except Exception as exc:
				self.showError(exc)
		else:
			self.disconnect()
			self.connectButton.set_label("Connect")
			self.controls.hide()
		
	def connect(self):
		try:
			self.serial = serial.Serial()
			self.serial.port = self.getOption('serialPort')
			self.serial.baudrate = self.getFloatOption('serialBaudRate')
			self.serial.timeout = 10

			if self.getOption('flowControl') == 'XON/XOFF':
				self.serial.xonxoff = True
			if self.getOption('flowControl') == 'RTS/CTS' or self.getOption('flowControl') == 'DSR/DTR + RTS/CTS':
				self.serial.rtscts = True
			if self.getOption('flowControl') == 'DSR/DTR + RTS/CTS':
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
		msg = str(msg)
			
		message = gtk.MessageDialog(type=gtk.MESSAGE_ERROR, buttons=gtk.BUTTONS_CLOSE, message_format="Error: %s" % msg)
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
			self.send("G1 X%0.2F Y%0.2F F%0.2F" % (self.pos[0], self.pos[1], self.getFloatOption('xyFeedrate')))
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
#	if len(ports) == 0:
#		inkex.errormsg("No serial ports found :(")
#		inkex.errormsg("Please connect your device and try again")
#	else:
	e = MyEffect()
	e.affect()		

	
