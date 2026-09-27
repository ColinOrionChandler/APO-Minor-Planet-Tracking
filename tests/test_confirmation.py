"""Offline tests using synthetic MPC-format rows, not candidate predictions."""
import contextlib
import datetime
import io
import unittest
from unittest.mock import Mock, patch

import requests
from astropy.table import Table

import apo_minor_planet_tracking as tracking
import mpc_pccp


def html_row(ut='0600', ra='12.0000', dec='+60.000', motion='2.00',
             dec_motion='-3.00', altitude='+45', magnitude='19.2'):
    return (f'2026 09 27 {ut}  {ra:>7}    {dec:>7}     90.0  {magnitude:>4}   '
            f'{motion:>5}  {dec_motion:>5}  180  {altitude:>3}   -30    0.50   90  -10'
            '   <a href="map">Map</a>')


def html_response(*rows, name='SWAN26Q', scheme='https', host='minorplanetcenter.net'):
    return '\n'.join([
        f'<p>Get the <a href="{scheme}://{host}/cgi-bin/showobsorbs.cgi?Obj={name}&amp;obs=y">observations</a>',
        '<pre>',
        'Date       UT      R.A. (J2000) Decl.  Elong.  V        Motion     Object     Sun         Moon        Uncertainty',
        '            h m                                      "/min  "/min  Azi. Alt.  Alt.  Phase Dist. Alt.',
        *(rows or [html_row()]), '</pre>',
    ])


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.post = self.enterContext(patch('mpc_pccp.requests.post'))
        self.post.return_value = Mock(text=html_response())
        self.epoch = '2026-09-27 06:00:00'

    def query(self, **kwargs):
        return mpc_pccp.get_confirmation_ephemeris('SWAN26Q', ut=self.epoch, **kwargs)

    def command(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            command = tracking.make_tcc_command('SWAN26Q', provider='PCCP', ut=self.epoch, **kwargs)
        return command, out.getvalue()

    def test_exact_target_request_and_units(self):
        clock = self.enterContext(patch('mpc_pccp.datetime'))
        clock.now.return_value = datetime.datetime(2026, 9, 27, 4, 30, tzinfo=datetime.timezone.utc)
        row = self.query(site_code='G96')
        self.assertEqual(row['ra_deg'], 180)
        data = self.post.call_args.kwargs['data']
        self.assertEqual(data, dict(W='j', obj='SWAN26Q', Parallax='1', obscode='G96',
                                   int='3', start='2', raty='d', mot='m', dmot='s',
                                   out='f', sun='x', oalt='-90'))
        self.assertEqual(self.post.call_args.kwargs['timeout'], 30)

    def test_parser_old_and_new_links_and_multiple_objects(self):
        html = html_response(scheme='http', host='cgi.minorplanetcenter.net')
        html += '\n' + html_response(name='Other01')
        self.assertEqual(set(mpc_pccp.parse_pccp_html(html)), {'SWAN26Q', 'Other01'})

    def test_nearest_sample_and_displayed_epoch(self):
        self.post.return_value.text = html_response(html_row(), html_row(ut='0601', ra='12.0010'))
        self.epoch = '2026-09-27 06:00:40'
        command, output = self.command()
        self.assertIn('180.015', command)
        self.assertIn('2026-09-27T06:01:00+00:00', output)

    def test_rate_conversion_applies_cosine_once(self):
        command, _ = self.command()
        values = command.split('Fk5')[0].removeprefix('tcc track ').split(', ')
        self.assertAlmostEqual(float(values[2]), 2 * 60 / 0.5 / 12960000)
        self.assertAlmostEqual(float(values[3]), -3 * 60 / 12960000)

    def test_modes_preserve_position(self):
        for mode, factor in [({}, 1), ({'half_rate': True}, 0.5), ({'sidereal': True}, 0)]:
            with self.subTest(mode=mode):
                command, _ = self.command(**mode)
                values = command.split('Fk5')[0].removeprefix('tcc track ').split(', ')
                self.assertEqual([float(v) for v in values[:2]], [180, 60])
                self.assertAlmostEqual(float(values[2]), factor * 240 / 12960000)
                self.assertAlmostEqual(float(values[3]), factor * -180 / 12960000)

    def test_neocp_alias(self):
        with contextlib.redirect_stdout(io.StringIO()):
            command = tracking.make_tcc_command('SWAN26Q', provider='neocp', ut=self.epoch)
        self.assertIn('/Name="SWAN26Q"', command)

    def test_elevation_guards_even_in_sidereal_mode(self):
        for altitude, error in [('+05', 'below minimum'), ('+89', 'above the maximum')]:
            with self.subTest(altitude=altitude):
                self.post.return_value.text = html_response(html_row(altitude=altitude))
                with self.assertRaisesRegex(ValueError, error):
                    self.command(sidereal=True)

    def test_missing_target_never_uses_another_object(self):
        self.post.return_value.text = html_response(name='Other01')
        with self.assertRaisesRegex(ValueError, 'No usable.*SWAN26Q'):
            self.query()

    def test_stale_or_out_of_range_epoch(self):
        self.epoch = '2026-09-27 07:00:00'
        with self.assertRaisesRegex(ValueError, 'refusing a stale'):
            self.query()

    def test_invalid_numeric_values(self):
        for fields in [{'ra': 'nan'}, {'motion': 'oops'}, {'altitude': 'nan'},
                       {'ra': '25.0000'}, {'dec': '+91.000'}, {'altitude': '+99'}]:
            with self.subTest(fields=fields):
                self.post.return_value.text = html_response(html_row(**fields))
                with self.assertRaises(ValueError):
                    self.query()

    def test_blank_magnitude_does_not_shift_rates_or_altitude(self):
        self.post.return_value.text = html_response(html_row(magnitude=''))
        row = self.query()
        self.assertEqual((row['dRA'], row['dDec'], row['obj_alt_deg']), (2, -3, 45))
        command, _ = self.command()
        self.assertIn('tcc track', command)

    def test_bad_timestamp_and_truncated_rows(self):
        for row in [html_row(ut='xxxx'), html_row(ut='2561'), '2026 09 27 0600 12.0 60.0']:
            with self.subTest(row=row):
                self.post.return_value.text = html_response(row)
                with self.assertRaises(ValueError):
                    self.query()

    def test_service_failures(self):
        self.post.side_effect = requests.Timeout('timeout')
        with self.assertRaisesRegex(ValueError, 'request failed'):
            self.query()
        self.post.side_effect = None
        self.post.return_value.raise_for_status.side_effect = requests.HTTPError('503')
        with self.assertRaisesRegex(ValueError, 'request failed'):
            self.query()

    def test_html_error_pages(self):
        for html, message in [('Incorrect Form Entry (009)', 'MPC rejected'),
                              ('<h1>Unavailable</h1>', 'No usable')]:
            self.post.return_value.text = html
            with self.assertRaisesRegex(ValueError, message):
                self.query()

    def test_zero_motion(self):
        self.post.return_value.text = html_response(html_row(motion='0.00', dec_motion='0.00'))
        command, output = self.command()
        self.assertIn('0.0, 0.0 Fk5', command)
        self.assertIn('Max Exptime = inf', output)

    def test_invalid_options_fail_before_request(self):
        with self.assertRaises(ValueError):
            self.command(half_rate=True, sidereal=True)
        with self.assertRaises(ValueError):
            mpc_pccp.get_confirmation_ephemeris('SWAN26Q/other')
        with self.assertRaises(ValueError):
            tracking.make_tcc_command('SWAN26Q', provider='unknown')
        self.post.assert_not_called()

    def test_default_jpl_provider_still_works(self):
        with patch.object(tracking, 'Horizons') as horizons:
            horizons.return_value.ephemerides.return_value = Table(
                dict(EL=[45.], RA=[180.], DEC=[60.], RA_rate=[120.], DEC_rate=[-180.]))
            with contextlib.redirect_stdout(io.StringIO()):
                command = tracking.make_tcc_command('Chandler', ut=self.epoch, sidereal=True)
        self.assertIn('180.0, 60.0, 0.0, 0.0', command)
        self.post.assert_not_called()


if __name__ == '__main__':
    unittest.main()
