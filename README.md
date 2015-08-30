MakeICT Foam Cutter Serial Export tool for Inkscape
===================================================

This is an Inkscape extension that allows you to export your Inkscape drawings as G-Code through a serial port.

This project is a modified version of [http://github.com/martymcguire/inkscape-unicorn](http://github.com/martymcguire/inkscape-unicorn)

Installation
============

Inkscape
--------
Copy the contents of `inkscape/` to your Inkscape `extensions/` folder.
Typical locations include:

* Linux - `/usr/share/inkscape/extensions`
* Windows - `C:\Program Files\Inkscape\share\extensions`
* OS X - `/Applications/Inkscape.app/Contents/Resources/extensions`

You will also need pyserial installed to `inkscape/python/Lib` folder.

Arduino
-------
Upload the Arduino code from the `arduino/` folder. We highly recommend using [Ino Tool](http://inotool.org)

Usage
=====

* Size and locate your image appropriately:
	* It looks like only **px** are supported as the units presently
* Convert all text to paths:
	* Select all text objects.
	* Path > Object to Path.
* Export to serial
	* Extensions > Export > MakeICT Foam Cutter Sender.

Credits
=======

* Marty McGuire pulled this all together into an Inkscape extension.
* [Inkscape](http://www.inkscape.org/) is an awesome open source vector graphics app.
* [Scribbles](https://github.com/makerbot/Makerbot/tree/master/Unicorn/Scribbles%20Scripts) is the original DXF-to-Unicorn Python script.
* [The Egg-Bot Driver for Inkscape](http://code.google.com/p/eggbotcode/) provided inspiration and good examples for working with Inkscape's extensions API.
* Dominic Canare for adding serial code to Marty's original extension
* Tom McGuire for sharing his vast knowledge of G-Code and CNC.

