import numpy as np
import pandas as pds
from datetime import datetime
from typing import List, Optional
from speasy.core import deprecation
from copy import deepcopy

import astropy.units
import astropy.table


def _to_index(key, time):
    if key is None:
        return None
    if type(key) is int:
        return key
    if isinstance(key, float):
        return np.searchsorted(time, np.datetime64(int(key * 1e9), 'ns'), side='left')
    if isinstance(key, datetime):
        return np.searchsorted(time, np.datetime64(key, 'ns'), side='left')


class SpeasyVariable(object):
    """SpeasyVariable object. Base class for storing variable data.

    Attributes
    ----------
    time: numpy.ndarray
        time vector (x-axis data)
    data: numpy.ndarray
        data
    meta: Optional[dict]
        metadata
    columns: Optional[List[str]]
        column names
    y: Optional[np.ndarray]
        y-axis for 2D data

    Methods
    -------
    view:
        Return view of the current variable within the desired :data:`time_range`
    to_dataframe:
        Convert the variable to a pandas.DataFrame object
    plot:
        Plot the data with matplotlib

    """
    __slots__ = ['meta', 'time', 'values', 'columns', 'y']

    def __init__(self, time=np.empty(0, dtype=np.dtype('datetime64[ns]')), data=np.empty((0, 1)),
                 meta: Optional[dict] = None,
                 columns: Optional[List[str]] = None, y: Optional[np.ndarray] = None):
        """Constructor
        """

        if time.dtype != np.dtype('datetime64[ns]'):
            raise ValueError(f"Please provide datetime64[ns] for time axis, got {time.dtype}")
        if len(time) != len(data):
            raise ValueError(f"Time and data must have the same length, got time:{len(time)} and data:{len(data)}")

        self.meta = meta or {}
        self.columns = columns or []
        if len(data.shape) == 1:
            self.values = data.reshape((data.shape[0], 1))  # to be consistent with pandas
        else:
            self.values = data
        self.time = time
        self.y = y

    def view(self, index_range: slice):
        """Return view of the current variable within the desired :data:`time_range`.

        Parameters
        ----------
        index_range: slice
            index range

        Returns
        -------
        speasy.common.variable.SpeasyVariable
            view of the variable on the given range
        """
        return SpeasyVariable(self.time[index_range], self.values[index_range], self.meta, self.columns,
                              self.y[index_range] if (
                                  self.y is not None and self.y.shape == self.values.shape) else self.y)

    def __eq__(self, other: 'SpeasyVariable') -> bool:
        """Check if this variable equals another.

        Parameters
        ----------
        other: speasy.common.variable.SpeasyVariable
            another SpeasyVariable object to compare with

        Returns
        -------
        bool:
            True if all attributes are equal
        """
        return self.meta == other.meta and \
               self.columns == other.columns and \
               len(self.time) == len(other.time) and \
               np.all(self.time == other.time) and \
               np.all(self.values == other.values)

    def __len__(self):
        return len(self.time)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.view(slice(_to_index(key.start, self.time), _to_index(key.stop, self.time)))

    def to_dataframe(self) -> pds.DataFrame:
        """Convert the variable to a pandas.DataFrame object.

        Parameters
        ----------
        Returns
        -------
        pandas.DataFrame:
            Variable converted to Pandas DataFrame
        """
        return pds.DataFrame(index=self.time, data=self.values, columns=self.columns, copy=True)

    def to_astropy_table(self) -> astropy.table.Table:
        """Convert the variable to a astropy.Table object.

        Parameters
        ----------
        datetime_index: bool
            boolean indicating that the index is datetime

        Returns
        -------
        astropy.Table:
            Variable converted to astropy.Table
        """
        try:
            units = astropy.units.Unit(self.meta["PARAMETER_UNITS"])
        except (ValueError, KeyError):
            units = None
        df = self.to_dataframe()
        umap = {c: units for c in df.columns}
        return astropy.table.Table.from_pandas(df, units=umap, index=True)

    def plot(self, *args, **kwargs):
        """Plot the variable.

        See https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.plot.html

        """
        return self.to_dataframe().plot(*args, **kwargs)

    @property
    def data(self):
        deprecation('data will be removed soon')
        return self.values

    @data.setter
    def data(self, values):
        deprecation('data will be removed soon')
        self.values = values

    @staticmethod
    def from_dataframe(df: pds.DataFrame) -> 'SpeasyVariable':
        """Load from pandas.DataFrame object.

        Parameters
        ----------
        dr: pandas.DataFrame
            Input DataFrame to convert

        Returns
        -------
        SpeasyVariable:
            Variable created from DataFrame
        """
        if df.index.dtype == np.dtype('datetime64[ns]'):
            time = np.array(df.index)
        elif hasattr(df.index[0], 'timestamp'):
            time = np.array([np.datetime64(d.timestamp() * 1e9, 'ns') for d in df.index])
        else:
            raise ValueError("Can't convert DataFrame index to datetime64[ns] array")
        return SpeasyVariable(time=time, data=df.values, meta={}, columns=list(df.columns))

    @staticmethod
    def epoch_to_datetime64(epoch_array: np.array):
        return (epoch_array * 1e9).astype('datetime64[ns]')

    def replace_fillval_by_nan(self, inplace=False) -> 'SpeasyVariable':
        if inplace:
            res = self
        else:
            res = deepcopy(self)
        if 'FILLVAL' in res.meta:
            res.data[res.data == res.meta['FILLVAL']] = np.nan
        return res


