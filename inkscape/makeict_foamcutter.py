#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
import getopt
import gtk
import ConfigParser
import gobject
import threading

from math import *

from makeict_foamcutter.context import GCodeContext
from makeict_foamcutter.svg_parser import SvgParser

import makeict_foamcutter

try:
	import serial
except ImportError, e:
	inkex.errormsg(_("pySerial is not installed."
		+ "\n\n1. Download pySerial here (not the \".exe\"!): http://pypi.python.org/pypi/pyserial"
		+ "\n2. Extract the \"serial\" subfolder from the zip to the following folder: C:\\[Program files]\\inkscape\\python\\Lib\\"
		+ "\n3. Restart Inkscape."
	))
	exit()

class MyEffect(inkex.Effect):
	def __init__(self, ports):
		inkex.Effect.__init__(self)

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
			'curveFlatness': '0.2',
			
		})
		self.config.read(self.configFile)
		self.preset = "Foam Cutter Defaults"
		try:
			self.config.add_section(self.preset)
		except: pass
		
		self.serial = None
		self.pos = [0, 0]
		
		self.ports = ports
		self.backgroundColors = {}
		self.paused = False
		self.stopped = False
		
		self.allControls = []
		
	'''
		Dealing with options
	'''
	def getOption(self, option):
		return self.config.get(self.preset, option)
											
	def getFloatOption(self, option):
		return float(self.getOption(option))
											
	def getIntOption(self, option):
		return int(self.getOption(option))
		self.backgroundColors = {}
											
	def getBooleanOption(self, option):
		return self.getOption(option) in ['True', 'true', '1', 'Yes', 'yes', 'T', 't', 'Y', 'y']
											
	def setOption(self, option, value):
		return self.config.set(self.preset, option, str(value))
		
	def saveOptions(self):
		for controlInfo in self.allControls:
			if isinstance(controlInfo['control'], gtk.ComboBox):
				self.setOption(controlInfo['id'], controlInfo['control'].get_active_text())
			else:
				self.setOption(controlInfo['id'], controlInfo['control'].get_value())
		
		f = open(self.configFile, 'w')
		self.config.write(f)
		f.close()
		
	def optionChanged(self, widget, data=None):		
		# saveOptions will update values from ALL controls, every time. Seems silly, but some updates are being lost
		self.saveOptions()
			
	'''
		Build and display GUI
	'''
	def effect(self):
		gobject.threads_init() 
		self.buildMainGUI()
		
		self.autoConnectDialog = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.connectLabel = gtk.Label("Trying to connect to device...")
		self.connectLabel.set_padding(50, 50)
		self.connectLabel.set_justify(gtk.JUSTIFY_CENTER)
		self.autoConnectDialog.add(self.connectLabel)
		self.autoConnectDialog.set_position(gtk.WIN_POS_CENTER)
		self.autoConnectDialog.show_all()
		self.pauseAndStopButtons.hide_all()
		threading.Thread(target=self.autoConnect).start()
		gtk.main()
		
	def _updateConnectLabel(self):
		self.connectLabel.set_markup("<b>Attempting to connect...</b>\n\n%s\n%s bps" % (self.getOption('serialPort'), self.getOption('serialBaudRate')))

	'''
		Auto-connect
	'''
	def autoConnect(self):
		for i, p in enumerate(self.ports):
			self.portSelector.set_active(i)
			gobject.idle_add(self._updateConnectLabel)
			try:
				self.connect(2.5)
				self.connectButton.set_label("Disconnect")
				self.controls.show_all()
				self.pauseAndStopButtons.hide_all()
				break
			except Exception as exc:
				pass

		self.autoConnectDialog.hide()
		if self.serial is None or self.serial == None:
			gobject.idle_add(self.controls.hide)
			gobject.idle_add(self.notebook.set_current_page, 2)
			gobject.idle_add(self.showError, "Auto-connect failed. Is the device connected and enabled?")
		
		self.window.set_position(gtk.WIN_POS_CENTER)
		self.window.show_all()
		self.pauseAndStopButtons.hide_all()

	def buildMainGUI(self):
		self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
		self.window.set_default_size(640, 640)
		self.window.connect("destroy", self.destroy)
		self.window.set_border_width(10)
		
		self.notebook = gtk.Notebook()
		self.notebook.append_page(self._buildControlsPage(), gtk.Label("Controls"))
		self.notebook.append_page(self._buildPlotterSetupPage(), gtk.Label("Setup"))
		self.notebook.append_page(self._buildSerialControlsPage(), gtk.Label("Port options"))
		self.notebook.append_page(self._buildGCodeLogPage(), gtk.Label("GCode Tools"))
		self.notebook.append_page(self._buildAboutPage(), gtk.Label("About"))
		self.window.add(self.notebook)

	'''
		Basic Controls Page
	'''
	def _buildControlsPage(self):		
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

		self.homeButtons = gtk.Frame()
		box = gtk.HBox(True)
		self.setHomeButton = gtk.Button("Set Home")
		self.setHomeButton.connect("clicked", self.setHome, None)
		box.add(self.setHomeButton)
		
		self.goHomeButton = gtk.Button("Go Home")
		self.goHomeButton.connect("clicked", self.goHome, None)
		box.add(self.goHomeButton)
		
		self.homeButtons.add(box)
		
		#self.controls.add(self.homeButtons)
		self.controls.pack_start(self.homeButtons, False, False)
		
		sendButtons = gtk.HBox(True)
