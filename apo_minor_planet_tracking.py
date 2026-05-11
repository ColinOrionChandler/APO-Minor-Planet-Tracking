#!/usr/bin/env python3

"""Generate APO TCC tracking commands for moving solar-system targets.

The main command path queries JPL Horizons, converts the returned ephemeris into
the rate convention expected by the APO Telescope Control Console (TCC), and
prints the human-checkable observing context before returning the one-line
``tcc track`` command.  The MPC provider is kept as a fallback when Horizons is
unavailable or when an object is easier to query through the Minor Planet Center.
"""

import datetime
from typing import Optional, Union

from astroquery.jplhorizons import Horizons
from astroquery.mpc import MPC
from astropy.time import Time
from astropy.coordinates import SkyCoord
from astropy.table import QTable
from astropy import units as u
import numpy as np


# APO TCC wants rates in degrees per second; ephemeris providers report the
# components in arcsec per hour.  3600 arcsec/degree * 3600 seconds/hour gives
# the conversion factor for arcsec/hour -> degrees/second.
APO_TCC_RATE_CONVERSION = 12960000.0

# Horizons has changed/varied uncertainty column names across output modes.  Try
# the most common RA/Dec pairs in priority order and report the first usable one.
JPL_UNCERTAINTY_COLUMNS = (
	('RA_3sigma', 'DEC_3sigma', '3-sigma'),
	('RA_3sig', 'DEC_3sig', '3-sigma'),
	('RA_sigma', 'DEC_sigma', '1-sigma'),
	('RA_sig', 'DEC_sig', '1-sigma'),
	('RA_1sigma', 'DEC_1sigma', '1-sigma'),
)


def _coerce_utc_string(ut: Optional[Union[str, datetime.datetime]], timedelta_s: int = 0) -> str:
	"""Return a UTC timestamp string accepted by Horizons and MPC queries."""
	if ut is None:
		dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=timedelta_s)
	elif isinstance(ut, datetime.datetime):
		dt = ut
		if dt.tzinfo is None:
			dt = dt.replace(tzinfo=datetime.timezone.utc)
		else:
			dt = dt.astimezone(datetime.timezone.utc)
	else:
		dt = Time(ut).to_datetime(timezone=datetime.timezone.utc)

	return dt.strftime('%Y-%m-%d %H:%M:%S')


def _ephemeris_value_to_arcsec(value):
	"""Convert a scalar ephemeris uncertainty to arcseconds, or ``None`` if unusable."""
	try:
		if np.ma.is_masked(value):
			return None
	except Exception:
		pass

	try:
		if hasattr(value, 'mask') and np.any(value.mask):
			return None
	except Exception:
		pass

	try:
		if hasattr(value, 'to'):
			return float(value.to(u.arcsec).value)
	except Exception:
		pass

	try:
		return float(value)
	except Exception:
		return None


def _extract_jpl_position_uncertainty(eph):
	"""Return the first finite JPL RA/Dec uncertainty pair in arcseconds."""
	for ra_col, dec_col, label in JPL_UNCERTAINTY_COLUMNS:
		if ra_col not in eph.colnames or dec_col not in eph.colnames:
			continue

		ra_arcsec = _ephemeris_value_to_arcsec(eph[ra_col][0])
		dec_arcsec = _ephemeris_value_to_arcsec(eph[dec_col][0])
		if ra_arcsec is None or dec_arcsec is None:
			continue
		if not (np.isfinite(ra_arcsec) and np.isfinite(dec_arcsec)):
			continue

		return {
			'label': label,
			'ra_arcsec': ra_arcsec,
			'dec_arcsec': dec_arcsec,
		}

	return None


def makeAPOtrackingCommand(objname, RA, DEC, dRA, dDEC, offsets_arcmin, verbose=False):
	'''
	Build the single-line ``tcc track`` command consumed by the APO TUI.

	``dRA`` and ``dDEC`` are expected in arcsec/hour.  Offsets are intentionally
	not folded into the command; observers should apply object-arc offsets in TUI
	after the slew completes.
	
	example tracking line:
		tcc track 45.43530667, 34.59037667, -0.000001208371914, -0.000002105362654 Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="426P"

	Instructions (for standalone, non-JPL case):
		1. Generate ephemeris in decimal degree mode
		2. Supply object name, RA, Dec, etc. to function, such as
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
		7. Don't use "slew" in TCS or it will override what we just did.
	'''
	newRA = RA
	newDEC = DEC
	s = f'tcc track {newRA}, {newDEC}, {dRA/APO_TCC_RATE_CONVERSION}, {dDEC/APO_TCC_RATE_CONVERSION} Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="{objname}"'
	if verbose: print(s)
	return(s)

