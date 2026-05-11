#!/usr/bin/env python3

"""
Query the MPC Possible Comet Confirmation Page and print APO TCC commands.

The PCCP lists objects that may not yet have stable provisional designations, so
the normal JPL Horizons workflow can be unavailable or ambiguous.  This helper
submits the MPC ``confirmeph2.cgi`` form for an observatory code, parses the
fixed-width response blocks, selects the ephemeris row nearest to the current UTC
time, and converts the MPC motion columns into an APO ``tcc track`` command.

Usage:
    python mpc_pccp.py --show-object P12hxMW --obs-code 705
"""

import argparse
import sys
import requests
from datetime import datetime, timezone

def makeAPOtrackingCommand_pccp(objname, RA, DEC, dRA, dDEC, verbose=False):
    """
    For APO TUI. 12/11/2025 COC
    This is for the Minor Planet Center Possible Comet Confirmation page.
    We have this coming in as arcseconds per minute so it needs to be
    converted first to arcseconds per hour.

    example tracking line:
        tcc track 45.43530667, 34.59037667, -0.000001208371914, -0.000002105362654 Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="426P"

    Instructions (for standalone, non-JPL case):
        1. Generate ephemeris in decimal degree mode.
        2. Supply object name, RA, Dec, etc. to function, such as
            makeAPOtrackingCommand_pccp(objname='2015 FW412', RA=171.71866, DEC=-11.84938, dRA=7.870796, dDEC=-10.8067)
           You should get a result similar to this:
              tcc track 171.71866, -11.84938, 6.073145061728395e-07, -8.338503086419753e-07 Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="2015 FW412"
        3. Paste the whole tcc track line into Scripts menu:Run_Commands in TUI.
        4. Click "Start" and the telescope will start slewing. Meanwhile...
        5. Offset:
            a. Open Offsets in the TCC menu of TUI.
            b. Choose "Object Arc" and "Abs" (absolute offset).
            c. Click "Offset" once the slew is over.
        6. Don't forget guiding!
        7. Don't use "slew" in TCS or it will override what we just did.
    """
    # APO TCC expects rates in degrees per second in the FK5 frame.
    # PCCP provides dRA, dDEC in arcsec per minute, so:
    #   1) convert to arcsec per hour
    #   2) convert arcsec/hour to deg/sec
    convfactor = 12960000.0  # arcsec/hour -> degrees/second for APO TCC

    # Use the RA/Dec values as provided (already in decimal degrees)
    newRA = RA
    newDEC = DEC

    # arcsec/min -> arcsec/hour
    dRA_hr = dRA * 60.0
    dDEC_hr = dDEC * 60.0

    s = (
        f'tcc track {newRA}, {newDEC}, {dRA_hr / convfactor}, {dDEC_hr / convfactor} '
        f'Fk5=2000.0 /Rotangle=0.0 /Rottype=Object /Name="{objname}"'
    )
    if verbose:
        print(s)
    return s

URL = "https://minorplanetcenter.net/cgi-bin/confirmeph2.cgi"


def parse_pccp_html(html_text: str) -> dict:
    """Parse an MPC PCCP confirmeph2 HTML response into a dict of DataFrames.

    Uses a line-based state machine similar to the user's prototype:

      - Detect object blocks from lines like:
        <p>Get the <a href="http://cgi.minorplanetcenter.net/cgi-bin/showobsorbs.cgi?Obj=XYZ...

      - For each object:
        * Find the header line starting with "Date".
        * Skip the following units row (starts with spaces).
        * Collect subsequent data lines, stripping HTML links.
        * Parse Date + UT (YYYY MM DD HHMM) into a pandas UTC datetime.

    Returns:
        dict[objname, pandas.DataFrame]
    """
    # Import pandas only when parsing so `mpc_pccp.py --help` stays lightweight
    # and does not emit optional pandas/Arrow CPU-probing warnings.
    import pandas as pd

    objs_lines = {}
    section = "pregame"
    objname = None

    for line in html_text.splitlines():
        # Start of a new object's block
        if line.startswith('<p>Get the <a href="http://cgi.minorplanetcenter.net/cgi-bin/showobsorbs.cgi?Obj='):
            section = "objname"
            objname = line.split("Obj=")[-1].split("&")[0]
            objs_lines[objname] = []
            continue

        if section == "pregame":
            continue

        if section == "objname":
            # Look for the header line starting with "Date"
            if line.startswith("Date"):
                section = "headerrow"
                objs_lines[objname].append(line.rstrip("\n"))  # header
                continue
            else:
                # Still waiting for the header line
                continue

        if section == "headerrow":
            # Skip the units row (starts with spaces)
            if line.startswith("      "):
                continue

            # If we encounter the beginning of another object while in headerrow,
            # treat it as a new object and reset state.
            if line.startswith('<p>Get the <a href="http://cgi.minorplanetcenter.net/cgi-bin/showobsorbs.cgi?Obj='):
                section = "objname"
                objname = line.split("Obj=")[-1].split("&")[0]
                objs_lines[objname] = []
                continue

            # Drop trailing HTML links (Map/Offsets)
            if "<a href" in line:
                line = line.split("<a href")[0]

            objs_lines[objname].append(line.rstrip("\n"))
    # print(objs_lines['P12hxMW'])
    # exit()
    tables = {}

    # Now convert the collected per-object lines into DataFrames
    for obj, lines in objs_lines.items():
        if not lines:
            continue

        header = lines[0]
        data_lines = [ln for ln in lines[1:] if ln.strip()]
        if not data_lines:
            continue

        rows = []
        for ln in data_lines:
            tokens = ln.split()
            if len(tokens) < 4:
                continue

            # First four tokens are YYYY MM DD HHMM
            try:
                year = int(tokens[0])
                month = int(tokens[1])
                day = int(tokens[2])
            except ValueError:
                # Not a data row starting with a year
                continue

            ut_str = tokens[3]
            # Normalize UT like "300" or "0300" -> "0300"
            ut_str = ut_str.zfill(4)
            hour = int(ut_str[:-2])
            minute = int(ut_str[-2:])

            row = {}

            # Build UTC datetime from the date and UT fields
            try:
                dt = pd.to_datetime(
                    f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}",
                    utc=True,
                )
            except Exception:
                dt = pd.NaT

            row["datetime_utc"] = dt

            # Map the remaining tokens to approximate MPC columns
            colnames = [
                "ra_deg",
                "dec_deg",
                "elong_deg",
                "V",
                "dRA",
                "dDec",
                "obj_az_deg",
                "obj_alt_deg",
                "sun_alt_deg",
                "phase",
                "moon_dist",
                "moon_alt_deg",
            ]

            for i, name in enumerate(colnames, start=4):
                if i >= len(tokens):
                    break
                val = tokens[i]
                try:
                    num = float(val)
                    if name == "ra_deg":
                        num = num * 15.0
                    row[name] = num
                except ValueError:
                    row[name] = val

            rows.append(row)

        if not rows:
            continue

        df = pd.DataFrame(rows)
        # Save raw header for reference
        df.attrs["header1"] = header
        cols = ["datetime_utc"] + [c for c in df.columns if c != "datetime_utc"]
        df = df[cols]
        tables[obj] = df

    return tables


