#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Tests for `speasy` package."""
import unittest
from datetime import datetime, timezone

import numpy as np
from ddt import data, ddt

from speasy.webservices import ssc


@ddt
class SscWeb(unittest.TestCase):
    def setUp(self):
        self.ssc = ssc.SSC_Webservice()

    def tearDown(self):
        pass

    @data(
        {
            "product": "moon",
            "start_time": datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2006, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "bepicolombo",
            "start_time": datetime(2019, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2019, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 10, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc)
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc),
            "coordinate_system": "GSE"
        },
        {
            "product": "mms1",
            "start_time": datetime(2021, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
            "stop_time": datetime(2021, 1, 8, 1, 0, 1, tzinfo=timezone.utc),
            "coordinate_system": "gse"
        }
    )
    def test_get_orbit(self, kw):
        result = self.ssc.get_data(**kw,
                                   debug=True,
                                   disable_cache=True,
                                   disable_proxy=True)
        self.assertIsNotNone(result)
        self.assertGreater(len(result), 0)
        self.assertGreater(np.timedelta64(60, 's'), np.datetime64(kw["start_time"], 'ns') - result.time[0])
        self.assertGreater(np.timedelta64(60, 's'), np.datetime64(kw["stop_time"], 'ns') - result.time[-1])

    def test_returns_none_for_a_request_outside_of_range(self):
        with self.assertLogs('speasy.core.dataprovider', level='WARNING') as cm:
            result = self.ssc.get_data('solarorbiter', datetime(2006, 1, 8, 1, 0, 0, tzinfo=timezone.utc),
                                       datetime(2006, 1, 8, 2, 0, 0, tzinfo=timezone.utc))
            self.assertIsNone(result)
            self.assertTrue(
                any(["outside of its definition range" in line for line in cm.output]))

    def test_get_observatories(self):
        obs_list = self.ssc.get_observatories()
        self.assertIsNotNone(obs_list)
        self.assertGreater(len(obs_list), 10)  # it has to return few elements

    @data({'sampling': '1'},
          {'unknown_arg': 10})
    def test_raises_if_user_passes_unexpected_kwargs_to_get_orbit(self, kwargs):
        with self.assertRaises(TypeError):
            self.ssc.get_data('moon', "2018-01-01", "2018-01-02", **kwargs)


class SscWebTrajectoriesPlots(unittest.TestCase):
    def setUp(self):
        import speasy as spz
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            self.skipTest("Can't import matplotlib")
        self.traj: spz.SpeasyVariable = spz.get_data(spz.inventories.data_tree.ssc.Trajectories.ace, "2018-01-01",
                                                     "2018-01-02")

    def tearDown(self):
        pass

    def test_should_be_able_to_plot_a_trajectory(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ax = self.traj.plot()
        self.assertIsNotNone(ax)

    def test_units_must_be_in_axis_label(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ax = self.traj.plot()
        self.assertIsNotNone(ax)
        self.assertIn("km", ax.get_ylabel())

    def test_legend_is_set_with_variable_columns_names(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ax = self.traj.plot()
        self.assertIsNotNone(ax)
        self.assertIn(self.traj.columns[0], ax.get_legend().texts[0].get_text())
        self.assertIn(self.traj.columns[1], ax.get_legend().texts[1].get_text())
        self.assertIn(self.traj.columns[2], ax.get_legend().texts[2].get_text())


if __name__ == '__main__':
    unittest.main()
