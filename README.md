# APO Minor Planet Tracking

A simple tool for generating a Telescope Control Console (TCC) command to track a specified minor planet (e.g., asteroids, comets). Written by Colin Orion Chandler (University of Washington, LINCC Frameworks, DiRAC Institute, Northern Arizona University) and most frequently used for follow-up observations of cometary objects identified by the NASA Partner program "Active Asteroids" (http://activeasteroids.net), a Citizen Science program he founded in 2021.

This program is specifically designed for the Apache Point Observatory (APO) 3.5-meter Astrophysical Research Consortium (ARC) Telescope User Interface (TUI). APO website: https://www.apo.nmsu.edu/

The input name should be a minor planet name that is queryable via JPL Horizons: https://ssd.jpl.nasa.gov/horizons

Example:

python apo_minor_planet_tracking.py "Chandler"

This will provide a command that (1) slews the telescope to asteroid "Chandler," (2) starts tracking at asteroid Chandler's rate of motion on the sky (so stars are trailed, not the asteroid), and (3) sets the FITS header to have the name "Chandler" in it. The command, which is in the form of a single-line of text, will look something like this:

tcc track 270.168133497, -22.53122276, 2.8419421296296294e-07, -7.75733024691358e-08 Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="Chandler"


Tips:

- Paste the command into the window that appears when activating "Run_Commands" from the "Scripts" menu.

- Apply any desired offsets using TUI after the slew is done. (Do not add offsets via this Python program.)

- Guide as normal. The telescope understands you are tracking the object, not the star, and adjusts accordingly.

- For nearby objects, it may be necessary to re-run this program to get updated rates, even if you manually offset the telescope to keep the object in the field of view (FOV).

- Some objects for JPL Horizons have multiple matching names. For example, Didymos has multiple entries (as of 2024 April 2), so typing "Didymos (primary body)" will let the program run.


Disclaimer:

- You should do a reality check before executing any tcc command.

- The program author makes no warranty, implied or otherise.


How to acknowledge use:

- If you use this code, please add the following text: "This research used APO Minor Planet Tracking by Colin Orion Chandler."

- Please also cite Giorgini 1996 for JPL Horizons, and astropy as appropriate.


Acknowledgements:

- Many thanks to APO operators, especially Candace and Russett.

- Thank you Will Oldroyd (Northern Arizona University) for testing this program.
