#!/usr/bin/python
#
#!/usr/bin/env /usr/bin/python
#
#----------------------------------------------------------------------------
#   Copyright 2016 Florian Schumacher (Ruhr-Universitaet Bochum, Germany)
#
#   This file is part of ASKI version 1.2.
#
#   ASKI version 1.2 is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 2 of the License, or
#   (at your option) any later version.
#
#   ASKI version 1.2 is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with ASKI version 1.2.  If not, see <http://www.gnu.org/licenses/>.
#----------------------------------------------------------------------------
#
# import python modules
from os import system as os_system
from os import environ as os_environ
from os import mkdir as os_mkdir
from os import path as os_path
from os import listdir as os_listdir
from os import access as os_access
from os import W_OK as os_W_OK
from os import X_OK as os_X_OK
from sys import exit as sys_exit
from sys import path as sys_path
from time import time as time_time
from time import ctime as time_ctime
#
# get SUN GRID ENGINE environmental variables (if any)
SGE_job_id = os_environ.get('JOB_ID')
runs_on_SGE = SGE_job_id is not None
SGE_o_workdir = os_environ.get('SGE_O_WORKDIR')
SGE_hostname = os_environ.get('HOSTNAME')
SGE_pe_hostfile = os_environ.get('PE_HOSTFILE')
if SGE_pe_hostfile is not None:
    SGE_pe_hostfile_content = open(SGE_pe_hostfile).read()
else:
    SGE_pe_hostfile_content = 'no content, file PE_HOSTFILE is empty'
#
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#
# IMPORTANT STUFF TO ADJUST
#
# import own modules
# when running in SUN GRID ENGINE (or maybe also on other HPC queueing systems), the PYTHONPATH
# environment variable must be additionally told, where your own python modules are, before you
# can import them. 
# There are two options here:
# 1) manually append the src path of your ASKI main package installation to variable sys_path:
#######sys_path.append("/home/florian/code/ASKI/src")
# 2) copy the files readEventStationFile.py and inputParameter.py to the path from which this
#    script is called. Then append current path "./" to the PYTHONPATH
sys_path.append("./")
# Following either 1) or 2), now the following modules can be imported:
from inputParameter import inputParameter
from readEventStationFile import eventList,stationList
#
# main parameter file of inversion
main_parfile = '/rscratch/minos27/Kernel/specfem3D/inversions/test/main_parfile_test_new_specfem3d'
#
# define the command which will be called (via system call) for each simulation;
# e.g. can be something like './process_solver_only.sh' along with using a different command in the first iteration (see below)
command_system_call = './process.sh'
#
# if in the VERY FIRST iteration (i.e. the first simulation that is done) a DIFFERENT
# command should be issued, indicate so by the following flag, and define the alternative command
use_different_command_in_first_simulation = False
command_system_call_first_simulation = './process.sh'
#
# say, if ASKI output volume, which is used in SPECFEM, should be defined by the inversion grid 
# definition of the current inversion grid (if possible)
define_ASKI_output_volume_by_inversion_grid = True
#
# OUTPUT_FILES_PATH and DATA_FILES_PATH (as used by SPECFEM3D_GLOBE)
# those paths must be defined RELATIVE to the current path, where this script is run from!!
OUTPUT_FILES_PATH = 'OUTPUT_FILES/'
LOCAL_PATH = 'DATABASES_MPI/'
DATA_FILES_PATH = 'DATA/'
#
# log file name, will be written to OUTPUT_FILES_PATH
logfile = 'run_specfem3dGlobeForASKI_simulations.log'
#
if runs_on_SGE:
    logfile += str(SGE_job_id)
