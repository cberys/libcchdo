''' libcchdo.ctd.netcdf_oceansites '''

from libcchdo import grav_ocean_surface_wrt_latitude, depth

from datetime import datetime

from format import format

WOCE_to_OceanSITES_flag = {
  1: 3, # Not calibrated -> Bad data that are potentially correctable (re-calibration)
  2: 1, # Acceptable measurement -> Good data
  3: 2, # Questionable measurement -> Probably good data
  4: 4, # Bad measurement -> Bad data
  5: 9, # Not reported -> Missing value
  6: 8, # Interpolated over >2 dbar interval -> Interpolated value
  7: 5, # Despiked -> Value changed
  9: 9  # Not sampled -> Missing value
}

TIMESERIES_INFO = {
  'BATS': {
    'platform_code': 'BATS',
    'institution': 'Bermuda Institute of Ocean Sciences',
    'institution_references': 'http://bats.bios.edu/',
    'site_code': 'BIOS-BATS',
    'references': 'http://cchdo.ucsd.edu/search?query=group:BATS',
    'comment': 'BIOS-BATS CTD data from SIO, translated to OceanSITES NetCDF by SIO',
    'summary': 'BIOS-BATS CTD data Bermuda',
    'area': 'Atlantic - Sargasso Sea',
    'institution_references': 'http://bats.bios.edu/',
    'contact': 'rodney.johnson@bios.edu',
    'pi_name': 'Rodney Johnson',
    'id': 'OS_BERMUDA_%s_SOT',
  },
  'HOT': {
    'platform_code': 'HOT',
    'institution': "University of Hawai'i School of Ocean and Earth Science and Technology",
    'site_code': 'ALOHA',
    'references': 'http://cchdo.ucsd.edu/search?query=group:HOT',
    'comment': 'HOT CTD data from SIO, translated to OceanSITES NetCDF by SIO',
    'summary': "HOT CTD data Hawai'i",
    'area': "Pacific - Hawai'i",
    'institution_references': 'http://hahana.soest.hawaii.edu/hot/hot_jgofs.html',
    'contact': 'santiago@soest.hawaii.edu',
    'pi_name': 'Roger Lukas',
    'id': 'OS_ALOHA_%s_SOT',
  },
}

