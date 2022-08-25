# -*- coding: utf-8 -*-

"""cda package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'

from typing import Optional, Dict
from types import SimpleNamespace
from datetime import datetime, timedelta
from speasy.core.cache import Cacheable, CacheCall, CACHE_ALLOWED_KWARGS
from speasy.products.variable import SpeasyVariable
from ...core import http, AllowedKwargs, deprecation
from speasy.core.proxy import Proxyfiable, GetProduct, PROXY_ALLOWED_KWARGS
from speasy.core.inventory.indexes import ParameterIndex, SpeasyIndex
from speasy.core.dataprovider import DataProvider
from speasy.core.datetime_range import DateTimeRange
import numpy as np
from astropy import units

import logging

log = logging.getLogger(__name__)


def _make_datetime(dt: str) -> np.datetime64:
    '''
        Hack to support python 3.6, once 3.6 support removed then go back to:
        datetime.strptime(v[1], '%Y-%m-%dT%H:%M:%S.%f%z').timestamp()
    '''
    return np.datetime64(dt[:-6], 'ns')


def _variable(orbit: dict) -> Optional[SpeasyVariable]:
    data = orbit['Result']['Data'][1][0]['Coordinates'][1][0]
    keys = list(data.keys())
    keys.remove('CoordinateSystem')
    values = np.array([data['X'][1], data['Y'][1], data['Z'][1]]).transpose() * units.km
    # this is damn slow!
    time_axis = np.array([_make_datetime(v[1]) for v in
                          orbit['Result']['Data'][1][0]['Time'][1]])
    return SpeasyVariable(time=time_axis,
                          values=values,
                          meta={'CoordinateSystem': data['CoordinateSystem'], 'UNITS': 'km'},
                          columns=['X', 'Y', 'Z'])


def _is_valid(orbit: dict):
    return orbit['Result']['StatusCode'] == 'SUCCESS' and orbit['Result']['StatusSubCode'] == 'SUCCESS'


def _make_cache_entry_name(prefix: str, product: str, start_time: str, **kwargs):
    return f"{prefix}/{product}/{kwargs.get('coordinate_system', 'gse')}/{start_time}"


def get_parameter_args(start_time: datetime, stop_time: datetime, product: str, **kwargs):
    return {'path': f"sscweb/{product}", 'start_time': f'{start_time.isoformat()}',
            'stop_time': f'{stop_time.isoformat()}', 'coordinate_system': kwargs.get('coordinate_system', 'gse')}


def make_index(meta: Dict):
    name = meta.pop('Name')
    meta['start_date'] = meta.pop('StartTime')[1]
    meta['stop_date'] = meta.pop('EndTime')[1]
    node = ParameterIndex(name=name, provider="ssc", uid=meta['Id'], meta=meta)
    return node


class SSC_Webservice(DataProvider):
    def __init__(self):
        self.__url = "https://sscweb.gsfc.nasa.gov/WS/sscr/2"
        DataProvider.__init__(self, provider_name='ssc', provider_alt_names=['sscweb'])

    def build_inventory(self, root: SpeasyIndex):
        inv = list(map(make_index, self.get_observatories()))
        root.Trajectories = SpeasyIndex(name='Trajectories', provider='ssc', uid='Trajectories',
                                        meta={item.Id: item for item in inv})

    @CacheCall(cache_retention=7 * 24 * 60 * 60, is_pure=True)
    def get_observatories(self):
        res = http.get(f"{self.__url}/observatories", headers={"Accept": "application/json"})
        if not res.ok:
            return None
        return res.json()['Observatory'][1]

    def version(self, product):
        return 2

    def parameter_range(self, parameter_id: str or ParameterIndex) -> Optional[DateTimeRange]:
        """Get product time range.

        Parameters
        ----------
        parameter_id: str or ParameterIndex
            parameter id

        Returns
        -------
        Optional[DateTimeRange]
            Data time range

        Examples
        --------

        >>> import speasy as spz
        >>> spz.cda.parameter_range("solarorbiter")
        <DateTimeRange: 2020-02-10T04:56:30+00:00 -> ...>

        """
        return self._parameter_range(parameter_id)

    # Wrapper to ensure that whatever the source (Proxy, Cache, SSCWeb) the returned variable is in km
    def get_trajectory(self, product: str, start_time: datetime, stop_time: datetime, coordinate_system: str = 'gse',
                       debug=False, **kwargs) -> Optional[SpeasyVariable]:
        var = self._get_orbit(product=product, start_time=start_time, stop_time=stop_time,
                              coordinate_system=coordinate_system, debug=debug, **kwargs)
        if var:
            if not hasattr(var.values, 'unit'):
                var.values *= units.km
        return var

    def get_orbit(self, *args, **kwargs) -> SpeasyVariable or None:
        deprecation("Use get_trajectory instead, get_orbit will be removed in speasy 1.0")
        return self.get_trajectory(*args, **kwargs)

    @AllowedKwargs(
        PROXY_ALLOWED_KWARGS + CACHE_ALLOWED_KWARGS + ['product', 'start_time', 'stop_time', 'coordinate_system',
                                                       'debug'])
    @Cacheable(prefix="ssc_orbits", fragment_hours=lambda x: 24, version=version, entry_name=_make_cache_entry_name)
    @Proxyfiable(GetProduct, get_parameter_args)
    def _get_orbit(self, product: str, start_time: datetime, stop_time: datetime, coordinate_system: str = 'gse',
                   debug=False) -> Optional[SpeasyVariable]:
        p_range = self.parameter_range(product)
        if not p_range.intersect(DateTimeRange(start_time, stop_time)):
            log.warning(f"You are requesting {product} outside of its definition range {p_range}")
            return None
        if stop_time - start_time < timedelta(days=1):
            stop_time += timedelta(days=1)
        url = f"{self.__url}/locations/{product}/{start_time.strftime('%Y%m%dT%H%M%SZ')},{stop_time.strftime('%Y%m%dT%H%M%SZ')}/{coordinate_system.lower()}/"
        if debug:
            print(url)
        res = http.get(url, headers={"Accept": "application/json"})
        orbit = res.json()
        if res.ok and _is_valid(orbit):
            return _variable(orbit)[start_time:stop_time]
        return None