#		b = gtk.Button("▶ Selection")
#		b.connect("clicked", self.sendSelection, None)
#		sendButtons.add(b)
		
		self.sendDrawingButton = gtk.Button("▶ Send drawing")
		self.sendDrawingButton.connect("clicked", self.sendAll, None)
		sendButtons.add(self.sendDrawingButton)
		
		self.controls.pack_start(sendButtons, False, False)
		
		self.progressBar = gtk.ProgressBar()
		self.progressBar.set_text(" ")
#		self.controls.add(self.progressBar)
		self.controls.pack_start(self.progressBar, False, False)

		basicControlsPage.add(self.controls)
		
		self.pauseAndStopButtons = gtk.HBox(True)
		self.pauseButton = gtk.Button("▌▌ Pause")
		self.pauseButton.connect("clicked", self.togglePause, None)
		self.pauseAndStopButtons.add(self.pauseButton)
		self.stopButton = gtk.Button("■ Stop")
		self.stopButton.connect("clicked", self.stop, None)
		self.pauseAndStopButtons.add(self.stopButton)
		basicControlsPage.add(self.pauseAndStopButtons)

		#self.stopButton.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#f00'))
		self.pauseButton.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#440'))
		self.pauseButton.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse('#440'))
		
		self.stopButton.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#f00'))
		self.stopButton.modify_bg(gtk.STATE_PRELIGHT, gtk.gdk.color_parse('#f00'))

		
		return basicControlsPage

	'''
		Serial controls
	'''
	def _buildSerialControlsPage(self):
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
			c['control'].connect('focus-out-event', self.optionChanged, c)
			#c['control'].connect('value-changed', self.optionChanged, c)
			
		self.allControls.extend(controls)

		serialControlsPage.pack_start(serialOptions, False, False)
		
		self.connectButton = gtk.Button("Connect")
		self.connectButton.connect("clicked", self.toggleConnect)
		serialControlsPage.pack_start(self.connectButton, False, False)
		
		return serialControlsPage
		
	'''
		Plotter Setup
	'''
	def _buildPlotterSetupPage(self):
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
			},{
				"label": "Curve flatness",
				"id": "curveFlatness",
				"control": gtk.SpinButton(gtk.Adjustment(0.2, .01, 10.0, 0.01, .1, 0), digits=2),
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
			
		self.allControls.extend(controls)
		
		return setupPage

	'''
		GCode Log
	'''
	def _buildGCodeLogPage(self):
		gcodeLogPage = gtk.VBox(False, 10)
		
		
		buttons = gtk.Table(1, 2, True)

		button = gtk.Button("Clear")
		button.connect("clicked", self.clearGCodeLog, None)
		buttons.attach(button, 0, 1, 0, 1)
				
		button = gtk.Button("Insert drawing")
		button.connect("clicked", self.addDocumentToGCodeLog, None)
		buttons.attach(button, 1, 2, 0, 1)
				
		gcodeLogPage.pack_start(buttons, False, False)
		
		self.gcodeLog = gtk.TextView()
		scroll = gtk.ScrolledWindow()
		scroll.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
		scroll.add(self.gcodeLog)
		gcodeLogPage.add(scroll)

		b = gtk.Button("▶ Send GCode")
		b.connect("clicked", self.sendGCode, None)
		gcodeLogPage.pack_start(b, False, False)
		
		return gcodeLogPage
		
	'''
		About Page
	'''
	def _buildAboutPage(self):
		text = 'Software by:\n\n'
		text = text + '  • Dominic Canare &lt;<a href="mailto:dom@makeict.org">dom@makeict.org</a>&gt;\n'
		text = text + '  • Tom McGuire &lt;<a href="atomicwire@gmail.com">atomicwire@gmail.com</a>&gt;\n'
		text = text + '\n<a href="http://github.com/makeict/inkscape-foamcutter">github.com/makeict/inkscape-foamcutter</a>\n'

		label = gtk.Label()
		label.set_markup(text)
		label.set_line_wrap(True)

		return label

	def togglePause(self, widget=None, data=None):
		self.paused = not self.paused
		if self.paused:
			self.pauseButton.set_label("▶ Resume")
		else:
			self.pauseButton.set_label("▌▌ Pause")

	def stop(self, widget=None, data=None):
		self.stopped = True

	def clearGCodeLog(self, widget=None, data=None):
		self.gcodeLog.get_buffer().set_text("")
		
	def addDocumentToGCodeLog(self, widget=None, data=None):
		code = "\n".join(self.generateBuffer())
		self.gcodeLog.get_buffer().insert_at_cursor(code)
		
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
		
	def dehighlight(self, widget, color="#000"):
		if widget in self.backgroundColors:
			self.highlight(widget, self.backgroundColors[widget])
		else:
			self.highlight(widget, color)

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
		
		makeict_foamcutter.svg_parser.curveFlatness = self.getFloatOption('curveFlatness')
		
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
		ok = self.serial.read(2).decode("ascii")
		if ok != "ok":
			raise Exception("Invalid response: '%s'" % ok)
		
	def destroy(self, widget, data=None):
		gtk.main_quit()

	def toggleConnect(self, widget, data=None):
		if self.serial is None:
			try:
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
		
	def connect(self, timeout=10):
		try:
			self.serial = serial.Serial()
			self.serial.port = self.getOption('serialPort')
			self.serial.baudrate = self.getFloatOption('serialBaudRate')
			self.serial.timeout = timeout

			if self.getOption('flowControl') == 'XON/XOFF':
				self.serial.xonxoff = True
			if self.getOption('flowControl') == 'RTS/CTS' or self.getOption('flowControl') == 'DSR/DTR + RTS/CTS':
				self.serial.rtscts = True
			if self.getOption('flowControl') == 'DSR/DTR + RTS/CTS':
				self.serial.dsrdtr = True
			
			self.serial.open()
			initString = self.serial.read(19).decode("ascii")
			if initString != "MakeICT Foam Cutter":
				s = "Invalid init string: '%s'" % initString
				raise Exception(s)

			self.serial.timeout = None

			self.send("G21 (metric ftw)")
			self.send("G90 (absolute mode)")
			self.send("G92 X%0.2f Y%0.2f" % (self.pos[0], self.pos[1]))
				
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
		
	def setHome(self, widget=None, data=None):
		try:
			self.pos = [0, 0]
			self.send("G92 X0.0 Y0.0")
			self.updatePosition()
		except Exception as exc:
			self.showError(exc)
			
	def goHome(self, widget=None, data=None):
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

	def sendAll(self, widget=None, data=None):
		self.stopped = False
		self.paused = False
		self.disableControls()
		self.progressBar.set_fraction(0.0)
		data = self.generateBuffer()
		t = threading.Thread(target=self._sendLines, args=[data])
		t.start()
		
	def sendGCode(self, widget=None, data=None):
		self.disableControls()
		self.progressBar.set_fraction(0.0)
		self.notebook.set_current_page(0)
		
		b = self.gcodeLog.get_buffer()
		data = b.get_text(*b.get_bounds()).split("\n")
		t = threading.Thread(target=self._sendLines, args=[data])
		t.start()

	def _sendLines(self, data):
		try:
			for count,line in enumerate(data):
				gobject.idle_add(self._updateProgressBar, float(count)/len(data))
				if line != "" and line[0] != "(":
					while self.paused and not self.stopped:
						time.sleep(0.25)
						
					if self.stopped:
						self.send("M5")
						self.highlight(self.homeButtons)
						break
					self.send(line)
			if not self.stopped:
				gobject.idle_add(self._updateProgressBar, 1.0)
				self.highlight(self.homeButtons)
				self.dehighlight(self.homeButtons)
		except Exception as exc:
			gobject.idle_add(self.showError, exc)
		finally:
			gobject.idle_add(self.enableControls)

	def _updateProgressBar(self, fraction):
		self.progressBar.set_text("%d%%" % int(fraction*100))
		self.progressBar.set_fraction(fraction)
		
	def disableControls(self):
		self.controls.set_sensitive(False)
		self.pauseButton.set_label("▌▌ Pause")
		self.pauseAndStopButtons.show_all()
		
	def enableControls(self):
		self.controls.set_sensitive(True)
		self.pauseAndStopButtons.hide_all()

		
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

	return ports

if __name__ == '__main__':   #pragma: no cover
	#	@TODO: explore text to path. ('inkscape --verb EditSelectAllInAllLayers --verb ObjectToPath --verb FileSave --verb FileQuit %s' % sys.argv[1])
	ports = get_serial_ports()
	if len(ports) == 0:
		inkex.errormsg("No serial ports found :(")
		inkex.errormsg("Please connect your device and try again")
	else:
		e = MyEffect(ports)
		e.affect()		