#
# EMAILING LOGFILE SOMEWHERE
#
# set to False if no emails should be sent at all
send_emails = False
# email address, to which log notifications are sent
email_receiver= 'receiver@mail.domain'
email_sender = 'sender@mail.domain'
# if send_emails = True, the script always writes an email after the 1st iteration and at the end of all iterations (or if script exits unintendedly)
# number_of_intermediate_status_emails defines the number of additional emails in between (1st and last iteration) while iterating over the simulations
# set number_of_intermediate_status_emails = 0 if you do not want to receive any additional emails aside from the two after 1st and last iteration
number_of_intermediate_status_emails = 0
#
####################################################################################################################
## define the (order of the) specfem3dForASKI simulations by strings displ_simulations,gt_simulations,measured_data_simulations
## in the following way:
##
## string displ_simulations defines the events for which kernel_displacement output for ASKI is computed, 
## string gt_simulations defines the (components of) stations for which kernel_green_tensor output for ASKI is computed,
## string measurde_data_simuulations defines the events for which synthetically calculated "measured_data" can be computed
##   (w.r.t a perturbed model) in case of pure synthetic test studies, these are regular SPECFEM3D simulations without producing
##   any ASKI output (in general, these simulations are made separately from kernel simulations, as you will use a different
##   model and do not need to compute ASKI output for kernels)
##
## displ_simulations must be of one of the folling forms:
##   displ_simulations = ''
##      no kernel_displacement simulations will be done
##   displ_simulations = 'all'
##      in this case kernel_displacement output is computed for all events defined in FILE_EVENT_LIST
##   displ_simulations = 'Source024,Source002,Source005'
##      for all events in the ','-separated list of eventIDs (here 3 events: Source024, Source002 and Source005), 
##      kernel_displacement output is computed (eventIDs must be present in FILE_EVENT_LIST)
##   displ_simulations = 'all-except:S001,S002,S024'
##      all events are taken into account, except the ones defined by the ','-separated list of eventIDs
##      following the word 'all-except:'  (here all events except the three S001,S002 and S024)
##   IF THERE IS ANY INVALID eventID (i.e. not present in FILE_EVENT_LIST), THIS SCRIPT WILL RAISE AN ERROR!
##
## gt_simulations must be of one of the folling forms:
##   gt_simulations = ''
##      no kernel_green_tensor simulations will be done
##   gt_simulations = 'all'
##      in this case kernel_green_tensor output is computed for all stations defined in FILE_STATION_LIST for 
##      all components defined by gt_components (see below for form of gt_components)
##   gt_simulations = 'all-except:AT03,SYRO'
##      all stations are taken into account (at all components defined by gt_components), except the ones defined by 
##      the ','-separated list of station names following the word 'all-except:' (here all stations excpet AT03 and SYRO)
##   gt_simulations = 'specific'
##      in this case kernel_green_tensor output is computed for specific components of specific stations, BOTH
##      defined by gt_components (see below for form of gt_components)
##   IF THERE IS ANY INVALID station name (i.e. not present in FILE_STATION_LIST), THIS SCRIPT WILL RAISE AN ERROR!
##
## gt_components must be of the following form in case of gt_simulations being 'all' or 'all-except:...' :
##   gt_components = 'CX,CZ'
##     a ','-separated list of valid components (the currently supported components are the global Cartesian 
##     components 'CX','CY','CZ' and the local components 'N','E','UP')
##   IF THERE IS ANY INVALID COMPONENT, THIS SCRIPT WILL RAISE AN ERROR!
##
## gt_components must be of the following form in case of gt_simulations being 'specific' :
##   gt_components = 'TUR8:CX,CY,CZ;SYRO:UP;AT03:N,W'
##     a ';'-separated list of entries consisting of the station name and ':' followed by a ','-separated list of 
##     valid components. This defines the stations and the station-specific components for which this script
##     computes Green functions. 
##   IF THERE IS ANY INVALID COMPONENT, THIS SCRIPT WILL RAISE AN ERROR!
## 
## measured_data_simulations must be of the same form as displ_simulations (see above)
####################################################################################################################
displ_simulations = 'all'
gt_simulations = 'all'
gt_components = 'UP'
measured_data_simulations = ''
#
# DATA OUTPUT
#
# Specify here, whether or not the SPECFEM3D_GLOBE STATIONS file should be produced by ASKI (based on ASKI's stations file).
# In case there are any Green tensor simulations, it is highly recommended to set this True in order to prevent SPECFEM runtime 
# errors (related to identical source and receiver positions when computing epicentral distances).
create_specfem_stations = True
# in case create_specfem_stations = True , specify whether or not the column "altitude" in 
# ASKI's stations file should be ignored (i.e. set to 0.0 in SPECFEM STATIONS file) 
ignore_aski_stations_altitude = True
#
# OTHER GLOBALLY DEFINED STUFF
#
# list of valid Green tensor components. Must be compatible with the SPECFEM3D_GLOBE FOR ASKI code! 
# So, do not modify if you don't know what you're doing.
valid_gt_components = ['CX','CY','CZ','N','E','UP']
#
#
# END OF STUFF TO ADJUST
#
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#
#
############################################################
# CLASS simulation
############################################################
#
class simulation:

    def __init__(self):
        # get number of processes from SPECFEM Par_file (optionally used in function check_process_sh() )
        try:
            Par_file = inputParameter(os_path.join(DATA_FILES_PATH,'Par_file'))
        except:
            self.log("   ERROR! could not create inputParameter object for Par_file '"+
                     os_path.join(DATA_FILES_PATH,'Par_file')+"\n")
            raise 
        noKeys = Par_file.keysNotPresent(['NPROC_XI','NPROC_ETA'])
        if len(noKeys) > 0:
            self.log("   ERROR! the following keywords are required in Par_file '"+
                     os_path.join(DATA_FILES_PATH,'Par_file')+"':\n"+
                     "   "+',  '.join(noKeys)+"\n")
            raise Exception("missing keywords in Par_file; see logfile '"+logfile+"'")
        self.nproc_XI = Par_file.ival('NPROC_XI')
        if self.nproc_XI is None:
            self.log("   ERROR! could not read a valid integer for keyword 'NPROC_XI' in Par_file '"+
                     os_path.join(DATA_FILES_PATH,'Par_file')+"':\n"+
                     "   "+',  '.join(noKeys)+"\n")
            raise Exception("no integer value for 'NPROC_XI' in Par_file; see logfile '"+logfile+"'")
        self.nproc_ETA = Par_file.ival('NPROC_ETA')
        if self.nproc_ETA is None:
            self.log("   ERROR! could not read a valid integer for keyword 'NPROC_ETA' in Par_file '"+
                     os_path.join(DATA_FILES_PATH,'Par_file')+"':\n"+
                     "   "+',  '.join(noKeys)+"\n")
            raise Exception("no integer value for 'NPROC_XI_ETA' in Par_file; see logfile '"+logfile+"'")
        self.nproc = self.nproc_XI * self.nproc_ETA

        # open main parfile and check if all required keywords are present
        if not os_path.exists(main_parfile):
            self.log("### STOP : file '"+main_parfile+"' as set for the main parameter file does not exist, "+
                     "please correct the definition of 'main_parfile = ...' at the beginning of this script\n\n")
            raise Exception("main parameter file does not exist; see logfile '"+logfile+"'")
        try:
            self.mparam = inputParameter(main_parfile)
            self.log("successfully read the main parameter file '"+main_parfile+"'\n\n")
        except:
            self.log("### STOP : could not create inputParameter object for main parameter file '"+
                     main_parfile+"', make sure that the file is of correct form\n\n")
            raise

        # check if all required keys are set
        only_data_simulations = displ_simulations == '' and gt_simulations == ''
        if only_data_simulations:
            noKeys = self.mparam.keysNotPresent(['MAIN_PATH_INVERSION','FILE_STATION_LIST','FILE_EVENT_LIST',
                                                 'PATH_MEASURED_DATA'])
        else:
            noKeys = self.mparam.keysNotPresent(['MAIN_PATH_INVERSION','CURRENT_ITERATION_STEP','ITERATION_STEP_PATH',
                                                 'PARFILE_ITERATION_STEP','FILE_STATION_LIST','FILE_EVENT_LIST',
                                                 'PATH_MEASURED_DATA','MEASURED_DATA_FREQUENCY_STEP'])
        if len(noKeys) > 0:
            self.log("### STOP : the following keywords are required in the main parameter file '"+
                     main_parfile+"':\n"+
                     "### "+',  '.join(noKeys)+"\n\n")
            raise Exception("missing keywords in main paramter file; see logfile '"+logfile+"'")

        if only_data_simulations:
            # check if the directory PATH_MEASURED_DATA is an existing path and whether you have write and execute permissions
            if not os_path.isdir(self.mparam.sval('PATH_MEASURED_DATA')):
                self.log("### STOP : as defined by the main parameter file, PATH_MEASURED_DATA = '"+
                         self.mparam.sval('PATH_MEASURED_DATA')+"' is not an existing directory\n\n")
                raise Exception("PATH_MEASURED_DATA is no existing directory; see logfile '"+logfile+"'")
            if not (os_access(self.mparam.sval('PATH_MEASURED_DATA'),os_W_OK) and  os_access(self.mparam.sval('PATH_MEASURED_DATA'),os_X_OK)):
                self.log("### STOP : you do not have write and execute permissions for PATH_MEASURED_DATA = '"+
                         self.mparam.sval('PATH_MEASURED_DATA')+"' (as defined by the main parameter file)\n\n")
                raise Exception("no write and execute permissions for PATH_MEASURED_DATA; see logfile '"+logfile+"'")
        else:
            # check if the iteration step path, as defined by the main parfile, is an existing path and you have write and execute permissions
            # store iteration step path for further use
            self.iter_path = os_path.join(self.mparam.sval('MAIN_PATH_INVERSION'),self.mparam.sval('ITERATION_STEP_PATH')+
                                          '%3.3i/'%self.mparam.ival('CURRENT_ITERATION_STEP'))
            if not os_path.isdir(self.iter_path):
                self.log("### STOP : as defined by the main parameter file, the iteration step path '"+
                         self.iter_path+"' is not an existing directory\n\n")
                raise Exception("iteration step path is no existing directory; see logfile '"+logfile+"'")

            # open iteration step parfile and check if all required keywords are present
            iter_parfile = os_path.join(self.iter_path,self.mparam.sval('PARFILE_ITERATION_STEP'))
            if not os_path.exists(iter_parfile):
                self.log("### STOP : the iteration step parameter file '"+iter_parfile+"' as derived from the main "+
                         "parameter file does not exist, please make sure that the settings of MAIN_PATH_INVERSION, "+
                         "CURRENT_ITERATION_STEP, ITERATION_STEP_PATH and PARFILE_ITERATION_STEP in main parameter file '"+
                         main_parfile+"' is correctly set\n\n")
                raise Exception("iteration step parameter file does not exist; see logfile '"+logfile+"'")
            try:
                self.iparam = inputParameter(iter_parfile)
                self.log("successfully read the iteration step parameter file '"+iter_parfile+"'\n\n")
            except:
                self.log("### STOP : could not create inputParameter object for the iteration step parameter file '"+
                         iter_parfile+"', make sure that the file is of correct form\n\n")
                raise
            # check if all required keys are set
            noKeys = self.iparam.keysNotPresent(['ITERATION_STEP_NUMBER_OF_FREQ','ITERATION_STEP_INDEX_OF_FREQ',
                                                 'PATH_KERNEL_DISPLACEMENTS','PATH_KERNEL_GREEN_TENSORS',
                                                 'TYPE_INVERSION_GRID','PARFILE_INVERSION_GRID'])
            if len(noKeys) > 0:
                self.log("### STOP : the following keywords are required in iteration step parameter file '"+
                         iter_parfile+"':\n"+
                         "### "+',  '.join(noKeys)+"\n\n")
                raise Exception("missing keywords in iteration step paramter file; see logfile '"+logfile+"'")

            # check if for displ simulations, PATH_KERNEL_DISPLACEMENT is an existing writeable, executable directory
            if displ_simulations != '':
                check_dir = os_path.join(self.iter_path,self.iparam.sval('PATH_KERNEL_DISPLACEMENTS'))
                if not os_path.isdir(check_dir):
                    self.log("### STOP : as conventionally defined by the main and iter parameter files, "+
                             "the path for the kernel displacement output '"+check_dir+"' is not an existing directory\n\n")
                    raise Exception("path for kernel displacement output is no existing directory; see logfile '"+logfile+"'")
                if not (os_access(check_dir,os_W_OK) and os_access(check_dir,os_X_OK)):
                    self.log("### STOP : you do not have write and execute permissions for the path for the kernel displacement output '"+
                             check_dir+"' (as defined conventionally by the main and iter parfiles)\n\n")
                    raise Exception("no write and execute permissions for kernel displacement output path; see logfile '"+logfile+"'")

            # check if for gt simulations, PATH_KERNEL_GREEN_TENSORS is an existing writeable, executable directory
            if gt_simulations != '':
                check_dir = os_path.join(self.iter_path,self.iparam.sval('PATH_KERNEL_GREEN_TENSORS'))
                if not os_path.isdir(check_dir):
                    self.log("### STOP : as conventionally defined by the main and iter parameter files, "+
                             "the path for the kernel Green tensor output '"+check_dir+"' is not an existing directory\n\n")
                    raise Exception("path for kernel Green tensor output is no existing directory; see logfile '"+logfile+"'")
                if not (os_access(check_dir,os_W_OK) and os_access(check_dir,os_X_OK)):
                    self.log("### STOP : you do not have write and execute permissions for the path for the kernel Green tensor output '"+
                             check_dir+"' (as defined conventionally by the main and iter parfiles)\n\n")
                    raise Exception("no write and execute permissions for kernel Green tensor output path; see logfile '"+logfile+"'")

        # in case of define_ASKI_output_volume_by_inversion_grid, we also need the content of PARFILE_INVERSION_GRID
        if define_ASKI_output_volume_by_inversion_grid and not only_data_simulations:
            if self.iparam.sval('TYPE_INVERSION_GRID') == 'schunkInversionGrid':
                ASKI_type_inversion_grid_char = 'schunkInversionGrid'
                self.ASKI_type_inversion_grid = '1'
                # nchunk is always 1 for this type of inversion grid
                self.ASKI_nchunk = '1'
                parfile_invgrid = os_path.join(self.iter_path,self.iparam.sval('PARFILE_INVERSION_GRID'))
                try:
                    param = inputParameter(parfile_invgrid)
                except:
                    self.log("### STOP : could not create inputParameter object for the 'schunkInversionGrid' parameter file '"+
                             parfile_invgrid+"' (for defining ASKI output volume from inversion grid)\n\n")
                    raise
                # check if all required keys are set
                noKeys = param.keysNotPresent(['SCHUNK_INVGRID_CLAT','SCHUNK_INVGRID_CLON','SCHUNK_INVGRID_RMAX',
                                               'SCHUNK_INVGRID_WLAT','SCHUNK_INVGRID_WLON','SCHUNK_INVGRID_ROT',
                                               'SCHUNK_INVGRID_NREF_BLOCKS','SCHUNK_INVGRID_NLAY',
                                               'SCHUNK_INVGRID_THICKNESS'])
                if len(noKeys) > 0:
                    self.log("### STOP : the following keywords are required in 'schunkInversionGrid' parameter file '"+
                             self.iparam.sval('PARFILE_INVERSION_GRID')+"' (for defining ASKI output volume from inversion grid):\n"+
                             "### "+',  '.join(noKeys)+"\n\n")
                    raise Exception("missing keywords in 'schunkInversionGrid' paramter file (for defining ASKI output volume from inversion grid); see logfile '"+logfile+"'")

                # SCHUNK_INVGRID_WLAT
                if param.fval('SCHUNK_INVGRID_WLAT') is not None and param.fval('SCHUNK_INVGRID_WLAT') > 0.:
                    self.ASKI_wlat = param.sval('SCHUNK_INVGRID_WLAT')
                else:
                    raise Exception("'SCHUNK_INVGRID_WLAT' = '"+param.sval('SCHUNK_INVGRID_WLAT')+
                                    "' is not valid in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"', must be positive")
                # SCHUNK_INVGRID_WLON
                if param.fval('SCHUNK_INVGRID_WLON') is not None and param.fval('SCHUNK_INVGRID_WLON') > 0.:
                    self.ASKI_wlon = param.sval('SCHUNK_INVGRID_WLON')
                else:
                    raise Exception("'SCHUNK_INVGRID_WLON' = '"+param.sval('SCHUNK_INVGRID_WLON')+
                                    "' is not valid in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"', must be positive")
                # SCHUNK_INVGRID_CLAT
                if param.fval('SCHUNK_INVGRID_CLAT') is not None:
                    self.ASKI_clat = param.sval('SCHUNK_INVGRID_CLAT')
                else:
                    raise Exception("'SCHUNK_INVGRID_CLAT' = '"+param.sval('SCHUNK_INVGRID_CLAT')+
                                    "' is no real number in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"'")
                # SCHUNK_INVGRID_CLON
                if param.fval('SCHUNK_INVGRID_CLON') is not None:
                    self.ASKI_clon = param.sval('SCHUNK_INVGRID_CLON')
                else:
                    raise Exception("'SCHUNK_INVGRID_CLON' = '"+param.sval('SCHUNK_INVGRID_CLON')+
                                    "' is no real number in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"'")
                # SCHUNK_INVGRID_ROT
                if param.fval('SCHUNK_INVGRID_ROT') is not None:
                    self.ASKI_rot_gamma = param.sval('SCHUNK_INVGRID_ROT')
                else:
                    raise Exception("'SCHUNK_INVGRID_ROT' = '"+param.sval('SCHUNK_INVGRID_ROT')+
                                    "' is no real number in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"'")
                # SCHUNK_INVGRID_RMAX
                if param.fval('SCHUNK_INVGRID_RMAX') is not None:
                    rmax = param.fval('SCHUNK_INVGRID_RMAX')
                else:
                    raise Exception("'SCHUNK_INVGRID_RMAX' = '"+param.sval('SCHUNK_INVGRID_RMAX')+
                                    "' is no real number in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"'")
                # SCHUNK_INVGRID_NREF_BLOCKS
                if param.ival('SCHUNK_INVGRID_NREF_BLOCKS') is not None and param.ival('SCHUNK_INVGRID_NREF_BLOCKS') > 0:
                    nref_blocks = param.ival('SCHUNK_INVGRID_NREF_BLOCKS')
                else:
                    raise Exception("'SCHUNK_INVGRID_NREF_BLOCKS' = '"+param.sval('SCHUNK_INVGRID_NREF_BLOCKS')+
                                    "' is not valid in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"', must be positive")
                # SCHUNK_INVGRID_NLAY
                if param.ilist('SCHUNK_INVGRID_NLAY',nref_blocks) is not None:
                    nlay = param.ilist('SCHUNK_INVGRID_NLAY',nref_blocks)
                    if any([ilay <= 0 for ilay in nlay]):
                        raise Exception("all entries of vector 'SCHUNK_INVGRID_NLAY' = '"+param.sval('SCHUNK_INVGRID_NLAY')+
                                        "' must be positive in 'schunkInversionGrid' parameter file '"+
                                        self.iparam.sval('PARFILE_INVERSION_GRID'))
                else:
                    raise Exception("'SCHUNK_INVGRID_NLAY' = '"+param.sval('SCHUNK_INVGRID_NLAY')+
                                    "' is not a vector of "+str(nref_blocks)+" integers in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID'))
                # SCHUNK_INVGRID_THICKNESS
                if param.flist('SCHUNK_INVGRID_THICKNESS',nref_blocks) is not None:
                    thickness = param.flist('SCHUNK_INVGRID_THICKNESS',nref_blocks)
                    if any([t <= 0. for t in thickness]):
                        raise Exception("all entries of vector 'SCHUNK_INVGRID_THICKNESS' = '"+param.sval('SCHUNK_INVGRID_THICKNESS')+
                                        "' must be positive in 'schunkInversionGrid' parameter file '"+
                                        self.iparam.sval('PARFILE_INVERSION_GRID'))
                else:
                    raise Exception("'SCHUNK_INVGRID_THICKNESS' = '"+param.sval('SCHUNK_INVGRID_THICKNESS')+
                                    "' is not a vector of "+str(nref_blocks)+" integers in 'schunkInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID'))
                rmin = rmax - sum([i*t for (i,t) in zip(nlay,thickness)])
                self.ASKI_rmax = str(rmax)
                self.ASKI_rmin = str(rmin)

            elif self.iparam.sval('TYPE_INVERSION_GRID') == 'chunksInversionGrid':
                ASKI_type_inversion_grid_char = 'chunksInversionGrid'
                self.ASKI_type_inversion_grid = '5'
                parfile_invgrid = os_path.join(self.iter_path,self.iparam.sval('PARFILE_INVERSION_GRID'))
                try:
                    param = inputParameter(parfile_invgrid)
                except:
                    self.log("### STOP : could not create inputParameter object for the 'chunksInversionGrid' parameter file '"+
                             parfile_invgrid+"' (for defining ASKI output volume from inversion grid)\n\n")
                    raise
                # check if all required keys are set
                noKeys = param.keysNotPresent(['CHUNKS_INVGRID_GEOM_CLAT','CHUNKS_INVGRID_GEOM_CLON','CHUNKS_INVGRID_GEOM_RMAX',
                                               'CHUNKS_INVGRID_GEOM_WLAT','CHUNKS_INVGRID_GEOM_WLON','CHUNKS_INVGRID_GEOM_ROT',
                                               'CHUNKS_INVGRID_BASE_NREF_BLOCKS','CHUNKS_INVGRID_BASE_NLAY',
                                               'CHUNKS_INVGRID_BASE_THICKNESS'])
                if len(noKeys) > 0:
                    self.log("### STOP : the following keywords are required in 'chunksInversionGrid' parameter file '"+
                             self.iparam.sval('PARFILE_INVERSION_GRID')+"' (for defining ASKI output volume from inversion grid):\n"+
                             "### "+',  '.join(noKeys)+"\n\n")
                    raise Exception("missing keywords in 'chunksInversionGrid' paramter file (for defining ASKI output volume from inversion grid); see logfile '"+logfile+"'")

                # CHUNKS_INVGRID_GEOM_NCHUNK
                if param.ival('CHUNKS_INVGRID_GEOM_NCHUNK') is not None and param.ival('CHUNKS_INVGRID_GEOM_NCHUNK') in [1,2,3,6]:
                    self.ASKI_nchunk = param.sval('CHUNKS_INVGRID_GEOM_NCHUNK')
                else:
                    raise Exception("'CHUNKS_INVGRID_GEOM_NCHUNK' = '"+param.sval('CHUNKS_INVGRID_GEOM_NCHUNK')+
                                    "' is not valid in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"', must be 1, 2, 3 or 6")
                # CHUNKS_INVGRID_GEOM_WLAT
                if param.fval('CHUNKS_INVGRID_GEOM_WLAT') is not None and param.fval('CHUNKS_INVGRID_GEOM_WLAT') > 0.:
                    self.ASKI_wlat = param.sval('CHUNKS_INVGRID_GEOM_WLAT')
                else:
                    raise Exception("'CHUNKS_INVGRID_GEOM_WLAT' = '"+param.sval('CHUNKS_INVGRID_GEOM_WLAT')+
                                    "' is not valid in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"', must be positive")
                # CHUNKS_INVGRID_GEOM_WLON
                if param.fval('CHUNKS_INVGRID_GEOM_WLON') is not None and param.fval('CHUNKS_INVGRID_GEOM_WLON') > 0.:
                    self.ASKI_wlon = param.sval('CHUNKS_INVGRID_GEOM_WLON')
                else:
                    raise Exception("'CHUNKS_INVGRID_GEOM_WLON' = '"+param.sval('CHUNKS_INVGRID_GEOM_WLON')+
                                    "' is not valid in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"', must be positive")
                # CHUNKS_INVGRID_GEOM_CLAT
                if param.fval('CHUNKS_INVGRID_GEOM_CLAT') is not None:
                    self.ASKI_clat = param.sval('CHUNKS_INVGRID_GEOM_CLAT')
                else:
                    raise Exception("'CHUNKS_INVGRID_GEOM_CLAT' = '"+param.sval('CHUNKS_INVGRID_GEOM_CLAT')+
                                    "' is no real number in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"'")
                # CHUNKS_INVGRID_GEOM_CLON
                if param.fval('CHUNKS_INVGRID_GEOM_CLON') is not None:
                    self.ASKI_clon = param.sval('CHUNKS_INVGRID_GEOM_CLON')
                else:
                    raise Exception("'CHUNKS_INVGRID_GEOM_CLON' = '"+param.sval('CHUNKS_INVGRID_GEOM_CLON')+
                                    "' is no real number in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"'")
                # CHUNKS_INVGRID_GEOM_ROT
                if param.fval('CHUNKS_INVGRID_GEOM_ROT') is not None:
                    self.ASKI_rot_gamma = param.sval('CHUNKS_INVGRID_GEOM_ROT')
                else:
                    raise Exception("'CHUNKS_INVGRID_GEOM_ROT' = '"+param.sval('CHUNKS_INVGRID_GEOM_ROT')+
                                    "' is no real number in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"'")
                # CHUNKS_INVGRID_GEOM_RMAX
                if param.fval('CHUNKS_INVGRID_GEOM_RMAX') is not None:
                    rmax = param.fval('CHUNKS_INVGRID_GEOM_RMAX')
                else:
                    raise Exception("'CHUNKS_INVGRID_GEOM_RMAX' = '"+param.sval('CHUNKS_INVGRID_GEOM_RMAX')+
                                    "' is no real number in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"'")
                # CHUNKS_INVGRID_BASE_NREF_BLOCKS
                if param.ival('CHUNKS_INVGRID_BASE_NREF_BLOCKS') is not None and param.ival('CHUNKS_INVGRID_BASE_NREF_BLOCKS') > 0:
                    nref_blocks = param.ival('CHUNKS_INVGRID_BASE_NREF_BLOCKS')
                else:
                    raise Exception("'CHUNKS_INVGRID_BASE_NREF_BLOCKS' = '"+param.sval('CHUNKS_INVGRID_BASE_NREF_BLOCKS')+
                                    "' is not valid in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID')+"', must be positive")
                # CHUNKS_INVGRID_BASE_NLAY
                if param.ilist('CHUNKS_INVGRID_BASE_NLAY',nref_blocks) is not None:
                    nlay = param.ilist('CHUNKS_INVGRID_BASE_NLAY',nref_blocks)
                    if any([ilay <= 0 for ilay in nlay]):
                        raise Exception("all entries of vector 'CHUNKS_INVGRID_BASE_NLAY' = '"+param.sval('CHUNKS_INVGRID_BASE_NLAY')+
                                        "' must be positive in 'chunksInversionGrid' parameter file '"+
                                        self.iparam.sval('PARFILE_INVERSION_GRID'))
                else:
                    raise Exception("'CHUNKS_INVGRID_BASE_NLAY' = '"+param.sval('CHUNKS_INVGRID_BASE_NLAY')+
                                    "' is not a vector of "+str(nref_blocks)+" integers in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID'))
                # CHUNKS_INVGRID_BASE_THICKNESS
                if param.flist('CHUNKS_INVGRID_BASE_THICKNESS',nref_blocks) is not None:
                    thickness = param.flist('CHUNKS_INVGRID_BASE_THICKNESS',nref_blocks)
                    if any([t <= 0. for t in thickness]):
                        raise Exception("all entries of vector 'CHUNKS_INVGRID_BASE_THICKNESS' = '"+param.sval('CHUNKS_INVGRID_BASE_THICKNESS')+
                                        "' must be positive in 'chunksInversionGrid' parameter file '"+
                                        self.iparam.sval('PARFILE_INVERSION_GRID'))
                else:
                    raise Exception("'CHUNKS_INVGRID_BASE_THICKNESS' = '"+param.sval('CHUNKS_INVGRID_BASE_THICKNESS')+
                                    "' is not a vector of "+str(nref_blocks)+" integers in 'chunksInversionGrid' parameter file '"+
                                    self.iparam.sval('PARFILE_INVERSION_GRID'))
                rmin = rmax - sum([i*t for (i,t) in zip(nlay,thickness)])
                self.ASKI_rmax = str(rmax)
                self.ASKI_rmin = str(rmin)

            else:
                raise Exception("'TYPE_INVERSION_GRID' = '"+self.iparam.sval('TYPE_INVERSION_GRID')+
                                "' is not supported by the automatic definition of ASKI output volume "+
                                "by the inversion grid. Supported inversion grid types are: "+
                                "'schunkInversionGrid', 'chunksInversionGrid'. Please define the ASKI "+
                                "output volume manually and set "+
                                "define_ASKI_output_volume_by_inversion_grid = False on top of this script")

        # read event list and station list
        if displ_simulations != '' or measured_data_simulations != '':
            if not os_path.exists(self.mparam.sval('FILE_EVENT_LIST')):
                self.log("### STOP : the event list file '"+self.mparam.sval('FILE_EVENT_LIST')+"' as set in the "+
                         "main parameter file '"+main_parfile+"' does not exist\n\n")
                raise Exception("event list file does not exist; see logfile '"+logfile+"'")
            try:
                self.evlist = eventList(self.mparam.sval('FILE_EVENT_LIST'),list_type='standard')
            except:
                self.log("### STOP : could not construct event list from file '"+self.mparam.sval('FILE_EVENT_LIST')+
                         "', make sure that the file is of correct form\n\n")
                raise
            if self.evlist.nev == 0:
                self.log("### STOP : event list from file '"+self.mparam.sval('FILE_EVENT_LIST')+"' does not contain"+
                         "any valid events\n\n")
                raise Exception("no events in ASKI event list file; see logfile '"+logfile+"'")
            if self.evlist.csys != 'S':
                self.log("### STOP : event list from file '"+self.mparam.sval('FILE_EVENT_LIST')+"' is for coordinate system '"+
                         self.evlist.csys+"', only 'S' supported here\n\n")
                raise Exception("coordinate system of event list file not supported; see logfile '"+logfile+"'")
            if create_specfem_stations:
                if not os_path.exists(self.mparam.sval('FILE_STATION_LIST')):
                    self.log("### STOP : the station list file '"+self.mparam.sval('FILE_STATION_LIST')+"' as set "+
                             "in the main parameter file '"+main_parfile+"' does not exist\n\n")
                    raise Exception("station list file does not exist; see logfile '"+logfile+"'")
                try:
                    self.statlist = stationList(self.mparam.sval('FILE_STATION_LIST'),list_type='standard')
                except:
                    self.log("### STOP : could not construct station list from file '"+self.mparam.sval('FILE_STATION_LIST')+
                             "', make sure that the file is of correct form\n\n")
                    raise
                if self.statlist.nstat == 0:
                    self.log("### STOP : station list from file '"+self.mparam.sval('FILE_STATION_LIST')+"' does not contain"+
                             "any valid stations\n\n")
                    raise Exception("no stations in ASKI station list file; see logfile '"+logfile+"'")
                if self.statlist.csys != 'S':
                    self.log("### STOP : station list from file '"+self.mparam.sval('FILE_EVENT_LIST')+"' is for coordinate system '"+
                             self.statlist.csys+"', only 'S' supported here\n\n")
                    raise Exception("coordinate system of station list file not supported; see logfile '"+logfile+"'")
        if gt_simulations != '' and not hasattr(self,'statlist'):
            if not os_path.exists(self.mparam.sval('FILE_STATION_LIST')):
                self.log("### STOP : the station list file '"+self.mparam.sval('FILE_STATION_LIST')+"' as set "+
                         "in the main parameter file '"+main_parfile+"' does not exist\n\n")
                raise Exception("station list file does not exist; see logfile '"+logfile+"'")
            try:
                self.statlist = stationList(self.mparam.sval('FILE_STATION_LIST'),list_type='standard')
            except:
                self.log("### STOP : could not construct station list from file '"+self.mparam.sval('FILE_STATION_LIST')+
                         "', make sure that the file is of correct form\n\n")
                raise
            if self.statlist.nstat == 0:
                self.log("### STOP : station list from file '"+self.mparam.sval('FILE_STATION_LIST')+"' does not contain"+
                         "any valid stations\n\n")
                raise Exception("no stations in ASKI station list file; see logfile '"+logfile+"'")
            if self.statlist.csys != 'S':
                self.log("### STOP : station list from file '"+self.mparam.sval('FILE_EVENT_LIST')+"' is for coordinate system '"+
                         self.statlist.csys+"', only 'S' supported here\n\n")
                raise Exception("coordinate system of station list file not supported; see logfile '"+logfile+"'")
            
        self.all_tasks = []
        self.gt_comp_files = []
        self.append_valid_tasks()
        for staname,file_content in self.gt_comp_files:
            # only if there are any gt simulations, this loop is entered at all (and self.iparam , self.iter_path were initated before)
            filename = os_path.join(self.iter_path,self.iparam.sval('PATH_KERNEL_GREEN_TENSORS'),'kernel_gt_'+staname+'.comp')
            try:
                open(filename,'w').write(file_content)
            except:
                self.log("### STOP : could not write Green tensor components file '"+filename+"' for station '"+
                         staname+"'\n\n")
                raise Exception("could not write a Green tensor components file; see logfile '"+logfile+"'")

        self.index_iteration_send_email = [0]
        if type(number_of_intermediate_status_emails) is int:
            self.index_iteration_send_email.extend([int( (i+1.)*max(float(len(self.all_tasks)-1)/float(number_of_intermediate_status_emails+1),1.) )
                                                    for i in range(min(number_of_intermediate_status_emails,len(self.all_tasks)-2))])

        # log initial information
        if runs_on_SGE:
            log_SGE_info = ('running on SUN GRID ENGINE with JOB_ID '+str(SGE_job_id)+'; master host is '+
                            str(SGE_hostname)+'; content of PE_HOSTFILE is \n--- START CONTENT PE_HOSTFILE ---\n'+
                            SGE_pe_hostfile_content+'--- END CONTENT PE_HOSTFILE ---')
        else:
            log_SGE_info = ''
        if not only_data_simulations:
            log_iter_info = ("iteration step %i\n"%self.mparam.ival('CURRENT_ITERATION_STEP')+
                             "iteration step specific parameter file: '"+iter_parfile+"'\n")
        else:
            log_iter_info = ""
        self.log('################################################################################\n'+
                 "Welcome to these automated SPECFEM3D_GLOBE simulations for ASKI\n"+
                 log_SGE_info+"\n\n"+
                 "main ASKI parameter file: '"+main_parfile+"'\n"+
                 log_iter_info+
                 "'"+os_path.join(DATA_FILES_PATH,'Par_file')+"' tells me, we're using a total of "+str(self.nproc)+" procs:\n"+
                 "  NPROC_XI  = "+str(self.nproc_XI)+"\n"
                 "  NPROC_ETA = "+str(self.nproc_ETA)+"\n"
                 "OUTPUT_FILES_PATH = '"+OUTPUT_FILES_PATH+"'\n"+
                 "LOCAL_PATH = '"+LOCAL_PATH+"'\n"+
                 "DATA_FILES_PATH = '"+DATA_FILES_PATH+"'\n"+
                 "\n"+
                 "according to the simulation strings \n"+
                 "  displ_simulations = '"+displ_simulations+"'\n"+
                 "  gt_simulations = '"+gt_simulations+"'\n"+
                 "  gt_components = '"+gt_components+"'\n"+
                 "  measured_data_simulations = '"+measured_data_simulations+"',\n"+
                 "now the following "+str(len(self.all_tasks))+" simulations are done (in this order): \n\n"+
                 "(TYPE ID[_component])\n"+
                 ',  '.join(["(%s %s)"%typ_task for typ_task in self.all_tasks])+"\n"+
                 '\n')
        if len(self.gt_comp_files) > 0:
            self.log("already in advance, all "+str(len(self.gt_comp_files))+" Green tensor component files "+
                     "(containing the Green tensor components for each station) were written to paths '"+
                     os_path.join(self.iter_path,self.iparam.sval('PATH_KERNEL_GREEN_TENSORS'),'kernel_gt_staname.comp')+"'\n"+
                     "\n")
        if send_emails:
            self.log("this log will be sent via email to '"+email_receiver+"' after the following simulations (indices, first index is 1):\n"+
                     ', '.join([str(i+1) for i in self.index_iteration_send_email])+'\n'
                     'and when all simulations are successfully finished (or the script exited unintendedly)\n'+
                     '\n')
        else:
            self.log("this log will not be sent via email anywhere\n\n")

        # info about ASKI output volume
        if define_ASKI_output_volume_by_inversion_grid and (displ_simulations != '' or gt_simulations!= '') :
            self.log("for every simulation of type displ or gt, the ASKI output volume in Par_file_ASKI\n"+
                     "will be defined by the following values:\n"+
                     "  ASKI_type_inversion_grid = "+self.ASKI_type_inversion_grid+" (meaning '"+ASKI_type_inversion_grid_char+"')\n"+
                     "  ASKI_nchunk = "+self.ASKI_nchunk+"\n"+
                     "  ASKI_wlat = "+self.ASKI_wlat+"\n"+
                     "  ASKI_wlon = "+self.ASKI_wlon+"\n"+
                     "  ASKI_rot_gamma = "+self.ASKI_rot_gamma+"\n"+
                     "  ASKI_clat = "+self.ASKI_clat+"\n"+
                     "  ASKI_clon = "+self.ASKI_clon+"\n"+
                     "  ASKI_rmax = "+self.ASKI_rmax+"\n"+
                     "  ASKI_rmin = "+self.ASKI_rmin+"\n"+
                     "\n")
        else:
            self.log("the ASKI output volume in Par_file_ASKI will not be defined by this script,\n"+
                     "you should have taken care of that yourself\n\n")

        self.time_start = time_time()
        self.log("starting simulations now at time -- "+time_ctime(self.time_start)+"\n"+
                 "\n")
#
#-----------------------------------------------------------
#
    def append_valid_tasks(self):#displ_simulations,gt_simulations,measured_data_simulations)
        # extract all valid eventIDs and station names for testing, omit numeric keys (event index, station index) present in dictionaries
        if displ_simulations != '' or measured_data_simulations != '':
            valid_evids = sorted([key for key in self.evlist.events.keys() if type(key) is str])
        if gt_simulations != '':
            valid_stanames = sorted([key for key in self.statlist.stations.keys() if type(key) is str])

        # handle string displ_simulations
        if displ_simulations != '':
            if displ_simulations == 'all':
                self.all_tasks += [('displ',evid) for evid in valid_evids]
            elif displ_simulations.startswith('all-except:'):
                given_evids = displ_simulations[11:].split(',')
                given_invalid_evids = [evid for evid in given_evids if not evid in valid_evids]
                if len(given_invalid_evids) > 0:
                    self.log("### STOP : the following invalid eventIDs (that are not contained in FILE_EVENT_LIST) "+
                             "were detected in string 'displ_simulations':\n"+
                             "### "+',  '.join(given_invalid_evids)+"\n\n")
                    raise Exception("there were "+int(len(given_invalid_evids))+
                                    " invalid eventIDs detected in string 'displ_simulations'; see logfile '"+logfile+"'")
                self.all_tasks += [('displ',evid) for evid in valid_evids if not evid in given_evids]
            else:
                # expect here simply a ','-separated list of eventIDs
                given_evids = displ_simulations.split(',')
                given_invalid_evids = [evid for evid in given_evids if not evid in valid_evids]
                if len(given_invalid_evids) > 0:
                    self.log("### STOP : the following invalid eventIDs (that are not contained in FILE_EVENT_LIST) "+
                             "were detected in string 'displ_simulations':\n"+
                             "### "+',  '.join(given_invalid_evids)+"\n\n")
                    raise Exception("there were "+int(len(given_invalid_evids))+
                                    " invalid eventIDs detected in string 'displ_simulations'; see logfile '"+logfile+"'")
                self.all_tasks += [('displ',evid) for evid in given_evids]

        # handle string gt_simulations
        if gt_simulations != '':
            # first check gt_components in case of gt_simulations being "all" or starting with "all-except:"
            if gt_simulations == 'all' or gt_simulations.startswith('all-except:'):
                given_components = gt_components.split(',')
                if len(given_components) == 0:
                    self.log("### STOP : the string 'gt_components' is empty! In case of 'gt_simulations = all' "+
                             "or gt_simulations starting with 'all-except:', "+
                             "'gt_components' must contain at least one valid component\n\n")
                    raise Exception("no gt_components present in case of 'gt_simulations = all' or gt_simulations starting with 'all-except:' ; see logfile '"+logfile+"'")
                given_invalid_components = [comp for comp in given_components if not comp in valid_gt_components]
                if len(given_invalid_components) > 0:
                    self.log("### STOP : the following invalid components were detected in string 'gt_components':\n"+
                             "### "+',  '.join(given_invalid_components)+"\n"+
                             "### currently supported components are:\n### "+', ',join(valid_gt_components)+"\n\n")
                    raise Exception("there were "+int(len(given_invalid_components))+
                                    " invalid components detected in string 'gt_components'; see logfile '"+logfile+"'")
            # now handle 'gt_simulations = all'
            if gt_simulations == 'all':
                self.all_tasks += [('gt',staname+'_'+comp) for staname in valid_stanames 
                                   for comp in given_components]
                file_content = str(len(given_components))+"\n"+"\n".join(given_components)+"\n"
                self.gt_comp_files += [(staname,file_content) for staname in valid_stanames]
            # now handle 'gt_simulations = all-except:...'
            elif gt_simulations.startswith('all-except:'):
                given_stanames = gt_simulations[11:].split(',')
                given_invalid_stanames = [staname for staname in given_stanames if not staname in valid_stanames]
                if len(given_invalid_stanames) > 0:
                    self.log("### STOP : the following invalid station names (that are not contained in FILE_STATION_LIST) "+
                             "were detected in string 'gt_simulations':\n"+
                             "### "+',  '.join(given_invalid_stanames)+"\n\n")
                    raise Exception("there were "+int(len(given_invalid_stanames))+
                                    " invalid station names detected in string 'gt_simulations'; see logfile '"+logfile+"'")
                self.all_tasks += [('gt',staname+'_'+comp) for staname in valid_stanames 
                                   if not staname in given_stanames
                                   for comp in given_components]
                file_content = str(len(given_components))+"\n"+"\n".join(given_components)+"\n"
                self.gt_comp_files += [(staname,file_content) for staname in valid_stanames 
                                       if not staname in given_stanames]
            # now handle 'gt_simulations = specific'
            elif gt_simulations == 'specific':
                given_stanames_comps = gt_components.split(';')
                if len(given_stanames_comps) == 0:
                    self.log("### STOP : the string 'gt_components' is empty! In case of 'gt_simulations = specific', "+
                             "'gt_components' must contain a list of valid station name - component combinations\n\n")
                    raise Exception("no gt_components specification present in case of 'gt_simulations = specific' ; see logfile '"+logfile+"'")
                for i,staname_comps in enumerate(given_stanames_comps):
                    staname_comps_split = staname_comps.split(':')
                    if len(staname_comps_split) != 2:
                        self.log("### STOP : the "+str(i+1)+"'th station-component definition '"+staname_comps+
                                 "' of string 'gt_components' is invalid! 'gt_components' must be of form "+
                                 " 'TUR8:CX,CY,CZ;SYRO:UP;AT03:N,W' in case of 'gt_simulations = specific'\n\n")
                        raise Exception("gt_components specification invalid in case of 'gt_simulations = specific' ; see logfile '"+logfile+"'")
                    staname = staname_comps_split[0]
                    if not staname in valid_stanames:
                        self.log("### STOP : the "+str(i+1)+"'th station '"+staname+
                                 "' of string 'gt_components' is not in stations list! 'gt_components' must be of form "+
                                 " 'TUR8:CX,CY,CZ;SYRO:UP;AT03:N,W' in case of 'gt_simulations = specific'\n\n")
                        raise Exception("gt_components specification invalid in case of 'gt_simulations = specific' ; see logfile '"+logfile+"'")
                    given_components = staname_comps_split[1].split(',')
                    if len(given_components) == 0:
                        self.log("### STOP : the "+str(i+1)+"'th list of components '"+staname_comps_split[1]+
                                 "' of string 'gt_components' does not contain any components! 'gt_components' must be of form "+
                                 " 'TUR8:CX,CY,CZ;SYRO:UP;AT03:N,W' in case of 'gt_simulations = specific'\n\n")
                        raise Exception("gt_components specification invalid in case of 'gt_simulations = specific' ; see logfile '"+logfile+"'")
                    given_invalid_components = [comp for comp in given_components if not comp in valid_gt_components]
                    if len(given_invalid_components) > 0:
                        self.log("### STOP : the following invalid components were detected in the "+str(i+1)+
                                 "'th list of components '"+staname_comps_split[1]+"' of string 'gt_components':\n"+
                                 "### "+',  '.join(given_invalid_components)+"\n"+
                                 "### currently supported components are:\n"+
                                 "### "+', ',join(valid_gt_components)+
                                 "### 'gt_components' must be of form 'TUR8:CX,CY,CZ;SYRO:UP;AT03:N,W' in case of 'gt_simulations = specific'\n\n")
                        raise Exception("gt_components specification invalid in case of 'gt_simulations = specific' ; see logfile '"+logfile+"'")
                    # after all checks, it was verified that staname is a valid station name and that 
                    # all given_components for this station are valid. so add those Green functions to tasks list
                    self.all_tasks += [('gt',staname+'_'+comp) for comp in given_components]
                    file_content = str(len(given_components))+"\n"+"\n".join(given_components)+"\n"
                    self.gt_comp_files += [(staname,file_content)]
            # if gt_silmulations is neiter 'all', 'specific', nor starts with 'all-except:', raise an ERROR
            else:
                self.log("### STOP : gt_simulations has the value '"+gt_simulations+"'. It can be either equal to 'all' or "+
                         "'specific' or can start with 'all-except:'\n\n")
                raise Exception("invalid value of string 'gt_simulations'; see logfile '"+logfile+"'")

        # handle string measured_data_simulations
        if measured_data_simulations != '':
            if measured_data_simulations == 'all':
                self.all_tasks += [('data',evid) for evid in valid_evids]
            elif measured_data_simulations.startswith('all-except:'):
                given_evids = measured_data_simulations[11:].split(',')
                given_invalid_evids = [evid for evid in given_evids if not evid in valid_evids]
                if len(given_invalid_evids) > 0:
                    self.log("### STOP : the following invalid eventIDs (that are not contained in FILE_EVENT_LIST) "+
                             "were detected in string 'measured_data_simulations':\n"+
                             "### "+',  '.join(given_invalid_evids)+"\n\n")
                    raise Exception("there were "+int(len(given_invalid_evids))+
                                    " invalid eventIDs detected in string 'measured_data_simulations'; see logfile '"+logfile+"'")
                self.all_tasks += [('data',evid) for evid in valid_evids if not evid in given_evids]
            else:
                # expect here simply a ','-separated list of eventIDs
                given_evids = measured_data_simulations.split(',')
                given_invalid_evids = [evid for evid in given_evids if not evid in valid_evids]
                if len(given_invalid_evids) > 0:
                    self.log("### STOP : the following invalid eventIDs (that are not contained in FILE_EVENT_LIST) "+
                             "were detected in string 'measured_data_simulations':\n"+
                             "### "+',  '.join(given_invalid_evids)+"\n\n")
                    raise Exception("there were "+int(len(given_invalid_evids))+
                                    " invalid eventIDs detected in string 'measured_data_simulations'; see logfile '"+logfile+"'")
                self.all_tasks += [('data',evid) for evid in given_evids]
#
#-----------------------------------------------------------
#
    def iterate(self):
        for i,typ_id in enumerate(self.all_tasks):
            #
            # get current time, start of this iteration
            t_begin_iteration = time_time()
            #
            typ,sid = typ_id
                
            self.log('################################################################################\n'+
                     time_ctime()+' -- now doing the '+str(i+1)+'-th simulation out of '+str(len(self.all_tasks))+'\n'+
                     "TYPE '"+typ+"', ID '"+sid+"'\n"+
                     "\n")
            #
            # set all relevant parameter files correctly for this simulation
            self.log("set SPECFEM3D_GLOBE parameter files for this simulation now\n")
            try:
                self.setSpecfemGlobeParameters(typ,sid)
            except:
                self.log("### STOP : an error occurred setting the SPECFEM3D_GLOBE parameter files for this simulation\n")
                raise
            self.log("done\n"+
                     "\n")
            #
            # call some command by system call which conducts the simulation
            #
            # according to flag use_different_command_in_first_simulation, select which run command to use here
            if use_different_command_in_first_simulation and i==0:
                run_command = command_system_call_first_simulation
            else:
                run_command = command_system_call
            self.log("run command '"+run_command+"' now via system call\n")
            os_system(run_command)
            self.check_if_simulation_was_successful(typ)
            self.log("done\n\n")
            #
            # move OUTPUT_FILES
            self.log("copy SPECFEM3D_GLOBE OUTPUT_FILES\n")
            try:
                self.copySpecfemGlobeOutput()
            except:
                self.log("### STOP : an error occurred moving the standard SPECFEM3D_GLOBE output files\n")
                raise
            self.log("done\n\n")
            #
            # get current time, end of this iteration
            t_end_iteration = time_time()
            #
            # elapsed time for this iteration in h,min,sec
            this_min,this_sec = divmod(int(t_end_iteration-t_begin_iteration),60)
            this_h,this_min = divmod(this_min,60)
            #
            # mean elapsed time per simulation (computed from all iterations done, so far)
            t_mean_sec = (t_end_iteration-self.time_start)/(i+1)
            mean_min,mean_sec = divmod(int(t_mean_sec),60)
            mean_h,mean_min = divmod(mean_min,60)
            #
            # presumable time to finish
            t_finish = self.time_start+len(self.all_tasks)*t_mean_sec
            #
            # log all this time statistics
            self.log("current time -- "+time_ctime(t_end_iteration)+"\n"+
                     "elapsed time for this simulation (h:min:sec) -- %i : %i : %i"%(this_h,this_min,this_sec)+"\n"
                     "current mean elapsed time per simulation after %i simulations (h:min:sec) -- %i : %i : %i"%(i+1,mean_h,mean_min,mean_sec)+"\n"
                     "assuming all remaining "+str(len(self.all_tasks)-i-1)+" simulations to last the same time, script will finish presumably -- "+time_ctime(t_finish)+"\n\n\n")
            #
            # send logfile via email
            if send_emails and i in self.index_iteration_send_email:
                self.email_log("done %i out of %i; finish " % (i+1,len(self.all_tasks)) + time_ctime(t_finish))
            #
            # copy logfile to current SPECFEM3D_GLOBE OUTPUT_FILES directory
            # which was created in call self.copySpecfemGlobeOutput() above
            os_system('cp '+logfile+' '+self.outfile_base+'_OUTPUT_FILES')
#
#-----------------------------------------------------------
#
    def log(self,message):
        open(logfile,'a').write(message)
#
#-----------------------------------------------------------
#
    def email_log(self,subject):
        if email_receiver != '':
            os_system('mail -s "'+subject+'" '+email_receiver+' < '+logfile+' -- -f '+email_sender)
#
#-----------------------------------------------------------
#
    def setSpecfemGlobeParameters(self,typ,sid):
        try:
            Par_file_ASKI = inputParameter(os_path.join(DATA_FILES_PATH,'Par_file_ASKI'))
        except:
            self.log("   ERROR! could not create inputParameter object for Par_file_ASKI '"+
                     os_path.join(DATA_FILES_PATH,'Par_file_ASKI')+"\n")
            raise 
        noKeys = Par_file_ASKI.keysNotPresent(['OVERWRITE_ASKI_OUTPUT'])
        if len(noKeys) > 0:
            self.log("   ERROR! in setSpecfemGlobeParameters: the following keywords are required in Par_file_ASKI '"+
                     os_path.join(DATA_FILES_PATH,'Par_file_ASKI')+"':\n"+
                     "   "+',  '.join(noKeys)+"\n")
            raise Exception("missing keywords in Par_file_ASKI; see logfile '"+logfile+"'")
        #
        # remember current value of 'OVERWRITE_ASKI_OUTPUT' for this simulation
        if Par_file_ASKI.lval('OVERWRITE_ASKI_OUTPUT') is not None:
            self.overwrite_ASKI_output = Par_file_ASKI.lval('OVERWRITE_ASKI_OUTPUT')
        else:
            raise Exception("'OVERWRITE_ASKI_OUTPUT' = '"+Par_file_ASKI.sval('OVERWRITE_ASKI_OUTPUT')+
                            "' is no logical expression in Par_file_ASKI '"+
                            os_path.join(DATA_FILES_PATH,'Par_file_ASKI')+"'")
        #
        # now, according to simulation type, set parameter files
        #
        ##########################
        # typ=='displ':
        ##########################
        if typ=='displ':
            slat = self.evlist.events[sid]['slat']
            slon = self.evlist.events[sid]['slon']
            sdepth = self.evlist.events[sid]['sdepth']
            styp = self.evlist.events[sid]['styp']
            df = self.mparam.sval('MEASURED_DATA_FREQUENCY_STEP')
            nf = self.iparam.sval('ITERATION_STEP_NUMBER_OF_FREQ')
            jf = self.iparam.sval('ITERATION_STEP_INDEX_OF_FREQ')
            self.outfile_base = os_path.join(self.iter_path,self.iparam.sval('PATH_KERNEL_DISPLACEMENTS'),'kernel_displ_'+sid)
            self.log("   in setSpecfemGlobeParameters:\n"+
                     "      this is event evid = "+sid+"\n"+
                     "      source lat , lon , depth = "+', '.join([slat,slon,sdepth])+"\n"+
                     "      source type = "+styp+"\n")
            if int(styp) == 0 and self.evlist.events[sid].has_key('force'):
                self.log("   ERROR! in setSpecfemGlobeParameters: source type = 0 (i.e. single force) is not supported "+
                         "by SPECFEM3D_GLOBE for simulations of type 'displ'\n")
                raise Exception("source type = 0 is not supported by SPECFEM3D_GLOBE for simulations of type 'displ'")
            elif int(styp) == 1 and self.evlist.events[sid].has_key('momten'):
                momten = self.evlist.events[sid]['momten']
                momten_DynCm = Moment_tensor_Nm2DynCm(momten)
                self.log("      moment tensor in Nm =  "+'  '.join(momten)+" (read from ASKI event list file)\n"+
                         "      moment tensor in dyn*cm =  "+'  '.join(momten_DynCm)+" (write to SPECFEM CMTSOLUTION file)\n"+
                         "      nf,df = "+', '.join([nf,df])+"\n"+
                         "      frequency indices = "+jf+"\n"+
                         "      kernel displacement output file (basename) = '"+self.outfile_base+"'\n")
                Mrr,Mtt,Mpp,Mrt,Mrp,Mtp = momten_DynCm
                try:
                    setCmtsolution(evname=sid,hdur='0',lat=slat,lon=slon,depth=sdepth,Mrr=Mrr,Mtt=Mtt,Mpp=Mpp,Mrt=Mrt,Mrp=Mrp,Mtp=Mtp)
                except:
                    self.log("   ERROR! in setSpecfemGlobeParameters: exception raised while setting CMTSOLUTION\n")
                    raise
            else:
                self.log("   ERROR! in setSpecfemGlobeParameters: source type is undefined (neither force nor moment tensor)\n")
                raise Exception("source type is undefined")

            if create_specfem_stations:
                log_string = ("      the SPECFEM STATIONS file was created from the "+str(self.statlist.nstat)+" stations in ASKI's station list file")
                if ignore_aski_stations_altitude:
                    STATIONS_content = '\n'.join(['   '.join([self.statlist.stations[i]['staname'], self.statlist.stations[i]['netcode'], 
                                                              self.statlist.stations[i]['lat'], self.statlist.stations[i]['lon'],
                                                              '0.0', '0.0'
                                                              ])
                                                  for i in range(self.statlist.nstat)
                                                  ])+'\n'
                    log_string += ", setting any altitudes to '0.0'"
                else:
                    STATIONS_content = '\n'.join(['   '.join([self.statlist.stations[i]['staname'], self.statlist.stations[i]['netcode'], 
                                                              self.statlist.stations[i]['lat'], self.statlist.stations[i]['lon'],
                                                              self.statlist.stations[i]['alt'], '0.0'
                                                              ])
                                                  for i in range(self.statlist.nstat)
                                                  ])+'\n'
                    log_string += ", keeping all original altitudes"
                try:
                    open(os_path.join(DATA_FILES_PATH,'STATIONS'),'w').write(STATIONS_content)
                except:
                    self.log("   ERROR! in setSpecfemGlobeParameters: could not open STATIONS file '"+os_path.join(DATA_FILES_PATH,'STATIONS')+
                                    "' to write\n")
                    raise
                self.log(log_string+"\n")
            else:
                self.log("      the SPECFEM STATIONS file was not modified by this script, you should have set it yourself correctly\n")

            if os_path.exists(self.outfile_base+'_OUTPUT_FILES'):
                if self.overwrite_ASKI_output:
                    self.log("      SPECFEM3D_GLOBE OUTPUT_FILES will be copied to '"+
                             self.outfile_base+'_OUTPUT_FILES'+"' (exists and will be overwritten).\n")
                else:
                    self.log("   ERROR! in setSpecfemGlobeParameters: path for SPECFEM3D_GLOBE OUTPUT_FILES '"+
                             self.outfile_base+'_OUTPUT_FILES'+"' exists and must not be overwritten "+
                             "(according to 'OVERWRITE_ASKI_OUTPUT' in Par_file_ASKI)\n")
                    raise Exception('path for SPECFEM3D_GLOBE OUTPUT_FILES already exists')
            else:
                self.log("      SPECFEM3D_GLOBE OUTPUT_FILES will be copied to '"+
                         self.outfile_base+'_OUTPUT_FILES'+"'.\n")

            try:
                setParfile(os_path.join(DATA_FILES_PATH,'Par_file_ASKI'),
                           [('COMPUTE_ASKI_OUTPUT','.true.'),('ASKI_outfile',self.outfile_base),
                            ('ASKI_output_ID',sid),('COMPUTE_ASKI_GREEN_FUNCTION','.false.'),
                            ('ASKI_df',df),('ASKI_nf',nf),('ASKI_jf',jf)])
                if define_ASKI_output_volume_by_inversion_grid:
                    setParfile(os_path.join(DATA_FILES_PATH,'Par_file_ASKI'),
                               [('ASKI_type_inversion_grid',self.ASKI_type_inversion_grid),('ASKI_nchunk',self.ASKI_nchunk),
                                ('ASKI_wlat',self.ASKI_wlat),('ASKI_wlon',self.ASKI_wlon),
                                ('ASKI_rot_gamma',self.ASKI_rot_gamma),
                                ('ASKI_clat',self.ASKI_clat),('ASKI_clon',self.ASKI_clon),
                                ('ASKI_rmax',self.ASKI_rmax),('ASKI_rmin',self.ASKI_rmin)])
            except:
                self.log("   ERROR! in setSpecfemGlobeParameters: exception raised while setting Par_file_ASKI\n")
                raise

        ##########################
        # typ=='gt':
        ##########################
        elif typ=='gt':
            staname_comp = sid.split('_')
            if len(staname_comp) != 2:
                self.log("   ERROR! in setSpecfemGlobeParameters: simulation ID '"+sid+"' is invalid for simulation "+
                         "type 'gt'. Must be of form 'stationname_component', where stationname MUST NOT contain '_' "+
                         "characters!\n")
                raise Exception("invalid simulation ID '"+sid+"' for Green tensor simulation")
            staname = staname_comp[0]
            comp = staname_comp[1]
            nwname = self.statlist.stations[staname]['netcode']
            lat = self.statlist.stations[staname]['lat']
            lon = self.statlist.stations[staname]['lon']
            alt = self.statlist.stations[staname]['alt']
            df = self.mparam.sval('MEASURED_DATA_FREQUENCY_STEP')
            nf = self.iparam.sval('ITERATION_STEP_NUMBER_OF_FREQ')
            jf = self.iparam.sval('ITERATION_STEP_INDEX_OF_FREQ')
            self.outfile_base = os_path.join(self.iter_path,self.iparam.sval('PATH_KERNEL_GREEN_TENSORS'),'kernel_gt_'+sid)
            self.log("   in setSpecfemGlobeParameters:\n"+
                     "      this is station staname,nwname = "+', '.join([staname,nwname])+"\n"+
                     "      lat , lon , alt = "+', '.join([lat,lon,alt])+"\n"+
                     "      green tensor component = "+comp+"\n"+
                     "      nf,df = "+', '.join([nf,df])+"\n"+
                     "      frequency indices = "+jf+"\n"+
                     "      kernel green tensor output file (basename) = '"+self.outfile_base+"'\n")

            if create_specfem_stations:
                log_string = ("      the SPECFEM STATIONS file was created from the "+str(self.statlist.nstat)+" stations in ASKI's station list file,\n"+
                              "         EXCLUDING station '"+staname+"' (where the source is located)")
                if ignore_aski_stations_altitude:
                    STATIONS_content = '\n'.join(['   '.join([self.statlist.stations[i]['staname'], self.statlist.stations[i]['netcode'], 
                                                              self.statlist.stations[i]['lat'], self.statlist.stations[i]['lon'],
                                                              '0.0', '0.0'
                                                              ])
                                                  for i in range(self.statlist.nstat)
                                                  if not self.statlist.stations[i]['staname'] == staname  # exclude the station at which the Green source is located
                                                  ])+'\n'
                    log_string += " and setting any altitudes to '0.0'"
                else:
                    STATIONS_content = '\n'.join(['   '.join([self.statlist.stations[i]['staname'], self.statlist.stations[i]['netcode'], 
                                                              self.statlist.stations[i]['lat'], self.statlist.stations[i]['lon'],
                                                              self.statlist.stations[i]['alt'], '0.0'
                                                              ])
                                                  for i in range(self.statlist.nstat)
                                                  if not self.statlist.stations[i]['staname'] == staname  # exclude the station at which the Green source is located
                                                  ])+'\n'
                    log_string += " and keeping all original altitudes"
                try:
                    open(os_path.join(DATA_FILES_PATH,'STATIONS'),'w').write(STATIONS_content)
                except:
                    self.log("   ERROR! in setSpecfemGlobeParameters: could not open STATIONS file '"+
                             os_path.join(DATA_FILES_PATH,'STATIONS')+"' to write\n")
                    raise
                self.log(log_string+"\n")
            else:
                self.log("      the SPECFEM STATIONS file was not modified by this script, you should have set it yourself correctly\n"+
                         "   WARNING! > when calculating Green's functions, SPECFEM3D_GLOBE might raise a runtime error of form\n"+
                         "   WARNING! > 'Floating-point exception - erroneous arithmetic operation.'\n"+
                         "   WARNING! > This exception might occurr in subroutine locate_receivers() when computing epicentral distances, \n"+
                         "   WARNING! > if station '"+staname+"' at which this Green source is located is also contained in the current STATIONS file.\n")

            if os_path.exists(self.outfile_base+'_OUTPUT_FILES'):
                if self.overwrite_ASKI_output:
                    self.log("      SPECFEM3D_GLOBE OUTPUT_FILES will be copied to '"+
                             self.outfile_base+'_OUTPUT_FILES'+"' (exists and will be overwritten).\n")
                else:
                    self.log("   ERROR! in setSpecfemGlobeParameters: path for SPECFEM3D_GLOBE OUTPUT_FILES '"+
                             self.outfile_base+'_OUTPUT_FILES'+"' exists and must not be overwritten "+
                             "(according to 'OVERWRITE_ASKI_OUTPUT' in Par_file_ASKI)\n")
                    raise Exception('path for SPECFEM3D_GLOBE OUTPUT_FILES already exists')
            else:
                self.log("      SPECFEM3D_GLOBE OUTPUT_FILES will be copied to '"+
                         self.outfile_base+'_OUTPUT_FILES'+"'.\n")

            self.log("      any possible altitude of this station is ignored for setting the source depth! always depth = 0 is used for Green functions\n")
            try:
                setCmtsolution(evname=sid,hdur='0',lat=lat,lon=lon,depth='0')
            except:
                self.log("   ERROR! in setSpecfemGlobeParameters: exception raised while setting CMTSOLUTION\n")
                raise

            try:
                setParfile(os_path.join(DATA_FILES_PATH,'Par_file_ASKI'),
                           [('COMPUTE_ASKI_OUTPUT','.true.'),('ASKI_outfile',self.outfile_base),
                            ('ASKI_output_ID',sid),('COMPUTE_ASKI_GREEN_FUNCTION','.true.'),
                            ('ASKI_GREEN_FUNCTION_COMPONENT',comp),
                            ('ASKI_df',df),('ASKI_nf',nf),('ASKI_jf',jf)])
                if define_ASKI_output_volume_by_inversion_grid:
                    setParfile(os_path.join(DATA_FILES_PATH,'Par_file_ASKI'),
                               [('ASKI_type_inversion_grid',self.ASKI_type_inversion_grid),('ASKI_nchunk',self.ASKI_nchunk),
                                ('ASKI_wlat',self.ASKI_wlat),('ASKI_wlon',self.ASKI_wlon),
                                ('ASKI_rot_gamma',self.ASKI_rot_gamma),
                                ('ASKI_clat',self.ASKI_clat),('ASKI_clon',self.ASKI_clon),
                                ('ASKI_rmax',self.ASKI_rmax),('ASKI_rmin',self.ASKI_rmin)])
            except:
                self.log("   ERROR! in setSpecfemGlobeParameters: exception raised while setting Par_file_ASKI\n")
                raise

        ##########################
        # typ=='data':
        ##########################
        elif typ=='data':
            slat = self.evlist.events[sid]['slat']
            slon = self.evlist.events[sid]['slon']
            sdepth = self.evlist.events[sid]['sdepth']
            styp = self.evlist.events[sid]['styp']
            self.outfile_base = os_path.join(self.mparam.sval('PATH_MEASURED_DATA'),'data_'+sid)
            self.log("   in setSpecfemGlobeParameters:\n"+
                     "      this is event evid = "+sid+"\n"+
                     "      source source lat[deg], lon[deg], depth[km] = "+', '.join([slat,slon,sdepth])+"\n"+
                     "      source type = "+styp+"\n")
            if int(styp) == 0 and self.evlist.events[sid].has_key('force'):
                self.log("   ERROR! in setSpecfemGlobeParameters: source type = 0 (i.e. single force) is not supported "+
                         "by SPECFEM3D_GLOBE for simulations of type 'data'\n")
                raise Exception("source type = 0 is not supported by SPECFEM3D_GLOBE for simulations of type 'data'")
            elif int(styp) == 1 and self.evlist.events[sid].has_key('momten'):
                momten = self.evlist.events[sid]['momten']
                self.log("      moment tensor in Nm =  "+'  '.join(momten)+" (read from ASKI event list file)\n")
                momten_DynCm = Moment_tensor_Nm2DynCm(momten)
                self.log("      moment tensor in dyn*cm =  "+'  '.join(momten_DynCm)+" (write to SPECFEM CMTSOLUTION file)\n")
                Mrr,Mtt,Mpp,Mrt,Mrp,Mtp = momten_DynCm
                try:
                    setCmtsolution(evname=sid,lat=slat,lon=slon,depth=sdepth,Mrr=Mrr,Mtt=Mtt,Mpp=Mpp,Mrt=Mrt,Mrp=Mrp,Mtp=Mtp)
                except:
                    self.log("   ERROR! in setSpecfemGlobeParameters: exception raised while setting CMTSOLUTION\n")
                    raise
            else:
                self.log("   ERROR! in setSpecfemGlobeParameters: source type is undefined (neither force nor moment tensor)\n")
                raise Exception("source type is undefined")

            if create_specfem_stations:
                log_string = ("      the SPECFEM STATIONS file was created from the "+str(self.statlist.nstat)+" stations in ASKI's station list file")
                if ignore_aski_stations_altitude:
                    STATIONS_content = '\n'.join(['   '.join([self.statlist.stations[i]['staname'], self.statlist.stations[i]['netcode'], 
                                                              self.statlist.stations[i]['lat'], self.statlist.stations[i]['lon'],
                                                              '0.0', '0.0'
                                                              ])
                                                  for i in range(self.statlist.nstat)
                                                  ])+'\n'
                    log_string += ", setting any altitudes to '0.0'"
                else:
                    STATIONS_content = '\n'.join(['   '.join([self.statlist.stations[i]['staname'], self.statlist.stations[i]['netcode'], 
                                                              self.statlist.stations[i]['lat'], self.statlist.stations[i]['lon'],
                                                              self.statlist.stations[i]['alt'], '0.0'
                                                              ])
                                                  for i in range(self.statlist.nstat)
                                                  ])+'\n'
                    log_string += ", keeping all original altitudes"
                try:
                    open(os_path.join(DATA_FILES_PATH,'STATIONS'),'w').write(STATIONS_content)
                except:
                    self.log("   ERROR! in setSpecfemGlobeParameters: could not open STATIONS file '"+os_path.join(DATA_FILES_PATH,'STATIONS')+
                                    "' to write\n")
                    raise
                self.log(log_string+"\n")
            else:
                self.log("      the SPECFEM STATIONS file was not modified by this script, you should have set it yourself correctly\n")

            if os_path.exists(self.outfile_base+'_OUTPUT_FILES'):
                if self.overwrite_ASKI_output:
                    self.log("      SPECFEM3D_GLOBE OUTPUT_FILES will be copied to '"+
                             self.outfile_base+'_OUTPUT_FILES'+"' (exists and will be overwritten).\n")
                else:
                    self.log("   ERROR! in setSpecfemGlobeParameters: path for SPECFEM3D_GLOBE OUTPUT_FILES '"+
                             self.outfile_base+'_OUTPUT_FILES'+"' exists and must not be overwritten "+
                             "(according to 'OVERWRITE_ASKI_OUTPUT' in Par_file_ASKI)\n")
                    raise Exception('path for SPECFEM3D_GLOBE OUTPUT_FILES already exists')
            else:
                self.log("      SPECFEM3D_GLOBE OUTPUT_FILES will be copied to '"+
                         self.outfile_base+'_OUTPUT_FILES'+"'.\n")

            try:
                setParfile(os_path.join(DATA_FILES_PATH,'Par_file_ASKI'),[('COMPUTE_ASKI_OUTPUT','.false.')])
            except:
                self.log("   ERROR! in setSpecfemGlobeParameters: exception raised while setting Par_file_ASKI\n")
                raise

        else:
            self.log("   ERROR! in setSpecfemGlobeParameters: simulation type '"+typ+"' not supported\n")
            raise Exception("simulation type '"+typ+"' not supported")
#
#-----------------------------------------------------------
#
    def check_if_simulation_was_successful(self,typ):
        # check if all binaries exist which should have been compiled correctly
        bin_list = ['bin/xmeshfem3D','bin/xspecfem3D']
        bin_not_exist = [f for f in bin_list if not os_path.exists(f)]
        if len(bin_not_exist)>0:
            self.log("### ERROR : the following binaries are not present, hence were not compiled correctly before starting this run:\n"+
                     "            '"+"', '".join(bin_not_exist)+"'\n")
            raise Exception("some binaries are not present; see logfile '"+logfile+"'")
        #
        # IT CAN BE ALSO CHECKED IF ALL DATABASE FILES ARE CREATED CORRECTLY AND ARE NOT EMPTY
        # THIS, HOWEVER, CAN BE DIFFICULT TO CHECK BY THE MASTER PROCESS, IF THE LOCAL PATHS
        # ARE ALL ON LOCAL DISCS
        # IF YOU WANT TO DO THE DATABASE CHECK, UNCOMMENT THE FOLLOWING CHECKS
        #
        # # check if all database files were produced
        # database_list = [os_path.join(LOCAL_PATH,'proc%6.6i_reg%1.1i_'%(iproc,i)+s+'.bin') 
        #                  for iproc in range(self.nproc) for i in range(1,4) for s in ['solver_data','solver_data_mpi','boundary']]
        # database_not_exist = [f for f in database_list if not os_path.exists(f)]
        # if len(database_not_exist)>0:
        #     self.log("### ERROR : the following database files were not created by xmeshfem3D: '"+
        #              "', ".join(database_not_exist)+"'\n")
        #     raise Exception("some database files were not created by xmeshfem3D; see logfile '"+
        #                     logfile+"'")
        # #
        # # check if database files are not empty
        # database_empty = [f for f in database_list if os_path.getsize(f) <= 0]
        # if len(database_empty)>0:
        #     self.log("### ERROR : the following database files are empty: '"+"', ".join(database_empty)+"'\n")
        #     raise Exception("some database files are empty; see logfile '"+logfile+"'")
        #
        # check if there are any "error_message*.txt" files in OUTPUT_FILES, i.e. if exit_mpi.f90 was called
        if any( [f.startswith('error_message') for f in os_listdir(OUTPUT_FILES_PATH)] ):
            self.log("### ERROR : there are files 'error_message*' in '"+OUTPUT_FILES_PATH+"'; "+
                     "mpiruns may have exited unintendedly\n")
            raise Exception("there are files 'error_message*' in '"+OUTPUT_FILES_PATH+"'; "+
                            "mpiruns may have exited unintendedly")
        #
        # check if there is a file "output_mesher.txt"
        if not os_path.exists(os_path.join(OUTPUT_FILES_PATH,'output_mesher.txt')):
            self.log("### ERROR : as there is no file 'output_mesher.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "this suggests that the mesher did not run correctly\n")
            raise Exception("as there is no file 'output_mesher.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "this suggests that the mesher did not run correctly")
        #
        # check if one of the last lines of output_mesher.txt is "End of mesh generation"
        last_lines_output_mesher = open(os_path.join(OUTPUT_FILES_PATH,'output_mesher.txt'),'r').readlines()[-10:]
        if not any( ['End of mesh generation' in line for line in last_lines_output_mesher] ):
            self.log("### ERROR : the last 10 lines of file 'output_mesher.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "do not contain line 'End of mesh generation'\n")
            raise Exception("the last 10 lines of file 'output_mesher.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "do not contain line 'End of mesh generation'")
        #
        # check if there is a file "output_solver.txt"
        if not os_path.exists(os_path.join(OUTPUT_FILES_PATH,'output_solver.txt')):
            self.log("### ERROR : as there is no file 'output_solver.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "this suggests that the solver did not run correctly\n")
            raise Exception("as there is no file 'output_solver.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "this suggests that the solver did not run correctly")
        #
        # check if there is a file "starttimeloop.txt"
        if not os_path.exists(os_path.join(OUTPUT_FILES_PATH,'starttimeloop.txt')):
            self.log("### ERROR : as there is no file 'starttimeloop.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "this suggests that the solver did not run correctly\n")
            raise Exception("as there is no file 'starttimeloop.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "this suggests that the solver did not run correctly")
        #
        # check if one of the last lines of output_solver.txt is "End of the simulation"
        last_lines_output_solver = open(os_path.join(OUTPUT_FILES_PATH,'output_solver.txt'),'r').readlines()[-10:]
        if not any( ['End of the simulation' in line for line in last_lines_output_solver] ):
            self.log("### ERROR : the last 10 lines of file 'output_solver.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "do not contain line 'End of the simulation'\n")
            raise Exception("the last 10 lines of file 'output_solver.txt' in '"+OUTPUT_FILES_PATH+"', "+
                     "do not contain line 'End of the simulation'")
        #
        # check if in case of simulation types displ and gt, actually kernel output was produced successfully
        if typ in ['displ','gt']:
            if not os_path.exists(os_path.join(OUTPUT_FILES_PATH,'LOG_ASKI_finish.txt')):
                self.log("### ERROR : as there is no file 'LOG_ASKI_finish.txt' in '"+OUTPUT_FILES_PATH+"', "+
                         "although this is type '"+typ+"', this suggests that ASKI output was not produced correctly\n")
                raise Exception("as there is no file 'LOG_ASKI_finish.txt' in '"+OUTPUT_FILES_PATH+"', "+
                                "this suggests that ASKI output was not produced correctly")
            lines_ASKI_finish = open(os_path.join(OUTPUT_FILES_PATH,'LOG_ASKI_finish.txt'),'r').readlines()
            if not any( ["successfully created ASKI output, as specified in 'LOG_ASKI_start.txt'" in line for line in lines_ASKI_finish] ):
                self.log("### ERROR : file 'LOG_ASKI_finish.txt' in '"+OUTPUT_FILES_PATH+"', "+
                         "does not contain line 'successfully created ASKI output'\n")
                raise Exception("file 'LOG_ASKI_finish.txt' in '"+OUTPUT_FILES_PATH+"', "+
                                "does not contain line 'successfully created ASKI output'")
#
#-----------------------------------------------------------
#
    def copySpecfemGlobeOutput(self):
        if os_path.exists(self.outfile_base+'_OUTPUT_FILES'):
            if self.overwrite_ASKI_output:
                # remove existing output first, before copying new one
                self.log("   in copySpecfemGlobeOutput: calling \"os_system('rm -rf "+self.outfile_base+'_OUTPUT_FILES/*'+"')\"\n")
                os_system('rm -rf '+self.outfile_base+'_OUTPUT_FILES/*')
            #else: already raised Exception in this case in routine setSpecfemGlobeParameters
        else: 
            self.log("   in copySpecfemGlobeOutput: calling \"os_mkdir('"+self.outfile_base+'_OUTPUT_FILES'+"')\"\n")
            os_mkdir(self.outfile_base+'_OUTPUT_FILES')
        #
        # finally copy output files 
        self.log("   in copySpecfemGlobeOutput: calling \"os_system('cp "+os_path.join(OUTPUT_FILES_PATH,'*')+" "+
                 self.outfile_base+'_OUTPUT_FILES'+"')\"\n")
        os_system('cp '+os_path.join(OUTPUT_FILES_PATH,'*')+' '+self.outfile_base+'_OUTPUT_FILES')
############################################################
# END OF CLASS simulation
############################################################
#
#
#-----------------------------------------------------------
#
def Moment_tensor_Nm2DynCm(momten):
    #return [  'e+'.join([ m.lower().split('e+')[0] , str(int(m.lower().split('e+')[1])+7) ])  for m in momten  ]
    return [str(float(m)*1e+7) for m in momten]
#
#-----------------------------------------------------------
#
def setParfile(filename,keys_vals):
    # locally define dictionary for better handling of incoming key,value pairs which are to be changed in parameter file
    values = dict(keys_vals)
    keys = values.keys()
    #
    # read in parameter file
    try:
        lines_orig = open(filename,'r').readlines()
    except:
        raise Exception("could not open parameter file '"+filename+"' to read")
    #
    # iterate over all lines and modify line if necessary
    lines_new = []
    for line in lines_orig:
        # ignore empty lines, comment lines and invalid lines (which do not contain any '=' in front of a comment)
        if line.strip() == '' or line.strip()[0:1]=='#' or not '=' in line.split('#')[0]:
            lines_new.append(line)
            continue
        #
        # if the key,value pair of this valid line is to be modified, do so
        key_line = line.split('=')[0].strip()
        val_line = line.split('=')[1].split('#')[0].strip()
        if key_line in keys:
            # first of all, remove newline character from end of line and append it to modified line
            line = line.strip('\n')
            # replace old value by new value, but keep all whitespace and commentary of this line as was before
            key_part = line.split('=')[0]
            val_part = line.split('=')[1].split('#')[0]
            # comment part ends on newline character
            if '#' in line:
                comment_part = '#'+line.split('=')[1].split('#')[1]+'\n'
            else:
                comment_part = '\n'
            if val_line == '':
                val_part = ' '+values[key_line]+' '
            else:
                val_part = val_part.replace(val_line,values[key_line])
            line = key_part+'='+val_part+comment_part
            # remove key of this line from keys list, in order to check (in the end) if all keys were found in the file
            keys.remove(key_line)
        #
        # add the line (if modified or not) to list of new lines
        lines_new.append(line)
    #
    # check if there are any keys which were not found on valid lines in the file
    if len(keys)>0:
        raise Exception("could not find the following parameters in parameter file '"+filename+"': "+
                        "'"+"', '".join(keys)+"'")
    #
    # if every key was found and the respective value was modified, write modified lines to file
    try:
        open(filename,'w').writelines(lines_new)
    except:
        raise Exception("could not open parameter file '"+filename+"' to write modified lines")
#
#-----------------------------------------------------------
#
def setCmtsolution(evname=None,hdur=None,lat=None,lon=None,depth=None,Mrr=None,Mtt=None,Mpp=None,Mrt=None,Mrp=None,Mtp=None):
    def setCmtsolution_replaceLine(line,key,newval):
        line_split = line.split(key)
        if line_split[1].strip() == '':
            return line_split[0]+key+'   '+newval+'\n'
        else:
            return line_split[0]+key+(line_split[1].replace(line_split[1].strip(),newval))
    #
    # read lines of CMTSOLUTION file
    try:
        lines = open(os_path.join(DATA_FILES_PATH,'CMTSOLUTION'),'r').readlines()
    except:
        raise Exception("could not open CMTSOLUTION file '"+os_path.join(DATA_FILES_PATH,'CMTSOLUTION')+
                        "' to read")
    # now modify lines
    if evname is not None:
        lines[1] = setCmtsolution_replaceLine(lines[1],'event name:',evname)
    if hdur is not None:
        lines[3] = setCmtsolution_replaceLine(lines[3],'half duration:',hdur)
    if lat is not None:
        lines[4] = setCmtsolution_replaceLine(lines[4],'latitude:',lat)
    if lon is not None:
        lines[5] = setCmtsolution_replaceLine(lines[5],'longitude:',lon)
    if depth is not None:
        lines[6] = setCmtsolution_replaceLine(lines[6],'depth:',depth)
    if Mrr is not None:
        lines[7] = setCmtsolution_replaceLine(lines[7],'Mrr:',Mrr)
    if Mtt is not None:
        lines[8] = setCmtsolution_replaceLine(lines[8],'Mtt:',Mtt)
    if Mpp is not None:
        lines[9] = setCmtsolution_replaceLine(lines[9],'Mpp:',Mpp)
    if Mrt is not None:
        lines[10] = setCmtsolution_replaceLine(lines[10],'Mrt:',Mrt)
    if Mrp is not None:
        lines[11] = setCmtsolution_replaceLine(lines[11],'Mrp:',Mrp)
    if Mtp is not None:
        lines[12] = setCmtsolution_replaceLine(lines[12],'Mtp:',Mtp)
    # write modified lines to new CMTSOLUTION file
    try:
        open(os_path.join(DATA_FILES_PATH,'CMTSOLUTION'),'w').writelines(lines)
    except:
        raise Exception("could not open CMTSOLUTION file '"+os_path.join(DATA_FILES_PATH,'CMTSOLUTION')+
                        "' to write modified lines")
#
############################################################
# MAIN
############################################################
#
def main():
    if runs_on_SGE:
        full_log_name = os_path.join(SGE_o_workdir,logfile)
    else:
        full_log_name = logfile
    open(logfile,'w').write('this is log '+full_log_name+'\nstarting script -- '+time_ctime()+'\n\n')

    # initiate simulation
    try:
        sm = simulation()
    except:
        open(logfile,'a').write('### STOP --'+time_ctime()+
                                '-- : could not initiate specfem3dGlobeForASKI simulations\n\n')
        raise

    # iterate over individual specfem3dGlobeForASKI simulations
    try:
        sm.iterate()
    except:
        open(logfile,'a').write('\n\n### STOP --'+time_ctime()+
                                '-- : there was an error iterating over the individual specfem3dGlobeForASKI simulations\n\n')
        if send_emails:
            sm.email_log('ERROR in one simulation')
        raise

    open(logfile,'a').write("\n"+
                            "--"+time_ctime()+"-- exiting script now. Good Bye\n"+
                            "\n")
    if send_emails:
        sm.email_log("successfully finished")
    sys_exit()
#
############################################################
#
if __name__ == "__main__":
    main()
