MakerBot Unicorn G-Code *Serial Export* for Inkscape
===========================================

This is an Inkscape extension that allows you to export your Inkscape drawings as
G-Code through a serial port.

Author: [Marty McGuire](http://github.com/martymcguire), with modifications for serial output by [Dominic Canare](http://github.com/domstyle)

Original project website: [http://github.com/martymcguire/inkscape-unicorn](http://github.com/martymcguire/inkscape-unicorn)

Credits
=======

* Marty McGuire pulled this all together into an Inkscape extension.
* [Inkscape](http://www.inkscape.org/) is an awesome open source vector graphics app.
* [Scribbles](https://github.com/makerbot/Makerbot/tree/master/Unicorn/Scribbles%20Scripts) is the original DXF-to-Unicorn Python script.
* [The Egg-Bot Driver for Inkscape](http://code.google.com/p/eggbotcode/) provided inspiration and good examples for working with Inkscape's extensions API.
* Dominic Canare for adding serial code to Marty's original extension
* Tom McGuire for sharing his vast knowledge of G-Code and CNC.

Install
=======

Copy the contents of `src/` to your Inkscape `extensions/` folder.
You will also need pyserial installed to `inkscape/python/Lib` folder.

Typical locations include:

* OS X - `/Applications/Inkscape.app/Contents/Resources/extensions`
* Linux - `/usr/share/inkscape/extensions`
* Windows - `C:\Program Files\Inkscape\share\extensions`

Usage
=====

* Size and locate your image appropriately:
	* It looks like only **px** are supported as the units presently
* Convert all text to paths:
	* Select all text objects.
	* Choose **Path | Object to Path**.
* Export to serial
	* **Extensions | Export | MakerBot Unicorn G-Code **.

