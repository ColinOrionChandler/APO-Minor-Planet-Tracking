#!/usr/bin/env python3

def makeAPOtrackingCommand(objname, RA, DEC, dRA, dDEC, offsets_arcmin, verbose=False):
	'''
	For APO TUI. 12/12/2023 COC
	Note: do not bother with offset_arcmin here (see instructions below) 1/13/2024 COC
	
	example tracking line:
		tcc track 45.43530667, 34.59037667, -0.000001208371914, -0.000002105362654 Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="426P"

	Instructions (for standalone, non-JPL case):
		1. Generate ephemeris in decimal degree mode
		2. Supply object name, RA, Dec, etc. to funtion, such as
			makeAPOtrackingCommand(objname='2015 FW412', RA=171.71866, DEC=-11.84938, dRA=7.870796, dDEC=-10.8067, offsets_arcmin=0)
		   You should get a result similar to this:
			  tcc track 171.71866, -11.84938, 6.073145061728395e-07, -8.338503086419753e-07 Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="2015 FW412"
		3. Paste the whole tcc track line into Scripts menu:Run_Commands in TUI
		4. Click "Start" and the telescope will start slewing. Meanwhile...
		5. Offset:
			a. Open Offsets in the TCC menu of TUI
			b. Choose "Object Arc" and "Abs" (absolute offset)
			c. Click "Offset" once the slew is over
		6. Don't forget guiding!
		8. Don't use "slew" in TCS or it will override what we just did.
	'''
	convfactor = 12960000
#	newRA = RA + 2*(1/60)
#	newDEC = DEC + 2*(1/60)
	# trying without offset, do the offset at the telescope
	newRA = RA
	newDEC = DEC
	s = f'tcc track {newRA}, {newDEC}, {dRA/convfactor}, {dDEC/convfactor} Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="{objname}"'
	if verbose: print(s)
	return(s)

# Example: 
#makeAPOtrackingCommand(objname='Chandler', RA=244.27359, DEC=-19.91599, dRA=55.68869, dDEC=-10.3602, offsets_arcmin=0, verbose=True) # 1/13/2024 COC "Chandler"


def getCommandViaJPL(objname, site_code='705', ut=None, timedelta_s=30, verbose=False):
	"""
	Function to generate the tracking command for APO based on current datetime and a specififed object name.
	4/22/2024 COC
	"""
	from astroquery.jplhorizons import Horizons
	import datetime
	if ut == None:
		dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=timedelta_s)
		ut = f'{dt.year}-{str(dt.month).zfill(2)}-{str(dt.day).zfill(2)} {str(dt.hour).zfill(2)}:{str(dt.minute).zfill(2)}:{str(dt.second).zfill(2)}'
		del dt
	if verbose:
		print(f'Running JPL query for {objname}, site_code={site_code}, ut={ut}, timedelta_s={timedelta_s} now...')
	#
	jpl_query = Horizons( id=objname,
					location=site_code,
					epochs={ut} # epochs={'start':'2010-01-01', 'stop':'2010-03-01','step':'10d'}
				)
	eph = jpl_query.ephemerides(extra_precision=True)
#	print(eph)
#	print(eph.columns)
	#
	r = makeAPOtrackingCommand(	objname			= objname, 
								RA				= eph['RA'][0], 
								DEC				= eph['DEC'][0], 
								dRA				= eph['RA_rate'][0], 
								dDEC			= eph['DEC_rate'][0],
								offsets_arcmin	= 0
							)
	return r


# Uncomment the following two lines and run here if that's more convenient
# get_command(objname='2000 GM137')
# exit()


if __name__ == '__main__':
	import argparse # This is to enable command line arguments.
	parser = argparse.ArgumentParser(description='Get APO telescope command for tracking an object. By Colin Orion Chandler (COC), 2024-04-22.')
	parser.add_argument('objects', nargs='+', help="Minor planets to query.")
	parser.add_argument('--site-code', dest='site_code', type=str, default='705', help='observatory site code (default is 705)')
	parser.add_argument('--ut', dest='ut', type=str, default=None, help=f'UT of format YYYY-MM-DD hh:mm:ss (default is now)')
	parser.add_argument('--timedelta', dest='time_delta', type=int, default=30, help=f'How many seconds after the UT to calculate. Used to make ephemeris more current (e.g., it takes time to query JPL, or you are planning for some time in the near future).')
	parser.add_argument('--verbose', dest='verbose', type=bool, default=False, help=f'say "--verbose True" to see more messages.')
	args = parser.parse_args()
	for objname in args.objects:
		command = getCommandViaJPL(objname=objname, site_code=args.site_code, ut=args.ut, timedelta_s=args.time_delta, verbose=args.verbose)
		print(command)
		