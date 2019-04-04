# -*- coding: utf-8 -*-

"""cdaweb package for Space Physics WebServices Client."""

__author__ = """Alexis Jeandet"""
__email__ = 'alexis.jeandet@member.fsf.org'
__version__ = '0.1.0'


from typing import Optional
from datetime import datetime, timedelta
import pandas as pds
import requests
from ..cache import _cache
from ..common.datetime_range import DateTimeRange


class cdaweb:
    def __init__(self):
        self.__url = "https://cdaweb.gsfc.nasa.gov/WS/cdasr/1"

    def get_dataviews(self):
        resp = requests.get(self.__url + '/dataviews', headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        dataviews = [dv['Id'] for dv in resp.json()['DataviewDescription']]
        return dataviews

    def get_instruments(self, dataview='sp_phys', observatory=None, instrumentType=None):
        args = []
        if observatory is not None:
            args.append(f'observatory={observatory}')
        if instrumentType is not None:
            args.append(f'instrumentType={instrumentType}')
        resp = requests.get(self.__url + f'/dataviews/{dataview}/instruments?' + "&".join(args),
                            headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        instruments = [instrument for instrument in resp.json()['InstrumentDescription'] if
                       instrument['Name'] is not '']
        return instruments

    def get_datasets(self, dataview='sp_phys', observatoryGroup=None, instrumentType=None, observatory=None,
                     instrument=None,
                     startDate=None, stopDate=None, idPattern=None, labelPattern=None, notesPattern=None):
        args = []
        if observatory is not None:
            args.append(f'observatory={observatory}')
        if observatoryGroup is not None:
            args.append(f'observatoryGroup={observatoryGroup}')
        if instrumentType is not None:
            args.append(f'instrumentType={instrumentType}')
        if instrument is not None:
            args.append(f'instrument={instrument}')
        if startDate is not None:
            args.append(f'startDate={startDate}')
        if stopDate is not None:
            args.append(f'stopDate={stopDate}')
        if idPattern is not None:
            args.append(f'idPattern={idPattern}')
        if labelPattern is not None:
            args.append(f'labelPattern={labelPattern}')
        if notesPattern is not None:
            args.append(f'notesPattern={notesPattern}')

        resp = requests.get(self.__url + f'/dataviews/{dataview}/datasets?' + "&".join(args),
                            headers={"Accept": "application/json"})
        if not resp.ok:
            return None
        datasets = [dataset for dataset in resp.json()['DatasetDescription']]
        return datasets

    def get_variables(self, dataset, dataview='sp_phys'):
        resp = requests.get(self.__url + f'/dataviews/{dataview}/datasets/{dataset}/variables',
                            headers={"Accept": "application/json"})

        if not resp.ok:
            return None
        variables = [varaible for varaible in resp.json()['VariableDescription']]
        return variables

    def _dl_variable(self, dataset: str, variable: str, tstart: datetime, tend: datetime) -> Optional[pds.DataFrame]:
        tstart, tend = tstart.strftime('%Y%m%dT%H%M%SZ'), tend.strftime('%Y%m%dT%H%M%SZ')
        resp = requests.get(
            f"{self.__url}/dataviews/sp_phys/datasets/{dataset}/data/{tstart},{tend}/{variable}?format=csv",
            headers={"Accept": "application/json"})
        if not resp.ok or 'FileDescription' not in resp.json():
            return None
        return pds.read_csv(resp.json()['FileDescription'][0]['Name'], comment='#', index_col=0,
                            infer_datetime_format=True, parse_dates=True)

    def get_variable(self, dataset: str, variable: str, tstart: datetime, tend: datetime) -> Optional[pds.DataFrame]:
        result = None
        cache_product = f"cdaweb/{dataset}/{variable}"
        if (tend-tstart) <= timedelta(minutes=1):
            tend += timedelta(minutes=5)
        hit = _cache.get_data(cache_product, DateTimeRange(tstart, tend))
        for df in hit:
            if result is None:
                result = df
            elif df is not None:
                if result.index[0] > df.index[-1]:
                    result = pds.concat([df, result])
                else:
                    result = pds.concat([result, df])

        miss = _cache.get_missing_ranges(cache_product, DateTimeRange(tstart, tend))
        for slice in miss:
            df = self._dl_variable(dataset, variable, slice.start_time, slice.stop_time)
            _cache.add_entry(cache_product,slice.start_time, slice.stop_time, df)
            if result is None:
                result = df
            elif df is not None:
                if result.index[0] > df.index[-1]:
                    result = pds.concat([df, result])
                else:
                    result = pds.concat([result, df])
        return result