class netcdf_oceansites(format):
  #def read(self, handle): TODO
  def write(self, handle, timeseries=None, timeseries_info={}):
    '''How to write a CTD NetCDF OceanSITES file.'''
    filename = handle.name
    handle.close()
    strdate = str(self.globals['DATE']) 
    strtime = str(self.globals['TIME']).rjust(4, '0')
    isowocedate = datetime(int(strdate[0:4]), int(strdate[5:7]), int(strdate[8:10]),
		                       int(strtime[0:2]), int(strtime[3:5]))
    nc_file = Dataset(filename, 'w', format='NETCDF3_CLASSIC')
    nc_file.data_type = 'OceanSITES time-series CTD data'
    nc_file.format_version = '1.1'
    nc_file.date_update = datetime.utcnow().isoformat()+'Z'
    nc_file.wmo_platform_code = ''
    nc_file.source = 'Shipborne observation'
    nc_file.history = isowocedate.isoformat()+"Z data collected\n"+
      datetime.utcnow().isoformat()+"Z date file translated/written"
    nc_file.data_mode = 'D'
    nc_file.quality_control_indicator = '1'
    nc_file.quality_index = 'B'
    nc_file.conventions = 'OceanSITES Manual 1.1, CF-1.1'
    nc_file.netcdf_version = '3.x'
    nc_file.naming_authority = 'OceanSITES'
    nc_file.cdm_data_type = 'Station'
    nc_file.geospatial_lat_min = str(self.globals['LATITUDE'])
    nc_file.geospatial_lat_max = str(self.globals['LATITUDE'])
    nc_file.geospatial_lon_min = str(self.globals['LONGITUDE'])
    nc_file.geospatial_lon_max = str(self.globals['LONGITUDE'])
    nc_file.geospatial_vertical_min = int(self.globals['DEPTH'])
    nc_file.geospatial_vertical_max = 0
    nc_file.author = 'Shen:Diggs (Scripps)'
    nc_file.data_assembly_center = 'SIO'
    nc_file.distribution_statement = ('Follows CLIVAR (Climate Varibility and'
      'Predictability) standards, cf. '
      'http://www.clivar.org/data/data_policy.php. Data available free of '
      'charge. User assumes all risk for use of data. User must display '
      'citation in any publication or product using data. User must contact '
      'PI prior to any commercial use of data.')
    nc_file.citation = ('These data were collected and made freely available '
                        'by the OceanSITES project and the national programs '
                        'that contribute to it.')
    nc_file.update_interval = 'void'
    nc_file.qc_manual = "OceanSITES User's Manual v1.1"
    nc_file.time_coverage_start = isowocedate.isoformat()+'Z'
    nc_file.time_coverage_end = isowocedate.isoformat()+'Z'

    nc_file.createDimension('TIME')
    nc_file.createDimension('DEPTH', len(self))
    nc_file.createDimension('LATITUDE', 1)
    nc_file.createDimension('LONGITUDE', 1)
    nc_file.createDimension('POSITION', 1)

    # OceanSITES coordinate variables
    var_time = nc_file.createVariable('TIME', 'd', ('TIME',))
    var_time.long_name = 'time'
    var_time.standard_name = 'time'
    var_time.units = 'days since 1950-01-01T00:00:00Z'
    var_time._FillValue = 999999.0
    var_time.valid_min = 0.0
    var_time.valid_max = 90000.0
    var_time.QC_indicator = 7 # Matthias Lankhorst
    var_time.QC_procedure = 5 # Matthias Lankhorst
    var_time.uncertainty = 0.0417 # 1/24 assuming a typical cast lasts one hour Matthias Lankhorst
    var_time.axis = 'T'

    var_latitude = nc_file.createVariable('LATITUDE', 'f', ('LATITUDE',))
    var_latitude.long_name = 'Latitude of each location'
    var_latitude.standard_name = 'latitude'
    var_latitude.units = 'degrees_north'
    var_latitude._FillValue = 99999.0
    var_latitude.valid_min = -90.0
    var_latitude.valid_max = 90.0
    var_time.QC_indicator = 7 # Matthias Lankhorst
    var_time.QC_procedure = 5 # Matthias Lankhorst
    var_latitude.uncertainty = 0.0045 # Matthias Lankhorst
    var_latitude.axis = 'Y'

    var_longitude = nc_file.createVariable('LONGITUDE', 'f', ('LONGITUDE',))
    var_longitude.long_name = 'Longitude of each location'
    var_longitude.standard_name = 'longitude'
    var_longitude.units = 'degrees_east'
    var_longitude._FillValue = 99999.0
    var_longitude.valid_min = -180.0
    var_longitude.valid_max = 180.0
    var_time.QC_indicator = 7 # Matthias Lankhorst
    var_time.QC_procedure = 5 # Matthias Lankhorst
    var_longitude.uncertainty = 0.0045/cos(self.globals['LATITUDE']) # Matthias Lankhorst
    var_longitude.axis = 'X'

    var_depth = nc_file.createVariable('DEPTH', 'f', ('DEPTH',))
    var_depth.long_name = 'Depth of each measurement'
    var_depth.standard_name = 'depth'
    var_depth.units = 'meters'
    var_depth._FillValue = -99999.0
    var_depth.valid_min = 0.0
    var_depth.valid_max = 12000.0
    var_depth.QC_indicator = 8 # Subject: OceanSITES: more on QC flags, uncertainty, depth Interpolated from latitude and pressure.
    var_depth.QC_procedure = 2 # See above
    var_depth.uncertainty = 1.0 # A decibar
    var_depth.axis = 'down' # oceanic

    since_1950 = isowocedate - datetime(1950, 1, 1)
    var_time[:] = [since_1950.days + since_1950.seconds/86400.0]
    var_latitude[:] = [self.globals['LATITUDE']]
    var_longitude[:] = [self.globals['LONGITUDE']]

    # CTD variables
    param_to_oceansites = {
      'ctd_pressure': 'PRES',
      'ctd_temperature': 'TEMP',
      'ctd_oxygen': 'DOXY',
      'ctd_salinity': 'PSAL',
    }
    oceansites_variables = {
      'TEMP': {'long': 'sea water temperature', 'std': 'sea_water_temperature', 'units': 'degree_Celsius'},
      'DOXY': {'long': 'dissolved oxygen', 'std': 'dissolved_oxygen', 'units': 'micromole/kg'},
      'PSAL': {'long': 'sea water salinity', 'std': 'sea_water_salinity', 'units': 'psu'},
      'PRES': {'long': 'sea water pressure', 'std': 'sea_water_pressure', 'units': 'decibars'}, # valid_min 0.0, valid_max 12000.0, QC_indicator =7, QC_procedure = 5, uncertainty 2.0
    }
    oceansites_uncertainty = {
      'TEMP': 0.002,
      'PSAL': 0.005,
      'DOXY': float('inf'),
      'PRES': float('inf'),
    }

    for column in self.columns.values():
      name = column.parameter.description.lower().replace(' ', '_').replace('(', '_').replace(')', '_')
      if name in param_to_oceansites.keys():
        name = param_to_oceansites[name]
      # Write variable
        var = nc_file.createVariable(name, 'f8', ('DEPTH',))
        variable = oceansites_variables[name]
        var.long_name = variable['long'] or ''
        var.standard_name = variable['std'] or ''
        var.units = variable['units'] or ''
        var._FillValue = float('nan') # TODO ref table 3
        var.QC_procedure = 5 # Data manually reviewed
        var.QC_indicator = 2 # Probably good data
        var.valid_min = column.parameter.bound_lower
        var.valid_max = column.parameter.bound_upper
        var.sensor_depth = -999 # TODO nominal sensor depth in meters positive in direction of DEPTH:positive
        var.cell_methods = 'TIME: point DEPTH: average LATITUDE: point LONGITUDE: point'
        var.uncertainty = oceansites_uncertainty[name]
        var[:] = column.values
      if name is 'PRES':
        # Fun using Sverdrup's depth integration with density.
        localgrav = grav_ocean_surface_wrt_latitude(self.globals['LATITUDE'])
        density_series = [density(*args) for args in zip(self.columns['CTDSAL'].values, self.columns['CTDTMP'].values, column.values)]
        depth_series = depth(localgrav, column.values, density_series)

        #depth_series = map(lambda pres: depth_unesco(pres, self.globals['LATITUDE']), self.columns['CTDPRS'].values)

        var_depth[:] = depth_series
      # Write QC variable
      if column.is_flagged_woce():
        var.ancillary_variables = name+'_QC'
        flag = nc_file.createVariable(name+'_QC', 'b', ('DEPTH',))
        flag.long_name = 'quality flag'
        flag.conventions = 'OceanSITES reference table 2'
        flag._FillValue = -128
        flag.valid_min = 0
        flag.valid_max = 9
        flag.flag_values = 0#, 1, 2, 3, 4, 5, 6, 7, 8, 9 TODO??
        flag.flag_meanings = ' '.join(['no_qc_performed',
                                       'good_data',
                                       'probably_good_data',
                                       'bad_data_that_are_potentially_correctable',
                                       'bad_data',
                                       'value_changed',
                                       'not_used',
                                       'nominal_value',
                                       'interpolated_value',
                                       'missing_value'
                                      ])
        flag[:] = map(lambda x: WOCE_to_OceanSITES_flag[x], column.flags_woce)
    # Write timeseries information, if given
    if (timeseries and timeseries in TIMESERIES_INFO) or timeseries_info:
      if timeseries:
          timeseries_info = TIMESERIES_INFO[timeseries]
      nc_file.title = '%s CTD Timeseries ExpoCode=%s Station=%s Cast=%s' %
        (timeseries_info['platform_code'], self.globals['EXPOCODE'],
         self.globals['STNNBR'], self.globals['CASTNO'])
      strdate = str(self.globals['DATE']) 
      isodate = datetime(int(strdate[0:4]), int(strdate[5:7]), int(strdate[8:10]), 0, 0)
      stringdate = isodate.date().isoformat().replace('-', '')

      variables_to_transfer = '''platform_code institution institution_references
        site_code references comment summary area institution_references contact
        pi_name'''.split()
      for var in variables_to_transfer:
        nc_file.__setattr__(var, timeseries_info[var])
      nc_file.id = timeseries_info['id'] % stringdate
    nc_file.close()