# Example: 
#makeAPOtrackingCommand(objname='Chandler', RA=244.27359, DEC=-19.91599, dRA=55.68869, dDEC=-10.3602, offsets_arcmin=0, verbose=True) # 1/13/2024 COC "Chandler"


def calculate_motion_components(ephemeris: QTable):
	"""
	Calculate RA and Dec rates from Proper Motion and Direction.

	Parameters:
	- ephemeris (QTable): The ephemeris table returned by `MPC.get_ephemeris`.

	Returns:
	- QTable: The input ephemeris table with additional columns for RA Rate and Dec Rate.
	"""
	if "Proper motion" not in ephemeris.colnames or "Direction" not in ephemeris.colnames:
		raise ValueError("The ephemeris table must contain 'Proper motion' and 'Direction' columns.")
		
	# Extract proper motion and direction
	proper_motion = ephemeris["Proper motion"]  # Total motion in arcseconds per hour
	direction = np.radians(ephemeris["Direction"])  # Convert direction from degrees to radians
	
	# Calculate RA and Dec rates
	ra_rate = proper_motion * np.sin(direction)  # RA Rate (arcsec/hour)
	dec_rate = proper_motion * np.cos(direction)  # Dec Rate (arcsec/hour)
	
	# Add rates to the ephemeris table
	ephemeris["RA Rate"] = ra_rate
	ephemeris["Dec Rate"] = dec_rate
	
	return ephemeris

def get_mpc_ephemeris(object_name: str, site_code: str = '705', ut: Optional[Union[str, datetime.datetime]] = None) -> QTable:
	"""
	Retrieve ephemeris data for a specified object from the Minor Planet Center.

	Parameters:
	- object_name (str): Name or designation of the minor planet or comet.
	- site_code (str): Observatory code (default is '705').
	- ut (str or datetime.datetime, optional): UTC date/time in ISO format (YYYY-MM-DDTHH:MM:SS) or a datetime object.
		Defaults to the current UTC time.

	Returns:
	- QTable: Ephemeris data table.
	"""
	# Determine the start time
	if ut is None:
		start_time = Time.now()
	elif isinstance(ut, str):
		start_time = Time(ut)
	elif isinstance(ut, datetime.datetime):
		start_time = Time(ut)
	else:
		raise ValueError("The 'ut' parameter must be a string, datetime object, or None.")
		
	# Retrieve ephemeris data
	ephemeris = MPC.get_ephemeris(
		target=object_name,
		location=site_code,
		start=start_time.iso,
		step='1d',
		number=1
	)
	
	ephemeris = calculate_motion_components(ephemeris=ephemeris) # add rates in our normal RA, Dec components and rates. 12/21/2024 COC
	
	return ephemeris


