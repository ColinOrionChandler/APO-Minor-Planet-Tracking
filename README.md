# APO Minor Planet Tracking

A tool for generating a Telescope Control Software (TCS) command to track a specified minor planet.

This program is specifically designed for the Apache Point Observatory (APO) 3.5-meter Astrophysical Research Consortium (ARC) Telescope User Interface (TUI). APO website: https://www.apo.nmsu.edu/

The input name should be a minor planet name that is queryable via JPL Horizons: https://ssd.jpl.nasa.gov/horizons

Example:

python apo_minor_planet_tracking.py "Chandler"

This will provide a command that (1) slews the telescope to asteroid "Chandler," (2) starts tracking at asteroid Chandler's rate of motion on the sky (so stars are trailed, not the asteroid), and (3) sets the FITS header to have the name "Chandler" in it. The output will look something like this:

tcc track 270.168133497, -22.53122276, 2.8419421296296294e-07, -7.75733024691358e-08 Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="Chandler"


Tips:

Paste the command into the window that appears when activating "Run_Commands" from the "Scripts" menu.

- Apply any desired offsets using TUI after the slew is done. (Do not add offsets via this Python program.)

- Guide as normal. The telescope understands you are tracking the object, not the star, and adjusts accordingly.

- For nearby objects, it may be necessary to re-run this program to get updated rates, even if you manually offset the telescope to keep the object in the field of view (FOV).