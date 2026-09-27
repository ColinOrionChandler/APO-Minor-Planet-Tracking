# Usage Notes

These notes capture the operational assumptions behind the two command-line
helpers in this repository.

## Main Horizons/MPC Workflow

`apo_minor_planet_tracking.py` is the normal entry point for named objects:

```console
python apo_minor_planet_tracking.py "Chandler"
```

By default the script:

1. Uses JPL Horizons.
2. Queries from APO site code `705`.
3. Requests an epoch 30 seconds in the future so the printed command is current
   by the time the query finishes and the observer pastes it into TUI.
4. Applies the default elevation guardrails of 10 to 85 degrees.

Useful options:

```console
python apo_minor_planet_tracking.py "Chandler" --ut "2026-05-11 06:00:00"
python apo_minor_planet_tracking.py "Chandler" --timedelta 120
python apo_minor_planet_tracking.py "Chandler" --provider MPC
python apo_minor_planet_tracking.py "Chandler" --min-elev 20 --max-elev 80
python apo_minor_planet_tracking.py "Chandler" --half-rate
python apo_minor_planet_tracking.py "Chandler" --sidereal
python apo_minor_planet_tracking.py "Chandler" --seeing 1.4
```

`--ut` should be a UTC timestamp.  If a timezone-aware Python `datetime` is
passed through the function API, it is converted to UTC before querying.

## Reading The Diagnostics

The final line is the command to paste into TUI.  The preceding lines are for
human review:

- `RA, Dec (HMS/DMS)` gives sexagesimal coordinates for quick comparison with
  other planning tools.
- `Rates ("/s)` shows the sky-motion components after the RA component has been
  adjusted by `cos(Dec)` for the TCC command convention.
- `Pos unc` appears only when JPL Horizons returns a finite RA/Dec uncertainty
  pair.  Horizons has used several column names for these values, so the script
  checks common 3-sigma and 1-sigma variants.
- `Brightness / Geometry` reports available JPL or MPC brightness fields and
  JPL true anomaly when present.
- `Max Exptime` estimates when motion equals the requested seeing.  This is a
  planning aid, not an exposure-time prescription.

## Half-Rate Tracking

`--half-rate` divides both RA and Dec rates by two after the diagnostics are
computed.  The pre-half-rate rates are still printed so the observer can see the
full on-sky motion before the command is modified.

## Sidereal Tracking

`--sidereal` keeps the queried RA/Dec position but emits zero dRA and dDec in
the final `tcc track` command.  This makes the telescope follow the sidereal
field, so field stars remain fixed and the moving target drifts through the
image.  The normal ephemeris query and elevation guardrails still run, and the
printed motion diagnostics describe the object's actual motion before the
sidereal mode is applied.  `--sidereal` and `--half-rate` cannot be used
together.

## NEOCP / PCCP Workflow

Use an exact temporary designation from the MPC [NEOCP](https://minorplanetcenter.net/iau/NEO/toconfirm_tabular.html)
or [PCCP](https://minorplanetcenter.net/iau/NEO/pccp_tabular.html) with the main script:

```console
python apo_minor_planet_tracking.py SWAN26Q --provider PCCP
python apo_minor_planet_tracking.py SWAN26Q --provider NEOCP --sidereal
python apo_minor_planet_tracking.py SWAN26Q --provider PCCP --ut "2026-09-27 14:00:00"
```

`NEOCP` and `PCCP` are aliases for the same confirmation ephemeris service;
neither needs a Horizons identity or a permanent designation. The exact,
case-sensitive designation is submitted to MPC. JPL remains the default provider,
and `MPC` continues to query the ordinary catalog ephemeris service.

The confirmation provider requests one-minute samples for the supplied site and
selects a row within 30 seconds of the requested UTC (default: now plus 30 seconds).
It prints both the requested time and the actual sample time; positions are not
interpolated. MPC accepts integer-hour start offsets, so the script requests a
window around the desired epoch and checks the returned timestamps. An uncovered
epoch, missing candidate, or invalid position/rate stops command generation.
Once a candidate is removed, query its assigned designation using JPL or MPC.

MPC decimal RA is in hours and is converted to degrees. The request uses separate
**sky-motion** components in arcsec/minute (`dmot=s`, `mot=m`), which are converted
to arcsec/hour before the main workflow applies its single RA cosine correction.
MPC altitude filtering is disabled for this query so the main script's configured
elevation limits apply. Half-rate and sidereal tracking work as usual.

Python callers can use:

```python
from apo_minor_planet_tracking import make_tcc_command
command = make_tcc_command('SWAN26Q', provider='PCCP', half_rate=True)
```

### Standalone PCCP Helper

Use `mpc_pccp.py` for candidates listed on the MPC Possible Comet Confirmation
Page:

```console
python mpc_pccp.py --show-object P12hxMW --obs-code 705
```

The script submits the selected object to the MPC `confirmeph2.cgi` form, parses its block,
selects the ephemeris row nearest to the current UTC time, and converts MPC
arcsec/minute rates to the APO TCC degrees/second convention.

For troubleshooting:

```console
python mpc_pccp.py --show-object P12hxMW --debug
python mpc_pccp.py --show-object P12hxMW --keep-mpc-html -o confirmeph2_response.html
```

The `--debug` flag prints the parsed table and the selected nearest row.  The
`--keep-mpc-html` flag saves the raw MPC response for later parser debugging.

## Safety Checklist

Before clicking Start in TUI:

1. Confirm the object name is the intended Horizons or MPC target.
2. Confirm the RA/Dec are plausible for the planned field.
3. Confirm the elevation is inside the observing limits.
4. Confirm the rates are plausible for the target class and epoch.
5. Paste only the final `tcc track ...` line into `Scripts -> Run_Commands`.
6. Apply any offsets through TUI after the slew, using object-arc absolute
   offsets.

## Development

Syntax-check the scripts without making network requests:

```console
python -m py_compile apo_minor_planet_tracking.py mpc_pccp.py
python -m unittest discover -s tests -v
```

Help output checks import the runtime dependencies but do not query JPL or MPC:

```console
python apo_minor_planet_tracking.py --help
python mpc_pccp.py --help
```

End-to-end command generation requires network access to the selected ephemeris
service.