def make_tcc_command(objname, site_code='705', ut=None, timedelta_s=30, verbose=False, limits={'min_elev':10, 'max_elev':85}, provider='JPL', half_rate=False, seeing=1):
	"""
	Query an ephemeris provider and produce the APO TCC command for one object.

	The printed pre-command diagnostics are intended for the observer's final
	reality check: RA/Dec in sexagesimal form, sky-motion components, brightness
	or geometry when available, elevation, exposure-time guidance, and JPL
	positional uncertainty when Horizons returns a usable uncertainty column.

	Args:
		objname: JPL Horizons/MPC object name or designation.
		site_code: Observatory code; APO is MPC site 705.
		ut: UTC timestamp string or datetime.  If omitted, query now plus
			``timedelta_s`` seconds so the generated rates are current by the time
			the command is pasted into TUI.
		timedelta_s: Offset in seconds used only when ``ut`` is omitted.
		limits: Optional elevation guardrails.  Use ``None`` or ``{}`` to disable.
		provider: ``JPL`` for Horizons or ``MPC`` for Minor Planet Center.
		half_rate: Divide both tracking rates by two for half-rate tracking.
		seeing: Seeing in arcseconds for the max-exposure estimate.
	"""
	ut = _coerce_utc_string(ut, timedelta_s=timedelta_s)
	provider_name = provider.upper()
	if verbose:
		print(f'Running query for {objname}, site_code={site_code}, ut={ut} UTC, timedelta_s={timedelta_s} now...')
	#
	d = {} # results go here
	if provider_name == 'JPL':
		ut_time = Time(ut)
		jpl_query = Horizons(
					id=objname,
					location=site_code,
					epochs=ut_time.jd  # single user-supplied epoch in JD
				)
		eph = jpl_query.ephemerides(extra_precision=True)
		d['elevation'] = eph['EL'][0]
		d['RA'] = eph['RA'][0]
		d['DEC'] = eph['DEC'][0]
		d['RA rate'] = eph['RA_rate'][0]
		d['Dec rate'] = eph['DEC_rate'][0]
		pos_unc = _extract_jpl_position_uncertainty(eph)
		d['pos_unc_label'] = pos_unc['label'] if pos_unc else None
		d['pos_unc_ra_as'] = pos_unc['ra_arcsec'] if pos_unc else None
		d['pos_unc_dec_as'] = pos_unc['dec_arcsec'] if pos_unc else None
		# Brightness (JPL)
		if 'V' in eph.colnames:
			d['mag'] = eph['V'][0]
			d['mag_label'] = 'V mag'
		elif 'Tmag' in eph.colnames:
			d['mag'] = eph['Tmag'][0]
			d['mag_label'] = 'Total mag'
		else:
			d['mag'] = None
			d['mag_label'] = 'Magnitude'
		# True anomaly (JPL, degrees)
		if 'true_anom' in eph.colnames:
			d['true_anom'] = eph['true_anom'][0]
		elif 'TA' in eph.colnames:  # legacy/alternate name fallback
			d['true_anom'] = eph['TA'][0]
		else:
			d['true_anom'] = None
	#
	if provider_name == 'MPC':
		mpc_ephem = get_mpc_ephemeris(object_name=objname, site_code=site_code, ut=ut)
		d['elevation'] = mpc_ephem['Altitude'][0]
		d['RA'] = mpc_ephem['RA'][0]
		d['DEC'] = mpc_ephem['Dec'][0]
		d['RA rate'] = mpc_ephem['RA Rate'][0]
		d['Dec rate'] = mpc_ephem['Dec Rate'][0]
		# Brightness (MPC)
		if 'Mag' in mpc_ephem.colnames:
			d['mag'] = mpc_ephem['Mag'][0]
			d['mag_label'] = 'MPC mag'
		else:
			d['mag'] = None
			d['mag_label'] = 'Magnitude'
		# True anomaly not provided by MPC ephemeris
		d['true_anom'] = None
		d['pos_unc_label'] = None
		d['pos_unc_ra_as'] = None
		d['pos_unc_dec_as'] = None
	if provider_name not in {'JPL', 'MPC'}:
		raise ValueError("provider must be 'JPL' or 'MPC'.")

	# Print RA/Dec in HMS/DMS along with rates in arcsec/sec
	coord = SkyCoord(ra=d['RA'], dec=d['DEC'], unit='deg', frame='icrs')

	# Rates are stored in arcsec/hour; convert to arcsec/second.
	# Apply a cos(Dec) correction to the stored RA rate so it is consistent everywhere.
	# (This also affects total_rate, half_rate, and the final tracking command.)
	cos_dec = np.cos(np.deg2rad(float(d['DEC'])))
	if np.isfinite(cos_dec) and np.abs(cos_dec) > 1e-12:
		# Preserve the original value for debugging/reference.
		d['RA rate_raw'] = d['RA rate']
		d['RA rate'] = d['RA rate'] / cos_dec
	else:
		d['RA rate_raw'] = d['RA rate']
		d['RA rate'] = np.nan

	ra_rate_as_s = d['RA rate'] / 3600.0
	dec_rate_as_s = d['Dec rate'] / 3600.0

	ra_hms = coord.ra.to_string(unit='hour', sep=':', precision=2, pad=True)
	dec_dms = coord.dec.to_string(unit='deg', sep=':', precision=1, alwayssign=True, pad=True)

	pos_unc_str = ''
	if d.get('pos_unc_ra_as') is not None and d.get('pos_unc_dec_as') is not None:
		if np.isfinite(d['pos_unc_ra_as']) and np.isfinite(d['pos_unc_dec_as']):
			pos_unc_str = f' | Pos unc ({d.get("pos_unc_label","?")}, "/"): sigma_RA={d["pos_unc_ra_as"]:.2f}, sigma_Dec={d["pos_unc_dec_as"]:.2f}'

	print(
		f'RA, Dec (HMS/DMS): {ra_hms}  {dec_dms} | '
		f'Rates ("/s): dRA={ra_rate_as_s:.8f}, dDec={dec_rate_as_s:.8f}'
		f'{pos_unc_str}'
	)
	# Print brightness and true anomaly information
	parts = []
	if d.get('mag') is not None and np.isfinite(d['mag']):
		parts.append(f'{d["mag_label"]} = {d["mag"]:.2f}')
	if d.get('true_anom') is not None and np.isfinite(d['true_anom']):
		parts.append(f'True anomaly = {d["true_anom"]:.1f}°')

	if len(parts) > 0:
		print('Brightness / Geometry: ' + ' | '.join(parts))
	else:
		print('Brightness / Geometry: not available from this ephemeris source')
	#
	total_rate = np.sqrt(d["RA rate"]**2 + d["Dec rate"]**2) / 60 # to "/min"
	max_exptime = seeing / (total_rate / 60)
	print(f'Elevation: {round(d["elevation"],2)}°. Pre-half-rate (half_rate={half_rate}) changes are dRA = {round(d["RA rate"]/60,3)} "/min and dDec = {round(d["Dec rate"]/60,3)} "/min.')
	print(f'Max Exptime = {round(max_exptime,1)} s given the total on-sky motion of {round(total_rate,3)} "/min and {seeing}" seeing.')
	#
	if half_rate:
		print("** Using half-rates **")
		d['RA rate'] = d['RA rate'] / 2.0
		d['Dec rate'] = d['Dec rate'] / 2.0
	#
	
	if limits != {} and limits != None:
		if 'min_elev' in limits or 'max_elev' in limits:
			# print(f'Elevation is: {d["elevation"]}')
			if 'min_elev' in limits and d['elevation'] < limits['min_elev']:
				raise ValueError(
					f'ERROR: {objname} at UT {ut} is at an elevation {round(d["elevation"],2)}°, '
					f'below minimum elevation ({limits["min_elev"]}°).'
				)
			if 'max_elev' in limits and d['elevation'] > limits['max_elev']:
				raise ValueError(
					f'ERROR: {objname} at UT {ut} is at an elevation {round(d["elevation"],2)}°, '
					f'above the maximum elevation ({limits["max_elev"]}°).'
				)
	#