def from_dataframe(df: pds.DataFrame) -> SpeasyVariable:
    """Convert a dataframe to SpeasyVariable.

    See Also
    --------
    SpeasyVariable.from_dataframe
    """
    return SpeasyVariable.from_dataframe(df)


def to_dataframe(var: SpeasyVariable) -> pds.DataFrame:
    """Convert a :class:`~speasy.common.variable.SpeasyVariable` to pandas.DataFrame.

    See Also
    --------
    SpeasyVariable.to_dataframe
    """
    return SpeasyVariable.to_dataframe(var)


def merge(variables: List[SpeasyVariable]) -> Optional[SpeasyVariable]:
    """Merge a list of :class:`~speasy.common.variable.SpeasyVariable` objects.

    Parameters
    ----------
    variables: List[SpeasyVariable]
        Variables to merge together

    Returns
    -------
    SpeasyVariable:
        Resulting variable from merge operation
    """
    if len(variables) == 0:
        return None
    sorted_var_list = [v for v in variables if (v is not None) and (len(v.time) > 0)]
    sorted_var_list.sort(key=lambda v: v.time[0])

    # drop variables covered by previous ones
    for prev, current in zip(sorted_var_list[:-1], sorted_var_list[1:]):
        if prev.time[-1] >= current.time[-1]:
            sorted_var_list.remove(current)

    # drop variables covered by next ones
    for current, nxt in zip(sorted_var_list[:-1], sorted_var_list[1:]):
        if nxt.time[0] == current.time[0] and nxt.time[-1] >= current.time[-1]:
            sorted_var_list.remove(current)

    if len(sorted_var_list) == 0:
        return SpeasyVariable(columns=variables[0].columns, meta=variables[0].meta, y=variables[0].y)

    overlaps = [np.where(current.time >= nxt.time[0])[0][0] if current.time[-1] >= nxt.time[0] else -1 for current, nxt
                in
                zip(sorted_var_list[:-1], sorted_var_list[1:])]

    dest_len = int(np.sum(
        [overlap if overlap != -1 else len(r.time) for overlap, r in zip(overlaps, sorted_var_list[:-1])]))
    dest_len += len(sorted_var_list[-1].time)

    time = np.zeros(dest_len, dtype=np.dtype('datetime64[ns]'))
    data = np.zeros((dest_len,) + sorted_var_list[0].values.shape[1:])
    if sorted_var_list[0].y is not None:
        if sorted_var_list[0].y.shape == sorted_var_list[0].values.shape:
            y = np.zeros((dest_len,) + sorted_var_list[0].y.shape[1:])
        else:
            y = sorted_var_list[0].y
    else:
        y = None

    units = set([var.values.unit for var in sorted_var_list if hasattr(var.values, 'unit')])
    if len(units) == 1:
        data <<= units.pop()

    pos = 0
    for r, overlap in zip(sorted_var_list, overlaps + [-1]):
        frag_len = len(r.time) if overlap == -1 else overlap
        time[pos:(pos + frag_len)] = r.time[0:frag_len]
        data[pos:(pos + frag_len)] = r.values[0:frag_len]
        if y is not None and len(y.shape) == 2:
            y[pos:(pos + frag_len)] = r.y[0:frag_len]
        pos += frag_len
    return SpeasyVariable(time, data, sorted_var_list[0].meta, sorted_var_list[0].columns, y=y)
