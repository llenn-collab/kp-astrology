# kpastro — KP Astrology Engine for Python

A Python engine for Krishnamurti Paddhati (KP) astrology calculations, using Swiss Ephemeris for planetary positions and Placidus houses, with KP star/sub/sub-sub-lord calculations, Vimshottari dasha, significators, ruling planets, panchanga helpers, horary charts, and birth-time rectification.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Swiss Ephemeris](https://img.shields.io/badge/ephemeris-Swiss%20Ephemeris-orange.svg)](https://www.astro.com/swisseph/)

## Contents

- [Features](#features)
- [Install](#install)
- [Ephemeris files and precision](#ephemeris-files-and-precision)
- [Quick start](#quick-start)
- [KP horary number and chart format](#kp-horary-number-and-chart-format)
- [CLI reference](#cli-reference)
- [Python API](#python-api)
- [Calculation conventions](#calculation-conventions)
- [Project layout](#project-layout)
- [Development and tests](#development-and-tests)
- [Citation, license, and disclaimer](#citation-license-and-disclaimer)

## Features

- **KP planetary and cusp details:** sidereal longitudes, signs, nakshatras, star-lords, sub-lords, and sub-sub-lords.
- **Ayanamsa modes:** Lahiri (default), KP / VP291, KP-old, and KP-new.
- **Placidus houses:** sidereal house cusps with KP lord details.
- **Vimshottari dasha:** mahadasha and nested antardasha/pratyantar-dasha periods, with deeper Sookshma and Prana levels for chart output.
- **Significators and ruling planets:** planet-to-house and house-to-planet significations, plus ruling-planet calculations.
- **KP horary (Prashna):** the specialised 1–249 number system.
- **Panchanga helpers:** sunrise/sunset and related calendar elements exposed through the Python package.
- **Birth-time rectification:** candidate-time scoring from dated life events, with supporting transit and interval helpers.
- **CLI and Python API:** use the same calculation engine from the terminal or from Python.
- **Offline-first calculation:** no remote astrology API is required at runtime. Downloading ephemeris data requires an internet connection.

## Install

Requires Python 3.9 or later.

From a checkout of this repository:

    git clone https://github.com/llenn-collab/kp-astrology.git
    cd kp-astrology
    python -m venv .venv

Activate the virtual environment before installing. On Linux/macOS:

    source .venv/bin/activate

On Windows PowerShell:

    .venv\Scripts\Activate.ps1

Install the package:

    python -m pip install --upgrade pip
    python -m pip install -e .

Install development and test dependencies too:

    python -m pip install -e ".[dev]"

The runtime dependency is pyswisseph. The command-line interface can be invoked as either python -m kpastro or, after installation, kpastro.

Check the available commands:

    python -m kpastro --help
    python -m kpastro --version
    python -m kpastro natal --help
    python -m kpastro horary --help

## Ephemeris files and precision

### Download the default data files

Run:

    python -m kpastro download-ephemeris

By default, the downloader installs these Swiss Ephemeris data files under **~/.kpastro/ephe**:

- **sepl_18.se1**
- **semo_18.se1**
- **seas_18.se1**

They are not bundled in the repository. The downloader validates that downloaded files are large enough to be plausible ephemeris files and avoids replacing an existing file that already passes its size check.

### Use a custom directory

Pass a directory to the downloader:

    python -m kpastro download-ephemeris --dir /path/to/ephe

The download directory and the directory used for subsequent calculations are separate settings. To use the custom directory for CLI calculations, set **SE_EPHE_PATH** in the environment.

Linux/macOS:

    export SE_EPHE_PATH="/path/to/ephe"
    python -m kpastro horary --number 117 --date 2026-10-30 --time 12:00 --tz 5.5 --lat 18.4593067 --lon 73.8654709 --ayanamsa kp_new

Windows PowerShell:

    $env:SE_EPHE_PATH = "C:\path\to\ephe"
    python -m kpastro horary --number 117 --date 2026-10-30 --time 12:00 --tz 5.5 --lat 18.4593067 --lon 73.8654709 --ayanamsa kp_new

The backend resolves the ephemeris directory in this order:

1. An explicit ephe_path argument when constructing SwissEphemeris through the Python API.
2. The **SE_EPHE_PATH** environment variable.
3. The default **~/.kpastro/ephe** directory.

The CLI does not have a general --ephe-path option. For CLI calculations, use the environment variable when the data files are outside the default directory.

### Verify which ephemeris is active

Missing data files do not prevent calculations. Swiss Ephemeris falls back to its built-in Moshier ephemeris when the required files are unavailable. That fallback is useful for running the engine, but results can differ from reference calculations; for KP Stellar comparisons, verify that the full data files are being used.

Check the status with Python:

    python -c "from kpastro import SwissEphemeris; e = SwissEphemeris(ayanamsa='kp_new'); print('precision:', e.precision); print('path:', e.ephe_path)"

The precision value is **full** when all required files are present and pass the loader's size checks; otherwise it is **moshier**. Check this before investigating small differences against reference outputs. The ephemeris directory and its data files are local runtime assets, not source files that need to be committed to the repository.

## Quick start

### 1. Generate a natal chart

The date and time are local to the supplied timezone offset. Latitude and longitude are geographic coordinates in decimal degrees.

    python -m kpastro natal --date 1990-01-15 --time 14:30 --tz 5.5 --lat 28.6139 --lon 77.2090 --place "New Delhi"

### 2. Generate a KP horary chart

Select the querent's horary number from **1 to 249**. This example uses number 117:

    python -m kpastro horary --number 117 --date 2026-10-30 --time 12:00:00 --tz 5.5 --lat 18.4593067 --lon 73.8654709 --place "Pune, India" --ayanamsa kp_new --node mean

### 3. Emit JSON in the KP Stellar-compatible schema

The chart commands support JSON output. The default JSON schema is **stellar**; use **--json-schema detailed** for the package's detailed schema.

    SE_EPHE_PATH="$HOME/.kpastro/ephe" python -m kpastro horary --number 117 --date 2026-10-30 --time 12:00:00 --tz 5.5 --lat 18.4593067 --lon 73.8654709 --place "Pune, India" --ayanamsa kp_new --node mean --json --name "KPstellaroutput" --gender Male --timezone Asia/Kolkata --query-utc "2026-10-18 12:00:00"

The fixed --query-utc value above matches the repository's reference-test setup. Use the query instant appropriate to your own calculation; it is a UTC timestamp used to resolve the dasha stack, not a replacement for the local chart date and time.

### 4. Get the ayanamsa for a date

    python -m kpastro ayanamsa --date 2026-10-30 --ayanamsa kp_new

### 5. Download the ephemeris files

    python -m kpastro download-ephemeris

## KP horary number and chart format

### Number range and JSON representation

A KP horary number is an integer from **1 through 249**. The dedicated horary command accepts it as **--number N**. The natal command can also carry a specialised horary number using **--horary-no N**.

In the default stellar JSON schema, the number is recorded in the horary details section in this format:

    {
      "horary_details": {
        "horary_no": "117 (249)"
      }
    }

This is an abbreviated fragment showing the field format, not the complete chart payload. The full output also contains planetary positions, house cusps, significators, ruling planets, and dasha-related data.

### Important distinction: division midpoint versus chart cusp

The backend exposes two related but distinct values:

- **Division midpoint:** ascendant_from_kp_number(n) returns the selected division's midpoint and its sign/star/sub/sub-sub lord chain.
- **Horary chart cusp:** the CLI chart-building paths use the selected division's **start degree** (start_deg) as the horary lagna for the house frame. The remaining Placidus cusps are constructed from that requested lagna.

This distinction is intentional in the current implementation. Do not substitute the midpoint for the cusp when reproducing the backend's chart output. The chart's astronomical ascendant and ruling planets remain tied to the supplied date, time, and place; the horary number determines the house-cusp frame. Therefore, the astronomical ascendant and cusp 1 can be different, including belonging to different signs.

The two CLI entry points are:

- **Dedicated horary chart:** use python -m kpastro horary --number 117 ...
- **Natal-style chart carrying a horary number:** use python -m kpastro natal --horary-no 117 .... This path is useful when reproducing the repository's KP Stellar reference command and metadata layout.

Example of the second form:

    SE_EPHE_PATH="$HOME/.kpastro/ephe" python -m kpastro natal --date 2026-10-30 --time 12:00:00 --tz 5.5 --lat 18.4593067 --lon 73.8654709 --place "Pune, India" --ayanamsa kp_new --node mean --json --name "KPstellaroutput" --gender Male --horary-no 117 --timezone Asia/Kolkata --query-utc "2026-10-18 12:00:00"

Use **--number** for the dedicated horary subcommand and **--horary-no** for the natal subcommand. Both validate the supported number range.

## CLI reference

Run python -m kpastro --help for the live command list and each subcommand's --help for its complete options.

| Command | Purpose |
|---|---|
| python -m kpastro natal ... | Compute a chart from the supplied date, local time, and place. |
| python -m kpastro horary --number N ... | Compute a KP horary chart for number N. |
| python -m kpastro dasha ... | Print the Vimshottari dasha timeline for the supplied chart data. |
| python -m kpastro rulings ... | Print the ruling planets for the supplied moment and place. |
| python -m kpastro ayanamsa --date YYYY-MM-DD | Print the configured ayanamsa value for the specified date. |
| python -m kpastro download-ephemeris | Download the required Swiss Ephemeris data files. |

### Common chart options

The natal and horary commands accept these principal options:

| Option | Meaning |
|---|---|
| --date YYYY-MM-DD | Local chart date. Defaults to the system date. |
| --time HH:MM[:SS] | Local chart time. Defaults to 12:00. |
| --tz HOURS | Local UTC offset in hours; defaults to +5.5. Use the offset that applies to the chart date and location. |
| --lat DEGREES | Latitude in decimal degrees. Required. |
| --lon DEGREES | Longitude in decimal degrees. Required. |
| --place TEXT | Optional place label included in output. |
| --ayanamsa MODE | lahiri (default), kp, kp_old, or kp_new. |
| --node MODE | mean (default) or true. |
| --json | Emit JSON instead of the standard text output. |
| --json-schema SCHEMA | Choose stellar (default) or detailed for JSON output. |
| --name TEXT | Name metadata for the JSON details section. |
| --gender TEXT | Gender metadata for the JSON details section. |
| --timezone ZONE | Optional IANA timezone label for the JSON details section, such as Asia/Kolkata. |
| --query-utc INSTANT | Pin the UTC instant used to resolve the dasha stack. Accepts a date or a date-time such as 2026-10-18 12:00:00. |
| --dasha-depth N | Dasha depth: 3 for MD/AD/PD, 4 to include Sookshma, or 5 to include Prana. Default is 5. |

The natal command additionally accepts --horary-no N to attach a specialised horary number and build the house frame from its division cusp. The horary command instead requires --number N.

When the current dasha stack must be reproducible, provide --query-utc explicitly. The natal command defaults that stack to the current UTC instant when the option is omitted; the horary command defaults it to the chart's own UTC instant. The local chart date/time and the UTC query timestamp serve different purposes.

## Python API

The package exports the principal chart, ephemeris, horary, significator, dasha, and rectification functions from kpastro. JSON chart rendering is provided by kpastro.chart.

### Compute a chart

    from datetime import date, time
    from kpastro import BirthInfo, compute_chart, render_chart

    birth = BirthInfo(
        date=date(1990, 1, 15),
        time=time(14, 30),
        latitude=28.6139,
        longitude=77.2090,
        tz_hours=5.5,
        place="New Delhi",
    )
    chart = compute_chart(birth, ayanamsa="lahiri")
    print(render_chart(chart))

### Compute a horary chart with the backend's cusp convention

    from datetime import date, time
    from kpastro import BirthInfo, SwissEphemeris, compute_chart, kp_divisions

    birth = BirthInfo(
        date=date(2026, 10, 30),
        time=time(12, 0),
        latitude=18.4593067,
        longitude=73.8654709,
        tz_hours=5.5,
        place="Pune, India",
    )

    horary_number = 117
    division = kp_divisions()[horary_number - 1]
    eph = SwissEphemeris(ayanamsa="kp_new", node="mean")

    chart = compute_chart(
        birth,
        ayanamsa="kp_new",
        node="mean",
        eph=eph,
        horary_lagna=division.start_deg,
    )

### Read the division midpoint separately

    from kpastro import ascendant_from_kp_number, kp_divisions

    number = 117
    division = kp_divisions()[number - 1]
    midpoint_details = ascendant_from_kp_number(number)

    print("Division start:", division.start_deg)
    print("Division end:", division.end_deg)
    print("Division midpoint:", midpoint_details["ascendant"])
    print("KP lord chain:", midpoint_details)

The midpoint helper is useful when the application specifically needs the division midpoint. To reproduce CLI horary house cusps, pass the division's start_deg to compute_chart as horary_lagna.

### Serialize chart JSON from Python

    from datetime import datetime
    from kpastro.chart import render_chart_json

    query_utc = datetime(2026, 10, 18, 12, 0, 0)  # naive datetime interpreted as UTC
    payload = render_chart_json(
        chart,
        schema="stellar",
        query_utc=query_utc,
        horary_no=117,
        name="KPstellaroutput",
        gender="Male",
        timezone="Asia/Kolkata",
    )
    print(payload)

For reproducible dasha output, pass the same query instant to compute_chart and render_chart_json. The JSON renderer accepts schema="stellar" or schema="detailed".

### Birth-time rectification

Rectification helpers accept an approximate birth record and dated life events associated with relevant KP houses. The available public API includes LifeEvent, rectify, and render_rectification.

    from datetime import date, time
    from kpastro import BirthInfo, LifeEvent, rectify, render_rectification

    birth = BirthInfo(
        date(1990, 1, 15),
        time(14, 30),
        28.6139,
        77.2090,
        5.5,
        "New Delhi",
    )
    events = [
        LifeEvent(date(1995, 9, 3), 2, (), "School admission"),
        LifeEvent(date(2007, 4, 1), 4, (), "Joined college"),
        LifeEvent(date(2018, 1, 20), 7, (), "Marriage"),
    ]
    result = rectify(birth, time(14, 30), events)
    print(render_rectification(result, birth))

The quality of rectification depends on the accuracy and relevance of the supplied event dates and house mappings. The reported posterior-band interval is a scoring summary, not a statistically calibrated credible interval.

## Calculation conventions

### Sidereal longitude and ayanamsa

The engine converts tropical longitudes to sidereal longitudes using the configured ayanamsa:

    sidereal longitude = tropical longitude - ayanamsa

The available modes are:

- **lahiri:** Swiss Ephemeris Lahiri/Chitrapaksha; the default.
- **kp:** the Swiss Ephemeris Krishnamurti VP291 mode.
- **kp_old:** the Swiss Ephemeris Krishnamurti mode.
- **kp_new:** a KP VP291-based mode with a code-level zero-point calibration intended to improve agreement with KP Stellar reference output.

KP-new compatibility adjustments are empirical software conventions, not a claim that the reference application's internal astronomical model is publicly documented. Validate results against the intended reference and epoch before relying on arcsecond-level comparisons.

### Nakshatras, sub-lords, and dasha

The sidereal zodiac is divided into 27 nakshatras of 13°20′ each. Each nakshatra is subdivided according to the Vimshottari proportions. The lord chain reports the star-lord, sub-lord, and sub-sub-lord for a longitude. The Vimshottari cycle totals 120 years:

| Planet | Years |
|---|---:|
| Ketu | 7 |
| Venus | 20 |
| Sun | 6 |
| Moon | 10 |
| Mars | 7 |
| Rahu | 18 |
| Jupiter | 16 |
| Saturn | 19 |
| Mercury | 17 |

The engine uses 365.25 days per dasha year for its balance and period calculations.

### Why the horary system has 249 numbers

The 27 nakshatras times 9 sub-lords produce 243 base subdivisions. Six zodiac sign boundaries fall inside subdivisions and split them into separate sign-specific divisions, giving 249 numbered divisions spanning the zodiac. The sequence is generated by kp_divisions() and is indexed from 1 for the public horary number; Python list indexing for that table is zero-based, so number N is kp_divisions()[N - 1].

### Ephemeris and precision caveats

Full Swiss Ephemeris data files and the Moshier fallback can produce different results. A mismatch with another application can also originate in ayanamsa conventions, the house-latitude model, time handling, or undocumented reference-software behaviour. For KP Stellar comparison work, use the relevant reference configuration, set SE_EPHE_PATH, choose the intended ayanamsa (often kp_new for this repository's current comparison fixtures), and pin --query-utc when comparing nested dasha periods.

The repository contains reconciliation notes and tests for measured differences against its committed KP Stellar reference output. These documents record the tested reference cases; they do not guarantee exact agreement for every date, location, or software version.

## Project layout

    src/kpastro/
      __init__.py       Public API and package version
      __main__.py       python -m kpastro entry point
      arithmetic.py     Exact arithmetic helpers for zodiac boundaries
      chart.py          BirthInfo, compute_chart, chart renderers and JSON schemas
      cli.py            Command-line interface
      constants.py      Vimshottari, sign, and nakshatra tables
      dasha.py          Vimshottari balance and timeline calculations
      deep_dasha.py     Nested current dasha periods
      ephemeris.py      Swiss Ephemeris wrapper and data-file downloader
      horary.py         The 249-division system and horary cusp calculations
      panchanga.py      Calendar, sunrise/sunset, and panchanga helpers
      rectification.py  Birth-time rectification and transit scoring
      significators.py  Planet/house significators and ruling planets
      vedic.py          KP longitude, star, sub, and sub-sub-lord calculations

Other useful repository references:

- [KP Stellar differences](KP_STELLAR_DIFF.md)
- [KP Stellar reconciliation notes](KP_STELLAR_RECONCILIATION.md)
- [Agent/developer guidance](AGENTS.md)
- [Horary tests](tests/test_horary.py)

## Development and tests

Install development dependencies:

    python -m pip install -e ".[dev]"

Run the test suite:

    python -m pytest

During iteration, run the suite without the configured coverage gate:

    python -m pytest --no-cov

Run the horary tests alone:

    python -m pytest --no-cov tests/test_horary.py

The repository's AGENTS.md documents the known baseline failures and expected-failure reference tests on the checked-in development baseline. Consult it before treating every full-suite failure as a regression or assuming the current baseline is fully green.

## Citation, license, and disclaimer

If you use the engine in research or an application, cite the software and repository version you used. The package metadata credits Rituparno Majumdar.

    @software{kpastro,
      author = {Rituparno Majumdar},
      title = {kpastro: A Krishnamurti Paddhati Astrology Engine},
      year = {2026},
      url = {https://github.com/llenn-collab/kp-astrology},
      license = {MIT}
    }

The project is released under the MIT License; see [LICENSE](LICENSE).

The software is provided for educational and computational purposes. Astrological interpretations are not scientific predictions and should not be used as the sole basis for financial, medical, legal, or other high-impact decisions.
