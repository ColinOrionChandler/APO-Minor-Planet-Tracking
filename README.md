# APO Minor Planet Tracking

APO Minor Planet Tracking generates one-line Telescope Control Console (TCC)
commands for tracking moving solar-system targets with the Apache Point
Observatory 3.5-meter ARC telescope.  It is most often used for follow-up of
active asteroids, comet candidates, and Rubin Comet Catchers targets where the
telescope should track the object instead of the field stars.

The main workflow queries JPL Horizons or, as a fallback, the Minor Planet Center
(MPC), prints observer-facing diagnostics, and returns a command like:

```console
tcc track 270.168133497, -22.53122276, 2.8419421296296294e-07, -7.75733024691358e-08 Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="Chandler"
```

## Scripts

- `apo_minor_planet_tracking.py` queries JPL Horizons by default and can query
  MPC ephemerides with `--provider MPC`.
- `mpc_pccp.py` queries the MPC Possible Comet Confirmation Page (PCCP) for
  objects that may not yet have stable provisional designations.

## Installation

Use a Python environment with:

```console
pip install astroquery astropy numpy pandas requests
```

The PCCP helper also expects the standard Python scientific stack used by the
main script.  No package install step is required for this repo; run the scripts
directly from the checkout.

## Quick Start

Query JPL Horizons for an object visible from APO site code `705`:

```console
python apo_minor_planet_tracking.py "Chandler"
```

Query a specific UTC epoch:

```console
python apo_minor_planet_tracking.py "Didymos (primary body)" --ut "2026-05-11 06:00:00"
```

Use half-rate tracking and a seeing estimate for exposure-time guidance:

```console
python apo_minor_planet_tracking.py "Chandler" --half-rate --seeing 1.2
```

Use MPC as the ephemeris provider if Horizons is unavailable:

```console
python apo_minor_planet_tracking.py "Chandler" --provider MPC
```

Generate a TCC command for an object listed on the PCCP:

```console
python mpc_pccp.py --show-object P12hxMW --obs-code 705
```

## Output

Before the final `tcc track` command, the main script prints:

- RA and Dec in sexagesimal form for a quick telescope-operator check.
- RA and Dec rates in arcsec/second.
- JPL positional uncertainty when Horizons exposes a usable RA/Dec uncertainty
  pair.
- Brightness and true anomaly when available from the selected ephemeris source.
- Elevation and an estimated maximum exposure time for the requested seeing.

Paste only the final `tcc track ...` line into TUI's `Scripts -> Run_Commands`
window unless you explicitly need one of the diagnostic lines elsewhere.

## Operational Notes

- Always sanity-check the object, coordinates, rates, and elevation before
  executing a command at the telescope.
- Apply offsets in TUI after the slew finishes.  Do not encode observing offsets
  in the Python command.
- Guide normally.  The telescope tracks the object, so field stars will trail.
- Nearby or fast-moving targets may need fresh commands during the night.
- Some Horizons names are ambiguous.  Use the exact disambiguated Horizons name
  when needed, such as `"Didymos (primary body)"`.

More detailed command notes live in [docs/usage.md](docs/usage.md).

## Development Checks

Run the lightweight syntax check before committing:

```console
python -m py_compile apo_minor_planet_tracking.py mpc_pccp.py
```

Live ephemeris checks require network access to JPL Horizons or MPC.

## Acknowledgement

If you use this code, please include:

> This research used APO Minor Planet Tracking by Colin Orion Chandler.

Please also cite JPL Horizons (Giorgini 1996) and Astropy as appropriate.

## Disclaimer

This repository is an observing aid.  The author provides no warranty, implied or
otherwise, and observers remain responsible for verifying commands before use.

## Acknowledgements

Thanks to APO operators, especially Candace and Russett, and to Will Oldroyd
(Northern Arizona University) for testing.
