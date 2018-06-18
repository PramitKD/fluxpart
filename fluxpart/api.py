from .fluxpart import fvspart


def fvs_partition(
    file_or_dir,
    ext="",
    interval="30min",
    hfd_format=None,
    hfd_options=None,
    meas_wue=None,
    wue_options=None,
    part_options=None,
    label=None,
):
    """Partition CO2 & H2O fluxes into stomatal & nonstomatal components.

    Provides a full implementation of the flux variance similarity
    partitioning algorithm [SS08]_[SAAS+18]_: reads high frequency eddy
    covariance data; performs data transformations and data QA/QC;
    analyzes water vapor and carbon dioxide fluxes; and partitions the
    fluxes into stomatal (transpiration, photosynthesis) and nonstomatal
    (evaporation, respiration) components.

    The following notation is used in variable naming and documentation
    to represent meteorological quantities::

        u, v, w = wind velocities
        q = water vapor mass concentration
        c = carbon dioxide mass concentration
        T = air temperature
        P = total air pressure

    Parameters
    ----------
    file_or_dir : str or list of str
        High frequency eddy covariance data file, data directory, or
        list of either. If a directory or list of directories is passed,
        data files within the directory(s) will be analyzed.
    ext : str, optional
        When `file_or_dir` is a directory(s), all files with extension
        `ext` will be read. Default ("") reads all files regardless of
        extension. When specifying `ext`, include the "dot" where
        appropriate (e.g., ext=".dat")
    interval : str, optional
        Time interval used to aggregate data and partition fluxes.
        Specified using the pandas string alias_ format (e.g.,
        ``interval="30min"``. Set to None to process whole data files
        without consideration of time or  date. Default is "30min".
    hfd_format : dict or {"ec-TOB1", "ec-TOA5"}, optional
        Dictionary of parameters specifying the high frequency data file
        format. See ``Other parameters`` below for an explanation of
        required and optional formatting parameters. Some pre-defined
        file formats can be specified by passing a string instead of a
        dictionary.  Currently two formats are defined: "ec-TOB1" and
        "ec-TOA5".  These formats correspond to files commonly created
        when using Campbell Scientific eddy covariance data logger
        software. See ``Notes`` below for an explanation of these
        pre-defined formats. Default is "ec-TOB1".
    hfd_options : dict, optional
        Dictionary of parameters specifying options for correcting
        high-frequency eddy covariance data and applying quality control
        measures. See ``Other parameters`` for a listing of options.
    meas_wue : float or callable, optional
        Measured (or otherwise prescribed) leaf-level water use
        efficiency (kg CO2 / kg H2O). Note that by definition,
        `meas_wue` must be a negative value (< 0). If callable, it
        should take a datetime object as its sole argument and return a
        float value.
    wue_options : dict, required if `meas_wue` is not provided
        Dictionary of parameters and options used to estimate water use
        efficiency if `meas_wue` is not provided. See ``Other
        parameters`` section for a description of valid fields.  When
        passing `wue_options`, it is always required to provide entries
        'canopy_ht', 'meas_ht', and 'ppath'. Other entries are optional.
        The values for 'canopy_ht' and 'meas_ht' can be either a float
        or a callable. A callable must accept a datetime object as its
        sole argument and return a float value.
    part_options : dict, optional
        Dictionary of options for the fvs partitioning procedure. See
        ``Other parameters`` section for a listing of valid options.
    label : optional
        Optional identifier to be appended to the results.


    Returns
    -------
    :class:`~fluxpart.fluxpart.FluxpartResult`


    Other Parameters
    ----------------
    hfd_format : dict
        High frequency data file format options. NOTE: When passing
        hfd_format, it is required at a minimum to provide values for
        'filetype' and 'cols' (detailed below).  'unit_convert' and
        'temper_unit' are also required if data are not in SI units.
    hfd_format['filetype'] : {'csv', 'tob1', 'pd.df'}
        'csv' = delimited text file; 'tob1' = Campbell Scientific binary
        data table format; 'pd.df' = pandas dataframe.
    hfd_format['cols'] : 7*(int,)
        7-tuple of integers indicating the data column numbers that
        contain series data for (u, v, w, c, q, T, P), in that order.
        Uses 0-based indexing.
    hfd_format['unit_convert'] : dict
        Dictionary of multiplication factors required to convert any u,
        v, w, c, q, or P data not in SI units to SI units (m/s, kg/m^3,
        Pa). (Note T is not in that list). The dictionary keys are the
        variable names. For example, if all data are in SI units except
        P and c, which are in kPa and mg/m^3, respectively, then set:
        ``hfd_options['unit_convert'] = {'P': 1e3, 'c': 1e-6}``,
        since it is necessary to multiply the kPa pressure data by 1e3
        to obtain the SI pressure unit (Pa), and the mg/m^3 CO2 data by
        1e-6 to obtain the SI concentration unit (kg/m^3).
    hfd_format['temper_unit'] : {'K', 'C'}
        Temperature data units. Default is 'K' (Kelvin).
    hfd_format['flags'] : 2-tuple or list of 2-tuples
        Specifies that one or more data columns are used to flag bad
        data records. Each tuple is of the form (col, goodval), where
        col is an int specifying the column number containing the flag
        (0-based indexing), and goodval is the value of the flag that
        indicates a good data record.
    hfd_format[ other keys ]
        when `hfd_format['filetype']` is 'csv', all other key:value
        pairs in `hfd_format` are passed as keyword arguments to
        pandas.read_csv_. Those keywords may be required to specify the
        details of the file formatting. Among the most commonly required
        are: 'sep', the str that is used to separate values or define
        column widths (default is sep=','); and 'skiprows', which will
        be needed if the file contains header rows. See pandas.read_csv_
        for a full description of available format options.

    hfd_options: dict
        Options for pre-processing high frequency data.
    hfd_options['correct_external'] : bool, optional
        If True (default), the water vapor and carbon dioxide series
        data are corrected for external fluctuations associated with air
        temperature and vapor density according to [WPL80]_ and [DK07]_.
    hfd_options['bounds'] : dict, optional
        Dictionary indicating any lower and upper bounds for valid data.
        Dictionary entries have the form ``varname: (float, float)``,
        where varname is one of 'u', 'v', 'w', 'q', 'c', 'T', or 'P',
        and the 2-tuple holds values for the lower and upper bounds:
        ``(lower, upper)``.  Data records are rejected if a variable in
        the record is outside the prescribed bounds. Default is ``bounds
        = {'c': (0, np.inf), 'q': (0, np.inf)}`` such that data records
        are rejected if c or q data are not positive values.
    hfd_options['rd_tol'] : float, optional
        Relative tolerance for rejecting the datafile. Default is
        'hfd_options['rd_tol']` = 0.4. See hfd_options['ad_tol'] for
        further explanation.
    hfd_options['ad_tol'] : int, optional
        Absolute tolerance for rejecting the datafile. Default is
        `ad_tol` = 1024. If the datafile contains bad records (not
        readable, out-of-bounds, or flagged data), the partitioning
        analysis is performed using the longest stretch of consecutive
        good data records found, unless that stretch is too short, in
        which case the analysis is aborted. The criteria for judging
        'too short' can be specified in both relative and absolute
        terms: the datafile is rejected if the good stretch is a
        fraction of the total data that is less than `rd_tol`, and/or is
        less than `ad_tol` records long.
    hfd_options['ustar_tol'] : float
        If the friction velocity (m/s) determined from the high
        frequency data is less than `ustar_tol`, the
        partitioning analysis is aborted due to insufficient turbulence.
        Defalult is `hfd_options['ustar_tol']` = 0.1 (m/s).

    wue_options: dict
        Parameters for estimating water use efficiency. 'canopy_ht',
        'meas_ht', and 'ppath' are required keys.
    wue_options['canopy_ht'] : float or callable
        Vegetation canopy height (m). If callable must accept a datetime
        object as its sole argument and return a float value.
    wue_options['meas_ht'] : float or callable
        Eddy covariance measurement height (m). If callable must accept
        a datetime object as its sole argument and return a float value.
    wue_options['ppath'] : {'C3', 'C4'}
        Photosynthetic pathway.
    wue_options['ci_mod'] : str
        Valid values: 'const_ratio', 'const_ppm', 'linear', 'sqrt'.
        See: :func:`~fluxpart.wue.water_use_efficiency`.
    wue_options['ci_mod_param'] : float or (float, float)
        Paramter values to be used with `ci_mod`.
        See: :func:`~fluxpart.wue.water_use_efficiency`.
    wue_options['leaf_temper'] : float
        Canopy leaf temperature (K). If not specified, it is assumed to
        be equal to the air temperature See:
        :func:`~fluxpart.wue.water_use_efficiency`.
    wue_options['leaf_temper_corr'] : float
        Offset adjustment applied to canopy temperature (K). Default is
        zero. See: :func:`~fluxpart.wue.water_use_efficiency`.
    wue_options['diff_ratio']: float, optional
        Ratio of molecular diffusivities for water vapor and CO2.
        Default is `diff_ratio` = 1.6.
        See: :func:`~fluxpart.wue.water_use_efficiency`.

    part_options : dict
        Options for the fvs partitioning algorithm
    part_options['adjust_fluxes'] : bool
        If True (default), the final partitioned fluxes are adjusted
        proportionally such that sum of the partitioned fluxes match
        exactly the total fluxes indicated in the original data.
    part_options['sun'] : 2-tuple = (sunrise, sunset), or callable
        A 2-tuple of times corresponding to sunrise and sunset. If
        specified, fluxes for times starting  before sunrise or after
        sunset will be taken to be all non-stomatal. If callable,
        it should take a datetime as its sole argument and return the
        2-tuple of times. Default is (None, None).


    NOTES
    -----
    Two pre-defined hfd_formats are available, 'ec.TOA5' and 'ec.TOB1'.

    'ec.TOA5'::

        hfd_format = {
            "filetype": 'csv',
            "skiprows": 4,
            "cols": (2, 3, 4, 5, 6, 7, 8),
            "time_col": 0,
            "temper_unit": 'C',
            "unit_convert": {"q": 1e-3, "c": 1e-6, "P": 1e3},

        }

    'ec.TOB1'::

        hfd_format = {
            "filetype": 'tob1',
            'cols': (3, 4, 5, 6, 7, 8, 9),
            "temper_unit": 'C',
            "unit_convert": {"q": 1e-3, "c": 1e-6, "P": 1e3},
        }


    .. _pandas.read_csv:
        https://pandas.pydata.org/pandas-docs/stable/generated/pandas.read_csv.html

    .. _alias:
        http://pandas.pydata.org/pandas-docs/stable/timeseries.html#offset-aliases

    """
    return fvspart(
        file_or_dir,
        ext,
        interval,
        hfd_format,
        hfd_options,
        meas_wue,
        wue_options,
        part_options,
        label,
    )