#	print(eph)
#	print(eph.columns)
	#
	r = makeAPOtrackingCommand(	objname			= objname, 
								RA				= d['RA'], 
								DEC				= d['DEC'], 
								dRA				= d['RA rate'], 
								dDEC			= d['Dec rate'],
								offsets_arcmin	= 0,
							)
	return r





if __name__ == '__main__':
	import argparse # This is to enable command line arguments.
	parser = argparse.ArgumentParser(description='Query JPL/MPC ephemerides and print an APO TCC tracking command.')
	parser.add_argument('objects', nargs='+', help="Minor planets to query.")
	parser.add_argument('--site-code', dest='site_code', type=str, default='705', help='observatory site code. Default: 705 (APO).')
	parser.add_argument('--ut', dest='ut', type=str, default=None, help=f'UT of format YYYY-MM-DD hh:mm:ss. Default: now.')
	parser.add_argument('--timedelta', dest='time_delta', type=int, default=30, help=f'How many seconds after the UT to calculate. Used to make ephemeris more current (e.g., it takes time to query JPL, or you are planning for some time in the near future). Default: 30 seconds.')
	parser.add_argument('--min-elev', dest='min_elev', type=float, default=10, help=f'Minimum elevation of the target. Default: 10°.')
	parser.add_argument('--max-elev', dest='max_elev', type=float, default=85, help=f'Maximum elevation of the target. Default: 85°.')
	parser.add_argument('--provider', dest='provider', type=str, default='JPL', help='Ephemeris service to use. Options are JPL or MPC. Default: JPL.')
	parser.add_argument('--half-rate', dest='half_rate', action='store_true', help='Use half the tracking rates (RA and Dec).')
	parser.add_argument('--seeing', dest='seeing', type=float, default=1.0, help='Seeing in arcseconds used to estimate max exposure time. Default: 1.0".')
	parser.add_argument('--verbose', dest='verbose', type=bool, default=False, help=f'say "--verbose True" to see more messages.')
	args = parser.parse_args()
	for objname in args.objects:
		command = make_tcc_command(objname=objname, 
									site_code=args.site_code, 
									ut=args.ut, 
									timedelta_s=args.time_delta, 
									provider = args.provider,
									limits = {'min_elev':args.min_elev, 'max_elev':args.max_elev},
									verbose=args.verbose,
									half_rate=args.half_rate,
									seeing=args.seeing,
								)
		print(command)