def main():
    parser = argparse.ArgumentParser(
        description="Query MPC PCCP ephemerides and generate an APO TCC tracking command."
    )
    parser.add_argument(
        "-o", "--output",
        default="confirmeph2_response.html",
        help="Output filename for the MPC HTML response (used only if --keep-mpc-html; default: confirmeph2_response.html)",
    )
    parser.add_argument(
        "--show-object",
        help="If set, parse the MPC response and print the table for this object name (e.g., P12hxMW)",
    )
    parser.add_argument(
        "--obs-code",
        default="705",
        help="MPC observatory code to use for ephemeris generation (default: 705)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print full table and nearest-row details before generating tracking command",
    )
    parser.add_argument(
        "--keep-mpc-html",
        action="store_true",
        help="If set, save the raw MPC HTML response to the output file",
    )
    parser.add_argument(
        "--half-rate",
        action="store_true",
        help="Use half tracking rates (divide dRA and dDec by 2) when generating the TCC command",
    )
    args = parser.parse_args()

    # MPC currently accepts a normal form POST.  Keep the headers intentionally
    # small so the script is not tied to a personal browser session.
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:146.0) Gecko/20100101 Firefox/146.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://minorplanetcenter.net/iau/NEO/pccp_tabular.html",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://minorplanetcenter.net",
    }

    # Form fields mirror the interactive PCCP "ephemerides" page.  The defaults
    # request decimal RA/Dec and rates, filter out objects below 20 degrees
    # altitude, and sort by discovery date.
    data = {
        "W": "a",
        "mb": "-30",
        "mf": "30",
        "dl": "-90",
        "du": "+90",   # will be encoded as %2B90
        "nl": "0",
        "nu": "100",
        "sort": "d",
        "Parallax": "1",
        "obscode": args.obs_code,
        "long": "",
        "lat": "",
        "alt": "",
        "int": "2",
        "start": "0",
        "raty": "d",
        "mot": "m",
        "dmot": "r",
        "out": "f",
        "sun": "x",
        "oalt": "20",
    }

    try:
        resp = requests.post(URL, headers=headers, data=data, timeout=30)
        resp.raise_for_status()
        html_text = resp.text
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Optionally save raw bytes so gzip/encoding/etc. are preserved as delivered
    if args.keep_mpc_html:
        with open(args.output, "wb") as f:
            f.write(resp.content)
        print(f"Response saved to: {args.output}")

    # Optionally parse the response into DataFrames and show one object
    tables = parse_pccp_html(html_text)

    if args.show_object:
        obj = args.show_object
        if obj not in tables:
            available = ", ".join(sorted(tables.keys()))
            print(
                f"Object '{obj}' not found in response. Available objects: {available}",
                file=sys.stderr,
            )
            sys.exit(1)

        df = tables[obj]

        if args.debug:
            print(df)

        # Select the row whose datetime_utc is closest to the current UTC time
        now = datetime.now(timezone.utc)

        if "datetime_utc" not in df.columns or df["datetime_utc"].isna().all():
            print("No valid datetime_utc values in table; cannot generate tracking command.", file=sys.stderr)
            sys.exit(1)

        deltas = (df["datetime_utc"] - now).abs()
        nearest_idx = deltas.idxmin()
        row = df.loc[nearest_idx]

        if args.debug:
            print(f"\nNearest ephemeris row to now (UTC={now.isoformat()}):")
            print(row)

        try:
            ra_deg = float(row["ra_deg"])
            dec_deg = float(row["dec_deg"])
            dRA = float(row["dRA"])
            dDEC = float(row["dDec"])
        except KeyError as e:
            print(f"Missing expected column in table: {e}", file=sys.stderr)
            sys.exit(1)

        if args.half_rate:
            dRA = dRA / 2.0
            dDEC = dDEC / 2.0

        if args.debug and args.half_rate:
            print("** Using half tracking rates (dRA/2, dDec/2) **")

        cmd = makeAPOtrackingCommand_pccp(
            objname=obj,
            RA=ra_deg,
            DEC=dec_deg,
            dRA=dRA,
            dDEC=dDEC,
            verbose=False,
        )

        print("\nAPO TCC tracking command:")
        print(cmd)


if __name__ == "__main__":
    main()
